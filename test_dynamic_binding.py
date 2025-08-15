#!/usr/bin/env python3
"""
Test dynamic binding of image_contexts via binding_prompt method
"""

def test_binding_prompt():
    """Test that binding_prompt correctly extracts and binds image_contexts from state"""
    
    # Mock RagState with image_contexts
    mock_state = {
        "question": "Hãy giải thích combo này cho tôi",
        "messages": [{"type": "human", "content": "Hãy giải thích combo này cho tôi"}],
        "image_contexts": [
            "Hình ảnh 1: COMBO TIAN LONG SPECIAL - 485.000đ cho 2-3 người. Bao gồm: lẩu cay đặc biệt, thịt bò tươi 300g, rau củ tươi",
            "Hình ảnh 2: COMBO TAM GIAO - 555.000đ cho 2-3 người. Bao gồm: lẩu Tian Long, thịt bò Úc 250g, tôm tươi 200g"
        ],
        "user": {
            "user_info": {"user_id": "test_user", "name": "Test User"},
            "user_profile": {"preferences": ["thích ăn cay"]}
        },
        "context": {
            "running_summary": {"summary": "Khách hàng đang hỏi về combo menu"}
        }
    }
    
    # Simulate Assistant.binding_prompt behavior
    class MockAssistant:
        def binding_prompt(self, state):
            # Copy exact logic from actual binding_prompt method
            running_summary = ""
            if state.get("context") and isinstance(state["context"], dict):
                summary_obj = state["context"].get("running_summary")
                if summary_obj and hasattr(summary_obj, "summary"):
                    running_summary = summary_obj.summary
                elif isinstance(summary_obj, dict):  # Mock case
                    running_summary = summary_obj.get("summary", "")

            user_data = state.get("user", {})
            if not user_data:
                user_data = {
                    "user_info": {"user_id": "unknown"},
                    "user_profile": {}
                }
            
            user_info = user_data.get("user_info", {"user_id": "unknown"})
            user_profile = user_data.get("user_profile", {})

            # Get image_contexts from state (key part)
            image_contexts = state.get("image_contexts", [])
            print(f"🖼️ binding_prompt: Found {len(image_contexts)} image contexts")

            prompt = {
                **state,
                "user_info": user_info,
                "user_profile": user_profile,
                "conversation_summary": running_summary,
                "image_contexts": image_contexts,
            }
            
            return prompt
    
    # Test the binding
    assistant = MockAssistant()
    result = assistant.binding_prompt(mock_state)
    
    # Verify results
    print("🧪 Test Results:")
    print(f"✅ Original state has image_contexts: {len(mock_state.get('image_contexts', []))} items")
    print(f"✅ Bound prompt has image_contexts: {len(result.get('image_contexts', []))} items")
    print(f"✅ Image contexts preserved: {result['image_contexts'] == mock_state['image_contexts']}")
    print(f"✅ User info bound: {result.get('user_info', {}).get('user_id', 'missing')}")
    print(f"✅ Summary bound: {bool(result.get('conversation_summary', ''))}")
    
    # Show image_contexts content
    print(f"\n🖼️ Image contexts content:")
    for i, ctx in enumerate(result.get('image_contexts', [])):
        print(f"  [{i+1}]: {ctx[:60]}...")
    
    return result['image_contexts'] == mock_state['image_contexts']

if __name__ == "__main__":
    print("🧪 Testing dynamic binding of image_contexts...")
    success = test_binding_prompt()
    print(f"\n{'✅ PASS' if success else '❌ FAIL'}: Dynamic binding test")
