#!/usr/bin/env python3
"""
Quick test script to verify that book_table_reservation tool can be called by LLM
and check if the debug logging works.
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_booking_tool():
    """Test the book_table_reservation tool directly"""
    print("🧪 Testing book_table_reservation Tool")
    print("=" * 50)
    
    try:
        from src.tools.reservation_tools import book_table_reservation
        
        print(f"✅ Tool imported successfully")
        print(f"📝 Tool name: {book_table_reservation.name}")
        print(f"📄 Tool description:")
        print("-" * 30)
        print(book_table_reservation.description)
        print("-" * 30)
        
        # Test tool execution with sample data
        print("\n🔧 Testing tool execution (test booking):")
        result = book_table_reservation.invoke({
            "restaurant_location": "Times City",
            "first_name": "Nguyen",
            "last_name": "Test",
            "phone": "0123456789",
            "reservation_date": "25/12/2024",
            "start_time": "19:00", 
            "amount_adult": 4,
            "amount_children": 2,
            "note": "Bàn yên tĩnh, có trẻ em",
            "has_birthday": True
        })
        
        print(f"✅ Tool execution result type: {type(result)}")
        print(f"📊 Result summary: {result.get('success', False)}")
        if result.get('success'):
            print(f"✅ Booking successful!")
            if 'formatted_message' in result:
                print("📝 Formatted message preview:")
                print(result['formatted_message'][:200] + "...")
        else:
            print(f"❌ Booking failed: {result.get('message', 'Unknown error')}")
        
        return result.get('success', False)
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def test_tool_description_quality():
    """Check if the tool description has good keywords for LLM recognition"""
    print("\n📊 Tool Description Analysis")
    print("=" * 35)
    
    try:
        from src.tools.reservation_tools import book_table_reservation
        
        description = book_table_reservation.description
        
        # Check for key booking keywords
        booking_keywords = [
            "book", "reservation", "table", "restaurant", 
            "customer", "phone", "date", "time"
        ]
        
        found_keywords = [kw for kw in booking_keywords if kw.lower() in description.lower()]
        print(f"📝 Booking keywords found: {len(found_keywords)}/{len(booking_keywords)}")
        for kw in found_keywords:
            print(f"   ✓ {kw}")
        
        missing_keywords = [kw for kw in booking_keywords if kw not in found_keywords]
        if missing_keywords:
            print(f"⚠️  Missing keywords:")
            for kw in missing_keywords:
                print(f"   ✗ {kw}")
        
        return len(found_keywords) >= 6  # At least 6 out of 8 keywords
        
    except Exception as e:
        print(f"❌ Description analysis failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Booking Tool Integration Test")
    print("=================================\n")
    
    tests = [
        ("Booking Tool Execution", test_booking_tool),
        ("Description Quality", test_tool_description_quality)
    ]
    
    passed = 0
    for test_name, test_func in tests:
        if test_func():
            passed += 1
            print(f"✅ {test_name}: PASSED")
        else:
            print(f"❌ {test_name}: FAILED")
        print()
    
    print(f"📊 FINAL RESULT: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("🎉 Booking tool should work properly!")
        print("\n💡 Next steps:")
        print("1. Restart your chatbot server")
        print("2. Test with booking request: 'Đặt bàn 4 người tối nay 7h tại Times City'")
        print("3. Check logs for: '🔥🔥🔥 BOOK_TABLE_RESERVATION TOOL ĐƯỢC GỌI!'")
    else:
        print("⚠️  Some tests failed. Check the issues above.")
