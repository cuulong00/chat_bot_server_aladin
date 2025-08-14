#!/bin/bash

# Pull the latest code from the repository
echo "🔄 Pulling the latest code..."
git pull

# Stop Docker containers
echo "🛑 Stopping Docker containers..."
docker-compose down

# Build Docker containers
echo "🔨 Building Docker containers..."
docker-compose build

# Start Docker containers with updated environment
echo "🚀 Starting Docker containers..."
docker-compose up -d

# Show container status
echo "📊 Container status:"
docker-compose ps

# Wait a moment for containers to start
echo "⏳ Waiting for containers to start..."
sleep 5

# View logs
echo "📋 Viewing logs (press Ctrl+C to exit)..."
docker-compose logs -f
