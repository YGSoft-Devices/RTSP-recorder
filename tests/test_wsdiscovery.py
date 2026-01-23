#!/usr/bin/env python3
"""
Test ONVIF WS-Discovery
"""
import socket
import struct
import time

# Test WS-Discovery multicast
print("[TEST] WS-Discovery multicast probe...")

MULTICAST_GROUP = '239.255.255.250'
MULTICAST_PORT = 3702

try:
    # Create socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    # Join multicast group
    mreq = struct.pack('4sL', socket.inet_aton(MULTICAST_GROUP), socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    sock.bind(('', MULTICAST_PORT))
    sock.settimeout(2)
    
    print(f"✓ Joined multicast group {MULTICAST_GROUP}:{MULTICAST_PORT}")
    
    # Send probe
    probe = '''<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
               xmlns:wsa="http://www.w3.org/2005/08/addressing"
               xmlns:wsd="http://schemas.xmlsoap.org/ws/2005/04/discovery">
  <soap:Header>
    <wsa:Action>http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</wsa:Action>
    <wsa:MessageID>urn:uuid:probe-test</wsa:MessageID>
  </soap:Header>
  <soap:Body>
    <wsd:Probe>
      <wsd:Types>tds:Device</wsd:Types>
    </wsd:Probe>
  </soap:Body>
</soap:Envelope>'''
    
    sock.sendto(probe.encode('utf-8'), (MULTICAST_GROUP, MULTICAST_PORT))
    print("✓ Sent probe message")
    
    # Wait for responses
    print("\nWaiting for ProbeMatch responses (2 sec timeout)...")
    count = 0
    while True:
        try:
            data, addr = sock.recvfrom(4096)
            if b'ProbeMatch' in data or b'Probe' in data:
                count += 1
                print(f"Response #{count} from {addr}: {len(data)} bytes")
                if count <= 2:  # Show first 2 responses
                    print(data.decode('utf-8', errors='ignore')[:500])
                    print("...")
        except socket.timeout:
            break
    
    if count > 0:
        print(f"\n✓ Received {count} response(s)")
    else:
        print("\n✗ No responses received")
    
except Exception as e:
    print(f"✗ Error: {e}")

print("\n[DONE]")
