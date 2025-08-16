"""Integration test for restaurant data embedding and reservation system.

This script tests the complete flow:
1. Embedding restaurant data from id_restaurant.json into vector database
2. Testing semantic search for restaurant lookup
3. Testing reservation system with real restaurant data
"""

import sys
from pathlib import Path
import json

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.tools.reservation_tools import _find_restaurant_id, lookup_restaurant_by_location
from src.database.qdrant_store import QdrantStore

def test_restaurant_data_structure():
    """Test that restaurant data has the expected structure"""
    restaurant_file = PROJECT_ROOT / "data" / "id_restaurant.json"
    
    if not restaurant_file.exists():
        print(f"❌ Restaurant data file not found: {restaurant_file}")
        return False
    
    try:
        with open(restaurant_file, 'r', encoding='utf-8') as f:
            restaurants = json.load(f)
        
        print(f"✅ Found {len(restaurants)} restaurants in data file")
        
        # Test first few restaurants for structure
        for i, restaurant in enumerate(restaurants[:5]):
            if not isinstance(restaurant, dict):
                print(f"❌ Restaurant {i} is not a dict: {type(restaurant)}")
                return False
            
            if 'id' not in restaurant or 'name' not in restaurant:
                print(f"❌ Restaurant {i} missing required fields: {restaurant}")
                return False
            
            print(f"✅ Restaurant {i}: ID={restaurant['id']}, Name={restaurant['name'][:50]}...")
        
        return True
        
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in restaurant file: {e}")
        return False
    except Exception as e:
        print(f"❌ Error reading restaurant file: {e}")
        return False

def test_restaurant_brand_extraction():
    """Test brand extraction from real restaurant names"""
    test_cases = [
        ("LW-BG01:L3-07 Vincom Bắc Giang - số 43 Ngô Gia Tự, Bắc Giang", "LW"),
        ("BTQM-HN01:102 Thái Thịnh, Đống Đa, Hà Nội", "BTQM"),
        ("TL-HN01:Trần Thái Tông", "TL"),
        ("CNHS-HN01:111 K1 Giảng Võ, P. Ô Chợ Dừa", "CNHS"),
        ("AP-SG01:Số 9 Thoại Ngọc Hầu, P. Hòa Thạnh", "AP"),
        ("AV-HN01:Vincom Phạm Ngọc Thạch", "AV")
    ]
    
    print("\n🧪 Testing brand extraction...")
    
    for restaurant_name, expected_brand in test_cases:
        # Extract brand code
        if ':' in restaurant_name:
            code_part = restaurant_name.split(':')[0]
            if '-' in code_part:
                brand_code = code_part.split('-')[0]
                if brand_code == expected_brand:
                    print(f"✅ {restaurant_name[:30]}... -> {brand_code}")
                else:
                    print(f"❌ {restaurant_name[:30]}... -> Expected {expected_brand}, got {brand_code}")
                    return False
    
    return True

def test_location_extraction():
    """Test location extraction from real restaurant names"""
    test_cases = [
        ("LW-HN01:84 Ngọc khánh - Ba Đình - Hà Nội", "Hà Nội"),
        ("LW-SG01:816 Sư Vạn Hạnh P12 Q10", "Hồ Chí Minh"),
        ("LW-HP01:Aeon Hải Phòng", "Hải Phòng"),
        ("LW-DN01:K33 Võ Thị Sáu - Biên Hòa - Đồng Nai", "Đồng Nai"),
        ("TL-HU01:Aeon Huế - 08 Võ Nguyên Giáp, An Đông", "Huế")
    ]
    
    print("\n🧪 Testing location extraction...")
    
    for restaurant_name, expected_city in test_cases:
        # Extract city
        city = ""
        if any(x in restaurant_name for x in ['Hà Nội', 'HN']):
            city = 'Hà Nội'
        elif any(x in restaurant_name for x in ['SG', 'Q10', 'Quận']):
            city = 'Hồ Chí Minh'
        elif 'Hải Phòng' in restaurant_name or 'HP' in restaurant_name:
            city = 'Hải Phòng'
        elif 'Đồng Nai' in restaurant_name or 'DN' in restaurant_name:
            city = 'Đồng Nai'
        elif 'Huế' in restaurant_name or 'HU' in restaurant_name:
            city = 'Huế'
        
        if city == expected_city:
            print(f"✅ {restaurant_name[:40]}... -> {city}")
        else:
            print(f"❌ {restaurant_name[:40]}... -> Expected {expected_city}, got {city}")
            return False
    
    return True

def test_reservation_fallback():
    """Test reservation system with vector database"""
    print("\n🧪 Testing reservation system with vector database...")
    
    test_queries = [
        ("times city", None),  # Should find a real restaurant ID
        ("vincom bà triệu", None),  # Should find a real restaurant ID  
        ("tian long", None),  # Should find a real restaurant ID
        ("unknown location xyz", None)  # Should return None for unknown locations
    ]
    
    for query, expected_id in test_queries:
        try:
            result_id = _find_restaurant_id(query)
            if query == "unknown location xyz":
                # For unknown locations, expect None
                if result_id is None:
                    print(f"✅ '{query}' -> None (expected for unknown location)")
                else:
                    print(f"⚠️ '{query}' -> {result_id} (found restaurant, but query seems generic)")
            else:
                # For known locations, expect a valid restaurant ID
                if result_id is not None:
                    print(f"✅ '{query}' -> ID {result_id}")
                else:
                    print(f"❌ '{query}' -> None (expected to find restaurant)")
                    return False
        except Exception as e:
            print(f"❌ Error testing '{query}': {e}")
            return False
    
    return True

def test_lookup_tool():
    """Test the lookup_restaurant_by_location tool"""
    print("\n🧪 Testing lookup_restaurant_by_location tool...")
    
    test_queries = [
        "times city",
        "vincom bà triệu", 
        "unknown location",
        "aeon mall"
    ]
    
    for query in test_queries:
        try:
            result = lookup_restaurant_by_location(query)
            if result.get("success"):
                restaurant_id = result["data"]["restaurant_id"]
                found = result["data"]["found"]
                print(f"✅ '{query}' -> ID {restaurant_id}, Found: {found}")
            else:
                print(f"❌ '{query}' -> Failed: {result.get('error', 'Unknown error')}")
                return False
        except Exception as e:
            print(f"❌ Error testing lookup for '{query}': {e}")
            return False
    
    return True

def test_vector_database_connection():
    """Test if we can connect to vector database with correct restaurant model"""
    print("\n🧪 Testing vector database connection...")
    
    try:
        # Try to create QdrantStore instance with restaurant-specific config
        # Use text-embedding-004 to match existing collection dimension
        from src.database.qdrant_store import QdrantStore
        restaurant_store = QdrantStore(
            embedding_model="text-embedding-004",
            output_dimensionality_query=768,
            collection_name="restaurants"
        )
        print("✅ Successfully connected to Qdrant vector database with restaurant model")
        
        # Try a simple search
        results = restaurant_store.search(namespace="restaurants", query="test", limit=1)
        print(f"✅ Search completed, found {len(results)} results")
        
        return True
        
    except Exception as e:
        print(f"⚠️ Vector database not available: {e}")
        print("ℹ️ This is normal if the restaurant data hasn't been embedded yet")
        return False

def main():
    """Run all integration tests"""
    print("🚀 Starting Restaurant Integration Tests")
    print("=" * 50)
    
    tests = [
        ("Restaurant Data Structure", test_restaurant_data_structure),
        ("Brand Extraction", test_restaurant_brand_extraction),
        ("Location Extraction", test_location_extraction),
        ("Vector Database Connection", test_vector_database_connection),
        ("Reservation Vector Search", test_reservation_fallback),
        ("Lookup Tool", test_lookup_tool)
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
        print("🎉 All tests passed!")
        print("\n📝 Next Steps:")
        print("1. Run the restaurant embedding script: python setup\\embedding-restaurant-data.py")
        print("2. Test the reservation system with vector search")
        print("3. Run unit tests: pytest tests\\unit_tests\\test_reservation_tools.py")
    else:
        print("⚠️ Some tests failed. Please check the issues above.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
