## PHẦN 2: REDIS DEPLOYMENT TRÊN UBUNTU VPS

### 2.1. Chuẩn bị VPS

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo apt install docker-compose -y

# Reboot to apply docker group changes
sudo reboot
```

### 2.2. Redis Docker Setup

#### A. Tạo thư mục project

```bash
mkdir -p ~/chatbot-redis
cd ~/chatbot-redis
```

#### B. Tạo docker-compose.yml

```yaml
# docker-compose.yml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    container_name: chatbot-redis
    restart: unless-stopped
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
      - ./redis.conf:/usr/local/etc/redis/redis.conf
    command: redis-server /usr/local/etc/redis/redis.conf
    environment:
      - REDIS_REPLICATION_MODE=master
    networks:
      - chatbot-network
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 30s
      timeout: 10s
      retries: 3
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  redis-commander:
    image: rediscommander/redis-commander:latest
    container_name: redis-commander
    restart: unless-stopped
    ports:
      - "8081:8081"
    environment:
      - REDIS_HOSTS=chatbot-redis:chatbot-redis:6379
      - HTTP_USER=admin
      - HTTP_PASSWORD=your-secure-password-here
    networks:
      - chatbot-network
    depends_on:
      - redis

volumes:
  redis_data:
    driver: local

networks:
  chatbot-network:
    driver: bridge
```

#### C. Tạo redis.conf

```bash
# redis.conf
# Network
bind 0.0.0.0
port 6379

# General
daemonize no
supervised no
pidfile /var/run/redis_6379.pid

# Logging
loglevel notice
logfile ""

# Persistence
save 900 1
save 300 10
save 60 10000
stop-writes-on-bgsave-error yes
rdbcompression yes
rdbchecksum yes
dbfilename dump.rdb
dir /data

# Memory Management
maxmemory 512mb
maxmemory-policy allkeys-lru

# Streams Configuration (CRITICAL for our use case)
stream-node-max-bytes 4096
stream-node-max-entries 100

# Performance Tuning for Low Latency
tcp-keepalive 60
tcp-nodelay yes
timeout 0

# Client Management
maxclients 10000

# Security (uncomment and set password in production)
# requirepass your-strong-password-here

# Disable dangerous commands
rename-command FLUSHDB ""
rename-command FLUSHALL ""
rename-command DEBUG ""
```

#### D. Security Setup

```bash
# Tạo file .env cho passwords
cat > .env << EOF
REDIS_PASSWORD=your-very-secure-redis-password-2024
REDIS_COMMANDER_USER=admin
REDIS_COMMANDER_PASSWORD=your-secure-admin-password-2024
EOF

# Set permissions
chmod 600 .env
```

#### E. Firewall Configuration

```bash
# Configure UFW firewall
sudo ufw allow ssh
sudo ufw allow 6379/tcp  # Redis port - only if needed externally
sudo ufw allow 8081/tcp  # Redis Commander - restrict to your IP
sudo ufw --force enable

# For production - restrict Redis Commander to specific IP
sudo ufw delete allow 8081/tcp
sudo ufw allow from YOUR_IP_ADDRESS to any port 8081
```

### 2.3. Redis Deployment và Monitoring

#### A. Deploy Redis

```bash
# Start Redis services
docker-compose up -d

# Verify deployment
docker-compose logs redis
docker-compose ps

# Test Redis connection
docker exec -it chatbot-redis redis-cli ping
# Should return: PONG

# Test streams functionality
docker exec -it chatbot-redis redis-cli XADD test-stream "*" message "hello"
docker exec -it chatbot-redis redis-cli XREAD STREAMS test-stream 0
```

#### B. Monitoring Script

```bash
# create redis-monitor.sh
cat > redis-monitor.sh << 'EOF'
#!/bin/bash

echo "=== Redis Health Check ==="
echo "Date: $(date)"
echo

# Container status
echo "Container Status:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep redis

echo

# Redis info
echo "Redis Info:"
docker exec chatbot-redis redis-cli info server | grep -E "(redis_version|uptime_in_seconds|connected_clients)"

echo

# Memory usage
echo "Memory Usage:"
docker exec chatbot-redis redis-cli info memory | grep -E "(used_memory_human|maxmemory_human)"

echo

# Stream info
echo "Messenger Stream Info:"
docker exec chatbot-redis redis-cli XINFO STREAM messenger:events 2>/dev/null || echo "Stream not created yet"

echo

# Consumer group info
echo "Consumer Group Info:"
docker exec chatbot-redis redis-cli XINFO GROUPS messenger:events 2>/dev/null || echo "Consumer group not created yet"

echo "================================"
EOF

chmod +x redis-monitor.sh

# Run monitoring
./redis-monitor.sh
```

#### C. Backup Script

```bash
# create backup-redis.sh
cat > backup-redis.sh << 'EOF'
#!/bin/bash

BACKUP_DIR="/home/ubuntu/redis-backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="redis-backup-${DATE}.rdb"

mkdir -p $BACKUP_DIR

# Create backup
docker exec chatbot-redis redis-cli BGSAVE
sleep 5

# Copy backup file
docker cp chatbot-redis:/data/dump.rdb $BACKUP_DIR/$BACKUP_FILE

echo "Backup created: $BACKUP_DIR/$BACKUP_FILE"

# Keep only last 7 days of backups
find $BACKUP_DIR -name "redis-backup-*.rdb" -mtime +7 -delete

# Verify backup
if [ -f "$BACKUP_DIR/$BACKUP_FILE" ]; then
    echo "✅ Backup successful"
else
    echo "❌ Backup failed"
    exit 1
fi
EOF

chmod +x backup-redis.sh

# Setup cron for daily backups
(crontab -l 2>/dev/null; echo "0 2 * * * /home/ubuntu/chatbot-redis/backup-redis.sh") | crontab -
```

### 2.4. Production Optimizations

#### A. System Optimizations

```bash
# Optimize system for Redis
echo 'vm.overcommit_memory = 1' | sudo tee -a /etc/sysctl.conf
echo 'net.core.somaxconn = 65535' | sudo tee -a /etc/sysctl.conf
echo 'echo never > /sys/kernel/mm/transparent_hugepage/enabled' | sudo tee -a /etc/rc.local

# Apply immediately
sudo sysctl -p
echo never | sudo tee /sys/kernel/mm/transparent_hugepage/enabled
```

#### B. Docker Optimizations

```bash
# Create optimized docker-compose.override.yml for production
cat > docker-compose.override.yml << 'EOF'
version: '3.8'

services:
  redis:
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: '1.0'
        reservations:
          memory: 512M
          cpus: '0.5'
    ulimits:
      memlock: -1
      nofile: 65535
    sysctls:
      - net.core.somaxconn=65535
EOF
```
