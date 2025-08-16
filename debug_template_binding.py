"""Debug script to test ChatPromptTemplate variable binding"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage
from datetime import datetime

def test_template_binding():
    """Test ChatPromptTemplate variable binding"""
    
    # Create a simple template similar to DirectAnswerAssistant
    template = ChatPromptTemplate.from_messages([
        (
            "system",
            "You are an assistant. User info: {user_info}. User profile: {user_profile}. Current date: {current_date}. Domain: {domain_context}"
        ),
        MessagesPlaceholder(variable_name="messages"),
    ]).partial(current_date=datetime.now, domain_context="restaurant")
    
    print("=== Template input variables ===")
    print(f"Template input_variables: {template.input_variables}")
    print(f"Template partial_variables: {list(template.partial_variables.keys())}")
    
    # Test data similar to our state
    test_data = {
        "messages": [
            HumanMessage(content="tên anh là gì?")
        ],
        "user_info": {
            "user_id": "24769757262629049", 
            "name": "Trần Tuấn Dương", 
            "email": None, 
            "phone": None, 
            "address": None
        },
        "user_profile": {
            "summary": "User's personalized information:\n- spice_preference: likes spicy food"
        },
        "thread_id": "test",
        "session_id": "test",
        "dialog_state": [],
        "reasoning_steps": [],
        "documents": [],
        "rewrite_count": 0,
        "search_attempts": 0,
        "datasource": "direct_answer",
        "question": "tên anh là gì?",
        "hallucination_score": "",
        "skip_hallucination": False,
        "image_contexts": [],
        "conversation_summary": ""
    }
    
    print("\n=== Test data keys ===")
    print(f"Test data keys: {list(test_data.keys())}")
    
    try:
        print("\n=== Formatting template ===")
        formatted = template.format_messages(**test_data)
        
        print(f"Successfully formatted {len(formatted)} messages")
        for i, msg in enumerate(formatted):
            print(f"Message {i} ({type(msg).__name__}): {msg.content[:200]}...")
            
    except Exception as e:
        print(f"ERROR formatting template: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_template_binding()
