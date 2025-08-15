#!/usr/bin/env python3
"""
Test script để kiểm tra định dạng link thân thiện trong các prompt
"""

import re
import sys
from pathlib import Path

def check_link_formatting(file_path):
    """Kiểm tra xem file có chứa link không thân thiện không"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    issues = []
    lines = content.split('\n')
    
    for i, line in enumerate(lines, 1):
        # Kiểm tra các pattern không thân thiện
        if 'https://menu.tianlong.vn/' in line and 'SAI:' not in line:
            issues.append(f"Line {i}: Found unfriendly link format: {line.strip()}")
        
        if re.search(r'Xem đầy đủ.*https://', line) and 'SAI:' not in line:
            issues.append(f"Line {i}: Found unfriendly link format: {line.strip()}")
            
        if '<link>' in line and 'Xem thêm tại:' not in line:
            issues.append(f"Line {i}: Generic <link> placeholder: {line.strip()}")
    
    return issues

def main():
    file_path = "src/graphs/core/adaptive_rag_graph.py"
    
    if not Path(file_path).exists():
        print(f"❌ File not found: {file_path}")
        return 1
    
    print("🔍 Checking link formatting in prompts...")
    issues = check_link_formatting(file_path)
    
    if not issues:
        print("✅ All link formats look good!")
        
        # Kiểm tra xem có các hướng dẫn về link thân thiện không
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        friendly_format_count = content.count("ĐỊNH DẠNG LINK THÂN THIỆN")
        menu_friendly_count = content.count("menu.tianlong.vn")
        
        print(f"📊 Statistics:")
        print(f"   - Friendly link format guidelines: {friendly_format_count}")
        print(f"   - Friendly menu links: {menu_friendly_count}")
        
        if friendly_format_count >= 4:  # Expect at least in 4 prompts
            print("✅ All major prompts have friendly link guidelines!")
        else:
            print("⚠️  Some prompts might be missing friendly link guidelines")
            
        return 0
    else:
        print("❌ Found link formatting issues:")
        for issue in issues:
            print(f"   {issue}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
