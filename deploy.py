#!/usr/bin/env python3
"""
Deployment and testing script for LangGraph Travel Agent with Agent Chat UI compatibility
"""

import subprocess
import sys
import os
import asyncio
import signal
from pathlib import Path

def install_requirements():
    """Install required packages"""
    requirements = [
        "langgraph-cli[inmem]",
        "langgraph-sdk", 
        "aiohttp",
        "fastapi",
        "uvicorn"
    ]
    
    print("Installing required packages...")
    for req in requirements:
        print(f"Installing {req}...")
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", req], check=True)
    
    print("✅ All packages installed successfully!")

def check_env_file():
    """Check if .env file exists and has required keys"""
    env_path = Path(".env")
    env_example_path = Path(".env.example")
    
    if not env_path.exists():
        if env_example_path.exists():
            print("⚠️  No .env file found. Please:")
            print("1. Copy .env.example to .env")
            print("2. Fill in your API keys")
            print("3. Run this script again")
            return False
        else:
            print("❌ No .env.example file found. Creating one...")
            return False
    
    # Check if .env has LANGSMITH_API_KEY
    with open(env_path, 'r') as f:
        content = f.read()
        if "LANGSMITH_API_KEY=" not in content or "your_api_key_here" in content:
            print("⚠️  Please set your LANGSMITH_API_KEY in .env file")
            print("You can get it from: https://smith.langchain.com/settings")
            return False
    
    print("✅ Environment file configured!")
    return True

def run_langgraph_server():
    """Run LangGraph server using langgraph dev command"""
    print("🚀 Starting LangGraph Server...")
    print("This will run on http://localhost:2024")
    print("Press Ctrl+C to stop the server")
    print("-" * 50)
    
    try:
        # Run langgraph dev
        process = subprocess.Popen(
            ["langgraph", "dev", "--host", "0.0.0.0", "--port", "2024"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        def signal_handler(signum, frame):
            print("\n🛑 Stopping LangGraph Server...")
            process.terminate()
            process.wait()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Stream output
        for line in process.stdout:
            print(line.strip())
            
    except FileNotFoundError:
        print("❌ langgraph command not found. Please install langgraph-cli:")
        print("pip install --upgrade 'langgraph-cli[inmem]'")
        return False
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
        return True
    except Exception as e:
        print(f"❌ Error running server: {e}")
        return False

def run_fastapi_fallback():
    """Fallback to FastAPI server if langgraph dev doesn't work"""
    print("🔄 Falling back to FastAPI server...")
    print("This will run on http://localhost:2024")
    print("Press Ctrl+C to stop the server")
    print("-" * 50)
    
    try:
        subprocess.run([
            sys.executable, "-m", "uvicorn", 
            "app:app", 
            "--host", "0.0.0.0", 
            "--port", "2024", 
            "--reload"
        ])
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
        return True

async def test_endpoints():
    """Test basic endpoints"""
    import aiohttp
    import json
    
    base_url = "http://localhost:2024"
    endpoints = [
        ("GET", "/info"),
        ("POST", "/threads/search"),
        ("POST", "/threads"),
    ]
    
    print("🔍 Testing endpoints...")
    
    async with aiohttp.ClientSession() as session:
        for method, endpoint in endpoints:
            url = f"{base_url}{endpoint}"
            try:
                if method == "GET":
                    async with session.get(url) as response:
                        if response.status == 200:
                            data = await response.json()
                            print(f"✅ {method} {endpoint}: OK")
                        else:
                            print(f"❌ {method} {endpoint}: {response.status}")
                else:
                    async with session.post(url, json={}) as response:
                        if response.status == 200:
                            data = await response.json()
                            print(f"✅ {method} {endpoint}: OK")
                        else:
                            print(f"❌ {method} {endpoint}: {response.status}")
            except Exception as e:
                print(f"❌ {method} {endpoint}: Connection failed - {e}")

def setup_agent_chat_ui():
    """Instructions for setting up Agent Chat UI"""
    print("\n" + "="*60)
    print("📱 AGENT CHAT UI SETUP INSTRUCTIONS")
    print("="*60)
    print()
    print("1. Clone Agent Chat UI:")
    print("   git clone https://github.com/langchain-ai/agent-chat-ui.git")
    print("   cd agent-chat-ui")
    print()
    print("2. Install dependencies:")
    print("   npm install")
    print()
    print("3. Set environment variables:")
    print("   # For development, create .env.local:")
    print("   echo 'NEXT_PUBLIC_API_URL=http://localhost:2024' > .env.local")
    print("   echo 'NEXT_PUBLIC_ASSISTANT_ID=agent' >> .env.local")
    print()
    print("4. Start the UI:")
    print("   npm run dev")
    print()
    print("5. Open browser:")
    print("   http://localhost:3000")
    print()
    print("6. In the UI, enter:")
    print("   - Deployment URL: http://localhost:2024")
    print("   - Assistant/Graph ID: agent")
    print("   - LangSmith API Key: (leave empty for local)")
    print()
    print("="*60)

def main():
    """Main deployment function"""
    print("🤖 LangGraph Travel Agent Deployment")
    print("="*50)
    
    # Check current directory
    if not Path("langgraph.json").exists():
        print("❌ langgraph.json not found. Please run from project root.")
        sys.exit(1)
    
    # Install requirements
    try:
        install_requirements()
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install requirements: {e}")
        sys.exit(1)
    
    # Check environment
    if not check_env_file():
        sys.exit(1)
    
    # Show setup instructions
    setup_agent_chat_ui()
    
    # Ask user how to proceed
    print("\nChoose deployment option:")
    print("1. LangGraph Server (recommended)")
    print("2. FastAPI Server (fallback)")
    print("3. Test endpoints only")
    print("4. Exit")
    
    choice = input("\nEnter choice (1-4): ").strip()
    
    if choice == "1":
        success = run_langgraph_server()
        if not success:
            print("\n🔄 LangGraph server failed, trying FastAPI fallback...")
            run_fastapi_fallback()
    elif choice == "2":
        run_fastapi_fallback()
    elif choice == "3":
        print("Please start the server first, then run tests...")
        input("Press Enter after starting server...")
        asyncio.run(test_endpoints())
    elif choice == "4":
        print("👋 Goodbye!")
        sys.exit(0)
    else:
        print("❌ Invalid choice")
        sys.exit(1)

if __name__ == "__main__":
    main()
