"""
Test script cho hệ thống bộ nhớ cá nhân hóa
"""
import os
import sys

# Thêm root directory vào Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import memory tools
try:
    from src.tools.memory_tools import save_user_preference, get_user_profile
    MEMORY_AVAILABLE = True
except ImportError as e:
    print(f"Memory tools not available: {e}")
    MEMORY_AVAILABLE = False


def test_memory_system():
    """Test các chức năng cơ bản của memory system"""
    if not MEMORY_AVAILABLE:
        print("❌ Memory tools not available")
        return
        
    print("🧪 Testing User Memory System...")
    
    # Test user ID
    test_user_id = "test_user_123"
    
    # Test 1: Lưu các preference khác nhau
    print("\n1. Testing save_user_preference...")
    
    preferences_to_save = [
        {
            "preference_type": "dietary_restriction",
            "content": "vegetarian, no nuts",
            "context": "mentioned during flight meal discussion"
        },
        {
            "preference_type": "seat_preference", 
            "content": "aisle seat, front of plane",
            "context": "prefers easy access to bathroom"
        },
        {
            "preference_type": "travel_style",
            "content": "budget-conscious but values comfort",
            "context": "willing to pay extra for good service"
        },
        {
            "preference_type": "favorite_destination",
            "content": "Japan, specifically Tokyo and Kyoto",
            "context": "travels there annually for business"
        }
    ]
    
    for pref in preferences_to_save:
        try:
            result = save_user_preference.invoke({
                "user_id": test_user_id,
                "preference_type": pref["preference_type"],
                "content": pref["content"],
                "context": pref["context"]
            })
            print(f"  ✅ {result}")
        except Exception as e:
            print(f"  ❌ Error saving {pref['preference_type']}: {e}")
    
    print("\n2. Testing get_user_profile...")
    
    # Test 2: Lấy user profile với context khác nhau
    test_contexts = [
        "meal planning",
        "seat selection", 
        "travel booking",
        "destination recommendation",
        ""  # No context
    ]
    
    for context in test_contexts:
        try:
            result = get_user_profile.invoke({
                "user_id": test_user_id,
                "query_context": context
            })
            print(f"\n  Context: '{context}'")
            print(f"  Profile: {result}")
        except Exception as e:
            print(f"  ❌ Error getting profile for context '{context}': {e}")
    
    # Test 3: Test với user không tồn tại
    print("\n3. Testing with non-existent user...")
    try:
        result = get_user_profile.invoke({
            "user_id": "non_existent_user",
            "query_context": "any context"
        })
        print(f"  Result for non-existent user: {result}")
    except Exception as e:
        print(f"  ❌ Error: {e}")
    
    print("\n✅ Memory system test completed!")


if __name__ == "__main__":
    test_memory_system()
