"""
PostgreSQL + Qdrant system setup
"""
import os
import sys
import traceback

# Thêm root directory vào Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_environment():
    """Kiểm tra các biến môi trường cần thiết"""
    print("🌍 Checking environment setup...")
    
    # Sử dụng tên biến từ file .env thực tế
    required_vars = [
        "QDRANT_HOST", "QDRANT_PORT", 
        "DATABASE_CONNECTION"  # Thay vì POSTGRES_HOST, POSTGRES_DB, etc.
    ]
    
    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)
    
    if missing:
        print(f"❌ Missing environment variables: {missing}")
        print("💡 Checking alternative variables...")
        # Kiểm tra biến backup
        if os.getenv("DATABASE_CONNECTION"):
            print("✅ DATABASE_CONNECTION found")
        else:
            return False
    
    print("✅ Environment variables configured")
    return True

def test_postgres_connection():
    """Test PostgreSQL connection"""
    try:
        import sqlalchemy
        from dotenv import load_dotenv
        
        load_dotenv()
        db_uri = os.getenv("DATABASE_CONNECTION")
        
        if not db_uri:
            print("❌ DATABASE_CONNECTION not found")
            return False
        
        engine = sqlalchemy.create_engine(db_uri)
        with engine.connect() as conn:
            # Simple test query
            result = conn.execute(sqlalchemy.text("SELECT 1"))
            result.fetchone()
        
        print("✅ PostgreSQL connection successful")
        return True
        
    except Exception as e:
        print(f"❌ PostgreSQL connection failed: {e}")
        return False

def setup_postgresql_system():
    """Setup PostgreSQL system cho LangGraph"""
    print("🔧 Setting up PostgreSQL system...")
    
    try:
        # Test connection first
        if not test_postgres_connection():
            print("❌ PostgreSQL connection failed")
            return False
        
        # Import database components
        from src.database.database import checkpointer
        from src.database.qdrant_store import retriever
        
        # Check checkpointer
        if checkpointer is None:
            print("❌ PostgreSQL checkpointer không khả dụng")
            return False
        
        # Test vector store
        if retriever is None:
            print("❌ Vector store không khả dụng")
            return False
        
        # Test graph compilation
        from src.graphs.travel.travel_graph import graph
        if graph is None:
            print("❌ Graph compilation failed")
            return False
            
        print("✅ PostgreSQL system ready")
        return True
        
    except Exception as e:
        print(f"❌ PostgreSQL setup failed: {e}")
        traceback.print_exc()
        return False

def setup_memory_system():
    """Setup memory system với Qdrant"""
    print("🧠 Setting up memory system...")
    
    try:
        # Test memory tools
        from src.tools.memory_tools import save_user_preference, get_user_profile
        
        # Quick test
        test_result = save_user_preference.invoke({
            "user_id": "setup_test_user",
            "preference_type": "system_test", 
            "content": "test setup",
            "context": "system setup verification"
        })
        print(f"✅ Memory test: {test_result}")
        
        # Test retrieval
        profile = get_user_profile.invoke({
            "user_id": "setup_test_user",
            "query_context": "test"
        })
        print(f"✅ Profile retrieval: {profile[:50]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Error setting up memory system: {e}")
        traceback.print_exc()
        return False

def fix_vector_collection():
    """Fix vector collection size"""
    print("🔧 Fixing vector collection size...")
    
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.http.models import Distance, VectorParams
        from dotenv import load_dotenv
        
        load_dotenv()
        
        qdrant_client = QdrantClient(
            host=os.getenv("QDRANT_HOST", "69.197.187.234"),
            port=int(os.getenv("QDRANT_PORT", "6333"))
        )
        
        collection_name = "user_memory"
        
        try:
            collection_info = qdrant_client.get_collection(collection_name)
            current_size = collection_info.config.params.vectors.size
            if current_size == 3072:
                print("✅ Collection already has correct size")
                return True
        except:
            pass
        
        # Recreate with correct size
        try:
            qdrant_client.delete_collection(collection_name)
        except:
            pass
            
        print("Creating new collection...")
        qdrant_client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=3072, distance=Distance.COSINE),
        )
        print("✅ New collection created")
        return True
        
    except Exception as e:
        print(f"❌ Error fixing collection: {e}")
        return False

def run_setup():
    """Main setup function"""
    print("🚀 Running PostgreSQL + Qdrant system setup...")
    print("="*50)
    
    success = True
    
    # Check environment
    if not check_environment():
        print("⚠️ Environment check failed, but continuing...")
    
    # Setup PostgreSQL system
    if not setup_postgresql_system():
        print("⚠️ PostgreSQL setup failed, but continuing...")
        success = False
    
    # Setup memory system (this is most important)
    if not setup_memory_system():
        print("❌ Memory system setup failed")
        success = False
        
    # Fix vector collection
    if not fix_vector_collection():
        print("⚠️ Vector collection fix failed, but continuing...")
    
    print("="*50)
    if success:
        print("✅ All systems ready!")
    else:
        print("⚠️ System setup completed with some issues!")
    
    return success

if __name__ == "__main__":
    run_setup()