# 🚀 LangGraph Chatbot Deployment Guide

Hướng dẫn triển khai LangGraph Chatbot với authentication trên VPS Ubuntu sử dụng Docker.

## 📋 Prerequisites

### VPS Requirements
- Ubuntu 20.04+ 
- 2GB+ RAM
- 1 CPU core
- 20GB+ storage
- Public IP address

### Required Services
- PostgreSQL database (accessible from VPS)
- Qdrant vector database (accessible from VPS)
- Supabase project (for authentication)

### API Keys Required
- OpenAI API Key
- Google API Key (for embeddings/TTS)
- Groq API Key
- Tavily API Key (for search)
- Supabase URL & Service Key
- SerpAPI Key

## 🔧 Quick Deployment

### Method 1: Auto Deployment Script (Recommended)

```bash
# Download and run deployment script
wget https://raw.githubusercontent.com/cuulong00/chat_bot_server/main/deploy.sh
chmod +x deploy.sh
./deploy.sh
```

### Method 2: Manual Deployment

```bash
# 1. Install Docker and Docker Compose
sudo apt update && sudo apt upgrade -y
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
newgrp docker

# 2. Clone repository
git clone https://github.com/cuulong00/chat_bot_server.git
cd chat_bot_server

# 3. Setup environment
cp .env.docker .env
nano .env  # Fill in your API keys (see below)

# 4. Deploy
docker-compose up -d
```

## ⚙️ Environment Configuration

Copy `.env.docker` to `.env` and fill in your values:

```bash
# Required API Keys
TAVILY_API_KEY=your_tavily_api_key
OPENAI_API_KEY=your_openai_api_key
GOOGLE_API_KEY=your_google_api_key
GROQ_API_KEY=your_groq_api_key
SERPAPI_API_KEY=your_serpapi_key
HF_TOKEN=your_huggingface_token

# Supabase Authentication
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your_service_role_secret_key

# Database Configuration
POSTGRES_HOST=your_postgres_host:5432
POSTGRES_DB=chatbot_db
POSTGRES_USER=your_username
POSTGRES_PASSWORD=your_password
DATABASE_CONNECTION=postgresql://user:pass@host:5432/db?sslmode=disable
POSTGRES_URI_CUSTOM=postgresql://user:pass@host:5432/db?sslmode=disable

# Vector Database
QDRANT_HOST=your_qdrant_host
QDRANT_PORT=6333

# Model Configuration
EMBEDDING_MODEL=gemini-embedding-exp-03-07
```

## 🔐 Supabase Setup

1. **Create Supabase Project**: https://supabase.com/dashboard
2. **Get Project URL**: Project Settings → API → Project URL
3. **Get Service Key**: Project Settings → API → Service Role Secret Key
4. **Enable Authentication**: Authentication → Settings → Enable Email/Password

## 🗄️ Database Setup

### PostgreSQL
- Create database: `chatbot_db`
- Ensure VPS can connect to your PostgreSQL instance
- Update connection string in `.env`

### Qdrant Vector Database
- Setup Qdrant instance (cloud or self-hosted)
- Ensure VPS can access Qdrant on port 6333
- Update host/port in `.env`

## 🚀 Deployment Steps

### 1. Deploy Application
```bash
# Build and start services
docker-compose build --no-cache
docker-compose up -d
```

### 2. Verify Deployment
```bash
# Check container status
docker-compose ps

# View logs
docker-compose logs -f chatbot

# Test health endpoint
curl http://localhost:2024/health
```

### 3. Access Application
- **LangGraph Server**: `http://your-vps-ip:2024`
- **LangSmith Studio**: `https://smith.langchain.com/studio/?baseUrl=http://your-vps-ip:2024`

## 🔧 Management Commands

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

# Specific service
docker-compose logs -f chatbot

# Last 100 lines
docker-compose logs --tail=100 chatbot
```

### Health Checks
```bash
# Container status
docker-compose ps

# Application health
curl http://localhost:2024/health

# Resource usage
docker stats
```

## 🌐 Domain & SSL Setup (Optional)

### 1. Setup Nginx Reverse Proxy
```bash
# Install Nginx
sudo apt install nginx -y

# Create config
sudo nano /etc/nginx/sites-available/chatbot
```

Nginx configuration:
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
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/chatbot /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 2. SSL with Let's Encrypt
```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx -y

# Get certificate
sudo certbot --nginx -d your-domain.com

# Auto-renewal
sudo systemctl enable certbot.timer
```

## 🛠️ Troubleshooting

### Common Issues

1. **Container won't start**
   ```bash
   # Check logs
   docker-compose logs chatbot
   
   # Rebuild
   docker-compose build --no-cache
   ```

2. **Database connection failed**
   - Verify database credentials in `.env`
   - Ensure VPS can reach database host
   - Check firewall settings

3. **Authentication errors**
   - Verify Supabase URL and Service Key
   - Check Supabase project settings
   - Ensure authentication is enabled

4. **Port 2024 in use**
   ```bash
   # Change port in docker-compose.yml
   ports:
     - "3000:2024"  # Use port 3000 instead
   ```

### Debug Container
```bash
# Access container shell
docker-compose exec chatbot bash

# Check environment variables
docker-compose exec chatbot env | grep SUPABASE

# Test Python imports
docker-compose exec chatbot python -c "import langgraph; print('OK')"
```

## 📊 Monitoring

### Application Monitoring
```bash
# Real-time logs
docker-compose logs -f

# Resource usage
docker stats

# Disk usage
df -h
docker system df
```

### Performance Optimization
```bash
# Clean up Docker
docker system prune -a

# Restart services
docker-compose restart

# Monitor memory usage
free -h
```

## 🔒 Security Best Practices

1. **Firewall Configuration**
   ```bash
   sudo ufw enable
   sudo ufw allow ssh
   sudo ufw allow 2024
   sudo ufw allow 80
   sudo ufw allow 443
   ```

2. **Environment Security**
   - Never commit `.env` files
   - Use strong passwords
   - Regularly rotate API keys
   - Enable Supabase RLS (Row Level Security)

3. **Regular Updates**
   ```bash
   # Update system
   sudo apt update && sudo apt upgrade -y
   
   # Update application
   git pull
   docker-compose build --no-cache
   docker-compose up -d
   ```

## 📚 API Documentation

### Authentication Flow
1. User logs in via Supabase (client app)
2. Client receives JWT access token
3. Client sends requests with `Authorization: Bearer <token>`
4. Server validates token with Supabase
5. Server allows/denies access based on token validity

### API Endpoints
- `GET /health` - Health check
- `POST /threads` - Create conversation thread
- `GET /threads/{thread_id}` - Get thread messages
- `POST /threads/{thread_id}/messages` - Send message
- `GET /threads/{thread_id}/state` - Get thread state

## 🚨 Emergency Procedures

### Complete Reset
```bash
# Stop all services
docker-compose down

# Remove containers and volumes
docker-compose down -v

# Rebuild from scratch
docker-compose build --no-cache
docker-compose up -d
```

### Backup Important Data
```bash
# Backup environment file
cp .env .env.backup

# Export logs
docker-compose logs > deployment.log
```

## 📞 Support

- **Repository**: https://github.com/cuulong00/chat_bot_server
- **Issues**: Report bugs via GitHub Issues
- **Documentation**: Check README.md and code comments

---

## 🎉 Success Indicators

When deployment is successful, you should see:

```bash
✅ Container status: Up
✅ Health check: HTTP 200 OK
✅ Authentication: Supabase connected
✅ Database: PostgreSQL connected
✅ Vector DB: Qdrant connected
✅ LangSmith Studio: Accessible
```

**Your LangGraph Chatbot is now live and ready for production! 🚀**