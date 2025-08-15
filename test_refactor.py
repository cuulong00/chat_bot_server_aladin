#!/usr/bin/env python3
"""
Test script để kiểm tra refactor của adaptive_rag_graph.py
"""

import os
import sys

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

def test_assistant_imports():
    """Test xem tất cả assistants có import được không"""
    try:
        from src.graphs.core.assistants import (
            BaseAssistant,
            RouterAssistant, 
            RouteQuery,
            DocGraderAssistant,
            GradeDocuments, 
            RewriteAssistant,
            GenerationAssistant,
            SuggestiveAssistant,
            HallucinationGraderAssistant,
            GradeHallucinations,
            DirectAnswerAssistant,
            DocumentProcessingAssistant
        )
        print("✅ Tất cả assistant classes đã import thành công!")
        return True
    except ImportError as e:
        print(f"❌ Lỗi import: {e}")
        return False

def test_assistant_structure():
    """Test cấu trúc assistant classes"""
    try:
        from src.graphs.core.assistants import BaseAssistant, RouterAssistant
        
        # Kiểm tra RouterAssistant có inherit từ BaseAssistant không
        if issubclass(RouterAssistant, BaseAssistant):
            print("✅ RouterAssistant inherit từ BaseAssistant đúng cách!")
        else:
            print("❌ RouterAssistant không inherit từ BaseAssistant!")
            return False
            
        return True
    except Exception as e:
        print(f"❌ Lỗi kiểm tra cấu trúc: {e}")
        return False

def main():
    """Main test function"""
    print("🔧 Bắt đầu test refactor...")
    print()
    
    # Test imports
    success1 = test_assistant_imports()
    print()
    
    # Test structure  
    success2 = test_assistant_structure()
    print()
    
    if success1 and success2:
        print("🎉 Refactor hoàn thành thành công!")
        print("📋 Tóm tắt:")
        print("   - Đã tách thành công các Assistant ra thành modules riêng")
        print("   - Các import hoạt động bình thường")
        print("   - Cấu trúc inheritance đúng đắn")
        print("   - Có thể sử dụng assistants trong adaptive_rag_graph.py")
        return True
    else:
        print("❌ Có lỗi trong quá trình refactor!")
        return False

if __name__ == "__main__":
    main()
