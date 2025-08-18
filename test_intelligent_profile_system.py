"""
Test script cho hệ thống quản lý thông tin khách hàng thông minh
"""
import os
import sys
import asyncio
from datetime import datetime

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from tools.memory_tools import (
    save_user_preference, 
    smart_save_user_info,
    get_user_profile, 
    get_missing_user_info
)

async def test_intelligent_profile_system():
    """Test the intelligent profile completeness system"""
    
    test_user_id = f"test_user_{datetime.now().strftime('%H%M%S')}"
    
    print(f"🧪 Testing Intelligent Profile System for user: {test_user_id}")
    print("=" * 80)
    
    # Test 1: Check initial profile (should be empty with all info missing)
    print("\n📋 Test 1: Initial Profile Check")
    print("-" * 50)
    initial_profile = get_user_profile.invoke({"user_id": test_user_id})
    print(f"Initial Profile: {initial_profile}")
    
    missing_info = get_missing_user_info.invoke({"user_id": test_user_id})
    print(f"Missing Info: {missing_info}")
    
    # Test 2: Smart save user info (should detect and save automatically)
    print("\n🎯 Test 2: Smart Information Detection")
    print("-" * 50)
    
    conversations = [
        "Tôi là nam, 28 tuổi",
        "Số điện thoại của tôi là 0987654321", 
        "Tôi sinh năm 1996",
        "Tôi thích đi du lịch biển"
    ]
    
    for i, content in enumerate(conversations, 1):
        print(f"\n2.{i}. Testing content: '{content}'")
        result = smart_save_user_info.invoke({
            "user_id": test_user_id, 
            "content": content, 
            "context": f"conversation_{i}"
        })
        print(f"Smart Save Result: {result}")
        
        # Check completeness after each save
        missing_info = get_missing_user_info.invoke({"user_id": test_user_id})
        print(f"Missing Info After Save: {missing_info}")
    
    # Test 3: Manual save of duplicate info (should be skipped)
    print("\n🔄 Test 3: Duplicate Prevention")
    print("-" * 50)
    
    print("\n3.1. Trying to save duplicate phone number")
    duplicate_phone_result = save_user_preference.invoke({
        "user_id": test_user_id,
        "preference_type": "phone_number", 
        "content": "0987-654-321"
    })
    print(f"Duplicate Phone Result: {duplicate_phone_result}")
    
    print("\n3.2. Trying to save duplicate gender") 
    duplicate_gender_result = save_user_preference.invoke({
        "user_id": test_user_id,
        "preference_type": "gender", 
        "content": "Nam"
    })
    print(f"Duplicate Gender Result: {duplicate_gender_result}")
    
    # Test 4: Final profile check
    print("\n📊 Test 4: Final Profile Analysis")
    print("-" * 50)
    
    final_profile = get_user_profile.invoke({"user_id": test_user_id})
    print(f"Final Profile: {final_profile}")
    
    final_missing = get_missing_user_info.invoke({"user_id": test_user_id})
    print(f"Final Missing Info: {final_missing}")
    
    # Test 5: Invalid information handling
    print("\n❌ Test 5: Invalid Information Handling")
    print("-" * 50)
    
    invalid_tests = [
        ("phone_number", "abc123", "Invalid phone format"),
        ("age", "300", "Invalid age"),
        ("birth_year", "1800", "Invalid birth year"),
        ("gender", "xyz", "Invalid gender")
    ]
    
    for pref_type, invalid_content, description in invalid_tests:
        print(f"\n5. Testing {description}: {invalid_content}")
        result = save_user_preference.invoke({
            "user_id": test_user_id,
            "preference_type": pref_type,
            "content": invalid_content
        })
        print(f"Invalid Save Result: {result}")
    
    print("\n" + "=" * 80)
    print("🎉 Intelligent Profile System Test Completed!")
    print("=" * 80)

if __name__ == "__main__":
    # Run the test
    asyncio.run(test_intelligent_profile_system())
