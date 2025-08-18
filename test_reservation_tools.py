#!/usr/bin/env python3
"""
Test script for reservation tools - booking and query functionality
"""

import json
import os
from pathlib import Path

def test_booking_system():
    """Test the booking system functionality"""
    
    print("🧪 Testing Reservation Tools Functionality")
    print("=" * 60)
    
    # Test import
    try:
        from src.tools.reservation_tools import (
            book_table_reservation, 
            get_user_bookings, 
            lookup_restaurant_by_location
        )
        print("✅ Successfully imported all reservation tools")
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    
    # Test 1: Book a table (should save to booking.json)
    print("\n📋 Test 1: Book a table reservation")
    try:
        booking_result = book_table_reservation.invoke({
            "restaurant_location": "chi nhánh trần hưng đạo",
            "first_name": "Nguyễn",
            "last_name": "Văn A",
            "phone": "0912345678",
            "reservation_date": "25/12/2025",  # Future date
            "start_time": "18:00",
            "amount_adult": 4,
            "amount_children": 1,
            "note": "Sinh nhật bé",
            "has_birthday": True
        })
        
        if booking_result.get('success'):
            print("✅ Booking created successfully")
            print(f"   📋 Booking ID: {booking_result['data']['id'][:8]}...")
            
            # Check if booking.json was created
            booking_file = Path("booking.json")
            if booking_file.exists():
                print("✅ booking.json file created")
                with open(booking_file, 'r', encoding='utf-8') as f:
                    bookings = json.load(f)
                print(f"   📊 Total bookings in file: {len(bookings)}")
            else:
                print("❌ booking.json file not found")
        else:
            print(f"❌ Booking failed: {booking_result.get('message')}")
            
    except Exception as e:
        print(f"❌ Booking test error: {e}")
    
    # Test 2: Query user bookings
    print("\n🔍 Test 2: Query user bookings")
    try:
        query_result = get_user_bookings.invoke({"phone": "0912345678"})
        
        if query_result.get('success'):
            bookings_count = query_result['data']['count']
            print(f"✅ Found {bookings_count} booking(s) for phone 0912345678")
            
            if bookings_count > 0:
                print("   📋 Latest booking details:")
                latest = query_result['data']['bookings'][0]
                print(f"   👤 Customer: {latest['customer_name']}")
                print(f"   📅 Date: {latest['reservation_date']}")
                print(f"   🏪 Location: {latest['restaurant_location']}")
                print(f"   👥 Guests: {latest['guests']}")
        else:
            print(f"❌ Query failed: {query_result.get('message')}")
            
    except Exception as e:
        print(f"❌ Query test error: {e}")
    
    # Test 3: Query non-existent phone
    print("\n🔍 Test 3: Query non-existent phone")
    try:
        empty_result = get_user_bookings.invoke({"phone": "0999999999"})
        
        if empty_result.get('success') and empty_result['data']['count'] == 0:
            print("✅ Correctly returned empty result for non-existent phone")
        else:
            print(f"❌ Unexpected result for non-existent phone")
            
    except Exception as e:
        print(f"❌ Empty query test error: {e}")
    
    # Test 4: Restaurant lookup
    print("\n🏪 Test 4: Restaurant lookup")
    try:
        lookup_result = lookup_restaurant_by_location.invoke({"location_query": "trần hưng đạo"})
        
        if lookup_result.get('success'):
            restaurant_id = lookup_result['data']['restaurant_id']
            print(f"✅ Found restaurant ID: {restaurant_id}")
        else:
            print(f"⚠️ Restaurant lookup: {lookup_result.get('message')}")
            
    except Exception as e:
        print(f"❌ Restaurant lookup error: {e}")
    
    print("\n" + "=" * 60)
    print("🎉 Reservation tools testing completed!")
    
    # Show current booking.json content
    booking_file = Path("booking.json")
    if booking_file.exists():
        with open(booking_file, 'r', encoding='utf-8') as f:
            bookings = json.load(f)
        print(f"📊 Total bookings in system: {len(bookings)}")
        print("\n📝 Sample booking data structure:")
        if bookings:
            sample = bookings[-1]  # Latest booking
            print(f"   ID: {sample.get('id', 'N/A')[:8]}...")
            print(f"   Customer: {sample.get('first_name')} {sample.get('last_name')}")
            print(f"   Phone: {sample.get('phone')}")
            print(f"   Date: {sample.get('reservation_date')}")
            print(f"   Time: {sample.get('start_time')} - {sample.get('end_time')}")
            print(f"   Guests: {sample.get('amount_adult')} adults, {sample.get('amount_children')} children")
            print(f"   Status: {sample.get('status')}")
    
    return True

if __name__ == "__main__":
    success = test_booking_system()
    
    if success:
        print("\n🚀 Next steps:")
        print("1. Add get_user_bookings to your assistant's tool list")
        print("2. Test booking and querying in your chatbot")
        print("3. When API is ready, uncomment the requests.post() call")
    
    exit(0 if success else 1)
