#!/usr/bin/env python3
"""
Test booking tool with simpler complete message
"""

import requests
import json

def test_simple_complete_booking():
    """Test with simpler complete booking message"""
    
    # Simpler complete booking message
    message = "Ok đặt bàn. Tên: An Nguyen, SĐT: 0909123456, 2 người, ngày 19/08/2025, 19h, Quận 1"
    
    print("🍽️ TESTING SIMPLE COMPLETE BOOKING")
    print("=" * 50)
    print(f"📝 Message: {message}")
    
    payload = {
        "messages": [
            {
                "role": "user",
                "content": message,
                "additional_kwargs": {
                    "session_id": "simple-booking",
                    "user_id": "simple-user"
                }
            }
        ]
    }
    
    try:
        response = requests.post(
            "http://localhost:8000/invoke",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=15  # Shorter timeout
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # Quick check for tool calls
            tool_calls = []
            messages = data.get("messages", [])
            
            for msg in messages:
                if isinstance(msg, dict) and 'tool_calls' in msg:
                    for call in msg['tool_calls']:
                        tool_calls.append(call.get('name'))
            
            print(f"🔧 Tools called: {tool_calls}")
            
            booking_called = 'book_table_reservation' in tool_calls
            print(f"🎯 Result: {'✅ BOOKING TOOL CALLED' if booking_called else '❌ NO BOOKING TOOL'}")
            
            return booking_called
            
        else:
            print(f"❌ HTTP {response.status_code}: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    test_simple_complete_booking()
