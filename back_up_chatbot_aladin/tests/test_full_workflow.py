import requests
import json
import time

# Test complete LangGraph Server workflow for Agent Chat UI
base_url = "http://localhost:2024"

print("Testing complete LangGraph Server workflow...")
print("=" * 60)

# 1. Get existing assistant or create new one
print("1. Getting/Creating assistant...")
try:
    # Search for existing assistants
    search_response = requests.post(f"{base_url}/assistants/search", json={})
    assistants = search_response.json()
    
    if assistants:
        # Use first available assistant
        assistant_id = assistants[0]["assistant_id"]
        print(f"Using existing assistant: {assistant_id}")
    else:
        # Create new assistant
        create_response = requests.post(
            f"{base_url}/assistants", 
            json={"graph_id": "agent", "name": "Travel Agent"}
        )
        assistant_data = create_response.json()
        assistant_id = assistant_data["assistant_id"]
        print(f"Created new assistant: {assistant_id}")
        
    print(f"Assistant ID: {assistant_id}")
    
except Exception as e:
    print(f"Error with assistant: {e}")
    exit(1)

print("-" * 40)

# 2. Create thread
print("2. Creating thread...")
try:
    thread_response = requests.post(f"{base_url}/threads", json={})
    thread_data = thread_response.json()
    thread_id = thread_data["thread_id"]
    print(f"Created thread: {thread_id}")
except Exception as e:
    print(f"Error creating thread: {e}")
    exit(1)

print("-" * 40)



print("-" * 40)

# 4. Test non-streaming run for comparison
print("4. Testing non-streaming run...")
try:
    run_data_no_stream = {
        "assistant_id": assistant_id,
        "input": {
            "messages": [
                {
                    "type": "human", 
                    "content": "What's the weather like?",
                    "id": "test-msg-2"
                }
            ]
        }
    }
    
    response = requests.post(
        f"{base_url}/threads/{thread_id}/runs",
        json=run_data_no_stream
    )
    
    print(f"Non-streaming status: {response.status_code}")
    if response.status_code == 200:
        print("✅ Non-streaming works!")
        run_result = response.json()
        print(f"Run ID: {run_result.get('run_id', 'unknown')}")
    else:
        print(f"❌ Non-streaming failed: {response.text}")
        
except Exception as e:
    print(f"Error with non-streaming: {e}")

print("-" * 40)

# 5. Get thread history
print("5. Getting thread history...")
try:
    history_response = requests.post(f"{base_url}/threads/{thread_id}/history", json={})
    print(f"History status: {history_response.status_code}")
    if history_response.status_code == 200:
        history = history_response.json()
        print(f"Messages in thread: {len(history)}")
        for i, msg in enumerate(history[:3]):  # Show first 3 messages
            print(f"  {i+1}. {msg.get('type', 'unknown')}: {msg.get('content', 'no content')[:50]}...")
    else:
        print(f"History error: {history_response.text}")
except Exception as e:
    print(f"Error getting history: {e}")

print("=" * 60)
print("Agent Chat UI Setup Instructions:")
print("1. Use Deployment URL: http://localhost:2024")
print(f"2. Use Assistant ID: {assistant_id}")
print("3. Leave LangSmith API Key empty for local development")
print("=" * 60)

# 3. Test streaming run - DETAILED ANALYSIS
print("3. Testing streaming run - ANALYZING TOKEN STREAMING...")
try:
    run_data = {
        "assistant_id": assistant_id,
        "input": {
            "messages": [
                {
                    "type": "human", 
                    "content": "Hi there, what time is my flight? My passenger ID is 3442 587242.",
                    "id": "test-msg-1"
                }
            ]
        },
        "stream_mode": ["values", "messages"]
    }
    
    print(f"Sending to: {base_url}/threads/{thread_id}/runs/stream")
    print(f"Data: {json.dumps(run_data, indent=2)}")
    
    # Use streaming
    response = requests.post(
        f"{base_url}/threads/{thread_id}/runs/stream",
        json=run_data,
        stream=True,
        headers={"Accept": "text/event-stream"}
    )
    
    print(f"Stream response status: {response.status_code}")
    
    if response.status_code == 200:
        print("\n🔍 DETAILED STREAMING ANALYSIS:")
        print("=" * 50)
        count = 0
        full_content = ""
        token_count = 0
        chunk_sizes = []
        
        for line in response.iter_lines():
            if count >= 20:  # Increased to see more
                break
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith('data: '):
                    try:
                        data = json.loads(line_str[6:])
                        
                        # Analyze different event types
                        event_type = data.get('event', 'unknown')
                        
                        if 'data' in data and isinstance(data['data'], list):
                            # This is likely token streaming
                            for item in data['data']:
                                if isinstance(item, dict) and 'content' in item:
                                    content = item['content']
                                    chunk_sizes.append(len(content))
                                    full_content += content
                                    token_count += 1
                                    
                                    print(f"📝 Token {token_count}: '{content}' (length: {len(content)})")
                                    
                        elif 'data' in data and isinstance(data['data'], dict):
                            # This might be state updates
                            data_content = data['data']
                            if 'messages' in data_content:
                                print(f"📋 State update: {event_type}")
                            else:
                                print(f"🔄 Event: {event_type}")
                        else:
                            print(f"❓ Unknown event: {event_type}")
                            
                        count += 1
                        
                    except json.JSONDecodeError:
                        # Raw content might be tokens
                        raw_content = line_str[6:]  # Remove 'data: '
                        if raw_content.strip():
                            print(f"📄 Raw content: '{raw_content[:50]}...'")
                            count += 1
        
        print("=" * 50)
        print("📊 STREAMING ANALYSIS RESULTS:")
        print(f"Total events processed: {count}")
        print(f"Total tokens received: {token_count}")
        print(f"Full accumulated content: '{full_content[:100]}...'")
        
        if chunk_sizes:
            avg_chunk_size = sum(chunk_sizes) / len(chunk_sizes)
            print(f"Average chunk size: {avg_chunk_size:.2f} characters")
            print(f"Chunk sizes: {chunk_sizes[:10]}")  # First 10 chunk sizes
            
            if avg_chunk_size <= 2:
                print("✅ TRUE TOKEN-BY-TOKEN STREAMING (1-2 chars per chunk)")
            elif avg_chunk_size <= 10:
                print("⚠️  SMALL CHUNK STREAMING (3-10 chars per chunk)")
            else:
                print("❌ BATCH STREAMING (large chunks)")
        else:
            print("❓ No token-level content detected in stream")
            
        print("✅ Streaming analysis completed!")
        
    else:
        print(f"❌ Streaming failed: {response.text}")
        
except Exception as e:
    print(f"Error with streaming: {e}")
