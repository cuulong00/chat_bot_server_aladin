# Use Python 3.11 slim image (compatible with langgraph-server)
FROM python:3.11-slim

# Set environment variables to avoid interactive prompts
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    apt-utils \
    gcc \
    g++ \
    curl \
    git \
    libpq-dev \
    postgresql-client \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies (as root before switching user)
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir --root-user-action=ignore --use-pep517 -r requirements.txt

# Copy the entire project
COPY . .

# Create non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 2024

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python healthcheck.py || exit 1

# Command to run the application
CMD ["langgraph", "dev", "--config", "langgraph.json", "--host", "0.0.0.0", "--port", "2024"]
