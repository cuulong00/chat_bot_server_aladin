#!/usr/bin/env python3
"""
Debug HTTP response format to understand streaming data structure
"""

import requests
import json

def debug_http_response():
    """Debug a single HTTP request to understand response format"""
    
    BASE_URL = "http://127.0.0.1:2024"
    ASSISTANT_ID = "agent"
    
    print("🔍 DEBUGGING HTTP RESPONSE FORMAT")
    print("=" * 50)
    
    try:
        # Create thread
        thread_response = requests.post(
            f"{BASE_URL}/threads",
            headers={"Content-Type": "application/json"},
            json={}
        )
        
        thread_id = thread_response.json()["thread_id"]
        print(f"Thread created: {thread_id}")
        
        # Send simple test message
        message_data = {
            "messages": [
                {
                    "role": "user", 
                    "content": "Tôi thích ăn cay!"  # Simple preference test
                }
            ],
            "user_id": "debug_user",
            "session_id": "debug_session"
        }
        
        print(f"Sending message: 'Tôi thích ăn cay!'")
        
        response = requests.post(
            f"{BASE_URL}/threads/{thread_id}/runs",
            headers={"Content-Type": "application/json"},
            json={
                "assistant_id": ASSISTANT_ID,
                "input": message_data
            },
            stream=True
        )
        
        print(f"Response status: {response.status_code}")
        print("\n📡 STREAMING RESPONSE DATA:")
        print("-" * 50)
        
        line_count = 0
        for line in response.iter_lines():
            if line:
                line_count += 1
                line_str = line.decode('utf-8')
                print(f"Line {line_count}: {line_str}")
                
                # Try to parse JSON if it looks like data
                if line_str.startswith('data: '):
                    try:
                        data = json.loads(line_str[6:])
                        print(f"  📝 Parsed JSON: {json.dumps(data, indent=2, ensure_ascii=False)}")
                    except json.JSONDecodeError as e:
                        print(f"  ❌ JSON parse error: {e}")
                
                # Stop after reasonable number of lines
                if line_count > 50:
                    print("  ... (truncated)")
                    break
                    
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    debug_http_response()
