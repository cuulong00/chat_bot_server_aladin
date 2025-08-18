#!/usr/bin/env python3
"""
Test RAG workflow với mixed content (info query + preference)
"""

import sys
sys.path.append('/Users/pro16/Documents/Code/Project/chatbot_aladdin/chat_bot_server_aladin')

def test_rag_workflow_mixed_content():
    print("🔍 TEST RAG WORKFLOW với MIXED CONTENT")
    print("=" * 60)
    
    print("\n🧪 THEORETICAL ANALYSIS:")
    print("Khi input: 'Menu có những món gì ngon? À mà tôi thích ăn cay nhé!'")
    
    print("\n📊 WORKFLOW ANALYSIS:")
    
    scenarios = [
        {
            "name": "🎯 PURE PREFERENCE (Router Fix Effect)",
            "input": "tôi thích ăn cay",
            "expected_route": "direct_answer",
            "workflow": "route → decide_entry → generate_direct",
            "node": "DirectAnswerAssistant",
            "has_documents": False,
            "tool_call_likelihood": "HIGH ✅"
        },
        {
            "name": "📚 PURE INFORMATION", 
            "input": "menu có những món gì ngon?",
            "expected_route": "vectorstore",
            "workflow": "route → retrieve → grade → generate",
            "node": "GenerationAssistant (RAG)",
            "has_documents": True,
            "tool_call_likelihood": "NONE (no preferences) ✅"
        },
        {
            "name": "🔥 MIXED CONTENT (Key Case)",
            "input": "Menu có những món gì ngon? À mà tôi thích ăn cay nhé!",
            "expected_route": "vectorstore (info query dominates)",
            "workflow": "route → retrieve → grade → generate", 
            "node": "GenerationAssistant (RAG)",
            "has_documents": True,
            "tool_call_likelihood": "SHOULD BE HIGH ✅ (nếu prompt đủ mạnh)"
        }
    ]
    
    print("\n🧪 SCENARIO ANALYSIS:")
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n{i}. {scenario['name']}")
        print(f"   Input: '{scenario['input']}'")
        print(f"   Expected Route: {scenario['expected_route']}")
        print(f"   Workflow: {scenario['workflow']}")
        print(f"   Final Node: {scenario['node']}")
        print(f"   Has Documents: {scenario['has_documents']}")
        print(f"   Tool Call Likelihood: {scenario['tool_call_likelihood']}")
        
        # Analyze potential issues
        if scenario['name'] == "🔥 MIXED CONTENT (Key Case)":
            print(f"   🔍 POTENTIAL ISSUES:")
            print(f"      • Documents có thể làm LLM distracted khỏi preference detection")
            print(f"      • GenerationAssistant prompt có thể chưa đủ mạnh khi có context")
            print(f"      • Tool calling competition: answer documents vs save preferences")
    
    print("\n" + "="*60)
    print("🎯 KEY INSIGHTS từ phân tích của bạn:")
    
    insights = [
        "✅ RAG workflow THỰC SỰ kết thúc ở GenerationAssistant có tool calling",
        "✅ Router fix chỉ ảnh hưởng đến PURE preference cases",
        "⚠️ MIXED content vẫn sẽ đi RAG vì info query dominates routing",
        "🔑 GIẢI PHÁP: Cần strengthen GenerationAssistant preference detection", 
        "🔑 GenerationAssistant phải handle BOTH document answering AND preference saving"
    ]
    
    for insight in insights:
        print(f"• {insight}")
        
    print("\n🔧 RECOMMENDED IMPROVEMENTS:")
    improvements = [
        "1. Test GenerationAssistant với documents + preferences",
        "2. Enhance prompt để ưu tiên preference detection dù có documents", 
        "3. Add explicit instruction: 'Luôn check preferences trước khi answer'",
        "4. Consider dual-output: document answer + preference tool call"
    ]
    
    for improvement in improvements:
        print(f"{improvement}")
        
    print(f"\n🎊 CONCLUSION:")
    print(f"✅ Router fix vẫn có giá trị cho pure preference cases")
    print(f"🔑 Cần focus vào GenerationAssistant để handle mixed content")
    print(f"🎯 RAG + Tool calling phải hoạt động song song, không exclude nhau")

def test_generation_assistant_mixed_capability():
    """Test khả năng của GenerationAssistant xử lý mixed content"""
    print(f"\n" + "="*60)
    print("🧪 GENERATION ASSISTANT MIXED CAPABILITY TEST")
    print("="*60)
    
    print("\n📋 CHECKING GenerationAssistant prompt strength:")
    
    try:
        with open('src/graphs/core/assistants/generation_assistant.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check key elements for mixed handling
        mixed_handling_elements = [
            ("PHẢI gọi tool", "Tool calling mandate"),
            ("thích", "Preference keyword detection"),
            ("save_user_preference_with_refresh_flag", "Preference tool reference"),
            ("documents", "Document handling context"),
            ("context", "Context awareness")
        ]
        
        print(f"\n🔍 Prompt Elements Analysis:")
        for element, description in mixed_handling_elements:
            has_element = element in content
            status = "✅" if has_element else "❌"
            print(f"   {status} {description}: {element}")
            
        # Check for specific mixed-content handling
        mixed_instructions = [
            "cả khi có documents",
            "dù có thông tin từ tài liệu", 
            "song song với việc trả lời",
            "đồng thời"
        ]
        
        print(f"\n🔍 Mixed Content Handling:")
        has_mixed_handling = any(instruction in content for instruction in mixed_instructions)
        
        if has_mixed_handling:
            print(f"   ✅ Has explicit mixed content handling")
        else:
            print(f"   ⚠️ No explicit mixed content handling detected")
            print(f"   💡 IMPROVEMENT NEEDED: Add instructions for document + preference scenarios")
            
    except Exception as e:
        print(f"❌ Error reading GenerationAssistant: {e}")
        
    print(f"\n🎯 MIXED CONTENT HANDLING RECOMMENDATION:")
    print(f"Need to add to GenerationAssistant prompt:")
    print(f"'🔑 QUAN TRỌNG: Dù có documents, LUÔN check user input cho preferences'")
    print(f"'• Nếu có preference → GỌI tool TRƯỚC khi answer documents'")
    print(f"'• Có thể vừa answer documents vừa save preferences'")

if __name__ == "__main__":
    test_rag_workflow_mixed_content()
    test_generation_assistant_mixed_capability()
