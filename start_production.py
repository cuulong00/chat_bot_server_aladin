#!/usr/bin/env python3
"""
Production startup script for LangGraph Chatbot
This script includes proper error handling and startup verification.
"""

import os
import sys
import asyncio
import logging
from pathlib import Path

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def verify_environment():
    """Verify all required environment variables are set"""
    required_vars = [
        'SUPABASE_URL',
        'SUPABASE_SERVICE_KEY',
        'DATABASE_CONNECTION',
        'GOOGLE_API_KEY',
        'OPENAI_API_KEY',
        'QDRANT_HOST',
        'QDRANT_PORT'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        sys.exit(1)
    
    logger.info("All required environment variables are set")

def verify_imports():
    """Verify all critical imports work"""
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        # Test critical imports
        from fastapi import FastAPI
        from src.auth.langgraph_auth import auth
        from src.graphs.travel.travel_graph import compile_graph_with_checkpointer
        from src.database.checkpointer import get_checkpointer_ctx
        
        logger.info("All critical imports successful")
        return True
        
    except ImportError as e:
        logger.error(f"Import error: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during import verification: {e}")
        return False

async def verify_database_connection():
    """Verify database connection works"""
    try:
        from src.database.checkpointer import get_checkpointer_ctx
        
        with get_checkpointer_ctx() as checkpointer:
            logger.info("Database connection verified")
            return True
            
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False

def main():
    """Main startup function"""
    logger.info("Starting LangGraph Chatbot...")
    
    # Verify environment
    verify_environment()
    
    # Verify imports
    if not verify_imports():
        logger.error("Import verification failed")
        sys.exit(1)
    
    # Verify database connection
    try:
        loop = asyncio.get_event_loop()
        if not loop.run_until_complete(verify_database_connection()):
            logger.error("Database verification failed")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Database verification error: {e}")
        sys.exit(1)
    
    # Import and start the app
    try:
        import uvicorn
        from webapp import app
        
        logger.info("Starting FastAPI server...")
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=2024,
            log_level="info",
            access_log=True
        )
        
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
