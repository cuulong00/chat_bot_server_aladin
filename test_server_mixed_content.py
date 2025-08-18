#!/usr/bin/env python3
"""
Quick test to verify the server can handle mixed content scenarios after the fixes.
"""

import asyncio
import aiohttp
import json
from datetime import datetime

async def test_mixed_content_server():
    """Test mixed content scenarios with the fixed server."""
    
    # Test cases for mixed content
    test_cases = [
        {
            "name": "Mixed Content - Menu + Preference",
            "input": "Menu hôm nay có gì ngon? Tôi thích ăn cay và đồ nướng!",
            "expected": "should search menu AND call preference tools"
        },
        {
            "name": "Mixed Content - Booking + Location Preference", 
            "input": "Tôi muốn đặt bàn cho 4 người lúc 7h tối mai. Tôi thích ngồi gần cửa sổ.",
            "expected": "should call booking tool AND preference tools"
        },
        {
            "name": "Pure Preference - Should route to DirectAnswer",
            "input": "Tôi thích ăn đồ Việt Nam và uống trà đá.",
            "expected": "should route to DirectAnswer and call preference tools"
        }
    ]
    
    server_url = "http://127.0.0.1:8000/invoke"
    
    print("🚀 Testing mixed content scenarios on fixed server...\n")
    
    async with aiohttp.ClientSession() as session:
        for i, test_case in enumerate(test_cases, 1):
            print(f"🧪 Test {i}: {test_case['name']}")
            print(f"📝 Input: {test_case['input']}")
            print(f"📋 Expected: {test_case['expected']}")
            
            payload = {
                "input": {
                    "messages": [{"role": "user", "content": test_case["input"]}],
                    "session_id": f"test_session_{i}_{int(datetime.now().timestamp())}",
                    "user_id": "test_user_mixed_content_123"
                },
                "config": {}
            }
            
            try:
                async with session.post(server_url, json=payload, timeout=30) as response:
                    if response.status == 200:
                        result = await response.json()
                        
                        # Extract the response message
                        output = result.get("output", {})
                        messages = output.get("messages", [])
                        
                        if messages:
                            last_message = messages[-1]
                            response_content = last_message.get("content", "No response content")
                            print(f"✅ Server Response: {response_content[:200]}...")
                            
                            # Check if tool calls were made
                            if hasattr(last_message, 'tool_calls') or 'tool_calls' in str(last_message):
                                print("🔧 Tool calls detected in response")
                            
                        else:
                            print("⚠️  No messages in response")
                            
                    else:
                        error_text = await response.text()
                        print(f"❌ Server error {response.status}: {error_text}")
                        
            except asyncio.TimeoutError:
                print("⏱️  Request timed out")
            except Exception as e:
                print(f"❌ Request failed: {e}")
            
            print("-" * 80 + "\n")

async def main():
    """Main test function."""
    print("🔍 Testing server after database and embedding fixes...\n")
    
    # Give user a chance to start server
    print("⚠️  Make sure your server is running on http://127.0.0.1:8000")
    print("   You can start it with: python3 app.py")
    print("   Press Enter when ready, or Ctrl+C to cancel...")
    
    try:
        input()
    except KeyboardInterrupt:
        print("\n👋 Test cancelled by user")
        return
    
    await test_mixed_content_server()
    
    print("🎯 Test completed!")
    print("Check the server logs to see detailed workflow execution.")

if __name__ == "__main__":
    asyncio.run(main())
