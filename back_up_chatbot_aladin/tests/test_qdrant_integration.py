"""Simple test script to verify restaurant lookup functionality works with global qdrant_store."""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def test_global_qdrant_store():
    """Test that we can import and use the global qdrant_store instance."""
    try:
        from src.database.qdrant_store import qdrant_store
        print(f"✅ Successfully imported global qdrant_store: {qdrant_store}")
        print(f"   Collection name: {qdrant_store.collection_name}")
        print(f"   Embedding model: {qdrant_store.embedding_model}")
        return True
    except Exception as e:
        print(f"❌ Failed to import global qdrant_store: {e}")
        return False

def test_reservation_tools_import():
    """Test that reservation tools can import and use qdrant_store."""
    try:
        from src.tools.reservation_tools import _find_restaurant_id, qdrant_store
        print(f"✅ Successfully imported reservation tools with qdrant_store: {qdrant_store}")
        
        # Test with a sample query (will return None if no data, but should not error)
        result = _find_restaurant_id("test location")
        print(f"   Test search result: {result}")
        return True
    except Exception as e:
        print(f"❌ Failed to import or use reservation tools: {e}")
        return False

def test_lookup_tool():
    """Test the lookup tool."""
    try:
        from src.tools.reservation_tools import lookup_restaurant_by_location
        
        result = lookup_restaurant_by_location("test restaurant")
        print(f"✅ Lookup tool executed successfully")
        print(f"   Result: {result}")
        return True
    except Exception as e:
        print(f"❌ Lookup tool failed: {e}")
        return False

def main():
    """Run simple integration tests."""
    print("🚀 Testing Global QdrantStore Integration")
    print("=" * 50)
    
    tests = [
        ("Global QdrantStore Import", test_global_qdrant_store),
        ("Reservation Tools Import", test_reservation_tools_import),
        ("Lookup Tool Test", test_lookup_tool)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 Running: {test_name}")
        try:
            if test_func():
                print(f"✅ {test_name} PASSED")
                passed += 1
            else:
                print(f"❌ {test_name} FAILED")
        except Exception as e:
            print(f"💥 {test_name} ERROR: {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All integration tests passed!")
        print("\n📝 Global qdrant_store is working correctly")
    else:
        print("⚠️ Some integration tests failed.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
