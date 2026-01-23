#!/usr/bin/env python3
"""Quick test to check if CSI server has applied saved tunings."""

import json
import subprocess
import sys

# Get current control values from IPC
result = subprocess.run(
    ['curl', '-s', 'http://192.168.1.4:8085/controls'],
    capture_output=True,
    text=True,
    timeout=5
)

if result.returncode != 0:
    print(f"ERROR: Could not connect to CSI server: {result.stderr}")
    sys.exit(1)

try:
    data = json.loads(result.stdout)
    controls = data.get('controls', {})
    
    # Check critical values
    saturation = controls.get('Saturation', {}).get('value', 'N/A')
    brightness = controls.get('Brightness', {}).get('value', 'N/A')
    analoguegain = controls.get('AnalogueGain', {}).get('value', 'N/A')
    
    print("=== Current Controls (API) ===")
    print(f"Saturation:    {saturation}")
    print(f"Brightness:    {brightness}")
    print(f"AnalogueGain:  {analoguegain}")
    
    # Compare with saved tuning
    try:
        with open('/tmp/csi_tuning_expected.json', 'r') as f:
            expected = json.load(f)
        
        print("\n=== Expected (from tuning file) ===")
        print(f"Saturation:    {expected.get('Saturation', 'N/A')}")
        print(f"Brightness:    {expected.get('Brightness', 'N/A')}")
        print(f"AnalogueGain:  {expected.get('AnalogueGain', 'N/A')}")
        
        # Check if they match
        print("\n=== Match Status ===")
        print(f"Saturation match:    {saturation == expected.get('Saturation')}")
        print(f"Brightness match:    {brightness == expected.get('Brightness')}")
        print(f"AnalogueGain match:  {analoguegain == expected.get('AnalogueGain')}")
    except FileNotFoundError:
        print("\n(No expected tuning file for comparison)")
    
except json.JSONDecodeError as e:
    print(f"ERROR: Invalid JSON response: {e}")
    sys.exit(1)
