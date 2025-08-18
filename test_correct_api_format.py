#!/usr/bin/env python3
"""
Quick test for mixed content with correct payload format
"""

import requests
import json
from datetime import datetime

def test_correct_api_format():
    """Test with the correct LangGraph format"""
    
    server_url = "http://localhost:8000/invoke"
    
    # Test case: mixed content
    test_input = "Menu có gì ngon? Tôi thích ăn cay!"
    
    # Correct payload format for LangGraph
    payload = {
        "messages": [{"role": "user", "content": test_input}],
        "session_id": f"test_{int(datetime.now().timestamp())}",
        "user_id": "test_user_123",
        "question": test_input,
        "documents": [],
        "rewrite_count": 0,
        "search_attempts": 0,
        "datasource": "",
        "hallucination_score": "",
        "skip_hallucination": False
    }
    
    print("🚀 Testing correct API format...")
    print(f"📝 Input: {test_input}")
    print(f"🔗 URL: {server_url}")
    print("-" * 60)
    
    try:
        response = requests.post(server_url, json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Server Response Received!")
            
            # Show the structure
            print(f"📊 Response keys: {list(result.keys())}")
            
            # Check messages
            messages = result.get("messages", [])
            print(f"📨 Messages count: {len(messages)}")
            
            if messages:
                last_message = messages[-1]
                content = last_message.get("content", "No content")
                print(f"💬 Last message: {content[:200]}...")
                
                # Check for tool calls
                if hasattr(last_message, 'tool_calls') or 'tool_calls' in str(last_message):
                    print("🔧 Tool calls detected!")
                else:
                    print("⚠️  No tool calls detected")
                
                return True
            else:
                print("⚠️  No messages in response")
                print(f"Raw response: {json.dumps(result, indent=2)}")
                return False
                
        else:
            print(f"❌ HTTP Error {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return False

def main():
    print("🧪 MIXED CONTENT API TEST (Correct Format)")
    print("=" * 60)
    
    success = test_correct_api_format()
    
    if success:
        print("\n🎉 Test completed! Check server logs for workflow details.")
    else:
        print("\n💥 Test failed!")

if __name__ == "__main__":
    main()
