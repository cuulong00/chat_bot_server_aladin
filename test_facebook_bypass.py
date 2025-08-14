#!/usr/bin/env python3
"""
Test script to verify Facebook webhook works with Supabase bypass enabled.
"""

import os
import requests
import json
from datetime import datetime

def test_facebook_webhook():
    """Test Facebook webhook with bypass configuration."""
    
    # Configuration
    webhook_url = "http://localhost:8000/webhook/facebook"
    test_user_id = "24769757262629049"  # User ID from the error log
    
    # Create test message payload
    test_payload = {
        "object": "page",
        "entry": [
            {
                "id": "662258643648319",
                "time": int(datetime.now().timestamp() * 1000),
                "messaging": [
                    {
                        "sender": {"id": test_user_id},
                        "recipient": {"id": "662258643648319"},
                        "timestamp": int(datetime.now().timestamp() * 1000),
                        "message": {
                            "mid": f"test_message_{int(datetime.now().timestamp())}",
                            "text": "Hello, this is a test message"
                        }
                    }
                ]
            }
        ]
    }
    
    print("🧪 Testing Facebook webhook with Supabase bypass...")
    print(f"📝 Test payload: {json.dumps(test_payload, indent=2)}")
    
    try:
        # Send test request
        response = requests.post(
            webhook_url,
            json=test_payload,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": "sha256=test"  # This would normally be validated
            },
            timeout=30
        )
        
        print(f"✅ Response status: {response.status_code}")
        print(f"📄 Response: {response.text}")
        
        if response.status_code == 200:
            print("🎉 Test successful! Facebook webhook is working with bypass mode.")
        else:
            print(f"❌ Test failed with status code: {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

def check_environment():
    """Check if bypass environment variables are set correctly."""
    print("🔍 Checking environment configuration...")
    
    skip_supabase = os.getenv("SKIP_SUPABASE_AUTH", "0")
    bypass_user_db = os.getenv("BYPASS_USER_DB", "0")
    
    print(f"SKIP_SUPABASE_AUTH: {skip_supabase}")
    print(f"BYPASS_USER_DB: {bypass_user_db}")
    
    if skip_supabase == "1" and bypass_user_db == "1":
        print("✅ Bypass configuration is correct")
        return True
    else:
        print("⚠️  Bypass configuration may not be set correctly")
        print("Make sure to set SKIP_SUPABASE_AUTH=1 and BYPASS_USER_DB=1 in your environment")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Facebook Webhook Test with Supabase Bypass")
    print("=" * 60)
    
    # Check environment
    env_ok = check_environment()
    
    if env_ok:
        print("\n" + "=" * 60)
        test_facebook_webhook()
    else:
        print("\n❌ Environment not configured for bypass mode")
        print("Please set the following environment variables:")
        print("SKIP_SUPABASE_AUTH=1")
        print("BYPASS_USER_DB=1")
    
    print("=" * 60)
