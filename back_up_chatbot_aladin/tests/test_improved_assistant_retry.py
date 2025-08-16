#!/usr/bin/env python3
"""
Test script for improved Assistant retry mechanism.
Tests the new retry logic with exponential backoff and fallback handling.
"""

import sys
import os
import time
import logging
from unittest.mock import Mock, patch, MagicMock

# Add the src directory to the path so we can import from it
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from graphs.core.adaptive_rag_graph import Assistant
from graphs.state.state import RagState
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def test_successful_response():
    """Test normal successful response - no retries needed"""
    print("\n🧪 Test 1: Successful response (no retries)")
    
    # Mock runnable that returns valid response
    mock_runnable = Mock()
    mock_response = AIMessage(content="Valid response from LLM")
    mock_runnable.invoke.return_value = mock_response
    
    # Create assistant
    assistant = Assistant(mock_runnable)
    
    # Mock state and config
    state = {
        "user": {
            "user_info": {"user_id": "test-user-123", "name": "Test User"},
            "user_profile": {}
        },
        "messages": [HumanMessage(content="Hello")]
    }
    config = {"configurable": {}}
    
    # Execute
    start_time = time.time()
    result = assistant(state, config)
    duration = time.time() - start_time
    
    # Verify
    assert isinstance(result, AIMessage)
    assert result.content == "Valid response from LLM"
    assert mock_runnable.invoke.call_count == 1
    assert duration < 0.1  # Should be fast, no retries
    print("✅ Test 1 passed: Normal response works correctly")

def test_empty_response_with_retries():
    """Test empty response triggers retries and eventually succeeds"""
    print("\n🧪 Test 2: Empty response with successful retry")
    
    # Mock runnable that fails twice then succeeds
    mock_runnable = Mock()
    responses = [
        AIMessage(content=""),  # Empty - should retry
        AIMessage(content=""),  # Empty - should retry  
        AIMessage(content="Success after retries!")  # Valid - should return
    ]
    mock_runnable.invoke.side_effect = responses
    
    # Create assistant
    assistant = Assistant(mock_runnable)
    
    # Mock state and config
    state = {
        "user": {
            "user_info": {"user_id": "test-user-123", "name": "Test User"},
            "user_profile": {}
        },
        "messages": [HumanMessage(content="Hello")]
    }
    config = {"configurable": {}}
    
    # Execute
    start_time = time.time()
    result = assistant(state, config)
    duration = time.time() - start_time
    
    # Verify
    assert isinstance(result, AIMessage)
    assert result.content == "Success after retries!"
    assert mock_runnable.invoke.call_count == 3
    assert duration >= 0.75  # Should have delays (0.5 + 1.0 + processing time)
    print("✅ Test 2 passed: Retry mechanism works correctly")

def test_max_retries_fallback():
    """Test fallback response when max retries reached"""
    print("\n🧪 Test 3: Max retries reached, fallback response")
    
    # Mock runnable that always returns empty
    mock_runnable = Mock()
    mock_runnable.invoke.return_value = AIMessage(content="")
    
    # Create assistant
    assistant = Assistant(mock_runnable)
    
    # Mock state and config
    state = {
        "user": {
            "user_info": {"user_id": "test-user-123", "name": "Tuấn Dương"},
            "user_profile": {}
        },
        "messages": [HumanMessage(content="Hello")]
    }
    config = {"configurable": {}}
    
    # Execute
    start_time = time.time()
    result = assistant(state, config)
    duration = time.time() - start_time
    
    # Verify
    assert isinstance(result, AIMessage)
    assert "Xin lỗi Tuấn Dương" in result.content
    assert "1900 636 886" in result.content
    assert result.additional_kwargs.get("fallback_response") is True
    assert mock_runnable.invoke.call_count == 4  # Initial + 3 retries
    assert duration >= 3.5  # Should have delays (0.5 + 1.0 + 2.0 + processing)
    print("✅ Test 3 passed: Fallback response works correctly")

def test_exception_handling():
    """Test exception handling with retries"""
    print("\n🧪 Test 4: Exception handling with retries")
    
    # Mock runnable that throws exception then succeeds
    mock_runnable = Mock()
    responses = [
        Exception("Network error"),
        Exception("Temporary failure"),
        AIMessage(content="Success after exceptions!")
    ]
    mock_runnable.invoke.side_effect = responses
    
    # Create assistant
    assistant = Assistant(mock_runnable)
    
    # Mock state and config
    state = {
        "user": {
            "user_info": {"user_id": "test-user-123", "name": "Test User"},
            "user_profile": {}
        },
        "messages": [HumanMessage(content="Hello")]
    }
    config = {"configurable": {}}
    
    # Execute
    start_time = time.time()
    result = assistant(state, config)
    duration = time.time() - start_time
    
    # Verify
    assert isinstance(result, AIMessage)
    assert result.content == "Success after exceptions!"
    assert mock_runnable.invoke.call_count == 3
    assert duration >= 0.75  # Should have delays
    print("✅ Test 4 passed: Exception handling works correctly")

def test_structured_output():
    """Test structured output (no tool_calls attribute) returns immediately"""
    print("\n🧪 Test 5: Structured output (no retries needed)")
    
    # Mock runnable that returns structured output (Pydantic model)
    mock_runnable = Mock()
    mock_response = {"route": "websearch"}  # Simulated structured output
    mock_runnable.invoke.return_value = mock_response
    
    # Create assistant
    assistant = Assistant(mock_runnable)
    
    # Mock state and config
    state = {
        "user": {
            "user_info": {"user_id": "test-user-123", "name": "Test User"},
            "user_profile": {}
        },
        "messages": [HumanMessage(content="Hello")]
    }
    config = {"configurable": {}}
    
    # Execute
    start_time = time.time()
    result = assistant(state, config)
    duration = time.time() - start_time
    
    # Verify
    assert result == mock_response
    assert mock_runnable.invoke.call_count == 1
    assert duration < 0.1  # Should be fast, no retries
    print("✅ Test 5 passed: Structured output works correctly")

def test_tool_calls_response():
    """Test response with tool calls (considered valid)"""
    print("\n🧪 Test 6: Response with tool calls")
    
    # Mock runnable that returns response with tool calls
    mock_runnable = Mock()
    mock_response = AIMessage(
        content="I'll help you book a table",
        tool_calls=[{
            "name": "book_table_reservation", 
            "args": {"restaurant": "Tian Long"},
            "id": "call_123456",
            "type": "tool_call"
        }]
    )
    mock_runnable.invoke.return_value = mock_response
    
    # Create assistant
    assistant = Assistant(mock_runnable)
    
    # Mock state and config
    state = {
        "user": {
            "user_info": {"user_id": "test-user-123", "name": "Test User"},
            "user_profile": {}
        },
        "messages": [HumanMessage(content="Book a table")]
    }
    config = {"configurable": {}}
    
    # Execute
    result = assistant(state, config)
    
    # Verify
    assert isinstance(result, AIMessage)
    assert result.content == "I'll help you book a table"
    assert len(result.tool_calls) == 1
    assert mock_runnable.invoke.call_count == 1
    print("✅ Test 6 passed: Tool calls response works correctly")

def main():
    """Run all tests"""
    print("🚀 Testing Improved Assistant Retry Mechanism")
    print("=" * 60)
    
    try:
        test_successful_response()
        test_empty_response_with_retries()
        test_max_retries_fallback()
        test_exception_handling()
        test_structured_output()
        test_tool_calls_response()
        
        print("\n" + "=" * 60)
        print("🎉 ALL TESTS PASSED! ✅")
        print("\n📊 Test Summary:")
        print("✅ Normal responses work correctly")
        print("✅ Retry mechanism with exponential backoff")
        print("✅ Fallback response when max retries reached")
        print("✅ Exception handling with retries")
        print("✅ Structured output bypasses retries")
        print("✅ Tool calls are considered valid responses")
        print("\n🎯 The improved Assistant class is production-ready!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    main()
