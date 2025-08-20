#!/usr/bin/env python3
"""Quick script to run marketing data embedding with default settings."""

import sys
import importlib.util
from pathlib import Path

# Add project root to Python path tianlong_marketing
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import the embedding module using importlib
embedding_file = PROJECT_ROOT / "setup" / "embedding-marketing-data.py"
spec = importlib.util.spec_from_file_location("embedding_marketing_data", embedding_file)
embedding_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(embedding_module)

if __name__ == "__main__":
    print("🚀 Starting Tian Long marketing data embedding...")
    
    try:
        embedding_module.run_marketing_embedding_pipeline(
            marketing_file=str(PROJECT_ROOT / "data" / "tianlong_marketing.json"),
            collection_name="tianlong_marketing",
            domain="marketing_content", 
            model_name="text-embedding-004",
            namespace="marketing"
            
            #namespace="marketing"
        )
        print("✅ Marketing embedding completed successfully!")
        
    except Exception as e:
        print(f"❌ Error during embedding: {e}")
        sys.exit(1)
