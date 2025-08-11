#!/bin/bash

# LangGraph Chatbot Deployment Script for Ubuntu VPS
# Run this script on your Ubuntu VPS to deploy the chatbot

set -e  # Exit on any error
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}
# Build and start the application
print_status "Building and starting the application..."
docker-compose down 2>/dev/null || true
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