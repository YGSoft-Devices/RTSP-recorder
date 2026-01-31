Features:
Implements the ONVIF Standard for a CCTV Camera and NVT (Network Video Transmitter)
Streams H264 video over RTSP from the Official Raspberry Pi camera (the one that uses the ribbon cable) and some USB cameras
Uses hardware H264 encoding using the GPU on the Pi
Implements Camera control (resolution and framerate) through ONVIF
Can set other camera options through a web interface.
Discoverable (WS-Discovery) on Pi/Linux by CCTV Viewing Software
Works with ONVIF Device Manager (Windows) and ONVIF Device Tool (Linux)
Works with other CCTV Viewing Software that implements the ONVIF standard including Antrica Decoder, Avigilon Control Centre, Bosch BVMS, Milestone, ISpy (Opensource), BenSoft SecuritySpy (Mac), IndigoVision Control Centre and Genetec Security Centre (add camera as ONVIF-BASIC mode)
Implements ONVIF Authentication
Implements Absolute, Relative and Continuous PTZ and controls the Pimononi Raspberry Pi Pan-Tilt HAT
Can also use the Waveshare Pan-Tilt HAT with a custom driver for the PWM chip used but be aware the servos in their kit do not fit so we recommend the Pimoroni model
Also converts ONVIF PTZ commands into Pelco D and Visca telemetry on a serial port (UART) for other Pan/Tilt platforms (ie a PTZ Proxy or PTZ Protocol Converter)
Can reference other RTSP servers, which in turn can pull in the video via RTSP, other ONVIF sources, Desktop Capture, MJPEG allowing RPOS to be a Video Stream Proxy
Implements Imaging service Brightness and Focus commands (for Profile T)
Implements Relay (digital output) function
Supports Unicast (UDP/TDP) and Multicast using mpromonet's RTSP server
Supports Unicast (UDP/TCP) RTSP using GStreamer
Works as a PTZ Proxy
Also runs on Mac, Windows and other Linux machines but you need to supply your own RTSP server. An example to use ffserver on the Mac is included.
USB cameras supported via the GStreamer RTSP server with limited parameters available. Tested with JPEG USB HD camera