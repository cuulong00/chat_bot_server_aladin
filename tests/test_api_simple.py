import requests
import json

# Test LangGraph Server API endpoints
base_url = "http://localhost:2024"

print("Testing LangGraph Server API endpoints...")
print("=" * 50)

# 1. Test /assistants endpoint with empty body
try:
    response = requests.post(f"{base_url}/assistants", json={})
    print(f"POST /assistants: {response.status_code}")
    if response.status_code == 200:
        print(json.dumps(response.json(), indent=2))
    else:
        print(f"Error: {response.text}")
except Exception as e:
    print(f"Error: {e}")

print("-" * 30)

# 2. Test /assistants with proper body
try:
    response = requests.post(f"{base_url}/assistants", json={"graph_id": "agent"})
    print(f"POST /assistants (with graph_id): {response.status_code}")
    if response.status_code == 200:
        print(json.dumps(response.json(), indent=2))
    else:
        print(f"Error: {response.text}")
except Exception as e:
    print(f"Error: {e}")

print("-" * 30)

# 3. Check what graphs are available
try:
    response = requests.get(f"{base_url}/")
    print(f"GET /: {response.status_code}")
    if response.status_code == 200:
        print("Server is running")
except Exception as e:
    print(f"Error: {e}")

print("-" * 30)

# 4. Try to create and use a thread directly with graph
try:
    # Create thread
    thread_response = requests.post(f"{base_url}/threads", json={})
    print(f"POST /threads: {thread_response.status_code}")
    
    if thread_response.status_code == 200:
        thread_data = thread_response.json()
        thread_id = thread_data["thread_id"]
        print(f"Created thread: {thread_id}")
        
        # Try to run with the graph directly
        run_data = {
            "input": {
                "messages": [
                    {"type": "human", "content": "Hello, what's my flight status?"}
                ]
            }
        }
        
        # Use runs endpoint with graph name
        run_response = requests.post(
            f"{base_url}/threads/{thread_id}/runs", 
            json=run_data
        )
        print(f"POST /threads/{thread_id}/runs: {run_response.status_code}")
        if run_response.status_code == 200:
            print("Run created successfully")
            print(json.dumps(run_response.json(), indent=2))
        else:
            print(f"Run error: {run_response.text}")
            
except Exception as e:
    print(f"Error: {e}")

print("-" * 30)

# 5. Check available graphs/assistants
try:
    response = requests.post(f"{base_url}/assistants/search", json={})
    print(f"POST /assistants/search: {response.status_code}")
    if response.status_code == 200:
        print(json.dumps(response.json(), indent=2))
    else:
        print(f"Error: {response.text}")
except Exception as e:
    print(f"Error: {e}")

print("=" * 50)
