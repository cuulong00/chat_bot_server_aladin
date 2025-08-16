"""
PostgreSQL Database Setup Script
Chuyển đổi từ SQLite sang PostgreSQL
"""
import os
import sqlite3
import pandas as pd
import requests
import sqlalchemy
from dotenv import load_dotenv
import tempfile

load_dotenv()

def setup_postgres_database():
    """Setup PostgreSQL database với dữ liệu từ SQLite demo"""
    
    # Lấy connection string PostgreSQL
    DB_URI = os.getenv("DATABASE_CONNECTION")
    if not DB_URI:
        raise ValueError("DATABASE_CONNECTION không được thiết lập trong .env")
    
    print("🚀 Setting up PostgreSQL database...")
    
    # Tạo SQLAlchemy engine
    engine = sqlalchemy.create_engine(DB_URI)
    
    # Tải SQLite demo database tạm thời
    db_url = "https://storage.googleapis.com/benchmarks-artifacts/travel-db/travel2.sqlite"
    
    with tempfile.NamedTemporaryFile(suffix='.sqlite', delete=False) as temp_file:
        temp_sqlite_path = temp_file.name
    
    try:
        print("📥 Downloading SQLite demo data...")
        response = requests.get(db_url)
        response.raise_for_status()
        
        with open(temp_sqlite_path, "wb") as f:
            f.write(response.content)
        
        # Kết nối SQLite để đọc dữ liệu
        print("📖 Reading data from SQLite...")
        sqlite_conn = sqlite3.connect(temp_sqlite_path)
        
        # Lấy danh sách các bảng
        tables = pd.read_sql(
            "SELECT name FROM sqlite_master WHERE type='table';", 
            sqlite_conn
        ).name.tolist()
        
        print(f"📋 Found tables: {tables}")
        
        # Đọc tất cả dữ liệu
        table_data = {}
        for table in tables:
            print(f"  - Reading table: {table}")
            table_data[table] = pd.read_sql(f"SELECT * FROM {table}", sqlite_conn)
        
        sqlite_conn.close()
        
        # Cập nhật thời gian cho phù hợp với hiện tại
        print("🕐 Updating timestamps...")
        if 'flights' in table_data:
            example_time = pd.to_datetime(
                table_data["flights"]["actual_departure"].replace("\\N", pd.NaT)
            ).max()
            current_time = pd.to_datetime("now").tz_localize(example_time.tz)
            time_diff = current_time - example_time
            
            # Cập nhật booking dates
            if 'bookings' in table_data:
                table_data["bookings"]["book_date"] = (
                    pd.to_datetime(table_data["bookings"]["book_date"].replace("\\N", pd.NaT), utc=True)
                    + time_diff
                )
            
            # Cập nhật flight times
            datetime_columns = [
                "scheduled_departure",
                "scheduled_arrival", 
                "actual_departure",
                "actual_arrival",
            ]
            for column in datetime_columns:
                if column in table_data["flights"].columns:
                    table_data["flights"][column] = (
                        pd.to_datetime(table_data["flights"][column].replace("\\N", pd.NaT)) 
                        + time_diff
                    )
        
        # Ghi dữ liệu vào PostgreSQL
        print("💾 Writing data to PostgreSQL...")
        with engine.connect() as conn:
            for table_name, df in table_data.items():
                print(f"  - Writing table: {table_name} ({len(df)} rows)")
                try:
                    # Chia nhỏ dữ liệu nếu quá lớn
                    chunk_size = 1000 if len(df) > 10000 else len(df)
                    
                    if len(df) > chunk_size:
                        print(f"    Splitting into chunks of {chunk_size}...")
                        for i in range(0, len(df), chunk_size):
                            chunk = df.iloc[i:i+chunk_size]
                            chunk.to_sql(
                                table_name, 
                                conn, 
                                if_exists="append" if i > 0 else "replace", 
                                index=False,
                                method='multi'
                            )
                            print(f"    Chunk {i//chunk_size + 1}: {len(chunk)} rows")
                    else:
                        df.to_sql(
                            table_name, 
                            conn, 
                            if_exists="replace", 
                            index=False,
                            method='multi'
                        )
                    print(f"    ✅ {table_name} completed")
                    conn.commit()
                    
                except Exception as table_error:
                    print(f"    ❌ Error writing {table_name}: {table_error}")
                    # Tiếp tục với bảng khác
                    continue
        
        print("✅ PostgreSQL database setup completed successfully!")
        print(f"📊 Tables created: {list(table_data.keys())}")
        
        # Hiển thị thống kê
        with engine.connect() as conn:
            for table_name in table_data.keys():
                result = conn.execute(sqlalchemy.text(f"SELECT COUNT(*) FROM {table_name}"))
                count = result.scalar()
                print(f"  - {table_name}: {count} records")
        
        engine.dispose()
        return True
        
    except Exception as e:
        print(f"❌ Error setting up PostgreSQL database: {e}")
        return False
        
    finally:
        # Xóa file SQLite tạm thời
        if os.path.exists(temp_sqlite_path):
            os.unlink(temp_sqlite_path)

def verify_postgres_setup():
    """Kiểm tra setup PostgreSQL"""
    print("\n🔍 Verifying PostgreSQL setup...")
    
    DB_URI = os.getenv("DATABASE_CONNECTION")
    if not DB_URI:
        print("❌ DATABASE_CONNECTION not set")
        return False
    
    try:
        engine = sqlalchemy.create_engine(DB_URI)
        
        with engine.connect() as conn:
            # Kiểm tra kết nối
            result = conn.execute(sqlalchemy.text("SELECT 1"))
            result.scalar()
            
            # Kiểm tra các bảng chính
            required_tables = ['flights', 'hotels', 'car_rentals', 'trip_recommendations']
            
            for table in required_tables:
                try:
                    result = conn.execute(sqlalchemy.text(f"SELECT COUNT(*) FROM {table}"))
                    count = result.scalar()
                    print(f"  ✅ {table}: {count} records")
                except Exception as e:
                    print(f"  ❌ {table}: {e}")
        
        engine.dispose()
        print("✅ PostgreSQL verification completed!")
        return True
        
    except Exception as e:
        print(f"❌ PostgreSQL verification failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 PostgreSQL Database Setup")
    print("=" * 50)
    
    if setup_postgres_database():
        verify_postgres_setup()
    else:
        print("❌ Setup failed!")
        exit(1)
