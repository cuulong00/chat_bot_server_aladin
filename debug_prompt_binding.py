"""Debug script to test prompt binding in DirectAnswerAssistant"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from src.graphs.core.assistants.direct_answer_assistant import DirectAnswerAssistant
from src.graphs.state.state import RagState
from langchain_core.messages import HumanMessage
from datetime import datetime

# Mock LLM for testing
class MockLLM:
    def bind_tools(self, tools):
        return self
    
    def invoke(self, prompt_data, config):
        print("=== PROMPT DATA SENT TO LLM ===")
        for key, value in prompt_data.items():
            if key == "messages":
                print(f"{key}: {[msg.content if hasattr(msg, 'content') else msg for msg in value]}")
            else:
                print(f"{key}: {value}")
        print("=== END PROMPT DATA ===")
        return type('MockResult', (), {"content": "Mock response", "tool_calls": []})()

def test_prompt_binding():
    """Test prompt binding with mock data"""
    # Create mock state
    state = RagState({
        "messages": [
            HumanMessage(content="tên anh là gì?", additional_kwargs={
                'session_id': 'facebook_session_24769757262629049', 
                'user_id': '24769757262629049'
            })
        ],
        "user": {
            "user_info": {
                "user_id": "24769757262629049", 
                "name": "Trần Tuấn Dương", 
                "email": None, 
                "phone": None, 
                "address": None
            },
            "user_profile": {
                "summary": "User's personalized information:\n- spice_preference: likes spicy food"
            }
        },
        "thread_id": "dba38c07-69c0-4556-ad8f-9a4c43ef71f9",
        "session_id": "facebook_session_24769757262629049",
        "dialog_state": [],
        "reasoning_steps": [],
        "documents": [],
        "rewrite_count": 0,
        "search_attempts": 0,
        "datasource": "direct_answer",
        "question": "tên anh là gì?",
        "hallucination_score": "",
        "skip_hallucination": False,
        "image_contexts": []
    })
    
    # Create assistant with mock LLM
    mock_llm = MockLLM()
    domain_context = "restaurant"
    tools = []
    
    assistant = DirectAnswerAssistant(mock_llm, domain_context, tools)
    
    # Test binding_prompt method directly
    print("=== TESTING binding_prompt METHOD ===")
    prompt_data = assistant.binding_prompt(state)
    
    print("\n=== BINDING RESULT ===")
    for key, value in prompt_data.items():
        if key == "messages":
            print(f"{key}: {[msg.content if hasattr(msg, 'content') else msg for msg in value]}")
        else:
            print(f"{key}: {value}")
    
    print("\n=== TESTING FULL INVOCATION ===")
    config = {"configurable": {"user_id": "24769757262629049"}}
    try:
        result = assistant(state, config)
        print("Result:", result)
    except Exception as e:
        print("Exception:", e)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_prompt_binding()
