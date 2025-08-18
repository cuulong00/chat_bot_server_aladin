#!/usr/bin/env python3
"""
Test COMPLETE booking tool calling with all required information
This tests if book_table_reservation tool actually works when given complete info
"""

import requests
import json
from datetime import datetime, timedelta

def test_complete_booking():
    """Test booking tool with COMPLETE information"""
    
    # Calculate tomorrow's date  
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%d/%m/%Y")
    
    # Complete booking message with ALL required info
    complete_booking_message = f"""Ok đặt bàn cho 2 người.
Tên: Nguyễn Văn An
SĐT: 0909123456  
Ngày: {tomorrow}
Giờ: 19:00
Chi nhánh: Quận 1"""
    
    print("🍽️ TESTING COMPLETE BOOKING TOOL")
    print("=" * 50)
    print(f"📝 Message: {complete_booking_message}")
    print(f"🎯 Expected: book_table_reservation should be called")
    
    # Send request
    payload = {
        "messages": [
            {
                "role": "user",  # Add required role field
                "content": complete_booking_message,
                "additional_kwargs": {
                    "session_id": "booking-test",
                    "user_id": "booking-user-123"
                }
            }
        ]
    }
    
    try:
        response = requests.post(
            "http://localhost:8000/invoke",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # Check for tool calls
            tool_calls_found = []
            final_response = ""
            
            messages = data.get("messages", [])
            for msg in messages:
                if isinstance(msg, dict):
                    if 'tool_calls' in msg:
                        for call in msg['tool_calls']:
                            tool_name = call.get('name', '')
                            tool_calls_found.append(tool_name)
                            print(f"🔧 Tool called: {tool_name}")
                            if 'args' in call:
                                args = call['args']
                                print(f"   Args: {json.dumps(args, ensure_ascii=False, indent=2)}")
                    
                    if msg.get('type') == 'ai' and 'content' in msg:
                        final_response = msg['content']
            
            print(f"\n📋 Summary:")
            print(f"🔧 Tools called: {tool_calls_found}")
            print(f"💬 Final response: {final_response[:200]}...")
            
            # Check results
            booking_tool_called = 'book_table_reservation' in tool_calls_found
            print(f"\n🎯 Result: {'✅ SUCCESS' if booking_tool_called else '❌ BOOKING TOOL NOT CALLED'}")
            
            return booking_tool_called
            
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return False

def test_incomplete_vs_complete():
    """Compare incomplete vs complete booking requests"""
    
    print("\n" + "=" * 60)
    print("🔄 COMPARING INCOMPLETE VS COMPLETE BOOKING")
    print("=" * 60)
    
    test_cases = [
        {
            "name": "❌ Incomplete Booking",
            "message": "Đặt bàn cho 4 người tối nay",
            "should_call_tool": False,
            "reason": "Missing: name, phone, location, specific time"
        },
        {
            "name": "✅ Complete Booking", 
            "message": "Ok đặt bàn. Tên: Trần Thị Bình, SĐT: 0901234567, Ngày: 19/08/2025, Giờ: 18:30, 3 người, Chi nhánh: Quận 3",
            "should_call_tool": True,
            "reason": "Has all required info"
        }
    ]
    
    results = []
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n📋 Test {i}: {test['name']}")
        print(f"📝 Message: {test['message']}")
        print(f"🎯 Expected: {'Should call booking tool' if test['should_call_tool'] else 'Should ask for more info'}")
        print(f"💡 Reason: {test['reason']}")
        
        # Send request
        payload = {
            "messages": [
                {
                    "role": "user",  # Add required role field
                    "content": test["message"],
                    "additional_kwargs": {
                        "session_id": f"compare-test-{i}",
                        "user_id": "compare-user-123"
                    }
                }
            ]
        }
        
        try:
            response = requests.post(
                "http://localhost:8000/invoke",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Check for booking tool calls
                booking_called = False
                asks_for_info = False
                
                messages = data.get("messages", [])
                for msg in messages:
                    if isinstance(msg, dict):
                        if 'tool_calls' in msg:
                            for call in msg['tool_calls']:
                                if call.get('name') == 'book_table_reservation':
                                    booking_called = True
                        
                        if msg.get('type') == 'ai' and 'content' in msg:
                            content = msg['content'].lower()
                            ask_keywords = ["số điện thoại", "tên", "chi nhánh", "giờ cụ thể", "thông tin"]
                            asks_for_info = any(keyword in content for keyword in ask_keywords)
                
                # Determine correctness
                if test['should_call_tool']:
                    correct = booking_called
                    status = "✅ CORRECT" if correct else "❌ SHOULD CALL TOOL"
                else:
                    correct = not booking_called and asks_for_info
                    status = "✅ CORRECT" if correct else "❌ SHOULD ASK FOR INFO"
                
                print(f"🔧 Booking tool called: {booking_called}")
                print(f"❓ Asks for info: {asks_for_info}")
                print(f"🎯 Result: {status}")
                
                results.append(correct)
                
            else:
                print(f"❌ HTTP Error: {response.status_code}")
                results.append(False)
                
        except Exception as e:
            print(f"❌ Request failed: {e}")
            results.append(False)
    
    # Summary
    print(f"\n{'='*60}")
    print("📊 BOOKING TOOL COMPARISON SUMMARY")
    print(f"{'='*60}")
    
    total_correct = sum(results)
    total_tests = len(results)
    
    print(f"✅ Correct behavior: {total_correct}/{total_tests}")
    print(f"📈 Accuracy: {total_correct/total_tests*100:.1f}%")
    
    return results

if __name__ == "__main__":
    print("🚀 Testing Complete Booking Tool Functionality...")
    
    # Test 1: Complete booking
    result1 = test_complete_booking()
    
    # Test 2: Compare incomplete vs complete
    result2 = test_incomplete_vs_complete()
    
    print(f"\n{'🎉' if result1 else '⚠️'} Complete booking tool test: {'PASSED' if result1 else 'NEEDS INVESTIGATION'}")
