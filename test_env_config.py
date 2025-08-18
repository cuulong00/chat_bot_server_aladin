#!/usr/bin/env python3
"""
Quick test to verify environment configuration is loaded correctly.
"""

import os
from dotenv import load_dotenv

def main():
    """Test environment loading."""
    print("🔍 Testing environment configuration loading...")
    
    # Load .env file
    load_dotenv()
    
    # Check embedding model
    embedding_model = os.getenv("EMBEDDING_MODEL")
    print(f"   EMBEDDING_MODEL: {embedding_model}")
    
    # Check other related configs
    google_api_key = os.getenv("GOOGLE_API_KEY")
    print(f"   GOOGLE_API_KEY: {'✅ Set' if google_api_key else '❌ Missing'}")
    
    openai_api_key = os.getenv("OPENAI_API_KEY")
    print(f"   OPENAI_API_KEY: {'✅ Set' if openai_api_key else '❌ Missing'}")
    
    # Test if we can import Google GenAI
    try:
        import google.generativeai as genai
        genai.configure(api_key=google_api_key)
        print("   ✅ Google GenAI configured successfully")
        
        # Test embedding
        if embedding_model:
            result = genai.embed_content(
                model=embedding_model,
                content="Test embedding",
                task_type="SEMANTIC_SIMILARITY"
            )
            print(f"   ✅ Embedding works: dimension={len(result['embedding'])}")
        
    except Exception as e:
        print(f"   ❌ Google GenAI error: {e}")
    
    print("\n📋 Summary:")
    if embedding_model == "models/text-embedding-004":
        print("   ✅ Embedding model correctly set to Google model")
        return True
    elif embedding_model == "text-embedding-3-small":
        print("   ❌ Embedding model still set to OpenAI model (incompatible)")
        return False
    else:
        print(f"   ⚠️  Unexpected embedding model: {embedding_model}")
        return False

if __name__ == "__main__":
    success = main()
    if success:
        print("\n🎉 Environment configuration looks good!")
    else:
        print("\n💥 Environment configuration has issues!")
    
    exit(0 if success else 1)
