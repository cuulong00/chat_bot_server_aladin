#!/usr/bin/env python3
"""
Simple Direct Graph Test - Test mixed content without server complexity
"""

import sys
sys.path.append('/Users/pro16/Documents/Code/Project/chatbot_aladdin/chat_bot_server_aladin')

import os
from dotenv import load_dotenv

# Load environment first
load_dotenv()

# Import what we need
from src.database.qdrant_store import QdrantStore
from src.tools.preference_tools import preference_tools 
from src.domain_configs.domain_configs import MARKETING_DOMAIN
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from src.graphs.core.adaptive_rag_graph import create_adaptive_rag_graph
from src.graphs.state.state import State

class Colors:
    SUCCESS = '\033[92m'  # Green
    FAIL = '\033[91m'     # Red
    WARNING = '\033[93m'  # Yellow
    INFO = '\033[94m'     # Blue
    BOLD = '\033[1m'      # Bold
    END = '\033[0m'       # Reset

def test_mixed_content_direct():
    """Test mixed content directly with graph"""
    
    print(f"{Colors.BOLD}🧪 TESTING MIXED CONTENT DIRECTLY{Colors.END}")
    print("=" * 80)
    
    try:
        # Setup LLMs like in app.py
        print("Setting up components...")
        
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        llm_grade_documents = ChatGoogleGenerativeAI(model="gemini-1.5-flash-latest", temperature=0)
        llm_router = ChatGoogleGenerativeAI(model="gemini-1.5-flash-latest", temperature=0)
        llm_rewrite = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        llm_generate_direct = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        llm_hallucination_grader = ChatGoogleGenerativeAI(model="gemini-1.5-flash-latest", temperature=0)
        llm_summarizer = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        llm_contextualize = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        
        retriever = QdrantStore(
            collection_name="tianlong_marketing", 
            embedding_model="text-embedding-3-small"
        )
        
        # Create graph
        print("Creating graph...")
        adaptive_graph = create_adaptive_rag_graph(
            llm=llm,
            llm_grade_documents=llm_grade_documents,
            llm_router=llm_router,
            llm_rewrite=llm_rewrite,
            llm_generate_direct=llm_generate_direct,
            llm_hallucination_grader=llm_hallucination_grader,
            llm_summarizer=llm_summarizer,
            llm_contextualize=llm_contextualize,
            retriever=retriever,
            tools=preference_tools,  # Use preference tools
            DOMAIN=MARKETING_DOMAIN,
        )
        
        compiled_graph = adaptive_graph.compile()
        print("Graph compiled successfully!")
        
        # Test mixed content case
        test_message = "Menu có gì ngon? Tôi thích ăn cay!"
        print(f"\n{Colors.INFO}Testing: {test_message}{Colors.END}")
        
        # Create initial state
        initial_state = State(
            user_input=test_message,
            user_id="test_user_direct",
            session_id="test_session_direct",
            documents=[],
            generation="",
            web_search="No",
            question=""
        )
        
        # Run the graph
        config = {"configurable": {"thread_id": "test_direct"}}
        
        print("Processing...")
        final_state = compiled_graph.invoke(initial_state, config)
        
        print(f"\n{Colors.BOLD}📋 RESULTS:{Colors.END}")
        print(f"Final generation: {final_state.get('generation', 'No generation')}")
        print(f"Documents found: {len(final_state.get('documents', []))}")
        
        # Check messages for tool calls
        messages = final_state.get('messages', [])
        tool_calls_found = []
        
        for msg in messages:
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                for tool_call in msg.tool_calls:
                    tool_calls_found.append(tool_call['name'])
                    print(f"{Colors.SUCCESS}🔧 Tool called: {tool_call['name']}{Colors.END}")
        
        if not tool_calls_found:
            print(f"{Colors.WARNING}⚠️ No tool calls found{Colors.END}")
        
        # Analyze result
        has_preference_tool = 'save_user_preference_with_refresh_flag' in tool_calls_found
        has_generation = bool(final_state.get('generation'))
        
        print(f"\n{Colors.BOLD}📊 ANALYSIS:{Colors.END}")
        print(f"Preference tool called: {Colors.SUCCESS if has_preference_tool else Colors.FAIL}{'✅' if has_preference_tool else '❌'}{Colors.END}")
        print(f"Answer generated: {Colors.SUCCESS if has_generation else Colors.FAIL}{'✅' if has_generation else '❌'}{Colors.END}")
        
        if has_preference_tool and has_generation:
            print(f"{Colors.SUCCESS}🎉 MIXED CONTENT HANDLING: SUCCESS{Colors.END}")
        else:
            print(f"{Colors.FAIL}🚨 MIXED CONTENT HANDLING: NEEDS IMPROVEMENT{Colors.END}")
            
    except Exception as e:
        print(f"{Colors.FAIL}❌ ERROR: {str(e)}{Colors.END}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_mixed_content_direct()
