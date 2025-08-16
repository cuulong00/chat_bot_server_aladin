"""
Script migrate dữ liệu từ travel2.sqlite sang PostgreSQL
Xóa toàn bộ dữ liệu cũ và import dữ liệu mới
"""
import os
import sqlite3
import requests
import pandas as pd
import sqlalchemy
from dotenv import load_dotenv
from typing import Dict, List

# Load environment variables
load_dotenv()

def download_sqlite_db(url: str, local_file: str) -> str:
    """Tải SQLite database từ URL"""
    if not os.path.exists(local_file):
        print(f"📥 Đang tải database từ {url}...")
        response = requests.get(url)
        response.raise_for_status()
        
        with open(local_file, "wb") as f:
            f.write(response.content)
        print(f"✅ Đã tải về {local_file}")
    else:
        print(f"📁 File {local_file} đã tồn tại")
    
    return local_file

def get_postgres_connection():
    """Tạo kết nối PostgreSQL"""
    db_uri = os.getenv("DATABASE_CONNECTION")
    if not db_uri:
        raise ValueError("DATABASE_CONNECTION không được thiết lập trong biến môi trường!")
    
    engine = sqlalchemy.create_engine(db_uri)
    return engine

def get_sqlite_tables(sqlite_path: str) -> List[str]:
    """Lấy danh sách bảng từ SQLite"""
    conn = sqlite3.connect(sqlite_path)
    try:
        tables_query = "SELECT name FROM sqlite_master WHERE type='table';"
        tables_df = pd.read_sql(tables_query, conn)
        return tables_df['name'].tolist()
    finally:
        conn.close()

def clean_postgres_tables(postgres_engine, tables_to_keep: List[str] = None):
    """Xóa tất cả bảng không cần thiết trong PostgreSQL"""
    if tables_to_keep is None:
        tables_to_keep = ['checkpoints', 'checkpoint_blobs', 'checkpoint_writes', 'store']
    
    print("🧹 Dọn dẹp PostgreSQL database...")
    
    with postgres_engine.connect() as conn:
        # Lấy danh sách tất cả bảng hiện tại
        inspector = sqlalchemy.inspect(postgres_engine)
        existing_tables = inspector.get_table_names()
        
        # Xóa các bảng không trong danh sách giữ lại
        tables_to_drop = [table for table in existing_tables if table not in tables_to_keep]
        
        if tables_to_drop:
            print(f"🗑️  Xóa {len(tables_to_drop)} bảng cũ: {', '.join(tables_to_drop)}")
            
            # Tắt foreign key constraints tạm thời
            conn.execute(sqlalchemy.text("SET session_replication_role = replica;"))
            
            try:
                for table in tables_to_drop:
                    conn.execute(sqlalchemy.text(f"DROP TABLE IF EXISTS {table} CASCADE;"))
                    print(f"   ✅ Đã xóa bảng: {table}")
                conn.commit()
            finally:
                # Bật lại foreign key constraints
                conn.execute(sqlalchemy.text("SET session_replication_role = DEFAULT;"))
        else:
            print("✅ Không có bảng nào cần xóa")

def migrate_table(sqlite_path: str, postgres_engine, table_name: str):
    """Migrate một bảng từ SQLite sang PostgreSQL"""
    print(f"📋 Migrating bảng: {table_name}")
    
    # Đọc dữ liệu từ SQLite
    sqlite_conn = sqlite3.connect(sqlite_path)
    try:
        # Lấy toàn bộ dữ liệu
        df = pd.read_sql(f"SELECT * FROM {table_name}", sqlite_conn)
        print(f"   📊 Đọc {len(df):,} dòng từ SQLite")
        
        if len(df) == 0:
            print(f"   ⚠️  Bảng {table_name} không có dữ liệu")
            return
        
        # Xử lý dữ liệu trước khi insert
        df = clean_dataframe(df)
        
        # Insert vào PostgreSQL
        with postgres_engine.connect() as pg_conn:
            # Sử dụng to_sql với if_exists='replace' để tạo bảng mới
            df.to_sql(
                table_name, 
                pg_conn, 
                if_exists='replace',  # Thay thế bảng nếu đã tồn tại
                index=False,
                method='multi',  # Faster bulk insert
                chunksize=1000   # Insert theo batch
            )
            
        print(f"   ✅ Đã insert {len(df):,} dòng vào PostgreSQL")
        
    except Exception as e:
        print(f"   ❌ Lỗi khi migrate bảng {table_name}: {e}")
        raise
    finally:
        sqlite_conn.close()

def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Làm sạch dữ liệu trước khi insert vào PostgreSQL"""
    # Thay thế các giá trị '\\N' bằng None (NULL)
    df = df.replace('\\N', None)
    df = df.replace('', None)
    
    # Chuyển đổi datetime columns
    datetime_columns = [
        'scheduled_departure', 'scheduled_arrival', 
        'actual_departure', 'actual_arrival',
        'book_date', 'created_at', 'updated_at'
    ]
    
    for col in datetime_columns:
        if col in df.columns:
            try:
                df[col] = pd.to_datetime(df[col], errors='coerce')
            except:
                pass
    
    # Xử lý các cột numeric
    numeric_columns = ['price', 'cost', 'amount', 'fee']
    for col in numeric_columns:
        if col in df.columns:
            try:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            except:
                pass
    
    return df

def verify_migration(postgres_engine, sqlite_path: str, table_names: List[str]):
    """Kiểm tra kết quả migration"""
    print("\n🔍 Kiểm tra kết quả migration...")
    print("=" * 60)
    
    sqlite_conn = sqlite3.connect(sqlite_path)
    
    try:
        for table_name in table_names:
            # Đếm dòng trong SQLite
            sqlite_count = pd.read_sql(f"SELECT COUNT(*) as count FROM {table_name}", sqlite_conn)['count'].iloc[0]
            
            # Đếm dòng trong PostgreSQL
            with postgres_engine.connect() as pg_conn:
                try:
                    pg_count = pd.read_sql(f"SELECT COUNT(*) as count FROM {table_name}", pg_conn)['count'].iloc[0]
                    
                    if sqlite_count == pg_count:
                        print(f"✅ {table_name}: {sqlite_count:,} dòng (SQLite) = {pg_count:,} dòng (PostgreSQL)")
                    else:
                        print(f"⚠️  {table_name}: {sqlite_count:,} dòng (SQLite) ≠ {pg_count:,} dòng (PostgreSQL)")
                        
                except Exception as e:
                    print(f"❌ {table_name}: Lỗi kiểm tra - {e}")
                    
    finally:
        sqlite_conn.close()

def create_indexes(postgres_engine, table_names: List[str]):
    """Tạo indexes cho các bảng quan trọng"""
    print("\n📇 Tạo indexes...")
    
    indexes = {
        'flights': ['flight_id', 'departure_airport', 'arrival_airport'],
        'bookings': ['booking_id', 'flight_id', 'user_id'],
        'hotels': ['hotel_id', 'location'],
        'cars': ['car_id', 'location'],
        'excursions': ['excursion_id', 'location']
    }
    
    with postgres_engine.connect() as conn:
        for table_name in table_names:
            if table_name in indexes:
                for column in indexes[table_name]:
                    try:
                        index_name = f"idx_{table_name}_{column}"
                        conn.execute(sqlalchemy.text(f"""
                            CREATE INDEX IF NOT EXISTS {index_name} 
                            ON {table_name} ({column})
                        """))
                        print(f"   ✅ Created index: {index_name}")
                    except Exception as e:
                        print(f"   ⚠️  Could not create index on {table_name}.{column}: {e}")
        
        conn.commit()

def main():
    """Hàm chính"""
    print("🚀 MIGRATE SQLITE TO POSTGRESQL")
    print("=" * 60)
    
    # URLs và files
    sqlite_url = "https://storage.googleapis.com/benchmarks-artifacts/travel-db/travel2.sqlite"
    local_sqlite_file = "travel2_migration.sqlite"
    
    try:
        # 1. Tải SQLite database
        print("📥 Step 1: Download SQLite database")
        sqlite_path = download_sqlite_db(sqlite_url, local_sqlite_file)
        
        # 2. Kết nối PostgreSQL
        print("\n🔗 Step 2: Connect to PostgreSQL")
        postgres_engine = get_postgres_connection()
        print("✅ Connected to PostgreSQL")
        
        # 3. Lấy danh sách bảng từ SQLite
        print("\n📋 Step 3: Get table list from SQLite")
        table_names = get_sqlite_tables(sqlite_path)
        print(f"Found {len(table_names)} tables: {', '.join(table_names)}")
        
        # 4. Dọn dẹp PostgreSQL
        print(f"\n🧹 Step 4: Clean PostgreSQL database")
        clean_postgres_tables(postgres_engine)
        
        # 5. Migrate từng bảng
        print(f"\n📦 Step 5: Migrate tables")
        for i, table_name in enumerate(table_names, 1):
            print(f"\n[{i}/{len(table_names)}] Migrating {table_name}...")
            migrate_table(sqlite_path, postgres_engine, table_name)
        
        # 6. Tạo indexes
        print(f"\n📇 Step 6: Create indexes")
        create_indexes(postgres_engine, table_names)
        
        # 7. Kiểm tra kết quả
        print(f"\n🔍 Step 7: Verify migration")
        verify_migration(postgres_engine, sqlite_path, table_names)
        
        print(f"\n🎉 MIGRATION HOÀN THÀNH!")
        print("=" * 60)
        print(f"✅ Đã migrate {len(table_names)} bảng từ SQLite sang PostgreSQL")
        print(f"✅ Database PostgreSQL đã sẵn sàng sử dụng")
        
    except Exception as e:
        print(f"\n❌ Migration thất bại: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        if os.path.exists(local_sqlite_file):
            os.remove(local_sqlite_file)
            print(f"\n🗑️  Đã xóa file tạm: {local_sqlite_file}")

if __name__ == "__main__":
    main()