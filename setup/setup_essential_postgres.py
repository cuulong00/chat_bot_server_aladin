"""
Simplified PostgreSQL Database Setup Script
Chỉ setup các bảng chính cần thiết cho chatbot
"""
import os
import sqlite3
import pandas as pd
import requests
import sqlalchemy
from dotenv import load_dotenv
import tempfile

load_dotenv()

def setup_essential_tables():
    """Setup chỉ các bảng cần thiết cho chatbot"""
    
    # Lấy connection string PostgreSQL
    DB_URI = os.getenv("DATABASE_CONNECTION")
    if not DB_URI:
        raise ValueError("DATABASE_CONNECTION không được thiết lập trong .env")
    
    print("🚀 Setting up essential PostgreSQL tables...")
    
    # Tạo SQLAlchemy engine
    engine = sqlalchemy.create_engine(DB_URI)
    
    # Test connection first
    try:
        with engine.connect() as conn:
            result = conn.execute(sqlalchemy.text("SELECT 1"))
            result.scalar()
        print("✅ PostgreSQL connection successful")
    except Exception as e:
        print(f"❌ PostgreSQL connection failed: {e}")
        return False
    
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
        print("📖 Reading essential data from SQLite...")
        sqlite_conn = sqlite3.connect(temp_sqlite_path)
        
        # Chỉ load các bảng cần thiết
        essential_tables = [
            'flights',
            'hotels', 
            'car_rentals',
            'trip_recommendations'
        ]
        
        table_data = {}
        for table in essential_tables:
            try:
                print(f"  - Reading table: {table}")
                df = pd.read_sql(f"SELECT * FROM {table}", sqlite_conn)
                table_data[table] = df
                print(f"    Loaded {len(df)} records")
            except Exception as e:
                print(f"    ⚠️  Could not load {table}: {e}")
        
        sqlite_conn.close()
        
        # Cập nhật thời gian cho phù hợp với hiện tại (chỉ cho flights)
        if 'flights' in table_data:
            print("🕐 Updating flight timestamps...")
            flights_df = table_data['flights']
            
            # Chỉ cập nhật nếu có dữ liệu thời gian
            datetime_columns = [
                "scheduled_departure",
                "scheduled_arrival", 
                "actual_departure",
                "actual_arrival",
            ]
            
            try:
                example_time = pd.to_datetime(
                    flights_df["actual_departure"].replace("\\N", pd.NaT)
                ).max()
                current_time = pd.to_datetime("now").tz_localize(example_time.tz)
                time_diff = current_time - example_time
                
                for column in datetime_columns:
                    if column in flights_df.columns:
                        flights_df[column] = (
                            pd.to_datetime(flights_df[column].replace("\\N", pd.NaT)) 
                            + time_diff
                        )
                        
                table_data['flights'] = flights_df
                print("    ✅ Flight timestamps updated")
                
            except Exception as e:
                print(f"    ⚠️  Could not update timestamps: {e}")
        
        # Ghi dữ liệu vào PostgreSQL
        print("💾 Writing essential data to PostgreSQL...")
        with engine.connect() as conn:
            for table_name, df in table_data.items():
                try:
                    print(f"  - Writing {table_name} ({len(df)} rows)...")
                    
                    # Giới hạn số lượng records để tránh timeout
                    if len(df) > 1000:
                        df_sample = df.head(1000)
                        print(f"    Taking sample of 1000 records from {len(df)}")
                    else:
                        df_sample = df
                    
                    df_sample.to_sql(
                        table_name, 
                        conn, 
                        if_exists="replace", 
                        index=False
                    )
                    
                    conn.commit()
                    print(f"    ✅ {table_name} completed")
                    
                except Exception as table_error:
                    print(f"    ❌ Error writing {table_name}: {table_error}")
                    continue
        
        print("✅ Essential PostgreSQL tables setup completed!")
        
        # Hiển thị thống kê
        print("\n📊 Table Statistics:")
        with engine.connect() as conn:
            for table_name in table_data.keys():
                try:
                    result = conn.execute(sqlalchemy.text(f"SELECT COUNT(*) FROM {table_name}"))
                    count = result.scalar()
                    print(f"  - {table_name}: {count} records")
                except Exception as e:
                    print(f"  - {table_name}: Error - {e}")
        
        engine.dispose()
        return True
        
    except Exception as e:
        print(f"❌ Error setting up essential tables: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Xóa file SQLite tạm thời
        if os.path.exists(temp_sqlite_path):
            os.unlink(temp_sqlite_path)

def test_essential_tools():
    """Test các tools chính với PostgreSQL"""
    print("\n🧪 Testing essential tools with PostgreSQL...")
    
    try:
        from src.tools.flight_tools import search_flights
        from src.tools.car_tools import search_car_rentals
        from src.tools.hotel_tools import search_hotels
        from src.tools.excursion_tools import search_trip_recommendations
        
        print("  - Testing flight search...")
        flights = search_flights.invoke({"departure_airport": "JFK"})
        print(f"    Found {len(flights)} flights")
        
        print("  - Testing car rental search...")
        cars = search_car_rentals.invoke({"location": "New York"})
        print(f"    Found {len(cars)} car rentals")
        
        print("  - Testing hotel search...")
        hotels = search_hotels.invoke({"location": "New York"})
        print(f"    Found {len(hotels)} hotels")
        
        print("  - Testing excursion search...")
        excursions = search_trip_recommendations.invoke({"location": "New York"})
        print(f"    Found {len(excursions)} trip recommendations")
        
        print("✅ All essential tools working with PostgreSQL!")
        return True
        
    except Exception as e:
        print(f"❌ Tool testing failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 Essential PostgreSQL Database Setup")
    print("=" * 50)
    
    if setup_essential_tables():
        test_essential_tools()
    else:
        print("❌ Setup failed!")
        exit(1)
