"""
Test memory system only - không cần SQLite/flight data
"""
import os
import sys

# Thêm root directory vào Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_memory_and_vector_only():
    """Test chỉ memory system và vector store - không test flight tools"""
    print("🧪 Testing Memory & Vector Systems Only...")
    
    # Test 1: Vector Store (company policies)
    print("\n1. Testing Vector Store (Company Policies)...")
    try:
        from tests.vector_store_db import lookup_policy
        
        test_queries = [
            "Can I change my flight booking?",
            "What is the refund policy?",
            "How to cancel a reservation?"
        ]
        
        for query in test_queries:
            result = lookup_policy.invoke({"query": query})
            print(f"  Query: {query}")
            print(f"  Result: {result[:100]}...")
            print()
            
        print("  ✅ Vector store test passed!")
        
    except Exception as e:
        print(f"  ❌ Vector store test failed: {e}")
        return False
    
    # Test 2: Memory Tools
    print("\n2. Testing Memory Tools...")
    try:
        from src.tools.memory_tools import save_user_preference, get_user_profile
        
        test_user_id = "memory_test_user"
        
        # Lưu preferences
        preferences = [
            ("dietary_preference", "vegetarian", "health choice"),
            ("seat_preference", "window seat", "likes the view"),
            ("travel_style", "budget-friendly", "cost conscious")
        ]
        
        print("  Saving preferences...")
        for pref_type, content, context in preferences:
            result = save_user_preference.invoke({
                "user_id": test_user_id,
                "preference_type": pref_type,
                "content": content,
                "context": context
            })
            print(f"    ✅ {result}")
        
        # Truy xuất profile
        print("  Retrieving user profile...")
        profile = get_user_profile.invoke({
            "user_id": test_user_id,
            "query_context": "travel planning"
        })
        print(f"    Profile: {profile}")
        
        print("  ✅ Memory tools test passed!")
        
    except Exception as e:
        print(f"  ❌ Memory tools test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 3: Vector Database Info
    print("\n3. Testing Vector Database Connection...")
    try:
        from qdrant_client import QdrantClient
        from dotenv import load_dotenv
        
        load_dotenv()
        
        QDRANT_HOST = os.getenv("QDRANT_HOST", "69.197.187.234")
        QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
        
        client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        
        # List collections
        collections = client.get_collections()
        print(f"  Available collections: {[c.name for c in collections.collections]}")
        
        # Check specific collections
        expected_collections = ["user_memory", "company_policies"]
        for collection_name in expected_collections:
            try:
                info = client.get_collection(collection_name)
                print(f"  ✅ {collection_name}: {info.points_count} points, vector size: {info.config.params.vectors.size}")
            except Exception as e:
                print(f"  ❌ {collection_name}: {e}")
        
        print("  ✅ Vector database test passed!")
        
    except Exception as e:
        print(f"  ❌ Vector database test failed: {e}")
        return False
    
    return True

def test_postgres_connection():
    """Test PostgreSQL connection"""
    print("\n4. Testing PostgreSQL Connection...")
    try:
        from dotenv import load_dotenv
        import sqlalchemy
        import pandas as pd
        
        load_dotenv()
        
        DB_URI = os.getenv("DATABASE_CONNECTION")
        if not DB_URI:
            print("  ❌ DATABASE_CONNECTION not found in .env")
            return False
        
        engine = sqlalchemy.create_engine(DB_URI)
        
        # Test connection
        with engine.connect() as conn:
            # Check if we can query
            result = pd.read_sql("SELECT 1 as test", conn)
            print(f"  ✅ Connection successful: {result['test'].iloc[0]}")
            
            # List tables
            tables_query = """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            """
            tables_df = pd.read_sql(tables_query, conn)
            tables = tables_df['table_name'].tolist()
            print(f"  📋 Available tables: {tables[:10]}...")  # Show first 10
        
        engine.dispose()
        print("  ✅ PostgreSQL test passed!")
        return True
        
    except Exception as e:
        print(f"  ❌ PostgreSQL test failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Testing Core Systems (No SQLite dependency)...\n")
    
    # Setup memory system if needed
    try:
        from fix_vector_collection import fix_vector_collection
        fix_vector_collection()
        print("✅ Vector collection setup completed\n")
    except Exception as e:
        print(f"⚠️ Vector setup warning: {e}\n")
    
    # Run tests
    memory_ok = test_memory_and_vector_only()
    postgres_ok = test_postgres_connection()
    
    print("\n" + "=" * 50)
    
    if memory_ok and postgres_ok:
        print("✅ All core system tests passed!")
        print("🎉 Your memory system is ready to use!")
    else:
        print("❌ Some tests failed!")
        if not memory_ok:
            print("  - Memory/Vector system needs attention")
        if not postgres_ok:
            print("  - PostgreSQL connection needs attention")
