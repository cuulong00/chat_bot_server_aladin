"""
Script để tự động convert tất cả tools từ SQLite sang PostgreSQL
"""
import os
import re

def convert_tool_file(file_path, tool_name):
    """Convert một tool file từ SQLite sang PostgreSQL"""
    print(f"🔄 Converting {tool_name}...")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Backup original file
        backup_path = file_path + '.backup'
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Replace imports
        content = re.sub(
            r'import sqlite3\n',
            'import pandas as pd\nimport sqlalchemy\n',
            content
        )
        
        # Add dotenv imports after existing imports
        if 'from dotenv import load_dotenv' not in content:
            # Find the last import line
            import_lines = []
            other_lines = []
            in_imports = True
            
            for line in content.split('\n'):
                if line.strip().startswith(('import ', 'from ')) and in_imports:
                    import_lines.append(line)
                else:
                    if in_imports and line.strip():
                        in_imports = False
                    other_lines.append(line)
            
            # Add new imports
            import_lines.extend([
                'from dotenv import load_dotenv',
                'import os',
                '',
                'load_dotenv()',
                '',
                '# Sử dụng PostgreSQL thay vì SQLite',
                'DB_URI = os.getenv("DATABASE_CONNECTION")',
                '',
                'def get_db_connection():',
                '    """Tạo kết nối database PostgreSQL"""',
                '    if not DB_URI:',
                '        raise ValueError("DATABASE_CONNECTION not found in environment variables")',
                '    return sqlalchemy.create_engine(DB_URI)',
                ''
            ])
            
            content = '\n'.join(import_lines + other_lines)
        
        # Remove old db variable
        content = re.sub(r'db = "travel2\.sqlite"\n', '', content)
        
        # Replace SQLite connection patterns with PostgreSQL patterns
        # This is a simplified replacement - more complex logic would be needed for production
        content = re.sub(
            r'conn = sqlite3\.connect\(db\)',
            'engine = get_db_connection()',
            content
        )
        
        # Add a comment about manual conversion needed
        conversion_comment = '''
# NOTE: This file has been partially converted from SQLite to PostgreSQL
# Manual review and testing is required to ensure all database operations work correctly
# Run migrate_to_postgres.py first to migrate the data to PostgreSQL

'''
        
        if '# NOTE: This file has been partially converted' not in content:
            content = conversion_comment + content
        
        # Write converted file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"  ✅ {tool_name} converted (backup saved as {backup_path})")
        print(f"  ⚠️  Manual review required for {tool_name}")
        
    except Exception as e:
        print(f"  ❌ Error converting {tool_name}: {e}")

def convert_all_tools():
    """Convert tất cả tool files"""
    print("🚀 Converting all tool files from SQLite to PostgreSQL...\n")
    
    tool_files = [
        ('src/tools/hotel_tools.py', 'hotel_tools'),
        ('src/tools/excursion_tools.py', 'excursion_tools'),
        ('src/tools/flight_tools.py', 'flight_tools'),
    ]
    
    for file_path, tool_name in tool_files:
        if os.path.exists(file_path):
            convert_tool_file(file_path, tool_name)
        else:
            print(f"❌ File not found: {file_path}")
    
    print("\n✅ Conversion completed!")
    print("\n📝 Next steps:")
    print("1. Run migrate_to_postgres.py to migrate data")
    print("2. Manually review and test each tool file")
    print("3. Update database queries to use PostgreSQL syntax")
    print("4. Test all tools with the new PostgreSQL backend")

if __name__ == "__main__":
    convert_all_tools()
