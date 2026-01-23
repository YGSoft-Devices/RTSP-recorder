#!/usr/bin/env python3
"""
Test ONVIF connectivity
"""
import socket
import urllib.request
import urllib.error

# Test 1: Port listening
print("[TEST 1] Checking if port 8080 is listening...")
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2)
    result = s.connect_ex(('localhost', 8080))
    s.close()
    if result == 0:
        print("✓ Port 8080 is listening")
    else:
        print("✗ Port 8080 is NOT listening (connection refused)")
except Exception as e:
    print(f"✗ Error: {e}")

# Test 2: Simple GET request
print("\n[TEST 2] Testing HTTP GET...")
try:
    response = urllib.request.urlopen('http://localhost:8080/test', timeout=2)
    print(f"✓ HTTP response: {response.status}")
except urllib.error.HTTPError as e:
    if e.code == 404:
        print(f"✓ Got HTTP 404 (expected for /test)")
    else:
        print(f"✓ Got HTTP {e.code}")
except socket.timeout:
    print("✗ Socket timeout (server not responding)")
except Exception as e:
    print(f"✗ Error: {e}")

# Test 3: ONVIF SOAP request
print("\n[TEST 3] Testing ONVIF SOAP GetDeviceInformation...")
soap_request = '''<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" 
               xmlns:tds="http://www.onvif.org/ver10/device/wsdl">
  <soap:Body>
    <tds:GetDeviceInformation/>
  </soap:Body>
</soap:Envelope>'''

try:
    req = urllib.request.Request(
        'http://localhost:8080/onvif/device_service',
        data=soap_request.encode('utf-8'),
        headers={'Content-Type': 'application/soap+xml'}
    )
    response = urllib.request.urlopen(req, timeout=5)
    data = response.read().decode('utf-8')
    print(f"✓ HTTP {response.status}")
    print(f"Response (first 500 chars):\n{data[:500]}")
except socket.timeout:
    print("✗ Socket timeout")
except urllib.error.HTTPError as e:
    print(f"HTTP {e.code}: {e.reason}")
    if e.fp:
        print(f"Response:\n{e.fp.read().decode('utf-8')[:500]}")
except Exception as e:
    print(f"✗ Error: {e}")

print("\n[DONE]")
