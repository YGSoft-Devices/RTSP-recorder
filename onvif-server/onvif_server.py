#!/usr/bin/env python3
"""
Simple ONVIF Server for RTSP Cameras
Provides ONVIF device discovery and media service for RTSP streams

Version: 1.5.7
Target: Raspberry Pi OS Trixie (64-bit)

Changelog:
  1.5.7 - All Set* operations allowed without auth (read-only camera)
        - SetVideoEncoderConfiguration, DeleteProfile, etc. now allowed
        - Fixes Synology Surveillance Station configuration phase errors
  1.5.6 - All ONVIF actions allowed without authentication for Synology compatibility
        - CreateProfile, SetNTP, Add*Configuration now allowed without auth
        - These actions return existing configs (read-only camera)
        - Eliminates HTTP 500 errors that confused Synology
  1.5.5 - Include RTSP credentials in GetStreamUri response
        - Fixes Synology Surveillance Station "not authorized" RTSP error
        - URL format: rtsp://user:password@ip:port/path
  1.5.4 - Public ONVIF actions without authentication (ONVIF standard compliance)
        - GetCapabilities, GetSystemDateAndTime, GetServices, etc. accessible without auth
        - Fixes Synology Surveillance Station "no connection" error
        - Protected actions (GetProfiles, GetStreamUri, etc.) still require auth
  1.5.3 - RTSP credentials sync from config.env
        - If RTSP_USER/RTSP_PASSWORD set in config.env, ONVIF uses same credentials
        - Enables Synology Surveillance Station to connect with consistent auth
  1.5.0 - Device name from Meeting API integration
        - If device is provisioned, uses Meeting device name (e.g., V1-S01-00030)
        - If not provisioned or API unavailable, uses "UNPROVISIONNED"
        - Reads MEETING_API_URL, MEETING_DEVICE_KEY, MEETING_TOKEN_CODE from config.env
  1.4.0 - Added ConstantBitRate support for Surveillance Station
        - CBR flag in H264Options, RateControl, and Profiles
        - Surveillance Station can now use fixed bitrate mode
  1.3.0 - Extended video encoder options for Surveillance Station compatibility
        - Added resolutions: 1920x1080, 800x600, 320x240
        - Added BitrateRange (128-8000 kbps) for CBR support
        - Added H264 High profile support
  1.2.0 - Network interface priority: Ethernet (eth0) > WiFi (wlan1 > wlan0)
        - Reads NETWORK_INTERFACE_PRIORITY from config.env
        - RTSP/ONVIF URL auto-switches based on active interface
  1.1.0 - Dynamic IP detection by client subnet (multi-interface support)
        - Fixed int('') error on empty H264_BITRATE_KBPS
  1.0.0 - Initial release
"""

import os
import sys
import json
import socket
import struct
import threading
import argparse
import hashlib
import base64
import secrets
import ssl
import urllib.request
import urllib.error
from datetime import datetime, timezone
from urllib.parse import quote
from http.server import HTTPServer, BaseHTTPRequestHandler
from xml.etree import ElementTree as ET

# ONVIF Namespaces
NAMESPACES = {
    'soap': 'http://www.w3.org/2003/05/soap-envelope',
    'wsa': 'http://www.w3.org/2005/08/addressing',
    'tds': 'http://www.onvif.org/ver10/device/wsdl',
    'trt': 'http://www.onvif.org/ver10/media/wsdl',
    'tt': 'http://www.onvif.org/ver10/schema',
    'wsnt': 'http://docs.oasis-open.org/wsn/b-2',
    'wsse': 'http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd',
    'wsu': 'http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd',
}

# Register namespaces for XML generation
for prefix, uri in NAMESPACES.items():
    ET.register_namespace(prefix, uri)


class ONVIFConfig:
    """ONVIF Server Configuration"""
    
    def __init__(self, config_file='/etc/rpi-cam/onvif.conf'):
        self.config_file = config_file
        self.rtsp_config_file = '/etc/rpi-cam/config.env'  # Main config file
        self.port = 8080
        self.name = 'UNPROVISIONNED'  # Default name if not provisioned
        self.username = ''
        self.password = ''
        self.rtsp_port = 8554
        self.rtsp_path = '/stream'
        # Video settings (read from main config)
        self.video_width = 640
        self.video_height = 480
        self.video_fps = 15
        self.video_bitrate = 2000
        # Meeting API settings
        self.meeting_api_url = ''
        self.meeting_device_key = ''
        self.meeting_token_code = ''
        self.load()
    
    def load(self):
        """Load configuration from file."""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                    self.port = data.get('port', 8080)
                    # Don't override name from onvif.conf - we get it from Meeting API
                    self.username = data.get('username', '')
                    self.password = data.get('password', '')
                    self.rtsp_port = data.get('rtsp_port', 8554)
                    self.rtsp_path = data.get('rtsp_path', '/stream')
        except Exception as e:
            print(f"[ONVIF] Error loading config: {e}")
        
        # Load video settings and Meeting API settings from RTSP config
        self.load_video_settings()
        
        # Fetch device name from Meeting API
        self.fetch_device_name_from_meeting()
    
    def load_video_settings(self):
        """Load video settings, RTSP credentials, and Meeting API settings from main config file."""
        try:
            if os.path.exists(self.rtsp_config_file):
                with open(self.rtsp_config_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith('#') or '=' not in line:
                            continue
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        
                        if key == 'VIDEO_WIDTH' and value:
                            self.video_width = int(value)
                        elif key == 'VIDEO_HEIGHT' and value:
                            self.video_height = int(value)
                        elif key == 'VIDEO_FPS' and value:
                            self.video_fps = int(value)
                        elif key == 'H264_BITRATE_KBPS' and value:
                            self.video_bitrate = int(value)
                        elif key == 'RTSP_PORT' and value:
                            self.rtsp_port = int(value)
                        elif key == 'RTSP_PATH' and value:
                            self.rtsp_path = '/' + value.lstrip('/')
                        # RTSP authentication credentials - sync with RTSP server
                        # If set, these will be used for ONVIF authentication
                        elif key == 'RTSP_USER' and value:
                            if not self.username:  # Don't override if set in onvif.conf
                                self.username = value
                        elif key == 'RTSP_PASSWORD' and value:
                            if not self.password:  # Don't override if set in onvif.conf
                                self.password = value
                        # Meeting API settings
                        elif key == 'MEETING_API_URL' and value:
                            self.meeting_api_url = value.rstrip('/')
                        elif key == 'MEETING_DEVICE_KEY' and value:
                            self.meeting_device_key = value
                        elif key == 'MEETING_TOKEN_CODE' and value:
                            self.meeting_token_code = value
                print(f"[ONVIF] Loaded video settings: {self.video_width}x{self.video_height}@{self.video_fps}fps")
                if self.username:
                    print(f"[ONVIF] RTSP authentication: user={self.username}")
        except Exception as e:
            print(f"[ONVIF] Error loading video settings: {e}")
    
    def fetch_device_name_from_meeting(self):
        """Fetch device name from Meeting API.
        
        If the device is provisioned in Meeting, uses the device name from Meeting.
        Otherwise, defaults to 'UNPROVISIONNED'.
        """
        if not self.meeting_api_url or not self.meeting_device_key:
            print(f"[ONVIF] Meeting API not configured, using default name: {self.name}")
            return
        
        try:
            url = f"{self.meeting_api_url}/devices/{self.meeting_device_key}"
            
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'User-Agent': 'ONVIF-Server/1.0'
            }
            
            if self.meeting_token_code:
                headers['X-Token-Code'] = self.meeting_token_code
            
            # Create SSL context that doesn't verify (for self-signed certs)
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            req = urllib.request.Request(url, headers=headers, method='GET')
            
            with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
                response_data = response.read().decode('utf-8')
                data = json.loads(response_data)
                
                # Try to get device name from the response
                # The API returns "product_serial" (e.g., "V1-S01-00030") as the device name
                device_name = data.get('product_serial', '') or data.get('name', '') or data.get('device_name', '')
                
                if device_name:
                    self.name = device_name
                    print(f"[ONVIF] Device name from Meeting API: {self.name}")
                else:
                    print(f"[ONVIF] No device name in Meeting response, using: {self.name}")
                    
        except urllib.error.HTTPError as e:
            if e.code == 404:
                print(f"[ONVIF] Device not found in Meeting (404), using: {self.name}")
            else:
                print(f"[ONVIF] Meeting API HTTP error {e.code}: {e.reason}, using: {self.name}")
        except urllib.error.URLError as e:
            print(f"[ONVIF] Meeting API connection error: {e.reason}, using: {self.name}")
        except json.JSONDecodeError as e:
            print(f"[ONVIF] Meeting API invalid JSON response: {e}, using: {self.name}")
        except Exception as e:
            print(f"[ONVIF] Meeting API error: {e}, using: {self.name}")

    def get_scope_safe_name(self):
        """Return URL-safe device name for ONVIF scope usage."""
        name = (self.name or '').strip() or 'UNPROVISIONNED'
        return quote(name, safe='')
    
    def get_local_ip(self, client_ip=None):
        """Get the local IP address with proper interface priority.
        
        Priority logic:
        1. If client_ip provided: find IP on same subnet (for ONVIF discovery)
        2. Otherwise: Ethernet first if connected, then WiFi by priority
        
        Interface priority order: eth0 > wlan1 > wlan0 (configurable via NETWORK_INTERFACE_PRIORITY)
        """
        try:
            import subprocess
            
            # If client IP provided, try to find IP on same subnet first
            if client_ip and client_ip not in ('127.0.0.1', 'localhost'):
                result = subprocess.run(['ip', '-4', 'addr'], capture_output=True, text=True)
                if result.returncode == 0:
                    client_prefix = '.'.join(client_ip.split('.')[:3])
                    for line in result.stdout.split('\n'):
                        if 'inet ' in line and 'scope global' in line:
                            parts = line.strip().split()
                            if len(parts) >= 2:
                                ip = parts[1].split('/')[0]
                                if ip.startswith(client_prefix + '.'):
                                    return ip
            
            # Get preferred IP based on interface priority (Ethernet first, then WiFi)
            preferred_ip = self._get_preferred_ip_by_priority()
            if preferred_ip:
                return preferred_ip
            
            # Ultimate fallback: default route IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception as e:
            print(f"[ONVIF] get_local_ip error: {e}")
            return "127.0.0.1"
    
    def _get_preferred_ip_by_priority(self):
        """Get IP address based on interface priority.
        
        Returns the IP of the highest priority interface that is UP and has an IP.
        Priority: eth0 (Ethernet) > wlan1 (USB WiFi) > wlan0 (built-in WiFi)
        """
        import subprocess
        
        # Default priority order - Ethernet first, then WiFi interfaces
        # This can be overridden by NETWORK_INTERFACE_PRIORITY in config
        priority_order = ['eth0', 'wlan1', 'wlan0', 'enp0s3', 'end0']
        
        # Try to read custom priority from config file
        try:
            if os.path.exists(self.rtsp_config_file):
                with open(self.rtsp_config_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith('NETWORK_INTERFACE_PRIORITY='):
                            value = line.split('=', 1)[1].strip().strip('"').strip("'")
                            if value:
                                priority_order = [iface.strip() for iface in value.split(',')]
                            break
        except Exception as e:
            print(f"[ONVIF] Error reading interface priority: {e}")
        
        # Get all interface IPs
        interface_ips = {}
        try:
            result = subprocess.run(['ip', '-4', 'addr'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                current_iface = None
                for line in result.stdout.split('\n'):
                    # Match interface line: "2: eth0: <BROADCAST,MULTICAST,UP,..."
                    if ': ' in line and not line.startswith(' '):
                        parts = line.split(': ')
                        if len(parts) >= 2:
                            current_iface = parts[1].split('@')[0]  # Handle eth0@if2 format
                    # Match IP line: "    inet 192.168.1.191/24 ..."
                    elif 'inet ' in line and 'scope global' in line and current_iface:
                        parts = line.strip().split()
                        if len(parts) >= 2:
                            ip = parts[1].split('/')[0]
                            # Skip loopback and link-local
                            if not ip.startswith('127.') and not ip.startswith('169.254.'):
                                interface_ips[current_iface] = ip
        except Exception as e:
            print(f"[ONVIF] Error getting interface IPs: {e}")
            return None
        
        # Return IP of highest priority interface that has one
        for iface in priority_order:
            if iface in interface_ips:
                print(f"[ONVIF] Using {iface} IP: {interface_ips[iface]}")
                return interface_ips[iface]
        
        # If no priority interface found, return any available
        if interface_ips:
            first_iface = list(interface_ips.keys())[0]
            print(f"[ONVIF] Fallback to {first_iface} IP: {interface_ips[first_iface]}")
            return interface_ips[first_iface]
        
        return None


class ONVIFHandler(BaseHTTPRequestHandler):
    """HTTP Handler for ONVIF requests"""
    
    config = None
    
    def log_message(self, format, *args):
        """Custom log format."""
        print(f"[ONVIF] {self.address_string()} - {format % args}")
    
    def log_action(self, action, client_ip):
        """Log ONVIF action for debugging."""
        print(f"[ONVIF] {client_ip} -> {action}")
    
    def do_GET(self):
        """Handle GET requests (for WSDL)."""
        if self.path.endswith('.wsdl') or self.path.endswith('.xsd'):
            self.send_response(200)
            self.send_header('Content-Type', 'application/xml')
            self.end_headers()
            # Return empty WSDL (most ONVIF clients don't need it)
            self.wfile.write(b'<?xml version="1.0" encoding="UTF-8"?><definitions/>')
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        """Handle POST requests (ONVIF SOAP)."""
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        
        # Parse SOAP request
        try:
            root = ET.fromstring(body)
            soap_body = root.find('.//{http://www.w3.org/2003/05/soap-envelope}Body')
            
            if soap_body is None:
                soap_body = root.find('.//{http://schemas.xmlsoap.org/soap/envelope/}Body')
            
            if soap_body is None:
                self.send_soap_fault("Missing SOAP body")
                return
            
            # Get the first child element (the actual request)
            request_element = list(soap_body)[0] if len(soap_body) > 0 else None
            
            if request_element is None:
                self.send_soap_fault("Empty SOAP body")
                return
            
            # Extract action from element tag
            action = request_element.tag.split('}')[-1] if '}' in request_element.tag else request_element.tag
            
            # Log the action for debugging
            self.log_action(action, self.address_string())
            
            # ONVIF standard: Some actions must be accessible without authentication
            # for device discovery and initial connection
            # Synology sends each request twice: with auth and without auth
            # We allow all "Get" read operations without auth for compatibility
            PUBLIC_ACTIONS = {
                # Device Service - Discovery & Info
                'GetSystemDateAndTime',  # Required for time sync before auth
                'GetCapabilities',       # Required for capability discovery
                'GetServices',           # Required for service discovery
                'GetServiceCapabilities', # Required for service discovery
                'GetScopes',             # Required for WS-Discovery
                'GetDeviceInformation',  # Often needed for initial setup
                'GetHostname',           # Basic device info
                'GetNetworkInterfaces',  # Basic network info
                'GetNTP',                # Time config
                'GetRelayOutputs',       # Relay info
                
                # Media Service - Read operations (needed by Synology)
                'GetProfiles',           # Profile list
                'GetProfile',            # Single profile
                'GetVideoSources',       # Video source info
                'GetVideoSourceConfigurations',      # Video source configs
                'GetVideoEncoderConfigurations',     # Encoder configs
                'GetVideoEncoderConfiguration',      # Single encoder config
                'GetVideoEncoderConfigurationOptions', # Encoder options
                'GetVideoSourceConfigurationOptions', # Source options
                'GetAudioSources',                   # Audio source info
                'GetAudioSourceConfigurations',      # Audio source configs
                'GetAudioEncoderConfigurations',     # Audio encoder configs
                'GetAudioEncoderConfigurationOptions', # Audio encoder options
                'GetStreamUri',          # RTSP URL (contains auth in URL if needed)
                'GetSnapshotUri',        # Snapshot URL
                'GetGuaranteedNumberOfVideoEncoderInstances',
                'GetCompatibleAudioSourceConfigurations',
                'GetCompatibleVideoSourceConfigurations',
                'GetCompatibleVideoEncoderConfigurations',
                'GetCompatibleAudioEncoderConfigurations',
                
                # Write actions - allowed without auth for Synology compatibility
                # These return our existing profile/config, they don't actually modify anything
                'CreateProfile',         # Returns existing profile (read-only camera)
                'DeleteProfile',         # Accepted but ignored (we keep MainProfile)
                'SetNTP',                # Accepted but ignored (NTP managed by OS)
                'AddVideoSourceConfiguration',   # Returns existing config
                'AddVideoEncoderConfiguration',  # Returns existing config
                'AddAudioSourceConfiguration',   # Returns existing config
                'AddAudioEncoderConfiguration',  # Returns existing config
                'SetVideoEncoderConfiguration',  # Accepted but ignored (read-only camera)
                'SetVideoSourceConfiguration',   # Accepted but ignored (read-only camera)
                'SetAudioEncoderConfiguration',  # Accepted but ignored (read-only camera)
                'SetAudioSourceConfiguration',   # Accepted but ignored (read-only camera)
            }
            
            # Check authentication if required (skip for public actions)
            if self.config.username and self.config.password:
                if action not in PUBLIC_ACTIONS:
                    if not self.verify_auth(root):
                        print(f"[ONVIF] Auth required for action: {action}")
                        self.send_soap_fault("Not Authorized", "ter:NotAuthorized")
                        return
            
            # Route to handler
            response = self.handle_action(action, request_element)
            
            if response:
                self.send_response(200)
                self.send_header('Content-Type', 'application/soap+xml; charset=utf-8')
                self.end_headers()
                self.wfile.write(response.encode('utf-8'))
            else:
                self.send_soap_fault(f"Unknown action: {action}")
                
        except ET.ParseError as e:
            self.send_soap_fault(f"XML Parse Error: {e}")
        except Exception as e:
            print(f"[ONVIF] Error: {e}")
            self.send_soap_fault(str(e))
    
    def verify_auth(self, root):
        """Verify WS-Security authentication."""
        try:
            # Find Security header
            security = root.find('.//{http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd}Security')
            if security is None:
                return False
            
            username_token = security.find('.//{http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd}UsernameToken')
            if username_token is None:
                return False
            
            username = username_token.findtext('.//{http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd}Username', '')
            password = username_token.findtext('.//{http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd}Password', '')
            nonce = username_token.findtext('.//{http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd}Nonce', '')
            created = username_token.findtext('.//{http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd}Created', '')
            
            if username != self.config.username:
                return False
            
            # Verify password digest if nonce is provided
            if nonce and created:
                # WS-Security password digest
                nonce_bytes = base64.b64decode(nonce)
                created_bytes = created.encode('utf-8')
                password_bytes = self.config.password.encode('utf-8')
                
                digest_input = nonce_bytes + created_bytes + password_bytes
                expected_digest = base64.b64encode(hashlib.sha1(digest_input).digest()).decode('utf-8')
                
                return password == expected_digest
            else:
                # Plain text password comparison
                return password == self.config.password
                
        except Exception as e:
            print(f"[ONVIF] Auth error: {e}")
            return False
    
    def handle_action(self, action, request_element):
        """Route action to appropriate handler."""
        handlers = {
            # Device Service
            'GetSystemDateAndTime': self.get_system_date_time,
            'GetDeviceInformation': self.get_device_information,
            'GetCapabilities': self.get_capabilities,
            'GetServices': self.get_services,
            'GetScopes': self.get_scopes,
            'GetHostname': self.get_hostname,
            'GetNetworkInterfaces': self.get_network_interfaces,
            
            # Media Service
            'GetProfiles': self.get_profiles,
            'GetProfile': self.get_profile,
            'GetStreamUri': self.get_stream_uri,
            'GetVideoSources': self.get_video_sources,
            'GetVideoSourceConfigurations': self.get_video_source_configurations,
            'GetVideoEncoderConfigurations': self.get_video_encoder_configurations,
            'GetVideoEncoderConfiguration': self.get_video_encoder_configuration,
            'SetVideoEncoderConfiguration': self.set_video_encoder_configuration,
            'GetVideoEncoderConfigurationOptions': self.get_video_encoder_configuration_options,
            'GetGuaranteedNumberOfVideoEncoderInstances': self.get_guaranteed_encoder_instances,
            'GetSnapshotUri': self.get_snapshot_uri,
            'GetAudioSources': self.get_audio_sources,
            'GetAudioSourceConfigurations': self.get_audio_source_configurations,
            'GetAudioEncoderConfigurations': self.get_audio_encoder_configurations,
            'GetAudioEncoderConfigurationOptions': self.get_audio_encoder_configuration_options,
            'GetVideoSourceConfigurationOptions': self.get_video_source_configuration_options,
            'GetServiceCapabilities': self.get_service_capabilities,
            'GetRelayOutputs': self.get_relay_outputs,
            'GetNTP': self.get_ntp,
            'SetNTP': self.set_ntp,
            'CreateProfile': self.create_profile,
            'DeleteProfile': self.delete_profile,
            'AddVideoSourceConfiguration': self.add_video_source_configuration,
            'AddVideoEncoderConfiguration': self.add_video_encoder_configuration,
            'AddAudioSourceConfiguration': self.add_audio_source_configuration,
            'AddAudioEncoderConfiguration': self.add_audio_encoder_configuration,
            'GetCompatibleAudioSourceConfigurations': self.get_compatible_audio_source_configurations,
            'GetCompatibleVideoSourceConfigurations': self.get_compatible_video_source_configurations,
            'GetCompatibleVideoEncoderConfigurations': self.get_compatible_video_encoder_configurations,
            'GetCompatibleAudioEncoderConfigurations': self.get_compatible_audio_encoder_configurations,
        }
        
        handler = handlers.get(action)
        if handler:
            return handler(request_element)
        
        print(f"[ONVIF] Unhandled action: {action}")
        return None
    
    def wrap_soap_response(self, content):
        """Wrap content in SOAP envelope."""
        return f'''<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" 
               xmlns:tds="http://www.onvif.org/ver10/device/wsdl"
               xmlns:trt="http://www.onvif.org/ver10/media/wsdl"
               xmlns:tt="http://www.onvif.org/ver10/schema">
    <soap:Body>
        {content}
    </soap:Body>
</soap:Envelope>'''
    
    def send_soap_fault(self, reason, code="soap:Receiver"):
        """Send SOAP fault response."""
        fault = f'''<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
    <soap:Body>
        <soap:Fault>
            <soap:Code>
                <soap:Value>{code}</soap:Value>
            </soap:Code>
            <soap:Reason>
                <soap:Text xml:lang="en">{reason}</soap:Text>
            </soap:Reason>
        </soap:Fault>
    </soap:Body>
</soap:Envelope>'''
        
        self.send_response(500)
        self.send_header('Content-Type', 'application/soap+xml; charset=utf-8')
        self.end_headers()
        self.wfile.write(fault.encode('utf-8'))
    
    # ========================================================================
    # Device Service Handlers
    # ========================================================================
    
    def get_system_date_time(self, request):
        """Handle GetSystemDateAndTime request."""
        now = datetime.now(timezone.utc)
        content = f'''<tds:GetSystemDateAndTimeResponse>
            <tds:SystemDateAndTime>
                <tt:DateTimeType>NTP</tt:DateTimeType>
                <tt:DaylightSavings>false</tt:DaylightSavings>
                <tt:TimeZone>
                    <tt:TZ>UTC0</tt:TZ>
                </tt:TimeZone>
                <tt:UTCDateTime>
                    <tt:Time>
                        <tt:Hour>{now.hour}</tt:Hour>
                        <tt:Minute>{now.minute}</tt:Minute>
                        <tt:Second>{now.second}</tt:Second>
                    </tt:Time>
                    <tt:Date>
                        <tt:Year>{now.year}</tt:Year>
                        <tt:Month>{now.month}</tt:Month>
                        <tt:Day>{now.day}</tt:Day>
                    </tt:Date>
                </tt:UTCDateTime>
            </tds:SystemDateAndTime>
        </tds:GetSystemDateAndTimeResponse>'''
        return self.wrap_soap_response(content)
    
    def get_device_information(self, request):
        """Handle GetDeviceInformation request."""
        content = f'''<tds:GetDeviceInformationResponse>
            <tds:Manufacturer>RTSP-Full</tds:Manufacturer>
            <tds:Model>RPI-CAM</tds:Model>
            <tds:FirmwareVersion>2.5.0</tds:FirmwareVersion>
            <tds:SerialNumber>{self.config.name}</tds:SerialNumber>
            <tds:HardwareId>Raspberry-Pi</tds:HardwareId>
        </tds:GetDeviceInformationResponse>'''
        return self.wrap_soap_response(content)
    
    def get_capabilities(self, request):
        """Handle GetCapabilities request."""
        ip = self.config.get_local_ip()
        port = self.config.port
        
        content = f'''<tds:GetCapabilitiesResponse>
            <tds:Capabilities>
                <tt:Device>
                    <tt:XAddr>http://{ip}:{port}/onvif/device_service</tt:XAddr>
                </tt:Device>
                <tt:Media>
                    <tt:XAddr>http://{ip}:{port}/onvif/media_service</tt:XAddr>
                    <tt:StreamingCapabilities>
                        <tt:RTPMulticast>false</tt:RTPMulticast>
                        <tt:RTP_TCP>true</tt:RTP_TCP>
                        <tt:RTP_RTSP_TCP>true</tt:RTP_RTSP_TCP>
                    </tt:StreamingCapabilities>
                </tt:Media>
            </tds:Capabilities>
        </tds:GetCapabilitiesResponse>'''
        return self.wrap_soap_response(content)
    
    def get_services(self, request):
        """Handle GetServices request."""
        ip = self.config.get_local_ip()
        port = self.config.port
        
        content = f'''<tds:GetServicesResponse>
            <tds:Service>
                <tds:Namespace>http://www.onvif.org/ver10/device/wsdl</tds:Namespace>
                <tds:XAddr>http://{ip}:{port}/onvif/device_service</tds:XAddr>
                <tds:Version>
                    <tt:Major>2</tt:Major>
                    <tt:Minor>0</tt:Minor>
                </tds:Version>
            </tds:Service>
            <tds:Service>
                <tds:Namespace>http://www.onvif.org/ver10/media/wsdl</tds:Namespace>
                <tds:XAddr>http://{ip}:{port}/onvif/media_service</tds:XAddr>
                <tds:Version>
                    <tt:Major>2</tt:Major>
                    <tt:Minor>0</tt:Minor>
                </tds:Version>
            </tds:Service>
        </tds:GetServicesResponse>'''
        return self.wrap_soap_response(content)
    
    def get_scopes(self, request):
        """Handle GetScopes request."""
        scope_name = self.config.get_scope_safe_name()
        scope_serial = scope_name
        scope_hardware = quote('RaspberryPi', safe='')
        content = f'''<tds:GetScopesResponse>
            <tds:Scopes>
                <tt:ScopeDef>Fixed</tt:ScopeDef>
                <tt:ScopeItem>onvif://www.onvif.org/type/video_encoder</tt:ScopeItem>
            </tds:Scopes>
            <tds:Scopes>
                <tt:ScopeDef>Fixed</tt:ScopeDef>
                <tt:ScopeItem>onvif://www.onvif.org/Profile/Streaming</tt:ScopeItem>
            </tds:Scopes>
            <tds:Scopes>
                <tt:ScopeDef>Configurable</tt:ScopeDef>
                <tt:ScopeItem>onvif://www.onvif.org/name/{scope_name}</tt:ScopeItem>
            </tds:Scopes>
            <tds:Scopes>
                <tt:ScopeDef>Configurable</tt:ScopeDef>
                <tt:ScopeItem>onvif://www.onvif.org/serial/{scope_serial}</tt:ScopeItem>
            </tds:Scopes>
            <tds:Scopes>
                <tt:ScopeDef>Configurable</tt:ScopeDef>
                <tt:ScopeItem>onvif://www.onvif.org/hardware/{scope_hardware}</tt:ScopeItem>
            </tds:Scopes>
            <tds:Scopes>
                <tt:ScopeDef>Configurable</tt:ScopeDef>
                <tt:ScopeItem>onvif://www.onvif.org/location/</tt:ScopeItem>
            </tds:Scopes>
        </tds:GetScopesResponse>'''
        return self.wrap_soap_response(content)
    
    def get_hostname(self, request):
        """Handle GetHostname request."""
        hostname = (self.config.name or '').strip() or socket.gethostname()
        content = f'''<tds:GetHostnameResponse>
            <tds:HostnameInformation>
                <tt:FromDHCP>false</tt:FromDHCP>
                <tt:Name>{hostname}</tt:Name>
            </tds:HostnameInformation>
        </tds:GetHostnameResponse>'''
        return self.wrap_soap_response(content)
    
    def get_network_interfaces(self, request):
        """Handle GetNetworkInterfaces request."""
        ip = self.config.get_local_ip()
        content = f'''<tds:GetNetworkInterfacesResponse>
            <tds:NetworkInterfaces token="eth0">
                <tt:Enabled>true</tt:Enabled>
                <tt:IPv4>
                    <tt:Enabled>true</tt:Enabled>
                    <tt:Config>
                        <tt:Manual>
                            <tt:Address>{ip}</tt:Address>
                            <tt:PrefixLength>24</tt:PrefixLength>
                        </tt:Manual>
                        <tt:DHCP>false</tt:DHCP>
                    </tt:Config>
                </tt:IPv4>
            </tds:NetworkInterfaces>
        </tds:GetNetworkInterfacesResponse>'''
        return self.wrap_soap_response(content)
    
    # ========================================================================
    # Media Service Handlers
    # ========================================================================
    
    def get_profiles(self, request):
        """Handle GetProfiles request."""
        # Reload video settings to get latest values
        self.config.load_video_settings()
        w = self.config.video_width
        h = self.config.video_height
        fps = self.config.video_fps
        bitrate = self.config.video_bitrate
        
        content = f'''<trt:GetProfilesResponse>
            <trt:Profiles token="MainProfile" fixed="true">
                <tt:Name>MainProfile</tt:Name>
                <tt:VideoSourceConfiguration token="VideoSourceConfig">
                    <tt:Name>VideoSourceConfig</tt:Name>
                    <tt:UseCount>1</tt:UseCount>
                    <tt:SourceToken>VideoSource</tt:SourceToken>
                    <tt:Bounds x="0" y="0" width="{w}" height="{h}"/>
                </tt:VideoSourceConfiguration>
                <tt:VideoEncoderConfiguration token="VideoEncoderConfig">
                    <tt:Name>VideoEncoderConfig</tt:Name>
                    <tt:UseCount>1</tt:UseCount>
                    <tt:Encoding>H264</tt:Encoding>
                    <tt:Resolution>
                        <tt:Width>{w}</tt:Width>
                        <tt:Height>{h}</tt:Height>
                    </tt:Resolution>
                    <tt:Quality>5</tt:Quality>
                    <tt:RateControl>
                        <tt:FrameRateLimit>{fps}</tt:FrameRateLimit>
                        <tt:EncodingInterval>1</tt:EncodingInterval>
                        <tt:BitrateLimit>{bitrate}</tt:BitrateLimit>
                        <tt:ConstantBitRate>true</tt:ConstantBitRate>
                    </tt:RateControl>
                    <tt:H264>
                        <tt:GovLength>{fps}</tt:GovLength>
                        <tt:H264Profile>Main</tt:H264Profile>
                    </tt:H264>
                    <tt:Multicast>
                        <tt:Address>
                            <tt:Type>IPv4</tt:Type>
                            <tt:IPv4Address>0.0.0.0</tt:IPv4Address>
                        </tt:Address>
                        <tt:Port>0</tt:Port>
                        <tt:TTL>0</tt:TTL>
                        <tt:AutoStart>false</tt:AutoStart>
                    </tt:Multicast>
                    <tt:SessionTimeout>PT60S</tt:SessionTimeout>
                </tt:VideoEncoderConfiguration>
            </trt:Profiles>
        </trt:GetProfilesResponse>'''
        return self.wrap_soap_response(content)
    
    def get_profile(self, request):
        """Handle GetProfile request."""
        # Same as GetProfiles but for single profile
        return self.get_profiles(request)
    
    def get_stream_uri(self, request):
        """Handle GetStreamUri request."""
        # Get client IP to return appropriate local IP
        client_ip = self.client_address[0] if hasattr(self, 'client_address') else None
        ip = self.config.get_local_ip(client_ip)
        
        # Include credentials in RTSP URL if authentication is configured
        # This allows NVR/VMS like Synology to connect with proper auth
        if self.config.username and self.config.password:
            from urllib.parse import quote
            # URL-encode credentials to handle special characters
            user = quote(self.config.username, safe='')
            passwd = quote(self.config.password, safe='')
            rtsp_url = f"rtsp://{user}:{passwd}@{ip}:{self.config.rtsp_port}{self.config.rtsp_path}"
        else:
            rtsp_url = f"rtsp://{ip}:{self.config.rtsp_port}{self.config.rtsp_path}"
        
        content = f'''<trt:GetStreamUriResponse>
            <trt:MediaUri>
                <tt:Uri>{rtsp_url}</tt:Uri>
                <tt:InvalidAfterConnect>false</tt:InvalidAfterConnect>
                <tt:InvalidAfterReboot>false</tt:InvalidAfterReboot>
                <tt:Timeout>PT60S</tt:Timeout>
            </trt:MediaUri>
        </trt:GetStreamUriResponse>'''
        return self.wrap_soap_response(content)
    
    def get_video_sources(self, request):
        """Handle GetVideoSources request."""
        self.config.load_video_settings()
        w = self.config.video_width
        h = self.config.video_height
        fps = self.config.video_fps
        
        content = f'''<trt:GetVideoSourcesResponse>
            <trt:VideoSources token="VideoSource">
                <tt:Framerate>{fps}</tt:Framerate>
                <tt:Resolution>
                    <tt:Width>{w}</tt:Width>
                    <tt:Height>{h}</tt:Height>
                </tt:Resolution>
            </trt:VideoSources>
        </trt:GetVideoSourcesResponse>'''
        return self.wrap_soap_response(content)
    
    def get_video_source_configurations(self, request):
        """Handle GetVideoSourceConfigurations request."""
        self.config.load_video_settings()
        w = self.config.video_width
        h = self.config.video_height
        
        content = f'''<trt:GetVideoSourceConfigurationsResponse>
            <trt:Configurations token="VideoSourceConfig">
                <tt:Name>VideoSourceConfig</tt:Name>
                <tt:UseCount>1</tt:UseCount>
                <tt:SourceToken>VideoSource</tt:SourceToken>
                <tt:Bounds x="0" y="0" width="{w}" height="{h}"/>
            </trt:Configurations>
        </trt:GetVideoSourceConfigurationsResponse>'''
        return self.wrap_soap_response(content)
    
    def get_video_encoder_configurations(self, request):
        """Handle GetVideoEncoderConfigurations request."""
        self.config.load_video_settings()
        w = self.config.video_width
        h = self.config.video_height
        fps = self.config.video_fps
        bitrate = self.config.video_bitrate
        
        content = f'''<trt:GetVideoEncoderConfigurationsResponse>
            <trt:Configurations token="VideoEncoderConfig">
                <tt:Name>VideoEncoderConfig</tt:Name>
                <tt:UseCount>1</tt:UseCount>
                <tt:Encoding>H264</tt:Encoding>
                <tt:Resolution>
                    <tt:Width>{w}</tt:Width>
                    <tt:Height>{h}</tt:Height>
                </tt:Resolution>
                <tt:Quality>5</tt:Quality>
                <tt:RateControl>
                    <tt:FrameRateLimit>{fps}</tt:FrameRateLimit>
                    <tt:EncodingInterval>1</tt:EncodingInterval>
                    <tt:BitrateLimit>{bitrate}</tt:BitrateLimit>
                    <tt:ConstantBitRate>true</tt:ConstantBitRate>
                </tt:RateControl>
                <tt:H264>
                    <tt:GovLength>{fps}</tt:GovLength>
                    <tt:H264Profile>Main</tt:H264Profile>
                </tt:H264>
                <tt:Multicast>
                    <tt:Address>
                        <tt:Type>IPv4</tt:Type>
                        <tt:IPv4Address>0.0.0.0</tt:IPv4Address>
                    </tt:Address>
                    <tt:Port>0</tt:Port>
                    <tt:TTL>0</tt:TTL>
                    <tt:AutoStart>false</tt:AutoStart>
                </tt:Multicast>
                <tt:SessionTimeout>PT60S</tt:SessionTimeout>
            </trt:Configurations>
        </trt:GetVideoEncoderConfigurationsResponse>'''
        return self.wrap_soap_response(content)
    
    def get_video_encoder_configuration(self, request):
        """Handle GetVideoEncoderConfiguration request (single config)."""
        self.config.load_video_settings()
        w = self.config.video_width
        h = self.config.video_height
        fps = self.config.video_fps
        bitrate = self.config.video_bitrate
        
        content = f'''<trt:GetVideoEncoderConfigurationResponse>
            <trt:Configuration token="VideoEncoderConfig">
                <tt:Name>VideoEncoderConfig</tt:Name>
                <tt:UseCount>1</tt:UseCount>
                <tt:Encoding>H264</tt:Encoding>
                <tt:Resolution>
                    <tt:Width>{w}</tt:Width>
                    <tt:Height>{h}</tt:Height>
                </tt:Resolution>
                <tt:Quality>5</tt:Quality>
                <tt:RateControl>
                    <tt:FrameRateLimit>{fps}</tt:FrameRateLimit>
                    <tt:EncodingInterval>1</tt:EncodingInterval>
                    <tt:BitrateLimit>{bitrate}</tt:BitrateLimit>
                    <tt:ConstantBitRate>true</tt:ConstantBitRate>
                </tt:RateControl>
                <tt:H264>
                    <tt:GovLength>{fps}</tt:GovLength>
                    <tt:H264Profile>Main</tt:H264Profile>
                </tt:H264>
                <tt:Multicast>
                    <tt:Address>
                        <tt:Type>IPv4</tt:Type>
                        <tt:IPv4Address>0.0.0.0</tt:IPv4Address>
                    </tt:Address>
                    <tt:Port>0</tt:Port>
                    <tt:TTL>0</tt:TTL>
                    <tt:AutoStart>false</tt:AutoStart>
                </tt:Multicast>
                <tt:SessionTimeout>PT60S</tt:SessionTimeout>
            </trt:Configuration>
        </trt:GetVideoEncoderConfigurationResponse>'''
        return self.wrap_soap_response(content)
    
    def set_video_encoder_configuration(self, request):
        """Handle SetVideoEncoderConfiguration request - acknowledge."""
        content = '''<trt:SetVideoEncoderConfigurationResponse>
        </trt:SetVideoEncoderConfigurationResponse>'''
        return self.wrap_soap_response(content)
    
    def get_snapshot_uri(self, request):
        """Handle GetSnapshotUri request."""
        ip = self.config.get_local_ip()
        
        content = f'''<trt:GetSnapshotUriResponse>
            <trt:MediaUri>
                <tt:Uri>http://{ip}:5000/api/camera/snapshot</tt:Uri>
                <tt:InvalidAfterConnect>false</tt:InvalidAfterConnect>
                <tt:InvalidAfterReboot>false</tt:InvalidAfterReboot>
                <tt:Timeout>PT60S</tt:Timeout>
            </trt:MediaUri>
        </trt:GetSnapshotUriResponse>'''
        return self.wrap_soap_response(content)
    
    def get_video_encoder_configuration_options(self, request):
        """Handle GetVideoEncoderConfigurationOptions request.
        
        Returns supported resolutions, framerates, and bitrate options.
        Surveillance Station uses this to populate the camera settings UI.
        """
        # Read current config for reasonable defaults
        self.config.load_video_settings()
        current_bitrate = self.config.video_bitrate
        
        content = f'''<trt:GetVideoEncoderConfigurationOptionsResponse>
            <trt:Options>
                <tt:QualityRange>
                    <tt:Min>1</tt:Min>
                    <tt:Max>10</tt:Max>
                </tt:QualityRange>
                <tt:H264>
                    <tt:ResolutionsAvailable>
                        <tt:Width>1920</tt:Width>
                        <tt:Height>1080</tt:Height>
                    </tt:ResolutionsAvailable>
                    <tt:ResolutionsAvailable>
                        <tt:Width>1280</tt:Width>
                        <tt:Height>720</tt:Height>
                    </tt:ResolutionsAvailable>
                    <tt:ResolutionsAvailable>
                        <tt:Width>800</tt:Width>
                        <tt:Height>600</tt:Height>
                    </tt:ResolutionsAvailable>
                    <tt:ResolutionsAvailable>
                        <tt:Width>640</tt:Width>
                        <tt:Height>480</tt:Height>
                    </tt:ResolutionsAvailable>
                    <tt:ResolutionsAvailable>
                        <tt:Width>320</tt:Width>
                        <tt:Height>240</tt:Height>
                    </tt:ResolutionsAvailable>
                    <tt:GovLengthRange>
                        <tt:Min>1</tt:Min>
                        <tt:Max>60</tt:Max>
                    </tt:GovLengthRange>
                    <tt:FrameRateRange>
                        <tt:Min>1</tt:Min>
                        <tt:Max>30</tt:Max>
                    </tt:FrameRateRange>
                    <tt:EncodingIntervalRange>
                        <tt:Min>1</tt:Min>
                        <tt:Max>4</tt:Max>
                    </tt:EncodingIntervalRange>
                    <tt:BitrateRange>
                        <tt:Min>128</tt:Min>
                        <tt:Max>8000</tt:Max>
                    </tt:BitrateRange>
                    <tt:ConstantBitRate>true</tt:ConstantBitRate>
                    <tt:H264ProfilesSupported>Main</tt:H264ProfilesSupported>
                    <tt:H264ProfilesSupported>Baseline</tt:H264ProfilesSupported>
                    <tt:H264ProfilesSupported>High</tt:H264ProfilesSupported>
                </tt:H264>
            </trt:Options>
        </trt:GetVideoEncoderConfigurationOptionsResponse>'''
        return self.wrap_soap_response(content)
    
    def get_guaranteed_encoder_instances(self, request):
        """Handle GetGuaranteedNumberOfVideoEncoderInstances request."""
        content = '''<trt:GetGuaranteedNumberOfVideoEncoderInstancesResponse>
            <trt:TotalNumber>1</trt:TotalNumber>
            <trt:H264>1</trt:H264>
        </trt:GetGuaranteedNumberOfVideoEncoderInstancesResponse>'''
        return self.wrap_soap_response(content)
    
    def get_audio_sources(self, request):
        """Handle GetAudioSources request."""
        content = '''<trt:GetAudioSourcesResponse>
            <trt:AudioSources token="AudioSource">
                <tt:Channels>1</tt:Channels>
            </trt:AudioSources>
        </trt:GetAudioSourcesResponse>'''
        return self.wrap_soap_response(content)
    
    def get_audio_source_configurations(self, request):
        """Handle GetAudioSourceConfigurations request."""
        content = '''<trt:GetAudioSourceConfigurationsResponse>
            <trt:Configurations token="AudioSourceConfig">
                <tt:Name>AudioSourceConfig</tt:Name>
                <tt:UseCount>1</tt:UseCount>
                <tt:SourceToken>AudioSource</tt:SourceToken>
            </trt:Configurations>
        </trt:GetAudioSourceConfigurationsResponse>'''
        return self.wrap_soap_response(content)
    
    def get_audio_encoder_configurations(self, request):
        """Handle GetAudioEncoderConfigurations request."""
        content = '''<trt:GetAudioEncoderConfigurationsResponse>
            <trt:Configurations token="AudioEncoderConfig">
                <tt:Name>AudioEncoderConfig</tt:Name>
                <tt:UseCount>1</tt:UseCount>
                <tt:Encoding>AAC</tt:Encoding>
                <tt:Bitrate>64</tt:Bitrate>
                <tt:SampleRate>44100</tt:SampleRate>
                <tt:Multicast>
                    <tt:Address>
                        <tt:Type>IPv4</tt:Type>
                        <tt:IPv4Address>0.0.0.0</tt:IPv4Address>
                    </tt:Address>
                    <tt:Port>0</tt:Port>
                    <tt:TTL>0</tt:TTL>
                    <tt:AutoStart>false</tt:AutoStart>
                </tt:Multicast>
                <tt:SessionTimeout>PT60S</tt:SessionTimeout>
            </trt:Configurations>
        </trt:GetAudioEncoderConfigurationsResponse>'''
        return self.wrap_soap_response(content)
    
    def get_audio_encoder_configuration_options(self, request):
        """Handle GetAudioEncoderConfigurationOptions request."""
        content = '''<trt:GetAudioEncoderConfigurationOptionsResponse>
            <trt:Options>
                <tt:Options>
                    <tt:Encoding>AAC</tt:Encoding>
                    <tt:BitrateList>
                        <tt:Items>64</tt:Items>
                        <tt:Items>128</tt:Items>
                    </tt:BitrateList>
                    <tt:SampleRateList>
                        <tt:Items>44100</tt:Items>
                        <tt:Items>48000</tt:Items>
                    </tt:SampleRateList>
                </tt:Options>
            </trt:Options>
        </trt:GetAudioEncoderConfigurationOptionsResponse>'''
        return self.wrap_soap_response(content)
    
    def get_video_source_configuration_options(self, request):
        """Handle GetVideoSourceConfigurationOptions request."""
        content = '''<trt:GetVideoSourceConfigurationOptionsResponse>
            <trt:Options>
                <tt:BoundsRange>
                    <tt:XRange>
                        <tt:Min>0</tt:Min>
                        <tt:Max>1920</tt:Max>
                    </tt:XRange>
                    <tt:YRange>
                        <tt:Min>0</tt:Min>
                        <tt:Max>1080</tt:Max>
                    </tt:YRange>
                    <tt:WidthRange>
                        <tt:Min>160</tt:Min>
                        <tt:Max>1920</tt:Max>
                    </tt:WidthRange>
                    <tt:HeightRange>
                        <tt:Min>120</tt:Min>
                        <tt:Max>1080</tt:Max>
                    </tt:HeightRange>
                </tt:BoundsRange>
                <tt:VideoSourceTokensAvailable>VideoSource</tt:VideoSourceTokensAvailable>
            </trt:Options>
        </trt:GetVideoSourceConfigurationOptionsResponse>'''
        return self.wrap_soap_response(content)
    
    def get_service_capabilities(self, request):
        """Handle GetServiceCapabilities request (Media Service)."""
        content = '''<trt:GetServiceCapabilitiesResponse>
            <trt:Capabilities>
                <trt:ProfileCapabilities MaximumNumberOfProfiles="2"/>
                <trt:StreamingCapabilities RTPMulticast="false" RTP_TCP="true" RTP_RTSP_TCP="true"/>
                <trt:SnapshotUri>true</trt:SnapshotUri>
            </trt:Capabilities>
        </trt:GetServiceCapabilitiesResponse>'''
        return self.wrap_soap_response(content)
    
    def get_relay_outputs(self, request):
        """Handle GetRelayOutputs request - no relay outputs."""
        content = '''<tds:GetRelayOutputsResponse>
        </tds:GetRelayOutputsResponse>'''
        return self.wrap_soap_response(content)
    
    def get_ntp(self, request):
        """Handle GetNTP request."""
        content = '''<tds:GetNTPResponse>
            <tds:NTPInformation>
                <tt:FromDHCP>true</tt:FromDHCP>
            </tds:NTPInformation>
        </tds:GetNTPResponse>'''
        return self.wrap_soap_response(content)
    
    def create_profile(self, request):
        """Handle CreateProfile request - return the main profile."""
        # We don't actually create new profiles, just return our existing one
        self.config.load_video_settings()
        w = self.config.video_width
        h = self.config.video_height
        fps = self.config.video_fps
        bitrate = self.config.video_bitrate
        
        content = f'''<trt:CreateProfileResponse>
            <trt:Profile token="MainProfile" fixed="true">
                <tt:Name>MainProfile</tt:Name>
                <tt:VideoSourceConfiguration token="VideoSourceConfig">
                    <tt:Name>VideoSourceConfig</tt:Name>
                    <tt:UseCount>1</tt:UseCount>
                    <tt:SourceToken>VideoSource</tt:SourceToken>
                    <tt:Bounds x="0" y="0" width="{w}" height="{h}"/>
                </tt:VideoSourceConfiguration>
                <tt:VideoEncoderConfiguration token="VideoEncoderConfig">
                    <tt:Name>VideoEncoderConfig</tt:Name>
                    <tt:UseCount>1</tt:UseCount>
                    <tt:Encoding>H264</tt:Encoding>
                    <tt:Resolution>
                        <tt:Width>{w}</tt:Width>
                        <tt:Height>{h}</tt:Height>
                    </tt:Resolution>
                    <tt:Quality>5</tt:Quality>
                    <tt:RateControl>
                        <tt:FrameRateLimit>{fps}</tt:FrameRateLimit>
                        <tt:EncodingInterval>1</tt:EncodingInterval>
                        <tt:BitrateLimit>{bitrate}</tt:BitrateLimit>
                    </tt:RateControl>
                    <tt:H264>
                        <tt:GovLength>{fps}</tt:GovLength>
                        <tt:H264Profile>Main</tt:H264Profile>
                    </tt:H264>
                    <tt:Multicast>
                        <tt:Address>
                            <tt:Type>IPv4</tt:Type>
                            <tt:IPv4Address>0.0.0.0</tt:IPv4Address>
                        </tt:Address>
                        <tt:Port>0</tt:Port>
                        <tt:TTL>0</tt:TTL>
                        <tt:AutoStart>false</tt:AutoStart>
                    </tt:Multicast>
                    <tt:SessionTimeout>PT60S</tt:SessionTimeout>
                </tt:VideoEncoderConfiguration>
            </trt:Profile>
        </trt:CreateProfileResponse>'''
        return self.wrap_soap_response(content)
    
    def set_ntp(self, request):
        """Handle SetNTP request - acknowledge but don't actually change NTP."""
        content = '''<tds:SetNTPResponse>
        </tds:SetNTPResponse>'''
        return self.wrap_soap_response(content)
    
    def delete_profile(self, request):
        """Handle DeleteProfile request - acknowledge but don't actually delete."""
        content = '''<trt:DeleteProfileResponse>
        </trt:DeleteProfileResponse>'''
        return self.wrap_soap_response(content)
    
    def add_video_source_configuration(self, request):
        """Handle AddVideoSourceConfiguration request - acknowledge."""
        content = '''<trt:AddVideoSourceConfigurationResponse>
        </trt:AddVideoSourceConfigurationResponse>'''
        return self.wrap_soap_response(content)
    
    def add_video_encoder_configuration(self, request):
        """Handle AddVideoEncoderConfiguration request - acknowledge."""
        content = '''<trt:AddVideoEncoderConfigurationResponse>
        </trt:AddVideoEncoderConfigurationResponse>'''
        return self.wrap_soap_response(content)
    
    def add_audio_source_configuration(self, request):
        """Handle AddAudioSourceConfiguration request - acknowledge."""
        content = '''<trt:AddAudioSourceConfigurationResponse>
        </trt:AddAudioSourceConfigurationResponse>'''
        return self.wrap_soap_response(content)
    
    def add_audio_encoder_configuration(self, request):
        """Handle AddAudioEncoderConfiguration request - acknowledge."""
        content = '''<trt:AddAudioEncoderConfigurationResponse>
        </trt:AddAudioEncoderConfigurationResponse>'''
        return self.wrap_soap_response(content)
    
    def get_compatible_audio_source_configurations(self, request):
        """Handle GetCompatibleAudioSourceConfigurations request."""
        content = '''<trt:GetCompatibleAudioSourceConfigurationsResponse>
            <trt:Configurations token="AudioSourceConfig">
                <tt:Name>AudioSourceConfig</tt:Name>
                <tt:UseCount>1</tt:UseCount>
                <tt:SourceToken>AudioSource</tt:SourceToken>
            </trt:Configurations>
        </trt:GetCompatibleAudioSourceConfigurationsResponse>'''
        return self.wrap_soap_response(content)
    
    def get_compatible_video_source_configurations(self, request):
        """Handle GetCompatibleVideoSourceConfigurations request."""
        self.config.load_video_settings()
        w = self.config.video_width
        h = self.config.video_height
        
        content = f'''<trt:GetCompatibleVideoSourceConfigurationsResponse>
            <trt:Configurations token="VideoSourceConfig">
                <tt:Name>VideoSourceConfig</tt:Name>
                <tt:UseCount>1</tt:UseCount>
                <tt:SourceToken>VideoSource</tt:SourceToken>
                <tt:Bounds x="0" y="0" width="{w}" height="{h}"/>
            </trt:Configurations>
        </trt:GetCompatibleVideoSourceConfigurationsResponse>'''
        return self.wrap_soap_response(content)
    
    def get_compatible_video_encoder_configurations(self, request):
        """Handle GetCompatibleVideoEncoderConfigurations request."""
        self.config.load_video_settings()
        w = self.config.video_width
        h = self.config.video_height
        fps = self.config.video_fps
        bitrate = self.config.video_bitrate
        
        content = f'''<trt:GetCompatibleVideoEncoderConfigurationsResponse>
            <trt:Configurations token="VideoEncoderConfig">
                <tt:Name>VideoEncoderConfig</tt:Name>
                <tt:UseCount>1</tt:UseCount>
                <tt:Encoding>H264</tt:Encoding>
                <tt:Resolution>
                    <tt:Width>{w}</tt:Width>
                    <tt:Height>{h}</tt:Height>
                </tt:Resolution>
                <tt:Quality>5</tt:Quality>
                <tt:RateControl>
                    <tt:FrameRateLimit>{fps}</tt:FrameRateLimit>
                    <tt:EncodingInterval>1</tt:EncodingInterval>
                    <tt:BitrateLimit>{bitrate}</tt:BitrateLimit>
                </tt:RateControl>
                <tt:H264>
                    <tt:GovLength>{fps}</tt:GovLength>
                    <tt:H264Profile>Main</tt:H264Profile>
                </tt:H264>
                <tt:Multicast>
                    <tt:Address>
                        <tt:Type>IPv4</tt:Type>
                        <tt:IPv4Address>0.0.0.0</tt:IPv4Address>
                    </tt:Address>
                    <tt:Port>0</tt:Port>
                    <tt:TTL>0</tt:TTL>
                    <tt:AutoStart>false</tt:AutoStart>
                </tt:Multicast>
                <tt:SessionTimeout>PT60S</tt:SessionTimeout>
            </trt:Configurations>
        </trt:GetCompatibleVideoEncoderConfigurationsResponse>'''
        return self.wrap_soap_response(content)
    
    def get_compatible_audio_encoder_configurations(self, request):
        """Handle GetCompatibleAudioEncoderConfigurations request."""
        content = '''<trt:GetCompatibleAudioEncoderConfigurationsResponse>
            <trt:Configurations token="AudioEncoderConfig">
                <tt:Name>AudioEncoderConfig</tt:Name>
                <tt:UseCount>1</tt:UseCount>
                <tt:Encoding>AAC</tt:Encoding>
                <tt:Bitrate>64</tt:Bitrate>
                <tt:SampleRate>44100</tt:SampleRate>
                <tt:Multicast>
                    <tt:Address>
                        <tt:Type>IPv4</tt:Type>
                        <tt:IPv4Address>0.0.0.0</tt:IPv4Address>
                    </tt:Address>
                    <tt:Port>0</tt:Port>
                    <tt:TTL>0</tt:TTL>
                    <tt:AutoStart>false</tt:AutoStart>
                </tt:Multicast>
                <tt:SessionTimeout>PT60S</tt:SessionTimeout>
            </trt:Configurations>
        </trt:GetCompatibleAudioEncoderConfigurationsResponse>'''
        return self.wrap_soap_response(content)


class WSDDiscovery:
    """WS-Discovery responder for ONVIF discovery."""
    
    MULTICAST_GROUP = '239.255.255.250'
    MULTICAST_PORT = 3702
    
    def __init__(self, config):
        self.config = config
        self.running = False
        self.sock = None
        self.thread = None
        # Generate a fixed UUID for this device (based on MAC address)
        self.device_uuid = self._generate_device_uuid()
    
    def _generate_device_uuid(self):
        """Generate a consistent UUID for this device based on MAC address."""
        mac = self._get_mac_address()
        if mac:
            # Create UUID from MAC address (version 1 style but deterministic)
            mac_hex = mac.replace(':', '')
            return f"{mac_hex[:8]}-{mac_hex[8:12]}-1000-8000-{mac_hex}"
        else:
            # Fallback to random but save it
            return f"{secrets.token_hex(4)}-{secrets.token_hex(2)}-1000-8000-{secrets.token_hex(6)}"
    
    def _get_mac_address(self):
        """Get MAC address of the primary network interface."""
        try:
            # Try to get MAC from /sys/class/net
            for iface in ['eth0', 'wlan0', 'wlan1', 'enp0s3']:
                mac_file = f'/sys/class/net/{iface}/address'
                if os.path.exists(mac_file):
                    with open(mac_file, 'r') as f:
                        mac = f.read().strip()
                        if mac and mac != '00:00:00:00:00:00':
                            return mac.upper()
        except:
            pass
        return None
    
    def start(self):
        """Start WS-Discovery responder."""
        self.running = True
        self.thread = threading.Thread(target=self._listen, daemon=True)
        self.thread.start()
        print(f"[WS-Discovery] Listening on {self.MULTICAST_GROUP}:{self.MULTICAST_PORT}")
        print(f"[WS-Discovery] Device UUID: {self.device_uuid}")
    
    def stop(self):
        """Stop WS-Discovery responder."""
        self.running = False
        if self.sock:
            self.sock.close()
    
    def _listen(self):
        """Listen for WS-Discovery probes."""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Bind to the multicast port
            self.sock.bind(('', self.MULTICAST_PORT))
            
            # Join multicast group
            mreq = struct.pack('4sL', socket.inet_aton(self.MULTICAST_GROUP), socket.INADDR_ANY)
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            
            while self.running:
                try:
                    self.sock.settimeout(1.0)
                    data, addr = self.sock.recvfrom(65535)
                    self._handle_probe(data, addr)
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        print(f"[WS-Discovery] Error: {e}")
        except Exception as e:
            print(f"[WS-Discovery] Failed to start: {e}")
    
    def _handle_probe(self, data, addr):
        """Handle WS-Discovery probe message."""
        try:
            # Parse probe
            root = ET.fromstring(data)
            
            # Check if it's a Probe message
            probe = root.find('.//{http://schemas.xmlsoap.org/ws/2005/04/discovery}Probe')
            if probe is None:
                return
            
            # Extract MessageID from the request for RelatesTo
            message_id = root.findtext('.//{http://schemas.xmlsoap.org/ws/2004/08/addressing}MessageID', '')
            
            # Check for ONVIF device types
            types = probe.findtext('.//{http://schemas.xmlsoap.org/ws/2005/04/discovery}Types', '')
            
            # Respond to network video transmitter or device probes
            if 'NetworkVideoTransmitter' in types or 'Device' in types or not types:
                self._send_probe_match(addr, message_id)
                
        except Exception as e:
            print(f"[WS-Discovery] Probe parse error: {e}")
    
    def _send_probe_match(self, addr, relates_to=''):
        """Send ProbeMatch response."""
        # Get IP that can reach the requesting client
        client_ip = addr[0]
        ip = self._get_ip_for_client(client_ip)
        port = self.config.port
        mac = self._get_mac_address() or '00:00:00:00:00:00'
        
        # Use fixed device UUID
        device_uuid = self.device_uuid
        # Generate unique message ID for this response
        msg_uuid = f"{secrets.token_hex(4)}-{secrets.token_hex(2)}-{secrets.token_hex(2)}-{secrets.token_hex(2)}-{secrets.token_hex(6)}"
        
        # If no relates_to provided, use wildcard
        if not relates_to:
            relates_to = 'urn:uuid:*'
        
        print(f"[WS-Discovery] Responding with IP {ip} for client {client_ip}")
        
        # Scopes without extra whitespace
        scope_name = self.config.get_scope_safe_name()
        scope_serial = scope_name
        scope_hardware = quote('RaspberryPi', safe='')
        scopes = f"onvif://www.onvif.org/type/video_encoder onvif://www.onvif.org/Profile/Streaming onvif://www.onvif.org/name/{scope_name} onvif://www.onvif.org/serial/{scope_serial} onvif://www.onvif.org/hardware/{scope_hardware} onvif://www.onvif.org/location/"
        
        # Instance ID based on boot time (stays same while running)
        import time
        instance_id = int(time.time()) % 1000000
        
        # Use the exact format that Synology expects - match their namespace style
        # Include AppSequence which some clients require
        response = f'''<?xml version="1.0" encoding="utf-8"?>
<Envelope xmlns="http://www.w3.org/2003/05/soap-envelope" xmlns:dn="http://www.onvif.org/ver10/network/wsdl" xmlns:tds="http://www.onvif.org/ver10/device/wsdl">
<Header>
<wsa:MessageID xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing">uuid:{msg_uuid}</wsa:MessageID>
<wsa:RelatesTo xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing">{relates_to}</wsa:RelatesTo>
<wsa:To xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing">http://schemas.xmlsoap.org/ws/2004/08/addressing/role/anonymous</wsa:To>
<wsa:Action xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing">http://schemas.xmlsoap.org/ws/2005/04/discovery/ProbeMatches</wsa:Action>
<d:AppSequence xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery" MessageNumber="1" InstanceId="{instance_id}"/>
</Header>
<Body>
<ProbeMatches xmlns="http://schemas.xmlsoap.org/ws/2005/04/discovery">
<ProbeMatch>
<wsa:EndpointReference xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing">
<wsa:Address>urn:uuid:{device_uuid}</wsa:Address>
</wsa:EndpointReference>
<Types>dn:NetworkVideoTransmitter</Types>
<Scopes>{scopes}</Scopes>
<XAddrs>http://{ip}:{port}/onvif/device_service</XAddrs>
<MetadataVersion>1</MetadataVersion>
</ProbeMatch>
</ProbeMatches>
</Body>
</Envelope>'''
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.sendto(response.encode('utf-8'), addr)
            sock.close()
            print(f"[WS-Discovery] Sent ProbeMatch to {addr}")
        except Exception as e:
            print(f"[WS-Discovery] Failed to send response: {e}")
    
    def _get_ip_for_client(self, client_ip):
        """Get the local IP that can reach the client on the same subnet."""
        try:
            # First try to find an IP on the same /24 subnet as the client
            import subprocess
            result = subprocess.run(['ip', '-4', 'addr'], capture_output=True, text=True)
            if result.returncode == 0:
                client_prefix = '.'.join(client_ip.split('.')[:3])
                for line in result.stdout.split('\n'):
                    if 'inet ' in line and 'scope global' in line:
                        parts = line.strip().split()
                        if len(parts) >= 2:
                            ip = parts[1].split('/')[0]
                            if ip.startswith(client_prefix + '.'):
                                return ip
            
            # Fallback: use socket to determine route
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect((client_ip, 1))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except:
            return self.config.get_local_ip()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='ONVIF Server for RTSP Cameras')
    parser.add_argument('-c', '--config', default='/etc/rpi-cam/onvif.conf',
                       help='Configuration file path')
    parser.add_argument('-p', '--port', type=int, help='Override port from config')
    args = parser.parse_args()
    
    # Load configuration
    config = ONVIFConfig(args.config)
    if args.port:
        config.port = args.port
    
    # Share config with handler
    ONVIFHandler.config = config
    
    # Start WS-Discovery
    discovery = WSDDiscovery(config)
    discovery.start()
    
    # Start HTTP server
    server_address = ('0.0.0.0', config.port)
    httpd = HTTPServer(server_address, ONVIFHandler)
    
    print(f"[ONVIF] Server starting on port {config.port}")
    print(f"[ONVIF] Device name: {config.name}")
    print(f"[ONVIF] RTSP URL: rtsp://{config.get_local_ip()}:{config.rtsp_port}{config.rtsp_path}")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[ONVIF] Shutting down...")
        discovery.stop()
        httpd.shutdown()


if __name__ == '__main__':
    main()
