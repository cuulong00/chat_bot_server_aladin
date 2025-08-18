#!/usr/bin/env python3
"""
Debug API Response - Check what the server actually returns
"""

import requests
import json

def debug_api_response():
    """Debug API response to understand the format"""
    
    BASE_URL = "http://localhost:8000"
    
    test_message = "Menu có gì ngon? Tôi thích ăn cay!"
    
    print(f"🔍 DEBUGGING API RESPONSE")
    print("=" * 60)
    print(f"Testing: {test_message}")
    
    try:
        # Prepare API request
        payload = {
            "user_input": test_message,
            "user_id": "debug_user", 
            "session_id": "debug_session",
            "documents": [],
            "generation": "",
            "web_search": "No",
            "question": ""
        }
        
        print("\n📤 Sending request to /invoke")
        print(f"Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
        
        # Call API
        response = requests.post(f"{BASE_URL}/invoke", json=payload, timeout=60)
        
        print(f"\n📥 Response Status: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            try:
                result_data = response.json()
                print(f"\n📋 Response Data:")
                print(json.dumps(result_data, indent=2, ensure_ascii=False))
                
                # Check specific fields
                print(f"\n🔍 Field Analysis:")
                print(f"- Has 'messages': {'messages' in result_data}")
                print(f"- Has 'generation': {'generation' in result_data}")
                
                if 'messages' in result_data:
                    print(f"- Messages count: {len(result_data['messages'])}")
                    for i, msg in enumerate(result_data.get('messages', [])):
                        print(f"  Message {i}: {type(msg)} - {str(msg)[:100]}...")
                
                if 'generation' in result_data:
                    print(f"- Generation length: {len(result_data.get('generation', ''))}")
                    print(f"- Generation preview: {result_data.get('generation', '')[:200]}...")
                    
            except json.JSONDecodeError as e:
                print(f"❌ JSON Decode Error: {e}")
                print(f"Raw response: {response.text[:500]}...")
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            print(f"Response text: {response.text}")
            
    except Exception as e:
        print(f"❌ Exception: {str(e)}")

if __name__ == "__main__":
    debug_api_response()
