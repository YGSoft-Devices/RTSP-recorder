#!/usr/bin/env python3
"""
Test network connectivity from external client perspective
"""
import socket
import sys
import urllib.request
import urllib.error

if len(sys.argv) < 2:
    print("Usage: test_remote_connection.py <device_ip>")
    sys.exit(1)

device_ip = sys.argv[1]
print(f"Testing connectivity to {device_ip}...")

# Test 1: Ping-like test (TCP SYN to port 8080)
print(f"\n[TEST 1] TCP connection to {device_ip}:8080 (ONVIF)...")
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(3)
    result = s.connect_ex((device_ip, 8080))
    s.close()
    if result == 0:
        print(f"✓ TCP port 8080 is reachable")
    else:
        print(f"✗ TCP port 8080 connection refused (errno {result})")
except Exception as e:
    print(f"✗ Error: {e}")

# Test 2: ONVIF GetCapabilities
print(f"\n[TEST 2] ONVIF GetCapabilities...")
soap_request = '''<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" 
               xmlns:tds="http://www.onvif.org/ver10/device/wsdl">
  <soap:Body>
    <tds:GetCapabilities/>
  </soap:Body>
</soap:Envelope>'''

try:
    req = urllib.request.Request(
        f'http://{device_ip}:8080/onvif/device_service',
        data=soap_request.encode('utf-8'),
        headers={'Content-Type': 'application/soap+xml'},
        timeout=5
    )
    response = urllib.request.urlopen(req)
    data = response.read().decode('utf-8')
    if b'Capabilities' in response.read():
        print(f"✓ Got ONVIF response")
    else:
        print(f"✓ Got response (check content)")
        # Rewind to show
        req = urllib.request.Request(
            f'http://{device_ip}:8080/onvif/device_service',
            data=soap_request.encode('utf-8'),
            headers={'Content-Type': 'application/soap+xml'},
            timeout=5
        )
        response = urllib.request.urlopen(req)
        data = response.read().decode('utf-8')
        if 'Capabilities' in data:
            print(f"✓ Capabilities returned")
        print(f"Response preview:\n{data[:300]}...")
except urllib.error.HTTPError as e:
    print(f"HTTP {e.code}: {e.reason}")
except socket.timeout:
    print(f"✗ Connection timeout")
except Exception as e:
    print(f"✗ Error: {e}")

# Test 3: RTSP port connectivity
print(f"\n[TEST 3] RTSP port {device_ip}:8554...")
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(3)
    result = s.connect_ex((device_ip, 8554))
    s.close()
    if result == 0:
        print(f"✓ RTSP port 8554 is reachable")
    else:
        print(f"✗ RTSP port 8554 connection refused")
except Exception as e:
    print(f"✗ Error: {e}")

print("\n[DONE]")
