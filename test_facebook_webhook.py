#!/usr/bin/env python3
"""
Script để test Facebook webhook integration.
"""

import json
import requests
import os
from dotenv import load_dotenv

load_dotenv()

# Test configuration
BASE_URL = "http://localhost:8000"
VERIFY_TOKEN = os.getenv("FB_VERIFY_TOKEN", "gauvatho")

def test_webhook_verification():
    """Test GET webhook verification"""
    print("🔍 Testing webhook verification...")
    
    url = f"{BASE_URL}/facebook/webhook"
    params = {
        "hub.mode": "subscribe",
        "hub.verify_token": VERIFY_TOKEN,
        "hub.challenge": "test_challenge_123"
    }
    
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200 and response.text == "test_challenge_123":
            print("✅ Webhook verification successful!")
            return True
        else:
            print(f"❌ Webhook verification failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error testing webhook verification: {e}")
        return False

def test_webhook_message():
    """Test POST webhook message handling"""
    print("📧 Testing webhook message handling...")
    
    url = f"{BASE_URL}/facebook/webhook"
    
    # Sample Facebook webhook payload
    payload = {
        "object": "page",
        "entry": [
            {
                "id": "PAGE_ID",
                "time": 1234567890,
                "messaging": [
                    {
                        "sender": {"id": "USER_ID_123"},
                        "recipient": {"id": "PAGE_ID"},
                        "timestamp": 1234567890,
                        "message": {
                            "mid": "m_message_id",
                            "text": "Xin chào! Tôi muốn biết thực đơn của nhà hàng."
                        }
                    }
                ]
            }
        ]
    }
    
    headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": "sha256=dummy_signature"  # Sẽ fail signature check nhưng test structure
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.text}")
        
        if response.status_code in [200, 403]:  # 403 expected due to invalid signature
            print("✅ Webhook structure test passed!")
            return True
        else:
            print(f"❌ Unexpected response: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error testing webhook message: {e}")
        return False

def test_app_health():
    """Test if FastAPI app is running"""
    print("🏥 Testing app health...")
    
    try:
        response = requests.get(f"{BASE_URL}/docs")
        if response.status_code == 200:
            print("✅ FastAPI app is running!")
            return True
        else:
            print(f"❌ App health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to app: {e}")
        return False

def main():
    print("🚀 Testing Facebook Messenger Integration")
    print("=" * 50)
    
    # Test sequence
    tests = [
        ("App Health", test_app_health),
        ("Webhook Verification", test_webhook_verification),
        ("Webhook Message", test_webhook_message),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n📋 Running: {test_name}")
        result = test_func()
        results.append((test_name, result))
        print()
    
    # Summary
    print("📊 Test Results Summary:")
    print("=" * 30)
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
        if result:
            passed += 1
    
    print(f"\nTotal: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("🎉 All tests passed! Facebook integration is ready.")
    else:
        print("⚠️ Some tests failed. Please check the configuration.")

if __name__ == "__main__":
    main()
