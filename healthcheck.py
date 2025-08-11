#!/usr/bin/env python3
"""
Docker healthcheck script for LangGraph Chatbot
This script checks if the application is running and responding properly.
"""

import sys
import httpx
import asyncio
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_health():
    """Check if the application is healthy"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Check health endpoint
            response = await client.get("http://localhost:2024/health")
            
            if response.status_code == 200:
                logger.info("Health check passed")
                return True
            else:
                logger.error(f"Health check failed with status: {response.status_code}")
                return False
                
    except httpx.TimeoutException:
        logger.error("Health check timed out")
        return False
    except Exception as e:
        logger.error(f"Health check failed with error: {e}")
        return False

def main():
    """Main health check function"""
    try:
        loop = asyncio.get_event_loop()
        is_healthy = loop.run_until_complete(check_health())
        
        if is_healthy:
            sys.exit(0)  # Success
        else:
            sys.exit(1)  # Failure
            
    except Exception as e:
        logger.error(f"Health check script failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
