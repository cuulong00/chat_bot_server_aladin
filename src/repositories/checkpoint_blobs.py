"""
Checkpoint blobs database operations
"""

import pandas as pd
import sqlalchemy
from typing import List, Dict, Any, Optional
from src.database.database import get_db_session

def get_checkpoint_blobs(
    thread_id: str,
    checkpoint_ns: str = "",
    channel: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get blobs for a specific thread and checkpoint namespace.
    
    Args:
        thread_id: The thread ID
        checkpoint_ns: Checkpoint namespace
        channel: Optional channel filter
        
    Returns:
        List of blob dictionaries
    """
    engine = get_db_session()
    
    conditions = ["thread_id = :thread_id", "checkpoint_ns = :checkpoint_ns"]
    params = {
        "thread_id": thread_id,
        "checkpoint_ns": checkpoint_ns
    }
    
    if channel:
        conditions.append("channel = :channel")
        params["channel"] = channel
    
    where_clause = " AND ".join(conditions)
    
    query = f"""
    SELECT 
        thread_id,
        checkpoint_ns,
        channel,
        version,
        type,
        blob
    FROM checkpoint_blobs
    WHERE {where_clause}
    ORDER BY version
    """
    
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
        raise Exception(f"Database error getting checkpoint blobs: {e}")

def get_blob_by_channel_version(
    thread_id: str,
    channel: str,
    version: str,
    checkpoint_ns: str = ""
) -> Optional[Dict[str, Any]]:
    """
    Get a specific blob by channel and version.
    
    Args:
        thread_id: The thread ID
        channel: The channel name
        version: The blob version
        checkpoint_ns: Checkpoint namespace
        
    Returns:
        Blob dictionary or None if not found
    """
    engine = get_db_session()
    
    query = """
    SELECT 
        thread_id,
        checkpoint_ns,
        channel,
        version,
        type,
        blob
    FROM checkpoint_blobs
    WHERE thread_id = :thread_id 
        AND channel = :channel
        AND version = :version
        AND checkpoint_ns = :checkpoint_ns
    """
    
    params = {
        "thread_id": thread_id,
        "channel": channel,
        "version": version,
        "checkpoint_ns": checkpoint_ns
    }
    
    try:
        with engine.connect() as conn:
            df = pd.read_sql(sqlalchemy.text(query), conn, params=params)
            if df.empty:
                return None
            
            result = df.to_dict("records")[0]
            
            # Convert blob data to string representation if needed
            if 'blob' in result and result['blob']:
                try:
                    # Try to decode blob as string
                    result['blob'] = result['blob'].decode('utf-8')
                except:
                    # If decoding fails, convert to hex string
                    result['blob'] = result['blob'].hex()
            
            engine.dispose()
            return result
    except Exception as e:
        engine.dispose()
        raise Exception(f"Database error getting blob: {e}")
