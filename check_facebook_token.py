#!/usr/bin/env python3
"""
Facebook Token Validator and Refresher
"""

import requests
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

def check_token_validity():
    """Check if current Facebook token is valid"""
    token = os.getenv("FB_PAGE_ACCESS_TOKEN", "")
    
    if not token:
        print("❌ No FB_PAGE_ACCESS_TOKEN found in environment")
        return False
    
    # Debug token endpoint
    debug_url = "https://graph.facebook.com/debug_token"
    params = {
        "input_token": token,
        "access_token": token  # For page tokens, can use same token
    }
    
    try:
        response = requests.get(debug_url, params=params, timeout=10)
        data = response.json()
        
        print("🔍 Token Information:")
        print(f"Status Code: {response.status_code}")
        
        if "data" in data:
            token_data = data["data"]
            print(f"Valid: {token_data.get('is_valid', False)}")
            print(f"App ID: {token_data.get('app_id', 'N/A')}")
            print(f"Type: {token_data.get('type', 'N/A')}")
            print(f"Scopes: {', '.join(token_data.get('scopes', []))}")
            
            if "expires_at" in token_data:
                expires_at = datetime.fromtimestamp(token_data["expires_at"])
                print(f"Expires: {expires_at}")
            else:
                print("Expires: Never (long-lived token)")
                
            return token_data.get('is_valid', False)
        else:
            print(f"Error: {data}")
            return False
            
    except Exception as e:
        print(f"❌ Error checking token: {e}")
        return False

def test_send_message():
    """Test sending a message with current token"""
    token = os.getenv("FB_PAGE_ACCESS_TOKEN", "")
    
    url = "https://graph.facebook.com/v18.0/me/messages"
    params = {"access_token": token}
    
    # Test payload (won't actually send since recipient is fake)
    payload = {
        "recipient": {"id": "TEST_USER_ID"},
        "message": {"text": "Test message"}
    }
    
    try:
        response = requests.post(url, params=params, json=payload, timeout=10)
        data = response.json()
        
        print("\n📧 Send Message Test:")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {data}")
        
        if response.status_code == 400 and "recipient" in str(data):
            print("✅ Token is valid (recipient error expected)")
            return True
        elif "expired" in str(data).lower():
            print("❌ Token is expired!")
            return False
        else:
            print("⚠️ Unexpected response")
            return False
            
    except Exception as e:
        print(f"❌ Error testing send: {e}")
        return False

def get_long_lived_token():
    """Get instructions for long-lived token"""
    app_id = os.getenv("APP_ID", "")
    app_secret = os.getenv("FB_APP_SECRET", "")
    
    print("\n🔄 To get a new long-lived token:")
    print("=" * 50)
    print("1. Go to Facebook Developers Console")
    print("2. Select your app")
    print("3. Go to Messenger > Settings")
    print("4. Generate new Page Access Token")
    print("5. Update FB_PAGE_ACCESS_TOKEN in .env")
    
    if app_id and app_secret:
        print(f"\n📋 Your App Details:")
        print(f"App ID: {app_id}")
        print(f"App Secret: {app_secret[:8]}...")
        
        # Exchange short-lived for long-lived token URL
        current_token = os.getenv("FB_PAGE_ACCESS_TOKEN", "")
        if current_token:
            exchange_url = f"https://graph.facebook.com/oauth/access_token?grant_type=fb_exchange_token&client_id={app_id}&client_secret={app_secret}&fb_exchange_token={current_token}"
            print(f"\n🔗 Token Exchange URL:")
            print(f"GET: {exchange_url}")

def main():
    print("🔑 Facebook Token Validator")
    print("=" * 40)
    
    token_valid = check_token_validity()
    
    if token_valid:
        print("\n✅ Token appears valid, testing send...")
        send_works = test_send_message()
        
        if send_works:
            print("\n🎉 Facebook token is working correctly!")
        else:
            print("\n❌ Token validation failed or expired")
            get_long_lived_token()
    else:
        print("\n❌ Token is invalid or expired")
        get_long_lived_token()

if __name__ == "__main__":
    main()
