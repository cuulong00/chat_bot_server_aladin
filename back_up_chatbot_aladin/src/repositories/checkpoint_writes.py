"""
Checkpoint writes database operations
"""

import pandas as pd
import sqlalchemy
from typing import List, Dict, Any
from src.database.database import get_db_connection

def get_checkpoint_tasks(
    thread_id: str,
    checkpoint_id: str,
    checkpoint_ns: str = ""
) -> List[Dict[str, Any]]:
    """
    Get tasks (writes) for a specific checkpoint.
    
    Args:
        thread_id: The thread ID
        checkpoint_id: The checkpoint ID
        checkpoint_ns: Checkpoint namespace
        
    Returns:
        List of task dictionaries
    """
    engine = get_db_connection()
    
    query = """
    SELECT 
        thread_id,
        checkpoint_ns,
        checkpoint_id,
        task_id,
        idx,
        channel,
        type,
        blob,
        task_path
    FROM checkpoint_writes
    WHERE thread_id = :thread_id 
        AND checkpoint_id = :checkpoint_id
        AND checkpoint_ns = :checkpoint_ns
    ORDER BY idx
    """
    
    params = {
        "thread_id": thread_id,
        "checkpoint_id": checkpoint_id,
        "checkpoint_ns": checkpoint_ns
    }
    
    try:
        with engine.connect() as conn:
            df = pd.read_sql(sqlalchemy.text(query), conn, params=params)
            results = df.to_dict("records")
            
            # Convert blob data to string representation if needed
            for result in results:
                if 'blob' in result and result['blob']:
                    try:
                        # Try to decode blob as string
                        result['blob'] = result['blob'].decode('utf-8')
                    except:
                        # If decoding fails, convert to hex string
                        result['blob'] = result['blob'].hex()
            
            engine.dispose()
            return results
    except Exception as e:
        engine.dispose()
        raise Exception(f"Database error getting checkpoint tasks: {e}")

def get_tasks_by_thread(
    thread_id: str,
    checkpoint_ns: str = ""
) -> List[Dict[str, Any]]:
    """
    Get all tasks for a thread across all checkpoints.
    
    Args:
        thread_id: The thread ID
        checkpoint_ns: Checkpoint namespace
        
    Returns:
        List of task dictionaries grouped by checkpoint
    """
    engine = get_db_connection()
    
    query = """
    SELECT 
        thread_id,
        checkpoint_ns,
        checkpoint_id,
        task_id,
        idx,
        channel,
        type,
        blob,
        task_path
    FROM checkpoint_writes
    WHERE thread_id = :thread_id 
        AND checkpoint_ns = :checkpoint_ns
    ORDER BY checkpoint_id, idx
    """
    
    params = {
        "thread_id": thread_id,
        "checkpoint_ns": checkpoint_ns
    }
    
    try:
        with engine.connect() as conn:
            df = pd.read_sql(sqlalchemy.text(query), conn, params=params)
            results = df.to_dict("records")
            
            # Convert blob data to string representation if needed
            for result in results:
                if 'blob' in result and result['blob']:
                    try:
                        # Try to decode blob as string
                        result['blob'] = result['blob'].decode('utf-8')
                    except:
                        # If decoding fails, convert to hex string
                        result['blob'] = result['blob'].hex()
            
            engine.dispose()
            return results
    except Exception as e:
        engine.dispose()
        raise Exception(f"Database error getting thread tasks: {e}")
