#!/bin/bash


# Pull the latest code from the repository
echo "🔄 Pulling the latest code from feature/tool-calling-improvements branch..."
git fetch --all
git reset --hard origin/feature/tool-calling-improvements

# Replace the entire client directory with the latest version from git to avoid conflicts
echo "🧹 Replacing client directory with latest version from git..."
git checkout origin/feature/tool-calling-improvements -- client

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
