# LangGraph Chatbot - Docker Deployment Guide

## Prerequisites
- Ubuntu VPS with Docker and Docker Compose installed
- Git installed
- Access to your databases (PostgreSQL, Qdrant)
- All required API keys

## Quick Start

### 1. Clone Repository
```bash
git clone https://github.com/cuulong00/chat_bot_server.git
cd chat_bot_server
```

### 2. Setup Environment Variables
```bash
# Copy environment template
cp .env.docker .env

# Edit with your actual values
nano .env
```

### 3. Deploy with Docker Compose
```bash
# Build and start the application
docker-compose up -d

# Check logs
docker-compose logs -f chatbot

# Check status
docker-compose ps
```

### 4. Access Application
- LangGraph Server: `http://your-vps-ip:2024`
- LangSmith Studio: `https://smith.langchain.com/studio/?baseUrl=http://your-vps-ip:2024`

## Environment Variables Configuration

### Required API Keys
```bash
TAVILY_API_KEY=your_tavily_api_key
GOOGLE_API_KEY=your_google_api_key
GROQ_API_KEY=your_groq_api_key
SERPAPI_API_KEY=your_serpapi_key
HF_TOKEN=your_huggingface_token
```

### Supabase Authentication
```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your_service_role_secret_key
```

### Database Configuration
```bash
POSTGRES_HOST=your_postgres_host:5432
POSTGRES_DB=chatbot_db
POSTGRES_USER=your_username
POSTGRES_PASSWORD=your_password
DATABASE_CONNECTION=postgresql://user:pass@host:5432/db?sslmode=disable
```

### Vector Database
```bash
QDRANT_HOST=your_qdrant_host
QDRANT_PORT=6333
```

## Production Deployment Steps

### 1. Server Setup
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo apt install docker-compose-plugin

# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker
```

### 2. Clone and Configure
```bash
git clone https://github.com/cuulong00/chat_bot_server.git
cd chat_bot_server

# Setup environment
cp .env.docker .env
nano .env  # Fill in your actual values
```

### 3. Deploy
```bash
# Build and start
docker-compose up -d

# Monitor logs
docker-compose logs -f
```

### 4. Setup Reverse Proxy (Optional)
```bash
# Install Nginx
sudo apt install nginx

# Create Nginx config
sudo nano /etc/nginx/sites-available/chatbot
```

Nginx config:
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:2024;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/chatbot /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## Management Commands

### Start/Stop Services
```bash
# Start
docker-compose up -d

# Stop
docker-compose down

# Restart
docker-compose restart

# Update and restart
git pull
docker-compose build --no-cache
docker-compose up -d
```

### View Logs
```bash
# All logs
docker-compose logs -f

# Specific service logs
docker-compose logs -f chatbot

# Last 100 lines
docker-compose logs --tail=100 chatbot
```

### Health Check
```bash
# Check container status
docker-compose ps

# Health check endpoint
curl http://localhost:2024/health
```

## Monitoring and Troubleshooting

### Common Issues
1. **Port 2024 already in use**: Change port in docker-compose.yml
2. **Database connection failed**: Check database credentials and network access
3. **Authentication errors**: Verify Supabase configuration
4. **API key errors**: Ensure all required API keys are set

### Debug Container
```bash
# Access container shell
docker-compose exec chatbot bash

# Check environment variables
docker-compose exec chatbot env | grep SUPABASE

# Check application logs
docker-compose logs chatbot
```

### Performance Monitoring
```bash
# Resource usage
docker stats

# Container health
docker-compose ps
curl http://localhost:2024/health
```

## Security Considerations

1. **Environment Variables**: Never commit .env files with real credentials
2. **Firewall**: Only expose necessary ports (2024, 80, 443)
3. **SSL/TLS**: Use HTTPS in production with Let's Encrypt
4. **Updates**: Regularly update Docker images and system packages
5. **Backup**: Backup your .env file and application data

## SSL Setup with Let's Encrypt (Optional)
```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Get SSL certificate
sudo certbot --nginx -d your-domain.com

# Auto-renewal
sudo systemctl enable certbot.timer
```

## Backup and Restore
```bash
# Backup environment file
cp .env .env.backup

# Backup application data (if any volumes)
docker-compose exec chatbot tar -czf /tmp/backup.tar.gz /app/data

# Copy backup from container
docker cp container_name:/tmp/backup.tar.gz ./backup.tar.gz
```
