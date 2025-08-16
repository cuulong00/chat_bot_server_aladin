"""
Script kiểm tra cấu trúc bảng dữ liệu của travel2.sqlite
"""
import os
import sqlite3
import requests
import pandas as pd
from typing import Dict, List, Any

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

def get_table_info(db_path: str) -> Dict[str, Any]:
    """Lấy thông tin chi tiết về các bảng trong database"""
    conn = sqlite3.connect(db_path)
    
    try:
        # Lấy danh sách tất cả bảng
        tables_query = "SELECT name FROM sqlite_master WHERE type='table';"
        tables_df = pd.read_sql(tables_query, conn)
        table_names = tables_df['name'].tolist()
        
        print(f"🗃️  Database có {len(table_names)} bảng:")
        for i, table in enumerate(table_names, 1):
            print(f"   {i}. {table}")
        print()
        
        table_info = {}
        
        for table_name in table_names:
            print(f"📋 Bảng: {table_name}")
            print("=" * 50)
            
            # Lấy cấu trúc bảng (schema)
            schema_query = f"PRAGMA table_info({table_name});"
            schema_df = pd.read_sql(schema_query, conn)
            
            print("🏗️  Cấu trúc bảng:")
            for _, row in schema_df.iterrows():
                nullable = "NULL" if row['notnull'] == 0 else "NOT NULL"
                default = f" DEFAULT {row['dflt_value']}" if row['dflt_value'] is not None else ""
                pk = " 🔑 PRIMARY KEY" if row['pk'] == 1 else ""
                print(f"   • {row['name']}: {row['type']} {nullable}{default}{pk}")
            
            # Đếm số dòng
            count_query = f"SELECT COUNT(*) as count FROM {table_name};"
            count_result = pd.read_sql(count_query, conn)
            row_count = count_result['count'].iloc[0]
            print(f"\n📊 Số dòng dữ liệu: {row_count:,}")
            
            # Lấy 3 dòng mẫu
            if row_count > 0:
                sample_query = f"SELECT * FROM {table_name} LIMIT 3;"
                sample_df = pd.read_sql(sample_query, conn)
                print(f"\n📝 Dữ liệu mẫu (3 dòng đầu):")
                print(sample_df.to_string(index=False, max_cols=10))
            
            # Lưu thông tin vào dict
            table_info[table_name] = {
                'schema': schema_df.to_dict('records'),
                'row_count': row_count,
                'sample_data': sample_df.to_dict('records') if row_count > 0 else []
            }
            
            print("\n" + "="*70 + "\n")
        
        return table_info
        
    except Exception as e:
        print(f"❌ Lỗi khi phân tích database: {e}")
        return {}
    finally:
        conn.close()

def analyze_relationships(db_path: str):
    """Phân tích mối quan hệ giữa các bảng"""
    conn = sqlite3.connect(db_path)
    
    try:
        print("🔗 Phân tích mối quan hệ giữa các bảng:")
        print("=" * 50)
        
        # Lấy danh sách tất cả bảng
        tables_query = "SELECT name FROM sqlite_master WHERE type='table';"
        tables_df = pd.read_sql(tables_query, conn)
        table_names = tables_df['name'].tolist()
        
        for table_name in table_names:
            # Lấy foreign key constraints
            fk_query = f"PRAGMA foreign_key_list({table_name});"
            fk_df = pd.read_sql(fk_query, conn)
            
            if not fk_df.empty:
                print(f"📋 Bảng {table_name} có foreign keys:")
                for _, fk in fk_df.iterrows():
                    print(f"   • {fk['from']} → {fk['table']}.{fk['to']}")
            
        # Phân tích các cột có thể liên quan dựa trên tên
        print(f"\n🔍 Phân tích các cột có thể liên quan (dựa trên tên):")
        all_columns = {}
        
        for table_name in table_names:
            schema_query = f"PRAGMA table_info({table_name});"
            schema_df = pd.read_sql(schema_query, conn)
            all_columns[table_name] = schema_df['name'].tolist()
        
        # Tìm các cột có tên tương tự
        potential_relationships = []
        for table1, cols1 in all_columns.items():
            for table2, cols2 in all_columns.items():
                if table1 != table2:
                    for col1 in cols1:
                        for col2 in cols2:
                            if col1 == col2 or (col1.endswith('_id') and col1[:-3] in table2):
                                potential_relationships.append(f"{table1}.{col1} ↔ {table2}.{col2}")
        
        if potential_relationships:
            print("   Các mối quan hệ có thể:")
            for rel in set(potential_relationships):
                print(f"   • {rel}")
        
    except Exception as e:
        print(f"❌ Lỗi khi phân tích mối quan hệ: {e}")
    finally:
        conn.close()

def generate_summary_report(table_info: Dict[str, Any]):
    """Tạo báo cáo tổng kết"""
    print("📊 BÁO CÁO TỔNG KẾT")
    print("=" * 50)
    
    total_tables = len(table_info)
    total_rows = sum(info['row_count'] for info in table_info.values())
    
    print(f"📈 Tổng số bảng: {total_tables}")
    print(f"📈 Tổng số dòng dữ liệu: {total_rows:,}")
    print()
    
    print("📋 Chi tiết từng bảng:")
    for table_name, info in table_info.items():
        column_count = len(info['schema'])
        print(f"   • {table_name}: {column_count} cột, {info['row_count']:,} dòng")
    
    print()
    print("🎯 Mục đích sử dụng có thể:")
    print("   • Hệ thống đặt vé du lịch")
    print("   • Quản lý chuyến bay, khách sạn, xe thuê")
    print("   • Theo dõi booking và thanh toán")

def main():
    """Hàm chính"""
    print("🔍 PHÂN TÍCH CẤU TRÚC DATABASE TRAVEL2.SQLITE")
    print("=" * 60)
    
    # URL và file local
    db_url = "https://storage.googleapis.com/benchmarks-artifacts/travel-db/travel2.sqlite"
    local_db_file = "travel2_analysis.sqlite"
    
    try:
        # Tải database
        db_path = download_sqlite_db(db_url, local_db_file)
        
        print()
        # Phân tích cấu trúc bảng
        table_info = get_table_info(db_path)
        
        # Phân tích mối quan hệ
        analyze_relationships(db_path)
        
        print()
        # Tạo báo cáo tổng kết
        generate_summary_report(table_info)
        
        print(f"\n✅ Hoàn thành phân tích! File database được lưu tại: {local_db_file}")
        
    except Exception as e:
        print(f"❌ Lỗi: {e}")
    finally:
        # Cleanup: xóa file tạm nếu muốn
        # if os.path.exists(local_db_file):
        #     os.remove(local_db_file)
        #     print(f"🗑️  Đã xóa file tạm {local_db_file}")
        pass

if __name__ == "__main__":
    main()