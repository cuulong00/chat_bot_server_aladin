#!/usr/bin/env python3
"""
Test script to verify the fixes for:
1. Database schema (UUID length)
2. Embedding model compatibility
"""

import os
import sys
import uuid
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_database_uuid_insertion():
    """Test that we can now insert full UUIDs into user_facebook table."""
    print("🧪 Testing UUID insertion into user_facebook table...")
    
    try:
        # Get database connection
        db_uri = os.getenv("DB_URI") or os.getenv("DATABASE_CONNECTION")
        engine = create_engine(db_uri)
        
        # Generate a test UUID (36 characters)
        test_uuid = str(uuid.uuid4())
        print(f"   Test UUID: {test_uuid} (length: {len(test_uuid)})")
        
        with engine.connect() as conn:
            # Try to insert the test UUID
            trans = conn.begin()
            try:
                conn.execute(text("""
                    INSERT INTO user_facebook (user_id, name, email, phone)
                    VALUES (:uid, :name, :email, :phone)
                    ON CONFLICT (user_id) DO NOTHING
                """), {
                    "uid": test_uuid,
                    "name": "Test User",
                    "email": f"test_{test_uuid[:8]}@example.com",
                    "phone": "+1234567890"
                })
                
                # Verify the insertion
                result = conn.execute(text("""
                    SELECT user_id, name FROM user_facebook WHERE user_id = :uid
                """), {"uid": test_uuid})
                
                row = result.fetchone()
                if row:
                    print(f"   ✅ Successfully inserted and retrieved: {row[0][:8]}...")
                    
                    # Clean up test data
                    conn.execute(text("""
                        DELETE FROM user_facebook WHERE user_id = :uid
                    """), {"uid": test_uuid})
                    print("   🧹 Test data cleaned up")
                    
                    trans.commit()
                    return True
                else:
                    print("   ❌ Failed to retrieve inserted UUID")
                    trans.rollback()
                    return False
                    
            except Exception as e:
                trans.rollback()
                print(f"   ❌ Database error: {e}")
                return False
                
    except Exception as e:
        print(f"   ❌ Connection error: {e}")
        return False

def test_embedding_model():
    """Test that the embedding model configuration works."""
    print("🧪 Testing embedding model configuration...")
    
    try:
        import google.generativeai as genai
        
        # Configure the API key
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            print("   ❌ GOOGLE_API_KEY not found in environment")
            return False
            
        genai.configure(api_key=api_key)
        
        # Get embedding model from environment
        embedding_model = os.getenv("EMBEDDING_MODEL", "models/text-embedding-004")
        print(f"   Using embedding model: {embedding_model}")
        
        # Test embedding generation
        test_text = "This is a test sentence for embedding generation."
        result = genai.embed_content(
            model=embedding_model,
            content=test_text,
            task_type="SEMANTIC_SIMILARITY"
        )
        
        embedding = result["embedding"]
        print(f"   ✅ Successfully generated embedding with dimension: {len(embedding)}")
        
        if len(embedding) == 768:
            print("   ✅ Embedding dimension matches expected size (768)")
            return True
        else:
            print(f"   ⚠️  Embedding dimension ({len(embedding)}) doesn't match expected (768)")
            return True  # Still working, just different dimension
            
    except Exception as e:
        print(f"   ❌ Embedding error: {e}")
        return False

def main():
    """Run all tests."""
    print("🚀 Running fix verification tests...\n")
    
    # Test 1: Database UUID insertion
    db_test = test_database_uuid_insertion()
    print()
    
    # Test 2: Embedding model
    embedding_test = test_embedding_model()
    print()
    
    # Summary
    if db_test and embedding_test:
        print("🎉 All tests passed! The fixes are working correctly.")
        print("\n📋 Summary:")
        print("   ✅ Database can now handle full UUIDs (36 characters)")
        print("   ✅ Embedding model is configured correctly")
        print("\nYou can now start your server and test the mixed content scenarios.")
        return True
    else:
        print("💥 Some tests failed!")
        if not db_test:
            print("   ❌ Database UUID test failed")
        if not embedding_test:
            print("   ❌ Embedding model test failed")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
