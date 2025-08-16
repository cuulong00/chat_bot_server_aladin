"""
Simple memory system test without LangGraph dependencies
"""
import os
import sys

# Thêm root directory vào Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_memory_only():
    """Test chỉ memory system, không dùng LangGraph"""
    print("🧪 Testing Memory System Only...")
    
    try:
        from src.tools.memory_tools import save_user_preference, get_user_profile
        
        # Test data
        test_user_id = "simple_test_user"
        
        print("\n1. Testing save_user_preference...")
        result = save_user_preference.invoke({
            "user_id": test_user_id,
            "preference_type": "seat_preference",
            "content": "window seat, front section",
            "context": "prefers view and early exit"
        })
        print(f"  ✅ {result}")
        
        print("\n2. Testing get_user_profile...")
        profile = get_user_profile.invoke({
            "user_id": test_user_id,
            "query_context": "seat selection"
        })
        print(f"  Profile: {profile}")
        
        print("\n✅ Memory-only test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Memory test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_vector_store_only():
    """Test chỉ vector store DB, không dùng memory tools"""
    print("\n🧪 Testing Vector Store Only...")
    
    try:
        from tests.vector_store_db import lookup_policy
        
        result = lookup_policy.invoke({
            "query": "Can I cancel my flight booking?"
        })
        print(f"  Policy lookup result: {result[:200]}...")
        print("\n✅ Vector store test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Vector store test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 Running simple component tests...\n")
    
    # Setup nếu cần
    try:
        from setup_system import setup_memory_system
        setup_memory_system()
    except Exception as e:
        print(f"Setup warning: {e}")
    
    print("\n" + "=" * 50)
    
    # Test memory system
    memory_ok = test_memory_only()
    
    print("\n" + "=" * 50)
    
    # Test vector store
    vector_ok = test_vector_store_only()
    
    print("\n" + "=" * 50)
    
    if memory_ok and vector_ok:
        print("✅ All component tests passed!")
    else:
        print("❌ Some component tests failed!")
