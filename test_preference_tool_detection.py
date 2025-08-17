#!/usr/bin/env python3
"""
Test to verify tool call detection for user preferences
"""

import logging
import sys
import os
sys.path.append(os.path.dirname(__file__))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)

def test_preference_detection():
    """Test phrases that should trigger save_user_preference tool"""
    
    test_phrases = [
        "anh thích ăn cay",
        "tôi yêu thích lẩu bò", 
        "em hay ăn cay",
        "anh thường đặt bàn tối",
        "tôi muốn không gian yên tĩnh",
        "anh ước có thể ăn thoải mái",
        "hôm nay là sinh nhật tôi",
        "bé thích ăn ngọt",
        "gia đình luôn chọn bàn gần cửa sổ"
    ]
    
    print("🔍 TESTING PREFERENCE DETECTION PHRASES:")
    print("=" * 50)
    
    for i, phrase in enumerate(test_phrases, 1):
        print(f"{i:2d}. '{phrase}'")
        
        # Check for keywords
        keywords_found = []
        if any(word in phrase.lower() for word in ['thích', 'yêu thích', 'ưa']):
            keywords_found.append('SỞ THÍCH')
        if any(word in phrase.lower() for word in ['thường', 'hay', 'luôn', 'quen']):
            keywords_found.append('THÓI QUEN')
        if any(word in phrase.lower() for word in ['mong muốn', 'ước', 'muốn', 'cần']):
            keywords_found.append('MONG MUỐN')
        if 'sinh nhật' in phrase.lower():
            keywords_found.append('SINH NHẬT')
            
        if keywords_found:
            print(f"    ✅ SHOULD TRIGGER TOOL: {', '.join(keywords_found)}")
        else:
            print(f"    ❌ NO TRIGGER DETECTED")
        print()

if __name__ == "__main__":
    test_preference_detection()
