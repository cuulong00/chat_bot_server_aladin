#!/usr/bin/env python3
"""
Test script to verify that skip_grade_documents configuration is working properly.
This script will check if the environment variable and parameter are being read correctly.
"""

import os
import logging
from src.graphs.core.adaptive_rag_graph import get_skip_grade_documents_from_env

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def test_skip_grade_documents_config():
    """Test the skip_grade_documents configuration"""
    
    print("=" * 60)
    print("TESTING SKIP_GRADE_DOCUMENTS CONFIGURATION")
    print("=" * 60)
    
    # Test 1: Check current environment variable
    current_env = os.getenv("SKIP_GRADE_DOCUMENTS")
    print(f"📄 Current SKIP_GRADE_DOCUMENTS env var: {current_env}")
    
    # Test 2: Check helper function
    skip_value = get_skip_grade_documents_from_env()
    print(f"🔄 get_skip_grade_documents_from_env() returns: {skip_value}")
    
    # Test 3: Test various values
    test_values = ["true", "True", "TRUE", "1", "yes", "YES", "false", "False", "0", "no", ""]
    
    print(f"\n🧪 TESTING VARIOUS VALUES:")
    for test_val in test_values:
        os.environ["SKIP_GRADE_DOCUMENTS"] = test_val
        result = get_skip_grade_documents_from_env()
        expected = test_val.lower() in ["true", "1", "yes"]
        status = "✅" if result == expected else "❌"
        print(f"   {status} '{test_val}' -> {result} (expected: {expected})")
    
    # Restore original value
    if current_env is not None:
        os.environ["SKIP_GRADE_DOCUMENTS"] = current_env
    else:
        os.environ.pop("SKIP_GRADE_DOCUMENTS", None)
    
    print(f"\n📊 SUMMARY:")
    print(f"   🔄 Final SKIP_GRADE_DOCUMENTS value: {get_skip_grade_documents_from_env()}")
    print(f"   📝 This means document grading will be: {'SKIPPED' if get_skip_grade_documents_from_env() else 'PERFORMED'}")
    
    if get_skip_grade_documents_from_env():
        print(f"   ⚡ Expected behavior: retrieve -> generate (skipping grade_documents)")
    else:
        print(f"   🔍 Expected behavior: retrieve -> grade_documents -> generate")
    
    print("=" * 60)
    print("TEST COMPLETED")
    print("=" * 60)

if __name__ == "__main__":
    test_skip_grade_documents_config()
