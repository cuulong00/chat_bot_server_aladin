#!/usr/bin/env python3
"""
Test script để kiểm tra tất cả tools đã được chuyển đổi thành công sang PostgreSQL
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

def test_tool_imports():
    """Kiểm tra tất cả tools có thể import và không còn SQLite dependencies"""
    print("=== KIỂM TRA IMPORT TOOLS ===")
    
    try:
        from src.tools.car_tools import search_car_rentals, book_car_rental
        print("✅ Car tools imported successfully")
    except Exception as e:
        print(f"❌ Car tools import failed: {e}")
        return False
    
    try:
        from src.tools.hotel_tools import search_hotels, book_hotel
        print("✅ Hotel tools imported successfully")
    except Exception as e:
        print(f"❌ Hotel tools import failed: {e}")
        return False
        
    try:
        from src.tools.excursion_tools import search_trip_recommendations, book_excursion
        print("✅ Excursion tools imported successfully")
    except Exception as e:
        print(f"❌ Excursion tools import failed: {e}")
        return False
        
    try:
        from src.tools.flight_tools import search_flights, fetch_user_flight_information
        print("✅ Flight tools imported successfully")
    except Exception as e:
        print(f"❌ Flight tools import failed: {e}")
        return False
        
    try:
        from src.tools.memory_tools import save_user_preference, get_user_profile
        print("✅ Memory tools imported successfully")
    except Exception as e:
        print(f"❌ Memory tools import failed: {e}")
        return False
        
    return True

def check_sqlite_references():
    """Kiểm tra không còn SQLite references trong các file tools chính"""
    print("\n=== KIỂM TRA SQLITE REFERENCES ===")
    
    import glob
    tool_files = glob.glob("src/tools/*.py")
    
    sqlite_found = False
    for file_path in tool_files:
        if "sqlite" in file_path.lower():
            continue  # Skip backup files
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            if 'sqlite3' in content and '__init__.py' not in file_path:
                print(f"❌ Found sqlite3 reference in {file_path}")
                sqlite_found = True
            elif 'travel2.sqlite' in content:
                print(f"❌ Found travel2.sqlite reference in {file_path}")
                sqlite_found = True
                
        except Exception as e:
            print(f"⚠️  Could not check {file_path}: {e}")
    
    if not sqlite_found:
        print("✅ No SQLite references found in tool files")
    
    return not sqlite_found

def test_database_connection():
    """Kiểm tra kết nối PostgreSQL"""
    print("\n=== KIỂM TRA KẾT NỐI DATABASE ===")
    
    db_uri = os.getenv("DATABASE_CONNECTION")
    if not db_uri:
        print("❌ DATABASE_CONNECTION không được thiết lập trong .env")
        return False
    
    try:
        from src.database.database import get_db_connection
        import sqlalchemy
        engine = get_db_connection()
        
        with engine.connect() as conn:
            result = conn.execute(sqlalchemy.text("SELECT 1"))
            result.fetchone()
        
        engine.dispose()
        print("✅ PostgreSQL connection successful")
        return True
        
    except Exception as e:
        print(f"❌ PostgreSQL connection failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 KIỂM TRA CHUYỂN ĐỔI TOOLS SANG POSTGRESQL")
    print("=" * 50)
    
    all_passed = True
    
    # Test 1: Import all tools
    if not test_tool_imports():
        all_passed = False
    
    # Test 2: Check for SQLite references
    if not check_sqlite_references():
        all_passed = False
        
    # Test 3: Test database connection
    if not test_database_connection():
        all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 TẤT CẢ TESTS PASSED! Tools đã được chuyển đổi thành công sang PostgreSQL.")
    else:
        print("❌ MỘT SỐ TESTS FAILED! Vui lòng kiểm tra lại.")
        sys.exit(1)

if __name__ == "__main__":
    main()
