"""
Migration script để chuyển data từ SQLite sang PostgreSQL
"""
import os
import sys
import sqlite3
import pandas as pd
import sqlalchemy
from dotenv import load_dotenv

# Thêm root directory vào Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

def migrate_sqlite_to_postgres():
    """Migrate dữ liệu từ SQLite sang PostgreSQL"""
    print("🔄 Migrating data from SQLite to PostgreSQL...")
    
    # Lấy connection strings
    postgres_uri = os.getenv("DATABASE_CONNECTION")
    if not postgres_uri:
        print("❌ DATABASE_CONNECTION not found in .env")
        return False
    
    # Kiểm tra SQLite database
    sqlite_db = "travel2.sqlite"
    if not os.path.exists(sqlite_db):
        print("❌ SQLite database not found, downloading...")
        try:
            from src.database.database import get_sqlite_db
            sqlite_db = get_sqlite_db()
        except Exception as e:
            print(f"❌ Failed to get SQLite database: {e}")
            return False
    
    try:
        # Kết nối databases
        sqlite_conn = sqlite3.connect(sqlite_db)
        postgres_engine = sqlalchemy.create_engine(postgres_uri)
        
        # Lấy danh sách tables từ SQLite
        tables_query = "SELECT name FROM sqlite_master WHERE type='table';"
        tables_df = pd.read_sql(tables_query, sqlite_conn)
        tables = tables_df['name'].tolist()
        
        print(f"📋 Found {len(tables)} tables to migrate: {tables}")
        
        # Migrate từng table
        migrated_tables = []
        for table in tables:
            try:
                print(f"🔄 Migrating table: {table}")
                
                # Đọc data từ SQLite
                df = pd.read_sql(f"SELECT * FROM {table}", sqlite_conn)
                print(f"  📊 {table}: {len(df)} rows")
                
                # Ghi vào PostgreSQL (replace nếu table đã tồn tại)
                df.to_sql(table, postgres_engine, if_exists='replace', index=False)
                print(f"  ✅ {table}: migrated successfully")
                migrated_tables.append(table)
                
            except Exception as e:
                print(f"  ❌ {table}: migration failed - {e}")
        
        sqlite_conn.close()
        postgres_engine.dispose()
        
        print(f"\n✅ Migration completed! {len(migrated_tables)}/{len(tables)} tables migrated")
        print(f"✅ Migrated tables: {migrated_tables}")
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False

def verify_postgres_data():
    """Verify dữ liệu trong PostgreSQL"""
    print("\n🔍 Verifying PostgreSQL data...")
    
    postgres_uri = os.getenv("DATABASE_CONNECTION")
    if not postgres_uri:
        print("❌ DATABASE_CONNECTION not found")
        return False
    
    try:
        engine = sqlalchemy.create_engine(postgres_uri)
        
        # Kiểm tra tables
        with engine.connect() as conn:
            # Lấy danh sách tables
            tables_query = """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            """
            tables_df = pd.read_sql(tables_query, conn)
            tables = tables_df['table_name'].tolist()
            
            print(f"📋 PostgreSQL tables: {tables}")
            
            # Kiểm tra một số tables quan trọng
            important_tables = ['tickets', 'flights', 'hotels', 'cars']
            for table in important_tables:
                if table in tables:
                    count_query = f"SELECT COUNT(*) as count FROM {table}"
                    count_df = pd.read_sql(count_query, conn)
                    count = count_df['count'].iloc[0]
                    print(f"  ✅ {table}: {count} rows")
                else:
                    print(f"  ❌ {table}: not found")
        
        engine.dispose()
        return True
        
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Starting SQLite to PostgreSQL migration...\n")
    
    success = migrate_sqlite_to_postgres()
    
    if success:
        verify_postgres_data()
        print("\n✅ Migration process completed!")
    else:
        print("\n❌ Migration process failed!")
