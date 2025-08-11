#!/usr/bin/env python3
"""
Test script for LangGraph Server API compatibility with Agent Chat UI
"""

import asyncio
import aiohttp
import json
import sys
import uuid
import pytest

@pytest.mark.anyio
async def test_streaming_endpoint_with_assistant():
    """Test the streaming endpoint using correct LangGraph Server API format"""
    
    # Test data with assistant_id
    test_data = {
        "input": {
            "messages": [
                {
                    "type": "human",
                    "content": "Hi there, what time is my flight?",
                    "id": str(uuid.uuid4())
                }
            ]
        },
        "assistant_id": "agent",  # Required for LangGraph Server
        "stream_mode": ["values", "messages"]
    }
    
    thread_id = str(uuid.uuid4())
    url = f"http://localhost:2024/threads/{thread_id}/runs/stream"
    
    print(f"Testing LangGraph Server streaming: {url}")
    print(f"Sending data: {json.dumps(test_data, indent=2)}")
    print("-" * 50)
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=test_data,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "text/event-stream"
                }
            ) as response:
                print(f"Response status: {response.status}")
                print(f"Response headers: {dict(response.headers)}")
                print("-" * 50)
                
                if response.status != 200:
                    text = await response.text()
                    print(f"Error response: {text}")
                    return
                
                # Read streaming response
                async for line in response.content:
                    line = line.decode('utf-8').strip()
                    if line and line.startswith('data: '):
                        try:
                            data = json.loads(line[6:])  # Remove 'data: ' prefix
                            print(f"Stream event: {json.dumps(data, indent=2)}")
                            print("-" * 30)
                            
                            # Check for end event
                            if data.get('event') == 'end':
                                print("Stream ended successfully!")
                                break
                                
                        except json.JSONDecodeError as e:
                            print(f"Failed to parse JSON: {line}")
                            print(f"Error: {e}")
                    elif line:
                        print(f"Non-data line: {line}")
                        
    except Exception as e:
        print(f"Connection error: {e}")

@pytest.mark.anyio
async def test_langgraph_server_api():
    """Test LangGraph Server API endpoints"""
    
    # Test info endpoint
    print("Testing LangGraph Server API...")
    url = "http://localhost:2024"
    
    try:
        async with aiohttp.ClientSession() as session:
            # Test assistants endpoint
            async with session.get(f"{url}/assistants") as response:
                print(f"GET /assistants: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    print(f"Assistants: {json.dumps(data, indent=2)}")
                print("-" * 30)
            
            # Test threads endpoint
            async with session.post(f"{url}/threads", json={"assistant_id": "agent"}) as response:
                print(f"POST /threads: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    print(f"Thread created: {json.dumps(data, indent=2)}")
                    
                    # Try to run in this thread
                    thread_id = data.get("thread_id")
                    if thread_id:
                        await _test_run_in_thread(session, url, thread_id)
                print("-" * 30)
                
    except Exception as e:
        print(f"Error testing LangGraph Server API: {e}")

async def _test_run_in_thread(session, base_url, thread_id):
    """Test running in a specific thread"""
    
    run_data = {
        "assistant_id": "agent",
        "input": {
            "messages": [
                {
                    "type": "human", 
                    "content": "Hello! What's my flight status?",
                    "id": str(uuid.uuid4())
                }
            ]
        },
        "stream_mode": ["values"]
    }
    
    url = f"{base_url}/threads/{thread_id}/runs/stream"
    print(f"Testing run in thread: {thread_id}")
    
    try:
        async with session.post(url, json=run_data) as response:
            print(f"Run status: {response.status}")
            if response.status == 200:
                print("Stream response (first 3 events):")
                count = 0
                async for line in response.content:
                    if count >= 3:  # Limit output
                        break
                    line = line.decode('utf-8').strip()
                    if line and line.startswith('data: '):
                        try:
                            data = json.loads(line[6:])
                            print(f"Event {count + 1}: {data.get('event', 'unknown')}")
                            count += 1
                        except:
                            pass
            else:
                text = await response.text()
                print(f"Run error: {text}")
    except Exception as e:
        print(f"Run error: {e}")

@pytest.mark.anyio
async def test_agent_chat_ui_compatibility():
    """Test specific Agent Chat UI compatibility requirements"""
    
    print("Testing Agent Chat UI compatibility...")
    base_url = "http://localhost:2024"
    
    async with aiohttp.ClientSession() as session:
        # Test what Agent Chat UI expects
        
        # 1. Check if assistant exists
        try:
            async with session.get(f"{base_url}/assistants/agent") as response:
                print(f"Assistant 'agent' exists: {response.status == 200}")
        except:
            print("Assistant check failed")
        
        # 2. Create thread for assistant
        try:
            async with session.post(f"{base_url}/assistants/agent/threads", json={}) as response:
                print(f"Create thread for assistant: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    print(f"Thread: {data}")
        except Exception as e:
            print(f"Thread creation failed: {e}")
        
        # 3. Test streaming format expected by Agent Chat UI
        thread_id = str(uuid.uuid4())
        stream_data = {
            "assistant_id": "agent",
            "input": {
                "messages": [{"type": "human", "content": "Test message"}]
            },
            "stream_mode": ["messages", "values"]  # Agent Chat UI expects both
        }
        
        try:
            async with session.post(f"{base_url}/threads/{thread_id}/runs/stream", json=stream_data) as response:
                print(f"Streaming test: {response.status}")
                if response.status == 200:
                    print("✅ Streaming works!")
                else:
                    text = await response.text()
                    print(f"❌ Streaming failed: {text}")
        except Exception as e:
            print(f"❌ Streaming error: {e}")

async def main():
    """Run all tests"""
    print("="*60)
    print("LANGGRAPH SERVER API COMPATIBILITY TESTS")
    print("="*60)
    
    await test_langgraph_server_api()
    print("\n" + "="*60)
    
    await test_agent_chat_ui_compatibility()
    print("\n" + "="*60)
    
    # await test_streaming_endpoint_with_assistant()
    
    print("TESTS COMPLETED")
    print("="*60)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
        sys.exit(1)
