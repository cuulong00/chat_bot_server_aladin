#!/bin/bash

# LangGraph Chatbot Deployment Script for Ubuntu VPS
# Run this script on your Ubuntu VPS to deploy the chatbot

set -e  # Exit on any error

echo "🚀 Starting LangGraph Chatbot deployment..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root


# --- Bỏ các bước cài đặt Docker, Qdrant, Postgres vì server đã có sẵn ---

# Clone repository if not exists
if [ ! -d "chat_bot_server" ]; then
    print_status "Cloning repository (tool-calling-improvements)..."
    git clone -b tool-calling-improvements git@github.com:cuulong00/chat_bot_server.git
    cd chat_bot_server
else
    print_status "Repository already exists, updating to tool-calling-improvements..."
    cd chat_bot_server
    # Force pull latest code from remote repo (overwrites all local files)
    git remote remove origin 2>/dev/null || true
    git remote add origin git@github.com:cuulong00/chat_bot_server.git
    git fetch origin tool-calling-improvements
    git reset --hard origin/tool-calling-improvements
fi

# Setup environment file
if [ ! -f ".env" ]; then
    print_status "Setting up environment file..."
    cp .env.docker .env
    print_warning "Please edit .env file with your actual API keys and configuration"
    print_warning "nano .env"
    read -p "Press Enter after you've configured the .env file..."
else
    print_status "Environment file already exists"
fi


# Build and start the application
print_status "Building and starting the application..."
docker-compose down 2>/dev/null || true
docker-compose build --no-cache
docker-compose up -d

# Wait for application to start
print_status "Waiting for application to start..."
sleep 30

# Check if application is running
if docker-compose ps | grep -q "Up"; then
    print_status "Application is running successfully!"
    
    # Get server IP
    SERVER_IP=$(curl -s ifconfig.me 2>/dev/null || echo "YOUR_SERVER_IP")
    
    echo ""
    echo "🎉 Deployment completed successfully!"
    echo ""
    echo "📋 Access Information:"
    echo "   • LangGraph Server: http://${SERVER_IP}:2024"
    echo "   • LangSmith Studio: https://smith.langchain.com/studio/?baseUrl=http://${SERVER_IP}:2024"
    echo ""
    echo "🔧 Management Commands:"
    echo "   • View logs: docker-compose logs -f"
    echo "   • Stop service: docker-compose down"
    echo "   • Restart service: docker-compose restart"
    echo "   • Check status: docker-compose ps"
    echo ""
    echo "📁 Project directory: $(pwd)"
    echo ""
else
    print_error "Application failed to start. Check logs with: docker-compose logs"
    exit 1
fi


print_status "Deployment script completed!"
print_warning "Remember to:"
print_warning "1. Configure your .env file with real API keys"
print_warning "2. Ensure your databases (PostgreSQL, Qdrant) are accessible"
print_warning "3. Test the authentication with Supabase"
print_warning "4. Monitor logs: docker-compose logs -f"
