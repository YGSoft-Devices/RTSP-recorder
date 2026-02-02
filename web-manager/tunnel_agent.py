#!/usr/bin/env python3
"""
RTSP-Full Meeting Tunnel Agent
Version: 1.4.2

Agent de tunnel inversé pour Meeting API.
Maintient une connexion TCP persistante vers le serveur proxy Meeting
et gère le multiplexage des connexions SSH/SCP/VNC.

Protocol:
- Handshake: Send JSON line {"token":"<TOKEN>","name":"<device_key>"}\n
- Response: {"status":"authenticated","device_key":"..."}\n or {"status":"error",...}
- Frames: 1 byte type + 4 bytes streamId (BE) + 4 bytes payloadLength (BE) + payload
- Types: N (New stream), D (Data), C (Close)

v1.4.2: Auto-configure SSH keys on startup (install Meeting pubkey, generate device key if needed)
"""

import socket
import ssl
import struct
import threading
import json
import logging
import time
import os
import sys
from typing import Dict, Optional, Tuple
from dataclasses import dataclass, field

# Configuration
DEFAULT_PROXY_HOST = "meeting.ygsoft.fr"
DEFAULT_PROXY_PORT = 9001
RECONNECT_DELAY_MIN = 5
RECONNECT_DELAY_MAX = 60
HEARTBEAT_INTERVAL = 30  # seconds, keep connection alive
SOCKET_TIMEOUT = 120  # seconds

# Frame types
FRAME_NEW = ord('N')
FRAME_DATA = ord('D')
FRAME_CLOSE = ord('C')

logger = logging.getLogger("TunnelAgent")


@dataclass
class LocalStream:
    """Represents a local TCP connection for a stream."""
    stream_id: int
    local_socket: socket.socket
    local_port: int
    closed: bool = False
    read_thread: Optional[threading.Thread] = None


class TunnelAgent:
    """
    Meeting Tunnel Agent - manages reverse tunnel to Meeting proxy.
    
    Handles:
    - Persistent TCP connection to proxy server
    - Handshake authentication with token + device_key
    - Multiplexed streams (N/D/C protocol)
    - Local connections to SSH (22), HTTP (5000), VNC (5900), etc.
    - Automatic reconnection with exponential backoff
    """
    
    def __init__(
        self,
        device_key: str,
        token: str,
        proxy_host: str = DEFAULT_PROXY_HOST,
        proxy_port: int = DEFAULT_PROXY_PORT,
        use_ssl: bool = True
    ):
        self.device_key = device_key
        self.token = token
        self.proxy_host = proxy_host
        self.proxy_port = proxy_port
        self.use_ssl = use_ssl
        
        self.proxy_socket: Optional[socket.socket] = None
        self.streams: Dict[int, LocalStream] = {}
        self.streams_lock = threading.Lock()
        
        self.running = False
        self.connected = False
        self.reconnect_delay = RECONNECT_DELAY_MIN
        
        self._reader_thread: Optional[threading.Thread] = None
        self._writer_lock = threading.Lock()
        self._pending_byte: Optional[bytes] = None  # For handling binary frames during handshake
        
        logger.info(f"TunnelAgent initialized for device {device_key[:8]}... -> {proxy_host}:{proxy_port}")
    
    def start(self):
        """Start the tunnel agent (blocking, handles reconnection)."""
        self.running = True
        logger.info("Tunnel agent starting...")
        
        while self.running:
            try:
                self._connect_and_run()
            except Exception as e:
                logger.error(f"Connection error: {e}")
            
            if self.running:
                logger.info(f"Reconnecting in {self.reconnect_delay}s...")
                time.sleep(self.reconnect_delay)
                # Exponential backoff
                self.reconnect_delay = min(self.reconnect_delay * 2, RECONNECT_DELAY_MAX)
        
        logger.info("Tunnel agent stopped")
    
    def stop(self):
        """Stop the tunnel agent."""
        logger.info("Stopping tunnel agent...")
        self.running = False
        self._close_all_streams()
        self._close_proxy_socket()
    
    def _connect_and_run(self):
        """Connect to proxy and handle messages until disconnection."""
        # Reset state
        self._pending_byte = None
        
        # Create socket
        raw_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        raw_socket.settimeout(SOCKET_TIMEOUT)
        
        try:
            if self.use_ssl:
                context = ssl.create_default_context()
                # For self-signed certs (development), uncomment:
                # context.check_hostname = False
                # context.verify_mode = ssl.CERT_NONE
                self.proxy_socket = context.wrap_socket(raw_socket, server_hostname=self.proxy_host)
            else:
                self.proxy_socket = raw_socket
            
            logger.info(f"Connecting to {self.proxy_host}:{self.proxy_port}...")
            self.proxy_socket.connect((self.proxy_host, self.proxy_port))
            logger.info("Connected to proxy server")
            
            # Perform handshake
            self._handshake()
            
            self.connected = True
            self.reconnect_delay = RECONNECT_DELAY_MIN  # Reset on successful connection
            
            # Read frames until disconnection
            self._read_loop()
            
        finally:
            self.connected = False
            self._close_all_streams()
            self._close_proxy_socket()
    
    def _handshake(self):
        """
        Send handshake message to proxy and read response.
        
        Per MEETING - integration.md:
        - Send: {"token":"<TOKEN>","name":"<device_key>"}\n
        - Response: {"status":"authenticated","device_key":"..."}\n
        """
        handshake = {
            "token": self.token,
            "name": self.device_key
        }
        handshake_line = json.dumps(handshake) + "\n"
        
        logger.debug(f"Sending handshake for device {self.device_key[:8]}...")
        self.proxy_socket.sendall(handshake_line.encode('utf-8'))
        logger.info("Handshake sent, waiting for response...")
        
        # Read response (JSON line terminated by \n)
        response_buffer = b''
        while len(response_buffer) < 4096:
            chunk = self.proxy_socket.recv(1)
            if not chunk:
                raise ConnectionError("Connection closed during handshake")
            if chunk == b'\n':
                break
            response_buffer += chunk
        
        if response_buffer:
            try:
                response = json.loads(response_buffer.decode('utf-8'))
                logger.info(f"Handshake response: {response.get('status', 'unknown')}")
                
                if response.get('status') == 'error':
                    error_msg = response.get('message', response.get('error', 'Unknown error'))
                    raise ConnectionError(f"Handshake rejected: {error_msg}")
                
                if response.get('status') == 'authenticated':
                    logger.info("Handshake completed - switching to frame mode")
                else:
                    logger.warning(f"Unexpected handshake response status: {response.get('status')}")
            except json.JSONDecodeError as e:
                logger.warning(f"Non-JSON handshake response: {response_buffer.decode('utf-8', errors='replace')[:100]}")

    def _read_loop(self):
        """Main loop: read frames from proxy and dispatch."""
        logger.info("Starting frame read loop...")
        
        while self.running and self.connected:
            try:
                frame = self._read_frame()
                if frame is None:
                    logger.info("Connection closed by proxy")
                    break
                
                frame_type, stream_id, payload = frame
                self._handle_frame(frame_type, stream_id, payload)
                
            except socket.timeout:
                # No activity, send keepalive or continue
                continue
            except Exception as e:
                import traceback
                logger.error(f"Error in read loop: {type(e).__name__}: {e}")
                logger.debug(traceback.format_exc())
                break
    
    def _read_frame(self) -> Optional[Tuple[int, int, bytes]]:
        """
        Read a single frame from the proxy.
        Returns (frame_type, stream_id, payload) or None if connection closed.
        """
        # Read header: 1 byte type + 4 bytes streamId + 4 bytes length = 9 bytes
        header = self._recv_exact(9)
        if header is None:
            return None
        
        frame_type = header[0]
        stream_id = struct.unpack('>I', header[1:5])[0]
        payload_length = struct.unpack('>I', header[5:9])[0]
        
        # Read payload
        if payload_length > 0:
            payload = self._recv_exact(payload_length)
            if payload is None:
                return None
        else:
            payload = b''
        
        return (frame_type, stream_id, payload)
    
    def _recv_exact(self, size: int) -> Optional[bytes]:
        """Read exactly `size` bytes from proxy socket."""
        data = b''
        
        # Check for pending byte from handshake
        if self._pending_byte:
            data = self._pending_byte
            self._pending_byte = None
        
        while len(data) < size:
            chunk = self.proxy_socket.recv(size - len(data))
            if not chunk:
                if len(data) > 0:
                    logger.warning(f"Connection closed mid-frame: received {len(data)}/{size} bytes, partial: {data[:20]!r}")
                return None
            data += chunk
        return data
    
    def _handle_frame(self, frame_type: int, stream_id: int, payload: bytes):
        """Handle a received frame."""
        if frame_type == FRAME_NEW:
            self._handle_new_stream(stream_id, payload)
        elif frame_type == FRAME_DATA:
            self._handle_data(stream_id, payload)
        elif frame_type == FRAME_CLOSE:
            self._handle_close(stream_id)
        else:
            logger.warning(f"Unknown frame type: {frame_type}")
    
    def _handle_new_stream(self, stream_id: int, payload: bytes):
        """Handle N (New stream) frame - open local connection."""
        if len(payload) < 2:
            logger.error(f"Invalid N frame payload length: {len(payload)}")
            self._send_close(stream_id)
            return
        
        local_port = struct.unpack('>H', payload[:2])[0]
        logger.info(f"New stream {stream_id} -> 127.0.0.1:{local_port}")
        
        try:
            # Connect to local service
            local_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            local_sock.settimeout(10)
            local_sock.connect(('127.0.0.1', local_port))
            local_sock.settimeout(None)
            
            # Create stream entry
            stream = LocalStream(
                stream_id=stream_id,
                local_socket=local_sock,
                local_port=local_port
            )
            
            with self.streams_lock:
                self.streams[stream_id] = stream
            
            # Start reader thread for local socket
            thread = threading.Thread(
                target=self._local_read_loop,
                args=(stream_id,),
                daemon=True
            )
            stream.read_thread = thread
            thread.start()
            
            logger.info(f"Stream {stream_id} connected to local port {local_port}")
            
        except Exception as e:
            logger.error(f"Failed to connect stream {stream_id} to port {local_port}: {e}")
            self._send_close(stream_id)
    
    def _handle_data(self, stream_id: int, payload: bytes):
        """Handle D (Data) frame - forward data to local socket."""
        with self.streams_lock:
            stream = self.streams.get(stream_id)
        
        if stream is None or stream.closed:
            logger.debug(f"Data for unknown/closed stream {stream_id}, ignoring")
            return
        
        try:
            stream.local_socket.sendall(payload)
        except Exception as e:
            logger.error(f"Error sending data to local socket for stream {stream_id}: {e}")
            self._close_stream(stream_id)
    
    def _handle_close(self, stream_id: int):
        """Handle C (Close) frame - close local connection."""
        logger.info(f"Close received for stream {stream_id}")
        self._close_stream(stream_id, send_close=False)
    
    def _local_read_loop(self, stream_id: int):
        """Read data from local socket and forward to proxy."""
        with self.streams_lock:
            stream = self.streams.get(stream_id)
        
        if stream is None:
            return
        
        try:
            while self.running and self.connected and not stream.closed:
                try:
                    data = stream.local_socket.recv(4096)
                    if not data:
                        logger.info(f"Local socket closed for stream {stream_id}")
                        break
                    
                    self._send_data(stream_id, data)
                    
                except socket.timeout:
                    continue
                except Exception as e:
                    logger.error(f"Error reading from local socket for stream {stream_id}: {e}")
                    break
        finally:
            self._close_stream(stream_id)
    
    def _send_frame(self, frame_type: int, stream_id: int, payload: bytes = b''):
        """Send a frame to the proxy."""
        header = bytes([frame_type])
        header += struct.pack('>I', stream_id)
        header += struct.pack('>I', len(payload))
        
        with self._writer_lock:
            try:
                if self.proxy_socket:
                    self.proxy_socket.sendall(header + payload)
            except Exception as e:
                logger.error(f"Error sending frame: {e}")
                self.connected = False
    
    def _send_data(self, stream_id: int, data: bytes):
        """Send D (Data) frame to proxy."""
        self._send_frame(FRAME_DATA, stream_id, data)
    
    def _send_close(self, stream_id: int):
        """Send C (Close) frame to proxy."""
        self._send_frame(FRAME_CLOSE, stream_id)
    
    def _close_stream(self, stream_id: int, send_close: bool = True):
        """Close a stream and clean up."""
        with self.streams_lock:
            stream = self.streams.pop(stream_id, None)
        
        if stream is None:
            return
        
        stream.closed = True
        
        try:
            stream.local_socket.close()
        except:
            pass
        
        if send_close:
            self._send_close(stream_id)
        
        logger.info(f"Stream {stream_id} closed")
    
    def _close_all_streams(self):
        """Close all active streams."""
        with self.streams_lock:
            stream_ids = list(self.streams.keys())
        
        for stream_id in stream_ids:
            self._close_stream(stream_id, send_close=False)
    
    def _close_proxy_socket(self):
        """Close the proxy socket."""
        if self.proxy_socket:
            try:
                self.proxy_socket.close()
            except:
                pass
            self.proxy_socket = None


def load_config() -> Optional[dict]:
    """Load tunnel configuration from config files."""
    # Try meeting.json first
    config_paths = [
        '/etc/rpi-cam/meeting.json',
        '/opt/rpi-cam-webmanager/meeting.json',
        'meeting.json'
    ]
    
    for path in config_paths:
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    config = json.load(f)
                    if config.get('device_key') and config.get('token_code'):
                        logger.info(f"Loaded config from {path}")
                        return config
            except Exception as e:
                logger.warning(f"Failed to load config from {path}: {e}")
    
    # Try environment variables
    device_key = os.environ.get('MEETING_DEVICE_KEY')
    token = os.environ.get('MEETING_TOKEN')
    
    if device_key and token:
        logger.info("Loaded config from environment variables")
        return {
            'device_key': device_key,
            'token_code': token
        }
    
    return None


def main():
    """Main entry point."""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Load configuration
    config = load_config()
    if not config:
        logger.error("No configuration found. Please set device_key and token_code in meeting.json or environment.")
        sys.exit(1)
    
    device_key = config.get('device_key')
    token = config.get('token_code')
    proxy_host = config.get('tunnel_host', DEFAULT_PROXY_HOST)
    proxy_port = config.get('tunnel_port', DEFAULT_PROXY_PORT)
    # NOTE: Meeting proxy port 9001 does NOT use SSL/TLS - it's plain TCP
    use_ssl = config.get('tunnel_ssl', False)
    
    # Auto-configure SSH keys before starting tunnel
    # This ensures Meeting can SSH into this device via the tunnel
    try:
        # Import from services module (same web-manager directory)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        if script_dir not in sys.path:
            sys.path.insert(0, script_dir)
        
        from services.meeting_service import ensure_ssh_keys_configured
        
        logger.info("Auto-configuring SSH keys for Meeting integration...")
        result = ensure_ssh_keys_configured()
        if result.get('success'):
            logger.info(f"SSH keys configured: {result.get('message', 'OK')}")
        else:
            logger.warning(f"SSH keys configuration issue: {result.get('error', 'unknown')}")
    except ImportError as e:
        logger.warning(f"Could not import meeting_service for SSH key setup: {e}")
    except Exception as e:
        logger.warning(f"SSH keys auto-configuration error: {e}")
    
    # Create and start agent
    agent = TunnelAgent(
        device_key=device_key,
        token=token,
        proxy_host=proxy_host,
        proxy_port=proxy_port,
        use_ssl=use_ssl
    )
    
    try:
        agent.start()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        agent.stop()


if __name__ == '__main__':
    main()
