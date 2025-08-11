"""
Script xác định bảng chính trong travel2.sqlite database
"""
import os
import sqlite3
import requests
import pandas as pd
from typing import Dict, List, Tuple

def download_and_analyze():
    """Tải và phân tích database để xác định bảng chính"""
    
    # Tải database
    url = "https://storage.googleapis.com/benchmarks-artifacts/travel-db/travel2.sqlite"
    local_file = "travel2_temp.sqlite"
    
    if not os.path.exists(local_file):
        print("📥 Downloading database...")
        response = requests.get(url)
        response.raise_for_status()
        with open(local_file, "wb") as f:
            f.write(response.content)
    
    conn = sqlite3.connect(local_file)
    
    try:
        # Lấy danh sách bảng và số dòng
        tables_query = "SELECT name FROM sqlite_master WHERE type='table';"
        tables = pd.read_sql(tables_query, conn)['name'].tolist()
        
        print("🗃️  PHÂN TÍCH BẢNG CHÍNH")
        print("=" * 60)
        
        table_analysis = []
        
        for table in tables:
            # Đếm số dòng
            count_query = f"SELECT COUNT(*) as count FROM {table};"
            count = pd.read_sql(count_query, conn)['count'].iloc[0]
            
            # Lấy cấu trúc bảng
            schema_query = f"PRAGMA table_info({table});"
            schema = pd.read_sql(schema_query, conn)
            
            # Tìm primary key
            pk_columns = schema[schema['pk'] == 1]['name'].tolist()
            
            # Lấy mẫu dữ liệu để phân tích
            if count > 0:
                sample_query = f"SELECT * FROM {table} LIMIT 3;"
                sample = pd.read_sql(sample_query, conn)
                columns = list(sample.columns)
            else:
                columns = schema['name'].tolist()
            
            table_analysis.append({
                'table': table,
                'row_count': count,
                'column_count': len(columns),
                'primary_keys': pk_columns,
                'columns': columns
            })
        
        # Sắp xếp theo số dòng (quan trọng nhất)
        table_analysis.sort(key=lambda x: x['row_count'], reverse=True)
        
        print("\n📊 BẢNG THEO SỐ LƯỢNG DỮ LIỆU:")
        print("-" * 60)
        for i, table_info in enumerate(table_analysis, 1):
            importance = "🥇 CHÍNH" if i <= 3 else "🥈 PHỤ" if i <= 6 else "🥉 KHÁC"
            print(f"{importance} {table_info['table']}: {table_info['row_count']:,} dòng, {table_info['column_count']} cột")
            if table_info['primary_keys']:
                print(f"      🔑 Primary Keys: {', '.join(table_info['primary_keys'])}")
        
        # Phân tích mối quan hệ
        print(f"\n🔗 PHÂN TÍCH MỐI QUAN HỆ:")
        print("-" * 60)
        
        main_tables = []
        transaction_tables = []
        lookup_tables = []
        
        for table_info in table_analysis:
            table = table_info['table']
            columns = table_info['columns']
            count = table_info['row_count']
            
            # Phân loại dựa trên tên và cấu trúc
            if any(word in table.lower() for word in ['booking', 'reservation', 'order']):
                transaction_tables.append(table)
            elif any(word in table.lower() for word in ['flight', 'hotel', 'car', 'excursion']):
                if count > 100:  # Bảng dữ liệu chính
                    main_tables.append(table)
                else:  # Bảng lookup
                    lookup_tables.append(table)
            elif count < 50:  # Bảng lookup nhỏ
                lookup_tables.append(table)
            else:
                main_tables.append(table)
        
        print("🏢 BẢNG DỮ LIỆU CHÍNH (Master Data):")
        for table in main_tables:
            info = next(t for t in table_analysis if t['table'] == table)
            print(f"   • {table}: {info['row_count']:,} dòng - Chứa thông tin cơ bản")
        
        print(f"\n💳 BẢNG GIAO DỊCH (Transaction Data):")
        for table in transaction_tables:
            info = next(t for t in table_analysis if t['table'] == table)
            print(f"   • {table}: {info['row_count']:,} dòng - Chứa giao dịch/đặt chỗ")
        
        print(f"\n📚 BẢNG TRA CỨU (Lookup Tables):")
        for table in lookup_tables:
            info = next(t for t in table_analysis if t['table'] == table)
            print(f"   • {table}: {info['row_count']:,} dòng - Dữ liệu tham chiếu")
        
        # Kết luận
        print(f"\n🎯 KẾT LUẬN:")
        print("=" * 60)
        most_important = table_analysis[0]['table']
        print(f"🥇 BẢNG QUAN TRỌNG NHẤT: {most_important}")
        print(f"   → {table_analysis[0]['row_count']:,} dòng dữ liệu")
        print(f"   → {table_analysis[0]['column_count']} cột")
        
        if transaction_tables:
            print(f"\n💼 BẢNG GIAO DỊCH CHÍNH: {transaction_tables[0]}")
            trans_info = next(t for t in table_analysis if t['table'] == transaction_tables[0])
            print(f"   → {trans_info['row_count']:,} giao dịch")
        
        print(f"\n📋 THỨ TỰ ƯU TIÊN MIGRATE:")
        priority_order = []
        
        # 1. Bảng lookup trước (để tạo foreign key)
        priority_order.extend(lookup_tables)
        # 2. Bảng dữ liệu chính
        priority_order.extend(main_tables)
        # 3. Bảng giao dịch cuối
        priority_order.extend(transaction_tables)
        
        for i, table in enumerate(priority_order, 1):
            info = next(t for t in table_analysis if t['table'] == table)
            print(f"   {i}. {table} ({info['row_count']:,} dòng)")
        
        return table_analysis, priority_order
        
    finally:
        conn.close()
        if os.path.exists(local_file):
            os.remove(local_file)

if __name__ == "__main__":
    download_and_analyze()