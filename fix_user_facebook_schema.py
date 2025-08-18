#!/usr/bin/env python3
"""
Fix user_facebook table schema to support full UUIDs (36 characters).

This script will:
1. Check current schema of user_facebook table
2. Alter the user_id column from VARCHAR(32) to VARCHAR(36)
3. Handle any data conflicts gracefully
"""

import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_database_connection():
    """Get database connection from environment variables."""
    db_uri = os.getenv("DB_URI") or os.getenv("DATABASE_CONNECTION")
    if not db_uri:
        print("❌ Error: No database connection string found in environment variables.")
        print("Please set DB_URI or DATABASE_CONNECTION in your .env file.")
        sys.exit(1)
    
    return create_engine(db_uri)

def check_table_exists(engine):
    """Check if user_facebook table exists."""
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'user_facebook'
            );
        """))
        return result.scalar()

def get_current_schema(engine):
    """Get current schema of user_facebook table."""
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT column_name, data_type, character_maximum_length
            FROM information_schema.columns
            WHERE table_name = 'user_facebook' 
            AND table_schema = 'public'
            ORDER BY ordinal_position;
        """))
        return result.fetchall()

def alter_user_id_column(engine):
    """Alter user_id column to VARCHAR(36)."""
    print("🔄 Altering user_id column from VARCHAR(32) to VARCHAR(36)...")
    
    try:
        with engine.connect() as conn:
            # Start transaction
            trans = conn.begin()
            try:
                # Alter the column
                conn.execute(text("""
                    ALTER TABLE user_facebook 
                    ALTER COLUMN user_id TYPE VARCHAR(36);
                """))
                
                trans.commit()
                print("✅ Successfully altered user_id column to VARCHAR(36)")
                return True
                
            except Exception as e:
                trans.rollback()
                print(f"❌ Error during column alteration: {e}")
                return False
                
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def create_table_if_not_exists(engine):
    """Create user_facebook table with correct schema if it doesn't exist."""
    print("🔄 Creating user_facebook table...")
    
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS user_facebook (
                    user_id VARCHAR(36) PRIMARY KEY NOT NULL,
                    name VARCHAR(255),
                    email VARCHAR(255) UNIQUE,
                    phone VARCHAR(20)
                );
            """))
            conn.commit()
            print("✅ Successfully created user_facebook table with correct schema")
            return True
            
    except Exception as e:
        print(f"❌ Error creating table: {e}")
        return False

def main():
    """Main function to fix the database schema."""
    print("🚀 Starting user_facebook schema fix...")
    
    # Get database connection
    try:
        engine = get_database_connection()
        print(f"✅ Connected to database: {engine.url.host}")
    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")
        return False
    
    # Check if table exists
    table_exists = check_table_exists(engine)
    
    if not table_exists:
        print("📋 user_facebook table doesn't exist, creating with correct schema...")
        return create_table_if_not_exists(engine)
    
    # Get current schema
    print("📋 Checking current table schema...")
    current_schema = get_current_schema(engine)
    
    print("\n📊 Current schema:")
    for row in current_schema:
        column_name, data_type, max_length = row
        if max_length:
            print(f"   {column_name}: {data_type}({max_length})")
        else:
            print(f"   {column_name}: {data_type}")
    
    # Check if user_id needs fixing
    user_id_info = [row for row in current_schema if row[0] == 'user_id']
    if not user_id_info:
        print("❌ user_id column not found!")
        return False
    
    current_length = user_id_info[0][2]
    if current_length and current_length >= 36:
        print(f"✅ user_id column already has sufficient length ({current_length})")
        return True
    
    print(f"⚠️  user_id column has insufficient length ({current_length}), needs to be 36")
    
    # Perform the alteration
    return alter_user_id_column(engine)

if __name__ == "__main__":
    success = main()
    if success:
        print("\n🎉 Schema fix completed successfully!")
        print("You can now restart your server.")
    else:
        print("\n💥 Schema fix failed!")
        print("Please check the errors above and try again.")
    
    sys.exit(0 if success else 1)
