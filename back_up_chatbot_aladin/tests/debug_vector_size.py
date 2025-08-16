"""
Debug script để kiểm tra vector size từ Gemini
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

gemini_client = genai.Client()

def debug_vector_size():
    """Debug để xem vector size thực tế"""
    print("🔍 Debugging Gemini embedding vector size...")
    
    test_texts = [
        "Hello world",
        "User test_user dietary_restriction: vegetarian",
        "Travel preference: business class"
    ]
    
    for text in test_texts:
        try:
            result = gemini_client.models.embed_content(
                model="gemini-embedding-exp-03-07",
                contents=text,
                config=types.EmbedContentConfig(task_type="SEMANTIC_SIMILARITY"),
            )
            
            embedding = result.embeddings[0].values
            print(f"Text: '{text}'")
            print(f"Vector size: {len(embedding)}")
            print(f"First 5 values: {embedding[:5]}")
            print()
            
        except Exception as e:
            print(f"Error with text '{text}': {e}")
            print()

if __name__ == "__main__":
    debug_vector_size()