"""Simple test to check LLM understanding of user_info format"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage
from datetime import datetime

def test_simple_user_info():
    """Test with minimal template focusing on user_info"""
    
    template = ChatPromptTemplate.from_messages([
        (
            "system",
            "You are Vy, a restaurant assistant. "
            "IMPORTANT: You have access to user information: {user_info} "
            "The user's name is available in user_info['name']. "
            "When they ask about their name, use the name from user_info. "
            "Answer in Vietnamese."
        ),
        MessagesPlaceholder(variable_name="messages"),
    ])
    
    test_data = {
        "messages": [
            HumanMessage(content="tên tôi là gì?")
        ],
        "user_info": {
            "user_id": "24769757262629049", 
            "name": "Trần Tuấn Dương", 
            "email": None, 
            "phone": None, 
            "address": None
        }
    }
    
    print("=== TESTING SIMPLE USER_INFO TEMPLATE ===")
    
    try:
        formatted = template.format_messages(**test_data)
        
        print(f"\n=== FORMATTED SYSTEM MESSAGE ===")
        system_msg = formatted[0]
        print(system_msg.content)
        
        print(f"\n=== FORMATTED USER MESSAGE ===")
        user_msg = formatted[1]
        print(user_msg.content)
        
        print(f"\n=== CHECKING USER_INFO PARSING ===")
        # Simulate what LLM should see
        system_content = system_msg.content
        if "Trần Tuấn Dương" in system_content:
            print("✅ User name 'Trần Tuấn Dương' is visible in system message")
        else:
            print("❌ User name 'Trần Tuấn Dương' is NOT visible in system message")
            
        if "'name': 'Trần Tuấn Dương'" in system_content:
            print("✅ Dictionary format with name is visible")
        else:
            print("❌ Dictionary format with name is NOT visible")
            
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_simple_user_info()
