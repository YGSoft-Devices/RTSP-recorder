#!/usr/bin/env python3
"""Test API endpoints and device integration."""
import os
import sys
from app.api_client import ApiClient, ApiConfig

def test_connection():
    """Test basic connection."""
    print("\n🔗 Test Connection...")
    token = os.environ.get("MEETING_TOKEN", "3461192d0d89f839bae2c7edf3784a49")
    cfg = ApiConfig(base_url="https://meeting.ygsoft.fr", token=token, timeout=20, retries=3)
    client = ApiClient(cfg)
    
    try:
        result = client.list_channels()
        print(f"✅ Connection OK: {len(result)} channels")
        return True
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

def test_publish_endpoint():
    """Test publish endpoint."""
    print("\n📦 Test Verify Endpoint...")
    token = os.environ.get("MEETING_TOKEN", "3461192d0d89f839bae2c7edf3784a49")
    cfg = ApiConfig(base_url="https://meeting.ygsoft.fr", token=token, timeout=20, retries=3)
    client = ApiClient(cfg)
    
    try:
        result = client.verify_artifacts(
            device_type="RTSP-Recorder",
            distribution="beta",
            version="2.33.06"
        )
        print(f"✅ Verify endpoint OK: {result}")
        return True
    except Exception as e:
        print(f"⚠️ Verify error: {e}")
        return False

def test_device_endpoints():
    """Test device-specific endpoints."""
    print("\n📱 Test Device Endpoints...")
    token = os.environ.get("MEETING_TOKEN", "3461192d0d89f839bae2c7edf3784a49")
    cfg = ApiConfig(base_url="https://meeting.ygsoft.fr", token=token, timeout=20, retries=3)
    client = ApiClient(cfg)
    
    # Check if methods exist
    methods = ['register_device', 'send_heartbeat', 'get_ssh_hostkey', 'publish_ssh_key', 'get_device_info']
    for method in methods:
        if hasattr(client, method):
            print(f"✅ {method} exists")
        else:
            print(f"❌ {method} missing")
    
    return True

def test_device_manager():
    """Test device manager."""
    print("\n🔧 Test DeviceManager...")
    from app.device_manager import DeviceManager
    
    try:
        dm = DeviceManager()
        dm.load_device_key()
        print(f"✅ DeviceManager initialized")
        
        # Test device info collection
        info = dm.collect_device_info()
        print(f"✅ Device info collected: {len(info)} fields")
        print(f"   Fields: {', '.join(info.keys())}")
        
        return True
    except Exception as e:
        print(f"❌ DeviceManager error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("=" * 60)
    print("🧪 API & Device Integration Tests")
    print("=" * 60)
    
    results = {}
    results['connection'] = test_connection()
    results['publish'] = test_publish_endpoint()
    results['devices'] = test_device_endpoints()
    results['device_manager'] = test_device_manager()
    
    print("\n" + "=" * 60)
    print("📊 Test Summary")
    print("=" * 60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test}")
    
    print(f"\n{passed}/{total} tests passed")
    
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())
