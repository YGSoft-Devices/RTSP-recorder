#!/usr/bin/env python3
"""
rpi_csi_rtsp_server.py
Version: 1.4.14

Python-based RTSP Server for CSI Cameras (Picamera2) on Raspberry Pi.
- Uses Picamera2 H264Encoder for HARDWARE video encoding (not x264enc!)
- Uses GStreamer RTSP Server to serve the H.264 stream
- Provides an internal HTTP API for dynamic controls

Key insight: Picamera2's H264Encoder uses the hardware V4L2 encoder natively,
avoiding buffer/format issues when trying to pass raw YUV to GStreamer encoders.
The output is Annex B H.264 stream which we pass directly to h264parse.
"""

import sys
import time
import threading
import logging
import os
import signal
import socket
import json
import io
import shutil
import subprocess
import tempfile
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [CSI-RTSP] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Try importing Picamera2
try:
    from picamera2 import Picamera2
    from picamera2.encoders import H264Encoder
    from picamera2.outputs import FileOutput
except ImportError:
    logger.error("Picamera2 module not found. Please install python3-picamera2")
    sys.exit(1)

# Try importing GStreamer bindings
try:
    import gi
    gi.require_version("Gst", "1.0")
    gi.require_version("GstRtspServer", "1.0")
    from gi.repository import Gst, GstRtspServer, GLib
except ImportError:
    logger.error("GStreamer python bindings not found. Please install python3-gi, gir1.2-gstreamer-1.0, gir1.2-gst-rtsp-server-1.0")
    sys.exit(1)

# ==============================================================================
# Configuration
# ==============================================================================
CONF = {
    'RTSP_PORT': int(os.environ.get('RTSP_PORT', 8554)),
    'RTSP_PATH': os.environ.get('RTSP_PATH', 'stream'),
    'WIDTH': int(os.environ.get('VIDEO_WIDTH', 1296)),
    'HEIGHT': int(os.environ.get('VIDEO_HEIGHT', 972)),
    'FPS': int(os.environ.get('VIDEO_FPS', 20)),
    'BITRATE_KBPS': int(os.environ.get('H264_BITRATE_KBPS', 2000)),
    'KEYINT': int(os.environ.get('H264_KEYINT', 30)),
    'H264_QP': int(os.environ['H264_QP']) if os.environ.get('H264_QP', '').isdigit() else None,
    'H264_PROFILE': os.environ.get('H264_PROFILE', '').strip() or None,
    'AUDIO_ENABLE': os.environ.get('AUDIO_ENABLE', 'yes').lower() in ('yes', 'true', '1', 'on'),
    'AUDIO_DEVICE': os.environ.get('AUDIO_DEVICE', 'plughw:0,0'),
    'AUDIO_RATE': int(os.environ.get('AUDIO_RATE', 44100)),
    'OVERLAY_ENABLE': os.environ.get('VIDEO_OVERLAY_ENABLE', 'no').lower() in ('yes', 'true', '1', 'on'),
    'OVERLAY_TEXT': os.environ.get('VIDEO_OVERLAY_TEXT', ''),
    'OVERLAY_POSITION': os.environ.get('VIDEO_OVERLAY_POSITION', 'top-left'),
    'OVERLAY_SHOW_DATETIME': os.environ.get('VIDEO_OVERLAY_SHOW_DATETIME', 'no').lower() in ('yes', 'true', '1', 'on'),
    'OVERLAY_DATETIME_FORMAT': os.environ.get('VIDEO_OVERLAY_DATETIME_FORMAT', '%Y-%m-%d %H:%M:%S'),
    'OVERLAY_CLOCK_POSITION': os.environ.get('VIDEO_OVERLAY_CLOCK_POSITION', 'bottom-right'),
    'OVERLAY_FONT_SIZE': int(os.environ['VIDEO_OVERLAY_FONT_SIZE']) if os.environ.get('VIDEO_OVERLAY_FONT_SIZE', '').isdigit() else 24,
    'CSI_OVERLAY_MODE': os.environ.get('CSI_OVERLAY_MODE', 'software').strip().lower(),
    'CSI_RPICAM_UDP_PORT': int(os.environ.get('CSI_RPICAM_UDP_PORT', 5000)),
    'CONTROL_PORT': 8085
}

RPI_CAM_POSTPROC_PLUGIN = "/usr/lib/aarch64-linux-gnu/rpicam-apps-postproc/opencv-postproc.so"
RPI_CAM_ANNOTATE_ASSET = "/usr/share/rpi-camera-assets/annotate_cv.json"


def load_config_from_file():
    """Load configuration from /etc/rpi-cam/config.env if it exists."""
    config_path = '/etc/rpi-cam/config.env'
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        
                        if key == 'AUDIO_DEVICE' and value:
                            CONF['AUDIO_DEVICE'] = value
                            logger.info(f"Config: AUDIO_DEVICE={value}")
                        elif key == 'VIDEO_WIDTH' and value.isdigit():
                            CONF['WIDTH'] = int(value)
                        elif key == 'VIDEO_HEIGHT' and value.isdigit():
                            CONF['HEIGHT'] = int(value)
                        elif key == 'VIDEO_FPS' and value.isdigit():
                            CONF['FPS'] = int(value)
                        elif key == 'H264_BITRATE_KBPS' and value.isdigit():
                            CONF['BITRATE_KBPS'] = int(value)
                        elif key == 'H264_KEYINT' and value.isdigit():
                            CONF['KEYINT'] = int(value)
                        elif key == 'H264_QP':
                            qp_value = value.strip().lower()
                            if qp_value in ('', 'auto', 'none'):
                                CONF['H264_QP'] = None
                            elif qp_value.isdigit():
                                qp_int = int(qp_value)
                                if 1 <= qp_int <= 51:
                                    CONF['H264_QP'] = qp_int
                                else:
                                    logger.warning(f"H264_QP out of range (1-51): {qp_int}")
                        elif key == 'H264_PROFILE' and value:
                            profile = value.strip().lower()
                            allowed_profiles = {
                                "baseline",
                                "constrained baseline",
                                "main",
                                "high"
                            }
                            if profile in allowed_profiles:
                                CONF['H264_PROFILE'] = profile
                        elif key == 'VIDEO_OVERLAY_ENABLE':
                            CONF['OVERLAY_ENABLE'] = value.strip().lower() in ('yes', 'true', '1', 'on')
                        elif key == 'VIDEO_OVERLAY_TEXT':
                            CONF['OVERLAY_TEXT'] = value
                        elif key == 'VIDEO_OVERLAY_POSITION' and value:
                            CONF['OVERLAY_POSITION'] = value.strip()
                        elif key == 'VIDEO_OVERLAY_SHOW_DATETIME':
                            CONF['OVERLAY_SHOW_DATETIME'] = value.strip().lower() in ('yes', 'true', '1', 'on')
                        elif key == 'VIDEO_OVERLAY_DATETIME_FORMAT' and value:
                            CONF['OVERLAY_DATETIME_FORMAT'] = value
                        elif key == 'VIDEO_OVERLAY_CLOCK_POSITION' and value:
                            CONF['OVERLAY_CLOCK_POSITION'] = value.strip()
                        elif key == 'VIDEO_OVERLAY_FONT_SIZE':
                            size_value = value.strip()
                            if size_value.isdigit():
                                CONF['OVERLAY_FONT_SIZE'] = max(1, min(64, int(size_value)))
                            else:
                                logger.warning(f"Invalid VIDEO_OVERLAY_FONT_SIZE '{value}', ignoring")
                        elif key == 'CSI_OVERLAY_MODE':
                            mode_value = value.strip().lower()
                            if mode_value in ('software', 'libcamera'):
                                CONF['CSI_OVERLAY_MODE'] = mode_value
                            else:
                                logger.warning(f"Invalid CSI_OVERLAY_MODE '{value}', using default")
                        elif key == 'CSI_RPICAM_UDP_PORT':
                            port_value = value.strip()
                            if port_value.isdigit():
                                CONF['CSI_RPICAM_UDP_PORT'] = max(1, min(65535, int(port_value)))
                        elif key == 'AUDIO_ENABLE':
                            CONF['AUDIO_ENABLE'] = value.lower() in ('yes', 'true', '1', 'on')
                            logger.info(f"Config: AUDIO_ENABLE={CONF['AUDIO_ENABLE']}")
                        elif key == 'AUDIO_RATE' and value.isdigit():
                            CONF['AUDIO_RATE'] = int(value)
            logger.info(f"Loaded config from {config_path}")
        except Exception as e:
            logger.warning(f"Could not load config from {config_path}: {e}")


load_config_from_file()


# ==============================================================================
# Audio Device Detection
# ==============================================================================
def find_usb_audio_device():
    """
    Detect USB audio device by name (more robust than static plughw:X,0).
    Uses card name matching instead of card number (which can change on reboot).
    
    Returns: Device name like "plughw:0,0" or original CONF['AUDIO_DEVICE'] if not found.
    """
    try:
        import subprocess
        result = subprocess.run(['arecord', '-l'], capture_output=True, text=True, timeout=2)
        if result.returncode != 0:
            logger.warning(f"arecord -l failed: {result.stderr}")
            return CONF['AUDIO_DEVICE']
        
        # Parse output: look for "USB" card names
        for line in result.stdout.split('\n'):
            if 'USB' in line and 'card' in line:
                # Line format: "card 0: Device [USB PnP Sound Device]..."
                try:
                    parts = line.split(':')
                    if len(parts) >= 2 and 'card' in parts[0]:
                        card_num = parts[0].strip().split()[-1]  # Extract "0" from "card 0"
                        if card_num.isdigit():
                            device = f"plughw:{card_num},0"
                            logger.info(f"Auto-detected USB audio device: {device}")
                            return device
                except (IndexError, ValueError) as e:
                    logger.debug(f"Failed to parse arecord line: {line}, error: {e}")
        
        logger.warning(f"No USB audio device found in arecord output, using configured: {CONF['AUDIO_DEVICE']}")
        return CONF['AUDIO_DEVICE']
    
    except FileNotFoundError:
        logger.warning("arecord not found, using configured audio device")
        return CONF['AUDIO_DEVICE']
    except Exception as e:
        logger.warning(f"Error detecting USB audio device: {e}, using configured: {CONF['AUDIO_DEVICE']}")
        return CONF['AUDIO_DEVICE']


def test_audio_device(device):
    """
    Test if an audio device is actually accessible.
    Returns: True if device works, False otherwise.
    """
    try:
        import subprocess
        # Use 'timeout' command to limit arecord duration instead of -d flag
        result = subprocess.run(
            ['bash', '-c', f'timeout 0.5 arecord -D {device} > /dev/null 2>&1'],
            timeout=1
        )
        is_working = result.returncode == 0 or result.returncode == 124  # 124 = timeout (expected)
        if is_working:
            logger.info(f"Audio device {device} is accessible ✓")
        else:
            logger.warning(f"Audio device {device} failed test (exit code: {result.returncode})")
        return is_working
    except Exception as e:
        logger.warning(f"Failed to test audio device {device}: {e}")
        return False


def resolve_audio_device():
    """
    Resolve the actual audio device to use:
    1. Try configured AUDIO_DEVICE from config.env
    2. Auto-detect USB audio if configured device fails
    3. Fallback to plughw:0,0 if nothing works
    
    Returns: Working audio device name
    """
    configured = CONF['AUDIO_DEVICE']
    
    # Try configured device first
    if test_audio_device(configured):
        return configured
    
    logger.warning(f"Configured device {configured} not accessible, attempting auto-detection...")
    
    # Auto-detect USB device
    detected = find_usb_audio_device()
    if detected != configured and test_audio_device(detected):
        logger.info(f"Using auto-detected device {detected} instead of {configured}")
        return detected
    
    # Fallback
    fallback = "plughw:0,0"
    logger.warning(f"Using fallback device {fallback}")
    return fallback


# ==============================================================================
# Streaming Output - Collects H.264 data from encoder
# ==============================================================================
class StreamingOutput(io.BufferedIOBase):
    """
    Output that collects H.264 NAL units from Picamera2 encoder.
    Data is read by the GStreamer push thread.
    """
    def __init__(self):
        self.lock = threading.Lock()
        self.condition = threading.Condition(self.lock)
        self.frame_data = None
        
    def write(self, data):
        with self.condition:
            self.frame_data = data
            self.condition.notify_all()
        return len(data)
    
    def read_frame(self, timeout=1.0):
        """Read the next H.264 frame/NAL unit."""
        with self.condition:
            if self.condition.wait_for(lambda: self.frame_data is not None, timeout=timeout):
                data = self.frame_data
                self.frame_data = None
                return data
            return None
    
    def readable(self):
        return True
    
    def writable(self):
        return True


# ==============================================================================
# Control API Handler (IPC)
# ==============================================================================
class ControlRequestHandler(BaseHTTPRequestHandler):
    server_instance = None

    def do_POST(self):
        if self.path == '/set_controls':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data)
                
                if self.server_instance:
                    self.server_instance.set_controls(data)
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "ok"}).encode())
                else:
                    self.send_error(500, "Server instance not ready")
            except Exception as e:
                logger.error(f"Error handling controls: {e}")
                self.send_error(400, str(e))
        else:
            self.send_error(404)
    
    def do_GET(self):
        if self.path == '/controls':
            try:
                if self.server_instance:
                    controls = self.server_instance.list_controls()
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps(controls, default=str).encode())
                else:
                    self.send_error(500, "Server instance not ready")
            except Exception as e:
                logger.error(f"Error handling controls GET: {e}")
                self.send_error(500, str(e))
        else:
            self.send_error(404)
            
    def log_message(self, format, *args):
        pass


# ==============================================================================
# RTSP Server Class with Hardware H264 Encoding
# ==============================================================================
class Picam2RtspServer:
    def __init__(self, conf):
        self.conf = conf
        self.picam2: Optional[Picamera2] = None
        self.encoder: Optional[H264Encoder] = None
        self.h264_output: Optional[StreamingOutput] = None
        self.appsrc = None
        self.rpicam_proc: Optional[subprocess.Popen] = None
        self.rpicam_udp_port = int(self.conf.get('CSI_RPICAM_UDP_PORT', 5000))
        self.using_rpicam_overlay = False
        self.rpicam_overlay_config_path: Optional[str] = None
        
        self.camera_properties = {}
        self.sensor_modes = []
        
        # Track applied control values (used by list_controls)
        self.applied_controls = {}
        
        # RTSP factory configuration state (shared pipeline)
        self._rtsp_factory_configured = False
        
        self._running = False
        self._push_thread: Optional[threading.Thread] = None
        self._push_loop_last_frame_time: float = 0.0  # Track if push loop is alive
        self._push_loop_error_count: int = 0  # Count consecutive errors
        
        self.control_server = None
        self.control_thread = None
        self.main_loop = None

        # Initialize GStreamer
        Gst.init(None)
        
    def setup_control_api(self):
        """Start the internal HTTP server for dynamic controls."""
        try:
            ControlRequestHandler.server_instance = self
            self.control_server = HTTPServer(('127.0.0.1', self.conf['CONTROL_PORT']), ControlRequestHandler)
            self.control_thread = threading.Thread(target=self.control_server.serve_forever, daemon=True)
            self.control_thread.start()
            logger.info(f"Control API listening on 127.0.0.1:{self.conf['CONTROL_PORT']}")
        except Exception as e:
            logger.error(f"Failed to start Control API: {e}")

    def _build_pipeline_launch(self) -> str:
        """
        Build GStreamer pipeline for RTSP.
        Video: appsrc receives H.264 NAL units from Picamera2 H264Encoder (HARDWARE!)
        Audio: alsasrc (optional) - uses dynamically resolved audio device
        """
        # Video pipeline - receives pre-encoded H.264 from Picamera2 hardware encoder
        # The H264Encoder outputs Annex B format (start codes 00 00 00 01)
        video_caps = (
            f"video/x-h264,stream-format=byte-stream,alignment=au,"
            f"width={self.conf['WIDTH']},height={self.conf['HEIGHT']},framerate={self.conf['FPS']}/1"
        )

        overlay_chain = self._build_overlay_chain()
        if overlay_chain:
            logger.warning("CSI overlay enabled: software decode/encode path used (CPU intensive).")
            encoder = self._select_overlay_encoder()
            video_pipeline = (
                f"appsrc name=src is-live=true do-timestamp=true format=time caps={video_caps} "
                f"! h264parse "
                f"! avdec_h264 "
                f"! videoconvert "
                f"! {overlay_chain} "
                f"! {encoder} "
                f"! h264parse config-interval=1 "
                f"! rtph264pay name=pay0 pt=96 config-interval=1 "
                f"timestamp-offset=0 seqnum-offset=0 perfect-rtptime=true"
            )
        else:
            video_pipeline = (
                f"appsrc name=src is-live=true do-timestamp=true format=time caps={video_caps} "
                f"! h264parse config-interval=1 "
                f"! rtph264pay name=pay0 pt=96 config-interval=1 "
                f"timestamp-offset=0 seqnum-offset=0 perfect-rtptime=true"
            )

        # Audio pipeline (optional)
        audio_pipeline = ""
        if self.conf['AUDIO_ENABLE']:
            # Resolve audio device dynamically (USB audio might change card number on reboot)
            device = resolve_audio_device()
            audio_pipeline = (
                f" alsasrc device=\"{device}\" buffer-time=200000 latency-time=25000 "
                f"! audioconvert ! audioresample "
                f"! voaacenc bitrate=64000 "
                f"! rtpmp4gpay name=pay1 pt=97 "
                f"timestamp-offset=0 seqnum-offset=0 perfect-rtptime=true"
            )

        full_pipeline = f"( {video_pipeline}{audio_pipeline} )"
        logger.info(f"GStreamer Pipeline: {full_pipeline}")
        return full_pipeline

    def _overlay_alignment_from_position(self, pos: str) -> tuple[str, str]:
        mapping = {
            'top-left': ('top', 'left'),
            'top-right': ('top', 'right'),
            'bottom-left': ('bottom', 'left'),
            'bottom-right': ('bottom', 'right')
        }
        return mapping.get(pos, ('top', 'left'))

    def _build_overlay_chain(self) -> str:
        if not self.conf.get('OVERLAY_ENABLE'):
            return ""

        clock_available = Gst.ElementFactory.find('clockoverlay') is not None
        text_available = Gst.ElementFactory.find('textoverlay') is not None
        decoder_available = Gst.ElementFactory.find('avdec_h264') is not None
        converter_available = Gst.ElementFactory.find('videoconvert') is not None
        encoder_available = self._select_overlay_encoder() is not None

        if not decoder_available or not converter_available or not encoder_available:
            logger.warning("CSI overlay disabled: missing decoder/encoder elements.")
            return ""

        overlay_chain = ""
        font_desc = f"Sans {self.conf.get('OVERLAY_FONT_SIZE', 24)}"

        if self.conf.get('OVERLAY_SHOW_DATETIME') and clock_available:
            valign, halign = self._overlay_alignment_from_position(self.conf.get('OVERLAY_CLOCK_POSITION', 'bottom-right'))
            overlay_chain = (
                f"clockoverlay time-format=\"{self.conf.get('OVERLAY_DATETIME_FORMAT')}\" "
                f"valignment={valign} halignment={halign} shaded-background=true font-desc=\"{font_desc}\""
            )

        overlay_text = (self.conf.get('OVERLAY_TEXT') or '').strip()
        if overlay_text and text_available:
            overlay_text = overlay_text.replace('{CAMERA_TYPE}', 'csi')
            overlay_text = overlay_text.replace('{VIDEO_DEVICE}', 'CSI')
            overlay_text = overlay_text.replace('{VIDEO_RESOLUTION}', f"{self.conf['WIDTH']}x{self.conf['HEIGHT']}")
            overlay_text = overlay_text.replace('{VIDEO_FPS}', str(self.conf['FPS']))
            overlay_text = overlay_text.replace('{VIDEO_FORMAT}', 'H264')
            overlay_text = overlay_text.replace('"', ' ').replace("'", ' ')
            valign, halign = self._overlay_alignment_from_position(self.conf.get('OVERLAY_POSITION', 'top-left'))
            if overlay_chain:
                overlay_chain += " ! "
            overlay_chain += (
                f"textoverlay text=\"{overlay_text}\" valignment={valign} halignment={halign} "
                f"shaded-background=true font-desc=\"{font_desc}\""
            )

        if overlay_chain and (not clock_available and self.conf.get('OVERLAY_SHOW_DATETIME')):
            logger.warning("CSI overlay: clockoverlay not available.")
        if overlay_text and not text_available:
            logger.warning("CSI overlay: textoverlay not available.")

        return overlay_chain

    def _select_overlay_encoder(self) -> Optional[str]:
        bitrate = int(self.conf.get('BITRATE_KBPS', 2000))
        keyint = int(self.conf.get('KEYINT', 30))
        if Gst.ElementFactory.find('x264enc') is not None:
            return f"x264enc tune=zerolatency speed-preset=ultrafast bitrate={bitrate} key-int-max={keyint} bframes=0 threads=2"
        if Gst.ElementFactory.find('openh264enc') is not None:
            return f"openh264enc bitrate={bitrate * 1000}"
        return None

    def _can_use_rpicam_overlay(self) -> bool:
        if not self.conf.get('OVERLAY_ENABLE'):
            return False
        if self.conf.get('CSI_OVERLAY_MODE') != 'libcamera':
            return False
        if self.conf.get('OVERLAY_SHOW_DATETIME'):
            logger.warning("CSI libcamera overlay does not support dynamic date/time. Falling back to software overlay.")
            return False
        overlay_text = (self.conf.get('OVERLAY_TEXT') or '').strip()
        if not overlay_text:
            logger.warning("CSI libcamera overlay requested but overlay text is empty.")
            return False
        if not shutil.which("rpicam-vid"):
            logger.warning("CSI libcamera overlay unavailable: rpicam-vid not found.")
            return False
        if not os.path.exists(RPI_CAM_POSTPROC_PLUGIN):
            logger.warning("CSI libcamera overlay unavailable: opencv postprocess plugin missing.")
            return False
        if not os.path.exists(RPI_CAM_ANNOTATE_ASSET):
            logger.warning("CSI libcamera overlay unavailable: annotate_cv asset missing.")
            return False
        return True

    def _build_rpicam_overlay_text(self) -> str:
        overlay_text = (self.conf.get('OVERLAY_TEXT') or '').strip()
        overlay_text = overlay_text.replace('{CAMERA_TYPE}', 'csi')
        overlay_text = overlay_text.replace('{VIDEO_DEVICE}', 'CSI')
        overlay_text = overlay_text.replace('{VIDEO_RESOLUTION}', f"{self.conf['WIDTH']}x{self.conf['HEIGHT']}")
        overlay_text = overlay_text.replace('{VIDEO_FPS}', str(self.conf['FPS']))
        overlay_text = overlay_text.replace('{VIDEO_FORMAT}', 'H264')
        return overlay_text.replace('"', ' ').replace("'", ' ')

    def _write_rpicam_overlay_config(self) -> str:
        overlay_text = self._build_rpicam_overlay_text()
        font_size = int(self.conf.get('OVERLAY_FONT_SIZE', 24))
        scale = max(0.2, min(4.0, font_size / 24.0))
        payload = {
            "annotate_cv": {
                "text": overlay_text,
                "fg": 255,
                "bg": 0,
                "scale": scale,
                "thickness": 2,
                "alpha": 0.3
            }
        }
        tmp = tempfile.NamedTemporaryFile(prefix="rpicam-annotate-", suffix=".json", delete=False)
        tmp.close()
        with open(tmp.name, 'w', encoding='utf-8') as handle:
            json.dump(payload, handle)
        self.rpicam_overlay_config_path = tmp.name
        return tmp.name

    def _build_rpicam_pipeline_launch(self) -> str:
        video_caps = (
            f"video/x-h264,stream-format=byte-stream,alignment=au,"
            f"width={self.conf['WIDTH']},height={self.conf['HEIGHT']},framerate={self.conf['FPS']}/1"
        )
        video_pipeline = (
            f"udpsrc port={self.rpicam_udp_port} caps=\"{video_caps}\" "
            f"! h264parse config-interval=1 "
            f"! rtph264pay name=pay0 pt=96 config-interval=1 "
            f"timestamp-offset=0 seqnum-offset=0 perfect-rtptime=true"
        )

        audio_pipeline = ""
        if self.conf['AUDIO_ENABLE']:
            device = resolve_audio_device()
            audio_pipeline = (
                f" alsasrc device=\"{device}\" buffer-time=200000 latency-time=25000 "
                f"! audioconvert ! audioresample "
                f"! voaacenc bitrate=64000 "
                f"! rtpmp4gpay name=pay1 pt=97 "
                f"timestamp-offset=0 seqnum-offset=0 perfect-rtptime=true"
            )

        return f"( {video_pipeline}{audio_pipeline} )"

    def _start_rpicam_annotate(self) -> None:
        overlay_config = self._write_rpicam_overlay_config()
        bitrate_bps = int(self.conf.get('BITRATE_KBPS', 2000)) * 1000
        keyint = int(self.conf.get('KEYINT', 30))
        cmd = [
            "rpicam-vid",
            "-n",
            "--codec", "h264",
            "--inline",
            "-t", "0",
            "--width", str(self.conf['WIDTH']),
            "--height", str(self.conf['HEIGHT']),
            "--framerate", str(self.conf['FPS']),
            "--bitrate", str(bitrate_bps),
            "--intra", str(keyint),
            "--post-process-file", overlay_config,
            "-o", f"udp://127.0.0.1:{self.rpicam_udp_port}"
        ]
        profile = self.conf.get('H264_PROFILE')
        if profile:
            cmd.extend(["--profile", profile])
        if self.conf.get('H264_QP'):
            logger.warning("CSI libcamera overlay does not support H264_QP; ignoring.")

        logger.info(f"Starting rpicam-vid overlay process: {' '.join(cmd)}")
        self.rpicam_proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True
        )

        def _log_rpicam_stderr():
            if not self.rpicam_proc or not self.rpicam_proc.stderr:
                return
            for line in self.rpicam_proc.stderr:
                msg = line.strip()
                if msg:
                    logger.info(f"rpicam-vid: {msg}")

        threading.Thread(target=_log_rpicam_stderr, daemon=True).start()

    def _monitor_rpicam_process(self):
        while self._running:
            if self.rpicam_proc and self.rpicam_proc.poll() is not None:
                logger.critical("rpicam-vid exited unexpectedly. Restarting service...")
                sys.exit(1)
            time.sleep(1.0)

    def _start_rpicam_overlay_rtsp(self):
        logger.info("Starting CSI RTSP Server with rpicam-vid overlay (hardware H.264).")
        logger.info(f"Config: {self.conf['WIDTH']}x{self.conf['HEIGHT']}@{self.conf['FPS']}fps, "
                   f"bitrate={self.conf['BITRATE_KBPS']}kbps")

        self.using_rpicam_overlay = True
        self._start_rpicam_annotate()
        time.sleep(0.5)

        self.setup_control_api()

        self.main_loop = GLib.MainLoop()
        server = GstRtspServer.RTSPServer()
        server.set_service(str(self.conf['RTSP_PORT']))

        factory = GstRtspServer.RTSPMediaFactory()
        factory.set_launch(self._build_rpicam_pipeline_launch())
        factory.set_shared(True)

        mounts = server.get_mount_points()
        mounts.add_factory(f"/{self.conf['RTSP_PATH']}", factory)

        server.attach(None)
        logger.info(f"RTSP Stream available at rtsp://0.0.0.0:{self.conf['RTSP_PORT']}/{self.conf['RTSP_PATH']}")

        self._running = True
        threading.Thread(target=self._monitor_rpicam_process, daemon=True).start()

        try:
            self.main_loop.run()
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received.")
        finally:
            self.stop()

    def _on_media_configure(self, factory, media):
        """Called when a client connects and the pipeline is created.
        
        IMPORTANT: With factory.set_shared(True), this is called ONCE for the first client,
        then reused for subsequent clients. Configure appsrc only once to avoid race conditions.
        """
        if self._rtsp_factory_configured:
            logger.debug("RTSP factory already configured for shared pipeline.")
            return
        
        logger.info("Configuring RTSP factory for first client...")
        element = media.get_element()
        self.appsrc = element.get_child_by_name("src")
        if self.appsrc:
            self.appsrc.set_property("block", False)
            self.appsrc.set_property("max-bytes", 2*1024*1024)
            self._rtsp_factory_configured = True
            logger.info("appsrc configured for hardware H.264 stream (shared pipeline).")
        else:
            logger.error("Could not find appsrc element in pipeline!")

    def _push_loop_watchdog(self):
        """Watchdog thread that monitors the H.264 push loop and restarts if it dies.
        
        The push loop can crash silently due to libcamera timeouts or other hardware
        issues. This watchdog detects if no frames are being pushed for >10 seconds
        and forces a restart of the entire service.
        
        FIXED v1.4.3: Corrected timestamp comparison logic.
        """
        logger.info("Starting push loop watchdog (timeout: 10s).")
        watchdog_timeout_sec = 10.0
        last_frame_timestamp = self._push_loop_last_frame_time
        
        while self._running:
            time.sleep(2.0)  # Check every 2 seconds
            current_frame_timestamp = self._push_loop_last_frame_time
            
            # Has the frame timestamp changed since last check?
            if current_frame_timestamp == last_frame_timestamp:
                # No new frames pushed, calculate how long it's been
                elapsed_since_frame = time.time() - current_frame_timestamp
                
                if elapsed_since_frame > watchdog_timeout_sec:
                    logger.critical(
                        f"Watchdog: Push loop appears dead! No new frames for {elapsed_since_frame:.1f}s "
                        f"(errors: {self._push_loop_error_count}). Restarting service..."
                    )
                    sys.exit(1)  # Let systemd restart the service
            else:
                # Frame timestamp changed, push loop is alive
                logger.debug(f"Watchdog: Push loop active (frames: {int((time.time() - current_frame_timestamp)*1000)}ms ago)")
            
            # Update for next check
            last_frame_timestamp = current_frame_timestamp

    def _push_loop(self):
        """Push H.264 data from Picamera2 hardware encoder to GStreamer appsrc.
        
        CRITICAL FIXES (v1.4.2):
        1. Comprehensive exception handling for libcamera timeouts
        2. Check pipeline state before pushing buffers (avoid busy-wait when NULL)
        3. Respect frame timing with proper sleep between pushes
        4. Handle backpressure gracefully (FlowReturn.NOT_LINKED = no consumers)
        5. Avoid memory bloat from unbounded buffer accumulation
        6. Reduce read_frame timeout to 2.0s to catch stalls faster (was 0.1s but libcamera can timeout >1s)
        """
        logger.info("Starting H.264 push loop (HARDWARE encoder).")
        self._push_loop_last_frame_time = time.time()
        self._push_loop_error_count = 0
        
        frame_duration_ns = int(1e9 / self.conf['FPS'])
        frame_duration_sec = frame_duration_ns / 1e9
        pts = 0
        last_push_time = time.time()
        consecutive_failures = 0
        max_failures = 30
        had_no_consumers = True

        try:
            while self._running:
                try:
                    # Read H.264 frame from encoder output with timeout
                    # IMPORTANT: Increased timeout to 2.0s to allow libcamera to work
                    # but not so long that we become unresponsive
                    h264_data = self.h264_output.read_frame(timeout=2.0)
                    self._push_loop_last_frame_time = time.time()
                    self._push_loop_error_count = 0  # Reset error counter on success
                    
                    if h264_data is None:
                        # No frame available, short sleep to avoid busy-wait
                        time.sleep(0.01)
                        continue
                    
                    # Check if we have appsrc and it's ready to accept buffers
                    if not self.appsrc:
                        # No client connected, throttle to avoid CPU waste
                        time.sleep(0.05)
                        consecutive_failures += 1
                        had_no_consumers = True
                        if consecutive_failures > max_failures:
                            logger.info("No active clients detected. Pausing push loop temporarily...")
                            time.sleep(0.5)
                        continue
                    
                    try:
                        # Create GStreamer buffer with the H.264 data
                        buf = Gst.Buffer.new_allocate(None, len(h264_data), None)
                        buf.fill(0, h264_data)
                        buf.pts = pts
                        buf.dts = pts
                        buf.duration = frame_duration_ns
                        
                        # Push to appsrc and check return value
                        ret = self.appsrc.emit("push-buffer", buf)
                         
                        if ret == Gst.FlowReturn.OK:
                            if had_no_consumers:
                                had_no_consumers = False
                                try:
                                    if self.encoder and hasattr(self.encoder, "request_key_frame"):
                                        self.encoder.request_key_frame()
                                        logger.info("Requested keyframe on first consumer reconnect.")
                                except Exception as e:
                                    logger.debug(f"Keyframe request failed: {e}")
                            # Success - advance PTS
                            pts += frame_duration_ns
                            consecutive_failures = 0
                            # Throttle to maintain desired frame rate
                            now = time.time()
                            elapsed = now - last_push_time
                            if elapsed < frame_duration_sec:
                                time.sleep(frame_duration_sec - elapsed)
                            last_push_time = time.time()
                         
                        elif ret == Gst.FlowReturn.NOT_LINKED:
                            # No consumer connected to appsrc, pause
                            consecutive_failures += 1
                            had_no_consumers = True
                            if consecutive_failures < 5:
                                time.sleep(0.02)
                            else:
                                logger.debug(f"appsrc has no consumer (attempt {consecutive_failures}), pausing...")
                                time.sleep(0.1)
                        
                        elif ret == Gst.FlowReturn.FLUSHING:
                            # Pipeline is being torn down, this is normal
                            time.sleep(0.02)
                        
                        else:
                            # Unexpected return value (ERROR, etc.)
                            logger.warning(f"appsrc push returned: {ret}. Pausing temporarily...")
                            consecutive_failures += 1
                            time.sleep(0.1)
                    
                    except Exception as e:
                        logger.error(f"Error pushing H.264 buffer: {e}")
                        consecutive_failures += 1
                        time.sleep(0.05)

                except Exception as e:
                    self._push_loop_error_count += 1
                    logger.error(f"Exception in push frame loop (#{self._push_loop_error_count}): {type(e).__name__}: {e}")
                    time.sleep(0.1)
                    if self._push_loop_error_count > 100:
                        logger.critical(f"Push loop exceeded error threshold ({self._push_loop_error_count} errors). Restarting...")
                        sys.exit(1)  # Let systemd restart the service

        except Exception as e:
            logger.critical(f"FATAL: Push loop catastrophic error: {type(e).__name__}: {e}")
            sys.exit(1)
        finally:
            logger.info("H.264 push loop stopped.")

    def _load_saved_tunings(self) -> Dict[str, Any]:
        """Load saved tuning parameters from config file."""
        import os
        config_path = '/etc/rpi-cam/csi_tuning.json'
        
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    tunings = json.load(f)
                    logger.info(f"Loaded {len(tunings)} tuning parameters from {config_path}")
                    return tunings
        except Exception as e:
            logger.warning(f"Failed to load tuning config from {config_path}: {e}")
        
        return {}

    def set_controls(self, controls: Dict[str, Any]):
        """Apply controls to the camera with validation.
        
        Note: Some controls (like resolution changes) may fail in streaming mode.
        These will be saved to config for next start.
        """
        if self.using_rpicam_overlay:
            raise RuntimeError("Controls unavailable in libcamera overlay mode")
        if not self.picam2:
            raise RuntimeError("Camera not initialized")
        
        # Validate and transform controls for array types
        validated_controls = self._validate_controls(controls)
        
        if not validated_controls:
            logger.warning(f"No valid controls to apply after validation")
            return
        
        try:
            # Try to apply controls directly (live mode)
            self.picam2.set_controls(validated_controls)
            logger.info(f"Applied controls (live): {validated_controls}")
            # Track applied controls for list_controls()
            self.applied_controls.update(validated_controls)
        except Exception as e:
            # Some controls may fail in streaming mode (e.g., resolution changes)
            # Try applying them one-by-one to see which ones work
            logger.warning(f"Live control application failed: {e}. Trying individual controls...")
            applied = []
            failed = []
            
            for ctrl_name, ctrl_value in validated_controls.items():
                try:
                    self.picam2.set_controls({ctrl_name: ctrl_value})
                    applied.append(ctrl_name)
                    self.applied_controls[ctrl_name] = ctrl_value
                    logger.info(f"Applied control (live): {ctrl_name}={ctrl_value}")
                except Exception as e2:
                    failed.append(f"{ctrl_name}: {e2}")
                    logger.warning(f"Failed to apply {ctrl_name} live: {e2}")
            
            if failed:
                logger.error(f"Some controls failed to apply live: {failed}. Save config for next restart.")
    
    def _validate_controls(self, controls: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and transform controls to match expected types.
        
        Some controls like ColourGains expect a tuple of 2 floats (red, blue gain).
        If a single scalar is provided, convert it to a tuple.
        """
        # Controls that expect array/tuple of 2 floats
        ARRAY2_FLOAT_CONTROLS = {'ColourGains'}
        # Controls that expect array/tuple of 2 ints
        ARRAY2_INT_CONTROLS = {'FrameDurationLimits'}
        # Controls that expect array of 4 ints (x, y, width, height)
        ARRAY4_INT_CONTROLS = {'ScalerCrop'}
        
        validated = {}
        for name, value in controls.items():
            try:
                if name in ARRAY2_FLOAT_CONTROLS:
                    # ColourGains: expects (red_gain, blue_gain)
                    if isinstance(value, (list, tuple)) and len(value) == 2:
                        validated[name] = tuple(float(v) for v in value)
                    elif isinstance(value, (int, float)):
                        # Single value provided - use same value for both gains
                        v = float(value)
                        validated[name] = (v, v)
                        logger.warning(f"{name}: single value {value} expanded to ({v}, {v})")
                    else:
                        logger.warning(f"{name}: invalid value {value}, skipping")
                        continue
                        
                elif name in ARRAY2_INT_CONTROLS:
                    if isinstance(value, (list, tuple)) and len(value) == 2:
                        validated[name] = tuple(int(v) for v in value)
                    elif isinstance(value, (int, float)):
                        v = int(value)
                        validated[name] = (v, v)
                        logger.warning(f"{name}: single value {value} expanded to ({v}, {v})")
                    else:
                        logger.warning(f"{name}: invalid value {value}, skipping")
                        continue
                        
                elif name in ARRAY4_INT_CONTROLS:
                    if isinstance(value, (list, tuple)) and len(value) == 4:
                        validated[name] = tuple(int(v) for v in value)
                    else:
                        logger.warning(f"{name}: expects 4 values, got {value}, skipping")
                        continue
                else:
                    # Standard scalar control
                    validated[name] = value
            except Exception as e:
                logger.warning(f"Error validating {name}={value}: {e}")
                continue
        
        return validated

    def list_controls(self) -> Dict[str, Any]:
        """List available camera controls with their current values."""
        if self.using_rpicam_overlay:
            return {"error": "Controls unavailable in libcamera overlay mode"}
        if not self.picam2:
            return {"error": "Camera not initialized"}
        
        # Known array controls and their descriptions
        ARRAY_CONTROLS = {
            'ColourGains': {'size': 2, 'labels': ['Red Gain', 'Blue Gain'], 'type': 'float'},
            'FrameDurationLimits': {'size': 2, 'labels': ['Min (µs)', 'Max (µs)'], 'type': 'int'},
            'ScalerCrop': {'size': 4, 'labels': ['X', 'Y', 'Width', 'Height'], 'type': 'int'},
        }
        
        try:
            controls_info = {}
            
            for name, info in self.picam2.camera_controls.items():
                min_val, max_val, default_val = info
                
                # Get current value - use tracked applied controls, fallback to default
                # applied_controls tracks what was set via set_controls()
                if name in self.applied_controls:
                    current_val = self.applied_controls[name]
                else:
                    # Fallback to capture_metadata for unset controls
                    try:
                        metadata = self.picam2.capture_metadata()
                        current_val = metadata.get(name, default_val)
                    except:
                        current_val = default_val

                # Adjust min/max for array controls to allow current values
                min_val_adjusted = min_val
                max_val_adjusted = max_val
                if name == "ColourCorrectionMatrix" and isinstance(max_val, (int, float)):
                    if not isinstance(min_val, (int, float)) or min_val >= 0:
                        min_val_adjusted = -max_val

                if isinstance(current_val, (list, tuple)):
                    numeric_vals = [v for v in current_val if isinstance(v, (int, float))]
                    if numeric_vals:
                        min_current = min(numeric_vals)
                        max_current = max(numeric_vals)
                        if isinstance(min_val_adjusted, (int, float)):
                            min_val_adjusted = min(min_val_adjusted, min_current)
                        if isinstance(max_val_adjusted, (int, float)):
                            max_val_adjusted = max(max_val_adjusted, max_current)
                
                # Determine control type - check for arrays first
                is_array = False
                array_size = 0
                array_labels = None
                
                if name in ARRAY_CONTROLS:
                    is_array = True
                    array_info = ARRAY_CONTROLS[name]
                    array_size = array_info['size']
                    array_labels = array_info['labels']
                    ctrl_type = f"array_{array_info['type']}_{array_size}"
                elif isinstance(current_val, (list, tuple)):
                    is_array = True
                    array_size = len(current_val)
                    ctrl_type = f"array_{array_size}"
                elif isinstance(min_val, bool):
                    ctrl_type = "bool"
                elif isinstance(min_val, float):
                    ctrl_type = "float"
                elif isinstance(min_val, int):
                    ctrl_type = "int"
                elif min_val is None or max_val is None:
                    ctrl_type = "other"
                else:
                    ctrl_type = "int"
                
                # Categorize controls
                category = "other"
                name_lower = name.lower()
                if any(x in name_lower for x in ['exposure', 'gain', 'iso', 'shutter']):
                    category = "exposure"
                elif any(x in name_lower for x in ['brightness', 'contrast', 'saturation', 'sharpness', 'colour', 'color']):
                    category = "color"
                elif any(x in name_lower for x in ['ae', 'awb', 'auto']):
                    category = "auto"
                elif any(x in name_lower for x in ['noise', 'denoise']):
                    category = "noise"
                
                ctrl_info = {
                    "name": name,
                    "display_name": name.replace('_', ' ').title(),
                    "type": ctrl_type,
                    "min": min_val_adjusted,
                    "max": max_val_adjusted,
                    "default": default_val,
                    "value": current_val,
                    "read_only": False,
                    "category": category,
                    "is_array": is_array
                }
                
                if is_array:
                    ctrl_info["array_size"] = array_size
                    if array_labels:
                        ctrl_info["array_labels"] = array_labels
                
                controls_info[name] = ctrl_info
            
            # Group by category
            categories = sorted(set(c["category"] for c in controls_info.values()))
            grouped = {cat: {} for cat in categories}
            for name, ctrl in controls_info.items():
                grouped[ctrl["category"]][name] = ctrl
            
            return {
                "camera_info": {
                    "model": self.camera_properties.get("Model", "unknown"),
                    "pixel_array_size": list(self.camera_properties.get("PixelArraySize", [0, 0])),
                    "unit_cell_size": list(self.camera_properties.get("UnitCellSize", [0, 0])),
                    "sensor_modes_count": len(self.sensor_modes)
                },
                "controls": controls_info,
                "grouped": grouped,
                "categories": categories
            }
        except Exception as e:
            logger.error(f"Error listing controls: {e}")
            return {"error": str(e)}

    def start(self):
        """Start the RTSP server with hardware H264 encoding."""
        logger.info("Starting CSI RTSP Server with HARDWARE H.264 Encoder...")
        logger.info(f"Config: {self.conf['WIDTH']}x{self.conf['HEIGHT']}@{self.conf['FPS']}fps, "
                   f"bitrate={self.conf['BITRATE_KBPS']}kbps")

        if self._can_use_rpicam_overlay():
            self._start_rpicam_overlay_rtsp()
            return
        
        # Initialize Picamera2 with retry logic
        # The camera may be busy during boot if kernel is still initializing
        logger.info("Initializing Picamera2...")
        max_retries = 6
        retry_delay = 0.5  # Start with 500ms, exponential backoff
        
        for attempt in range(1, max_retries + 1):
            try:
                self.picam2 = Picamera2()
                logger.info("Picamera2 initialized.")
                break
            except RuntimeError as e:
                if "Device or resource busy" in str(e) and attempt < max_retries:
                    # Camera is busy, retry with exponential backoff
                    retry_delay = min(5.0, retry_delay * 1.5)  # Max 5 seconds between retries
                    logger.warning(f"Camera busy (attempt {attempt}/{max_retries}). Retrying in {retry_delay:.1f}s...")
                    time.sleep(retry_delay)
                else:
                    # Max retries reached or different error
                    logger.error(f"Failed to initialize Picamera2 after {max_retries} attempts: {e}", exc_info=True)
                    raise
        
        # Cache camera properties before configuration
        self.camera_properties = dict(self.picam2.camera_properties)
        self.sensor_modes = [dict(m) for m in self.picam2.sensor_modes]
        
        # Configure camera for video
        # Use a video configuration that's compatible with the hardware encoder
        config = self.picam2.create_video_configuration(
            main={"size": (self.conf['WIDTH'], self.conf['HEIGHT'])},
            controls={"FrameRate": self.conf['FPS']}
        )
        self.picam2.configure(config)
        logger.info(f"Camera configured: {self.conf['WIDTH']}x{self.conf['HEIGHT']}@{self.conf['FPS']}fps")
        
        # Load and apply saved tuning parameters from config BEFORE start
        # Apply immediately after configure() but before start()
        try:
            saved_tunings = self._load_saved_tunings()
            if saved_tunings:
                logger.info(f"Attempting to apply {len(saved_tunings)} saved tuning parameters BEFORE start...")
                self.set_controls(saved_tunings)
                logger.info(f"Applied {len(saved_tunings)} saved tuning parameters BEFORE start")
            else:
                logger.info("No saved tuning parameters found")
        except Exception as e:
            logger.error(f"Could not apply saved tunings BEFORE start: {e}", exc_info=True)
        
        # Create H.264 encoder (HARDWARE via V4L2!)
        # This is the key difference - Picamera2's H264Encoder uses the Pi's hardware encoder
        self.encoder = H264Encoder(
            bitrate=self.conf['BITRATE_KBPS'] * 1000,
            repeat=True,  # Repeat SPS/PPS with each keyframe
            iperiod=self.conf['KEYINT'],
            qp=self.conf.get('H264_QP'),
            profile=self.conf.get('H264_PROFILE')
        )
        logger.info(
            f"HARDWARE H264Encoder created: bitrate={self.conf['BITRATE_KBPS']}kbps, "
            f"keyint={self.conf['KEYINT']}, qp={self.conf.get('H264_QP')}, "
            f"profile={self.conf.get('H264_PROFILE')}"
        )
        
        # Create output for H.264 stream
        self.h264_output = StreamingOutput()
        
        # Start camera with encoder
        # FileOutput wraps our StreamingOutput - encoder writes H.264 data to it
        self.picam2.start_encoder(self.encoder, FileOutput(self.h264_output))
        self.picam2.start()
        logger.info("Picamera2 started with HARDWARE H.264 encoder.")
        
        # Load and apply saved tuning parameters from config AFTER start (as fallback)
        # If controls didn't apply before, try again after stream starts
        try:
            saved_tunings = self._load_saved_tunings()
            if saved_tunings:
                logger.info(f"Attempting to re-apply {len(saved_tunings)} tuning parameters AFTER start...")
                self.set_controls(saved_tunings)
                logger.info(f"Re-applied {len(saved_tunings)} tuning parameters AFTER start")
        except Exception as e:
            logger.warning(f"Could not re-apply saved tunings AFTER start: {e}")
        
        # Start control API
        self.setup_control_api()
        
        # Setup GStreamer RTSP server
        self.main_loop = GLib.MainLoop()
        server = GstRtspServer.RTSPServer()
        server.set_service(str(self.conf['RTSP_PORT']))
        
        factory = GstRtspServer.RTSPMediaFactory()
        factory.set_launch(self._build_pipeline_launch())
        factory.set_shared(True)
        factory.connect("media-configure", self._on_media_configure)
        
        mounts = server.get_mount_points()
        mounts.add_factory(f"/{self.conf['RTSP_PATH']}", factory)
        
        server.attach(None)
        logger.info(f"RTSP Stream available at rtsp://0.0.0.0:{self.conf['RTSP_PORT']}/{self.conf['RTSP_PATH']}")
        
        # Start H.264 push thread
        self._running = True
        self._push_loop_last_frame_time = time.time()
        self._push_thread = threading.Thread(target=self._push_loop, daemon=True)
        self._push_thread.start()
        
        # Start watchdog thread to detect if push loop crashes
        watchdog_thread = threading.Thread(target=self._push_loop_watchdog, daemon=True)
        watchdog_thread.start()
        
        # Run main loop
        try:
            self.main_loop.run()
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received.")
        finally:
            self.stop()

    def stop(self):
        """Stop the server and clean up."""
        logger.info("Stopping server...")
        self._running = False
        
        if self._push_thread:
            self._push_thread.join(timeout=2)
        
        if self.main_loop:
            self.main_loop.quit()
        
        if self.picam2:
            try:
                self.picam2.stop_encoder()
                self.picam2.stop()
                self.picam2.close()
                logger.info("Camera stopped and closed.")
            except Exception as e:
                logger.warning(f"Error stopping camera: {e}")

        if self.rpicam_proc:
            try:
                self.rpicam_proc.terminate()
                self.rpicam_proc.wait(timeout=2)
            except Exception:
                try:
                    self.rpicam_proc.kill()
                except Exception:
                    pass

        if self.rpicam_overlay_config_path:
            try:
                os.unlink(self.rpicam_overlay_config_path)
            except OSError:
                pass
        
        if self.control_server:
            self.control_server.shutdown()
        
        logger.info("Server stopped.")


# ==============================================================================
# Signal handlers
# ==============================================================================
server_instance: Optional[Picam2RtspServer] = None

def signal_handler(signum, frame):
    logger.info(f"Signal {signum} received, shutting down...")
    if server_instance:
        server_instance.stop()
    sys.exit(0)


# ==============================================================================
# Main
# ==============================================================================
if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    server_instance = Picam2RtspServer(CONF)
    server_instance.start()
