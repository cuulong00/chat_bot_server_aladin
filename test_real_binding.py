#!/usr/bin/env python3
"""
Test real adaptive RAG graph with dynamic image_contexts binding
"""
import sys
import logging

# Setup logging to see the binding process
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def test_real_system():
    """Test with actual RagState structure"""
    from src.graphs.state.state import RagState
    from src.graphs.core.adaptive_rag_graph import Assistant
    from langchain_core.runnables import RunnablePassthrough
    
    # Create a mock state that matches RagState structure
    test_state = {
        "question": "Combo này có gì?",
        "messages": [],
        "documents": [],
        "generation": "",
        "web_search": "",
        "search_context": "",
        "image_contexts": [
            "📸 Phân tích hình ảnh: COMBO TIAN LONG - Giá 485.000đ bao gồm lẩu cay đặc biệt + thịt bò tươi 300g",
            "📸 Phân tích hình ảnh: COMBO TAM GIAO - Giá 555.000đ bao gồm lẩu Tian Long + thịt bò Úc + tôm tươi"
        ],
        "user": {
            "user_info": {"user_id": "test123", "name": "Khách Test"},
            "user_profile": {"preferences": ["thích ăn cay", "thích tôm"]}
        },
        "context": {}
    }
    
    # Create an assistant instance to test binding
    class TestAssistant(Assistant):
        def __init__(self):
            # Mock runnable - we just want to test binding_prompt
            self.runnable = RunnablePassthrough()
    
    assistant = TestAssistant()
    
    print("🧪 Testing real system dynamic binding...")
    
    # Test the actual binding_prompt method
    try:
        bound_data = assistant.binding_prompt(test_state)
        
        print("✅ binding_prompt executed successfully")
        print(f"📊 Bound data keys: {list(bound_data.keys())}")
        print(f"🖼️ image_contexts count: {len(bound_data.get('image_contexts', []))}")
        print(f"👤 user_info: {bound_data.get('user_info', {})}")
        print(f"📝 Has conversation_summary: {bool(bound_data.get('conversation_summary'))}")
        
        # Verify image contexts are properly bound
        img_contexts = bound_data.get('image_contexts', [])
        if img_contexts:
            print(f"\n🖼️ Image contexts successfully bound:")
            for i, ctx in enumerate(img_contexts):
                print(f"  [{i+1}]: {ctx[:50]}...")
        else:
            print("❌ No image contexts found in bound data")
            
        return len(img_contexts) == 2  # Should have 2 test contexts
        
    except Exception as e:
        print(f"❌ Error testing binding: {e}")
        return False

if __name__ == "__main__":
    success = test_real_system()
    print(f"\n{'🎉 SUCCESS' if success else '💥 FAILED'}: Real system binding test")
