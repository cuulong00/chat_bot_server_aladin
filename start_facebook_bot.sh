#!/bin/bash

# Facebook Messenger Chatbot Startup Script

echo "🚀 Starting Facebook Messenger Chatbot..."
echo "========================================="

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    echo "Please create .env file with required Facebook credentials."
    exit 1
fi

# Check if required Facebook env vars are set
source .env

missing_vars=()

if [ -z "$FB_PAGE_ACCESS_TOKEN" ]; then
    missing_vars+=("FB_PAGE_ACCESS_TOKEN")
fi

if [ -z "$FB_APP_SECRET" ]; then
    missing_vars+=("FB_APP_SECRET")
fi

if [ -z "$FB_VERIFY_TOKEN" ]; then
    missing_vars+=("FB_VERIFY_TOKEN")
fi

if [ ${#missing_vars[@]} -ne 0 ]; then
    echo "❌ Error: Missing required environment variables:"
    for var in "${missing_vars[@]}"; do
        echo "   - $var"
    done
    echo ""
    echo "Please add these to your .env file."
    exit 1
fi

echo "✅ Environment variables check passed"
echo "✅ FB_VERIFY_TOKEN: ${FB_VERIFY_TOKEN:0:8}..."
echo "✅ FB_PAGE_ACCESS_TOKEN: ${FB_PAGE_ACCESS_TOKEN:0:8}..."
echo "✅ FB_APP_SECRET: ${FB_APP_SECRET:0:8}..."

# Start the server
echo ""
echo "🌟 Starting FastAPI server with Facebook Messenger integration..."
echo "📱 Webhook URL: http://localhost:8000/facebook/webhook"
echo "📖 API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Run the application
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
