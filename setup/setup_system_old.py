"""
Setup script chỉ cho PostgreSQL và Qdrant - không còn SQLite
"""
import os
import sys

# Thêm root directory vào Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def setup_postgresql():
    """Thiết lập và kiểm tra PostgreSQL connection"""
    print("🔧 Setting up PostgreSQL connection...")
    
    try:
        from src.database.database import get_db_connection
        import sqlalchemy
        
        engine = get_db_connection()
        
        # Test connection
        with engine.connect() as conn:
            result = conn.execute(sqlalchemy.text("SELECT 1"))
            result.fetchone()
        
        # Liệt kê các bảng có sẵn
        with engine.connect() as conn:
            result = conn.execute(sqlalchemy.text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name
            """))
            tables = [row[0] for row in result.fetchall()]
            print(f"📋 Available PostgreSQL tables: {tables}")
        
        engine.dispose()
        print("✅ PostgreSQL connection successful")
        return True
        
    except Exception as e:
        print(f"❌ Error connecting to PostgreSQL: {e}")
        print("💡 Make sure DATABASE_CONNECTION is set in .env file")
        return False

def setup_memory_system():
    """Thiết lập memory system với Qdrant"""
    print("\n🧠 Setting up memory system...")
    
    try:
        # Chạy fix vector collection
        from fix_vector_collection import fix_vector_collection
        fix_vector_collection()
        print("✅ Memory system ready")
        return True
    except Exception as e:
        print(f"❌ Error setting up memory system: {e}")
        return False

def setup_checkpointer():
    """Thiết lập PostgreSQL checkpointer"""
    print("\n🔧 Setting up PostgreSQL checkpointer...")
    
    try:
        from src.database.database import checkpointer
        if checkpointer:
            print("✅ PostgreSQL checkpointer ready")
            return True
        else:
            print("⚠️  PostgreSQL checkpointer not available")
            return False
    except Exception as e:
        print(f"❌ Error setting up checkpointer: {e}")
        return False

def run_setup():
    """Chạy toàn bộ setup chỉ với PostgreSQL và Qdrant"""
    print("🚀 Running PostgreSQL + Qdrant setup...")
    
    postgres_ok = setup_postgresql()
    memory_ok = setup_memory_system()  
    checkpointer_ok = setup_checkpointer()
    
    if postgres_ok and memory_ok:
        print("\n✅ System setup completed successfully!")
        if not checkpointer_ok:
            print("⚠️  Checkpointer setup có vấn đề, nhưng system vẫn có thể hoạt động")
        return True
    else:
        print("\n❌ System setup failed!")
        return False

if __name__ == "__main__":
    run_setup()
