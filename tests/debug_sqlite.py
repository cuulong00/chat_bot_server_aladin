"""
Debug script cho SQLite database
"""
import os
import sqlite3

def debug_sqlite():
    """Debug SQLite database"""
    print("🔍 Debugging SQLite database...")
    
    # Kiểm tra xem file có tồn tại không
    db_files = ["travel2.sqlite", "travel2.backup.sqlite"]
    
    for db_file in db_files:
        if os.path.exists(db_file):
            print(f"✅ Found {db_file}")
            
            # Kết nối và kiểm tra tables
            try:
                conn = sqlite3.connect(db_file)
                cursor = conn.cursor()
                
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = cursor.fetchall()
                print(f"  Tables in {db_file}: {[t[0] for t in tables]}")
                
                # Kiểm tra tickets table cụ thể
                if ('tickets',) in tables:
                    cursor.execute("SELECT COUNT(*) FROM tickets;")
                    count = cursor.fetchone()[0]
                    print(f"  Tickets count: {count}")
                    
                    # Lấy sample data
                    cursor.execute("SELECT * FROM tickets LIMIT 3;")
                    sample = cursor.fetchall()
                    print(f"  Sample tickets: {sample}")
                
                conn.close()
                
            except Exception as e:
                print(f"  ❌ Error accessing {db_file}: {e}")
        else:
            print(f"❌ Missing {db_file}")
    
    # Thử download database
    print("\n🔄 Trying to download database...")
    try:
        from src.database.database import get_sqlite_db
        db_path = get_sqlite_db()
        print(f"✅ Database ready at: {db_path}")
    except Exception as e:
        print(f"❌ Download failed: {e}")

if __name__ == "__main__":
    debug_sqlite()
