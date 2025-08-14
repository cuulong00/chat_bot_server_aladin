#!/bin/bash

# Pull the latest code from the repository
echo "Pulling the latest code..."
git pull

# Stop Docker containers
echo "Stopping Docker containers..."
docker-compose down

# Build Docker containers
echo "Building Docker containers..."
docker-compose build

# Start Docker containers
echo "Starting Docker containers..."
docker-compose up -d

# View logs
echo "Viewing logs..."
docker-compose logs -f
