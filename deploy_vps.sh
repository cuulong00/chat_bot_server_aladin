#!/usr/bin/env bash

set -euo pipefail

REPO_URL="https://github.com/cuulong00/chat_bot_server_aladin.git"
APP_DIR="chat_bot_server_aladin"
PORT=2025

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()  { echo -e "${RED}[ERROR]${NC} $1"; }

info "Starting deployment for ${REPO_URL} on port ${PORT}..."

# Ensure Docker and docker-compose exist
if ! command -v docker >/dev/null 2>&1; then
  err "Docker not found. Please install Docker first."
  exit 1
fi
if ! command -v docker-compose >/dev/null 2>&1; then
  warn "docker-compose not found; attempting 'docker compose' fallback"
  if ! docker compose version >/dev/null 2>&1; then
    err "Neither docker-compose nor 'docker compose' available. Install Docker Compose."
    exit 1
  fi
fi

# Clone or update repo
if [ ! -d "$APP_DIR" ]; then
  info "Cloning repository..."
  git clone "$REPO_URL" "$APP_DIR"
else
  info "Repository exists, pulling latest..."
  cd "$APP_DIR"
  git fetch origin
  git reset --hard origin/feature/tool-calling-improvements
  cd - >/dev/null
fi

cd "$APP_DIR"

# Prepare env file
if [ ! -f .env ]; then
  if [ -f .env.docker ]; then
    info "Creating .env from .env.docker"
    cp .env.docker .env
    warn "Update .env with real secrets before going to production."
  else
    warn ".env not found and .env.docker missing; create .env manually."
    touch .env
  fi
fi

# Ensure docker-compose exposes 2024:2024 (container listens on 2024)
if ! grep -q '"2024:2024"' docker-compose.yml; then
  warn "Make sure docker-compose.yml maps 2024:2024 under services.chatbot."
fi

# Build and run
if command -v docker-compose >/dev/null 2>&1; then
  DC="docker-compose"
else
  DC="docker compose"
fi

info "Building images..."
$DC down || true
$DC build --no-cache

info "Starting services..."
$DC up -d

info "Waiting for the app to become healthy..."
sleep 20

$DC ps

SERVER_IP=$(curl -s ifconfig.me || echo "69.197.187.234")

echo
echo "🎉 Deployment completed"
echo "API base: http://${SERVER_IP}:${PORT}"
echo "Health:   http://${SERVER_IP}:${PORT}/health"
echo
echo "Useful commands:"
echo "  $DC logs -f"
echo "  $DC ps"
echo "  $DC restart"
echo "  $DC down"
