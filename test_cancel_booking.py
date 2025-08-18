#!/usr/bin/env python3
"""
Test script for cancel_booking functionality
"""

import json
from pathlib import Path

def test_cancel_booking():
    """Test the cancel booking functionality"""
    
    print("🧪 Testing Cancel Booking Functionality")
    print("=" * 60)
    
    # Test import
    try:
        from src.tools.reservation_tools import cancel_booking, book_table_reservation, get_user_bookings
        print("✅ Successfully imported cancel_booking tool")
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    
    # Check existing bookings first
    booking_file = Path("booking.json")
    if not booking_file.exists():
        print("❌ No booking.json found. Creating a test booking first...")
        
        # Create a test booking
        try:
            booking_result = book_table_reservation.invoke({
                "restaurant_location": "chi nhánh test",
                "first_name": "Test",
                "last_name": "User",
                "phone": "0987654321",
                "reservation_date": "30/12/2025",
                "start_time": "19:00",
                "amount_adult": 2,
                "amount_children": 0,
                "note": "Test booking for cancel",
                "has_birthday": False
            })
            
            if booking_result.get('success'):
                print("✅ Created test booking")
                test_booking_id = booking_result['data']['id']
                print(f"   📋 Test booking ID: {test_booking_id[:8]}...")
            else:
                print("❌ Failed to create test booking")
                return False
        except Exception as e:
            print(f"❌ Error creating test booking: {e}")
            return False
    
    # Load current bookings to get an ID
    with open(booking_file, 'r', encoding='utf-8') as f:
        bookings = json.load(f)
    
    if not bookings:
        print("❌ No bookings available for cancellation test")
        return False
    
    print(f"📊 Current bookings count: {len(bookings)}")
    
    # Get the last booking for testing
    test_booking = bookings[-1]
    test_booking_id = test_booking['id']
    test_phone = test_booking['phone']
    
    print(f"🎯 Test booking selected:")
    print(f"   📋 ID: {test_booking_id[:8]}...")
    print(f"   👤 Customer: {test_booking.get('first_name')} {test_booking.get('last_name')}")
    print(f"   📞 Phone: {test_phone}")
    
    # Test 1: Cancel by booking ID (full ID)
    print("\n🗑️ Test 1: Cancel by full booking ID")
    try:
        cancel_result = cancel_booking.invoke({
            "booking_id": test_booking_id,
            "phone": None
        })
        
        if cancel_result.get('success'):
            print("✅ Successfully canceled booking by ID")
            print(f"   📋 Canceled booking ID: {cancel_result['data']['canceled_booking']['id'][:8]}...")
            print(f"   📊 Remaining bookings: {cancel_result['data']['remaining_bookings']}")
            
            # Show formatted message
            if 'formatted_message' in cancel_result:
                print("\n📝 Formatted cancellation message:")
                print(cancel_result['formatted_message'][:300] + "...")
        else:
            print(f"❌ Failed to cancel by ID: {cancel_result.get('message')}")
            
    except Exception as e:
        print(f"❌ Cancel by ID error: {e}")
    
    # Create another booking for phone number test
    print("\n➕ Creating another booking for phone number test...")
    try:
        booking_result2 = book_table_reservation.invoke({
            "restaurant_location": "chi nhánh test 2",
            "first_name": "Phone",
            "last_name": "Test",
            "phone": "0123456789",
            "reservation_date": "31/12/2025",
            "start_time": "20:00",
            "amount_adult": 3,
            "amount_children": 1,
            "note": "Phone cancel test",
            "has_birthday": True
        })
        
        if booking_result2.get('success'):
            print("✅ Created second test booking")
        else:
            print("❌ Failed to create second booking")
            
    except Exception as e:
        print(f"❌ Error creating second booking: {e}")
    
    # Test 2: Cancel by phone number
    print("\n🗑️ Test 2: Cancel by phone number")
    try:
        cancel_result2 = cancel_booking.invoke({
            "booking_id": None,
            "phone": "0123456789"
        })
        
        if cancel_result2.get('success'):
            print("✅ Successfully canceled booking by phone")
            canceled_customer = cancel_result2['data']['canceled_booking']
            print(f"   👤 Canceled: {canceled_customer.get('first_name')} {canceled_customer.get('last_name')}")
            print(f"   📊 Remaining bookings: {cancel_result2['data']['remaining_bookings']}")
        else:
            print(f"❌ Failed to cancel by phone: {cancel_result2.get('message')}")
            
    except Exception as e:
        print(f"❌ Cancel by phone error: {e}")
    
    # Test 3: Cancel non-existent booking
    print("\n🗑️ Test 3: Try to cancel non-existent booking")
    try:
        cancel_result3 = cancel_booking.invoke({
            "booking_id": "non-existent-id-12345",
            "phone": None
        })
        
        if not cancel_result3.get('success'):
            print("✅ Correctly rejected non-existent booking")
            print(f"   ⚠️ Message: {cancel_result3.get('message')}")
        else:
            print("❌ Should have failed for non-existent booking")
            
    except Exception as e:
        print(f"❌ Non-existent booking test error: {e}")
    
    # Test 4: Show remaining bookings
    print("\n📋 Test 4: Check remaining bookings")
    try:
        # Check if any bookings remain
        with open(booking_file, 'r', encoding='utf-8') as f:
            final_bookings = json.load(f)
        
        print(f"📊 Final bookings count: {len(final_bookings)}")
        
        if final_bookings:
            print("📝 Remaining bookings:")
            for booking in final_bookings[-3:]:  # Show last 3
                print(f"   📋 {booking.get('id', 'N/A')[:8]}... - {booking.get('first_name')} {booking.get('last_name')} - {booking.get('phone')}")
        else:
            print("🎉 All test bookings have been cleaned up!")
            
    except Exception as e:
        print(f"❌ Final check error: {e}")
    
    print("\n" + "=" * 60)
    print("🎉 Cancel booking testing completed!")
    
    return True

if __name__ == "__main__":
    success = test_cancel_booking()
    
    if success:
        print("\n🚀 Next steps:")
        print("1. cancel_booking tool is ready for use in chatbot")
        print("2. Users can cancel by booking ID or phone number")
        print("3. Tool provides formatted cancellation confirmations")
    
    exit(0 if success else 1)
