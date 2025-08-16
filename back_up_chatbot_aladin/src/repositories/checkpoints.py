"""
Checkpoint database operations
"""

import pandas as pd
import sqlalchemy
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from src.database.database import get_db_connection, DatabaseManager, DB_URI
from sqlalchemy import create_engine, text, inspect, select, func, literal_column
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import sessionmaker

# Create an engine with echo=True for logging
engine = create_engine(DB_URI, echo=True)
Session = sessionmaker(bind=engine)


def get_thread_checkpoints(
    thread_id: str,
    limit: int = 10,
    before_checkpoint_id: Optional[str] = None,
    checkpoint_ns: str = "",
) -> List[Dict[str, Any]]:
    """
    Get checkpoints for a specific thread with pagination support.

    Args:
        thread_id: The thread ID to get checkpoints for
        limit: Maximum number of checkpoints to return
        before_checkpoint_id: Get checkpoints before this checkpoint ID
        checkpoint_ns: Checkpoint namespace filter

    Returns:
        List of checkpoint dictionaries
    """
    engine = get_db_connection()

    # Build query with optional filters
    conditions = ["thread_id = :thread_id"]
    params = {"thread_id": thread_id, "limit": limit}

    if checkpoint_ns:
        conditions.append("checkpoint_ns = :checkpoint_ns")
        params["checkpoint_ns"] = checkpoint_ns
    else:
        conditions.append("checkpoint_ns = ''")

    # Add before filter if provided
    if before_checkpoint_id:
        conditions.append("checkpoint_id < :before_checkpoint_id")
        params["before_checkpoint_id"] = before_checkpoint_id

    where_clause = " AND ".join(conditions)

    query = f"""
    SELECT 
        thread_id,
        checkpoint_ns,
        checkpoint_id,
        parent_checkpoint_id,
        type,
        checkpoint,
        metadata,
        created_at
    FROM checkpoints
    WHERE {where_clause}
    ORDER BY checkpoint_id DESC
    LIMIT :limit
    """

    try:
        with engine.connect() as conn:
            df = pd.read_sql(sqlalchemy.text(query), conn, params=params)
            results = df.to_dict("records")

            # Convert pandas timestamps to string if needed
            for result in results:
                if "created_at" in result and pd.notna(result["created_at"]):
                    result["created_at"] = result["created_at"].isoformat()
                elif "created_at" not in result or pd.isna(result["created_at"]):
                    result["created_at"] = datetime.now().isoformat()

            engine.dispose()
            return results
    except Exception as e:
        engine.dispose()
        raise Exception(f"Database error getting checkpoints: {e}")


def get_checkpoint_by_id(
    thread_id: str, checkpoint_id: str, checkpoint_ns: str = ""
) -> Optional[Dict[str, Any]]:
    """
    Get a specific checkpoint by ID.

    Args:
        thread_id: The thread ID
        checkpoint_id: The checkpoint ID
        checkpoint_ns: Checkpoint namespace

    Returns:
        Checkpoint dictionary or None if not found
    """
    engine = get_db_connection()

    query = """
    SELECT 
        thread_id,
        checkpoint_ns,
        checkpoint_id,
        parent_checkpoint_id,
        type,
        checkpoint,
        metadata,
        created_at
    FROM checkpoints
    WHERE thread_id = :thread_id 
        AND checkpoint_id = :checkpoint_id
        AND checkpoint_ns = :checkpoint_ns
    """

    params = {
        "thread_id": thread_id,
        "checkpoint_id": checkpoint_id,
        "checkpoint_ns": checkpoint_ns,
    }

    try:
        with engine.connect() as conn:
            df = pd.read_sql(sqlalchemy.text(query), conn, params=params)
            if df.empty:
                return None

            result = df.to_dict("records")[0]

            # Convert timestamp to string if needed
            if "created_at" in result and pd.notna(result["created_at"]):
                result["created_at"] = result["created_at"].isoformat()
            elif "created_at" not in result or pd.isna(result["created_at"]):
                result["created_at"] = datetime.now().isoformat()

            engine.dispose()
            return result
    except Exception as e:
        engine.dispose()
        raise Exception(f"Database error getting checkpoint: {e}")


def get_thread_history_with_tasks(
    thread_id: str, limit: int = 10, checkpoint_ns: str = ""
) -> List[Dict[str, Any]]:
    """
    Get complete thread history with nested tasks structure.
    This function joins data from checkpoints, checkpoint_writes, and checkpoint_blobs tables.

    Args:
        thread_id: The thread ID to get history for
        limit: Maximum number of history items to return
        checkpoint_ns: Checkpoint namespace filter

    Returns:
        List of history items with nested structure matching the API spec
    """
    engine = get_db_connection()

    # Main query to get checkpoints with tasks
    query = """
    WITH checkpoint_data AS (
        SELECT 
            c.thread_id,
            c.checkpoint_ns,
            c.checkpoint_id,
            c.parent_checkpoint_id,
            c.type as checkpoint_type,
            c.checkpoint,
            c.metadata,
            c.created_at
        FROM checkpoints c
        WHERE c.thread_id = :thread_id 
            AND c.checkpoint_ns = :checkpoint_ns
        ORDER BY c.checkpoint_id DESC
        LIMIT :limit
    ),
    task_data AS (
        SELECT 
            cw.thread_id,
            cw.checkpoint_ns,
            cw.checkpoint_id,
            cw.task_id,
            cw.idx,
            cw.channel,
            cw.type as task_type,
            cw.blob,
            cw.task_path
        FROM checkpoint_writes cw
        WHERE cw.thread_id = :thread_id 
            AND cw.checkpoint_ns = :checkpoint_ns
        ORDER BY cw.checkpoint_id DESC, cw.idx
    )
    SELECT 
        cd.*,
        td.task_id,
        td.idx,
        td.channel,
        td.task_type,
        td.blob,
        td.task_path
    FROM checkpoint_data cd
    LEFT JOIN task_data td ON cd.checkpoint_id = td.checkpoint_id
    ORDER BY cd.checkpoint_id DESC, td.idx
    """

    params = {"thread_id": thread_id, "limit": limit, "checkpoint_ns": checkpoint_ns}

    try:
        with engine.connect() as conn:
            df = pd.read_sql(sqlalchemy.text(query), conn, params=params)

            # Group by checkpoint_id to build nested structure
            history_items = []
            current_checkpoint = None
            current_tasks = []

            for _, row in df.iterrows():
                checkpoint_id = row["checkpoint_id"]

                # If we're starting a new checkpoint
                if (
                    current_checkpoint is None
                    or current_checkpoint["checkpoint_id"] != checkpoint_id
                ):
                    # Save previous checkpoint if exists
                    if current_checkpoint is not None:
                        current_checkpoint["tasks"] = current_tasks
                        history_items.append(current_checkpoint)

                    # Start new checkpoint
                    current_checkpoint = {
                        "values": [{}],  # Default empty values
                        "next": [],  # Extract from checkpoint data if available
                        "tasks": [],
                        "checkpoint": {
                            "thread_id": row["thread_id"],
                            "checkpoint_ns": row["checkpoint_ns"],
                            "checkpoint_id": row["checkpoint_id"],
                            "checkpoint_map": {},
                        },
                        "metadata": (
                            row["metadata"] if pd.notna(row["metadata"]) else {}
                        ),
                        "created_at": (
                            row["created_at"].isoformat()
                            if pd.notna(row["created_at"])
                            else datetime.now().isoformat()
                        ),
                        "parent_checkpoint": (
                            {
                                "thread_id": row["thread_id"],
                                "checkpoint_ns": row["checkpoint_ns"],
                                "checkpoint_id": (
                                    row["parent_checkpoint_id"]
                                    if pd.notna(row["parent_checkpoint_id"])
                                    else ""
                                ),
                                "checkpoint_map": {},
                            }
                            if pd.notna(row["parent_checkpoint_id"])
                            else {}
                        ),
                    }
                    current_tasks = []

                    # Extract values and next from checkpoint data
                    if pd.notna(row["checkpoint"]) and isinstance(
                        row["checkpoint"], dict
                    ):
                        checkpoint_data = row["checkpoint"]
                        if "channel_values" in checkpoint_data:
                            current_checkpoint["values"] = [
                                checkpoint_data["channel_values"]
                            ]
                        elif "values" in checkpoint_data:
                            current_checkpoint["values"] = [checkpoint_data["values"]]

                        if "next" in checkpoint_data and isinstance(
                            checkpoint_data["next"], list
                        ):
                            current_checkpoint["next"] = checkpoint_data["next"]

                # Add task if exists
                if pd.notna(row["task_id"]):
                    task_blob = ""
                    if pd.notna(row["blob"]):
                        try:
                            task_blob = row["blob"].decode("utf-8")
                        except:
                            task_blob = row["blob"].hex()

                    task_item = {
                        "id": row["task_id"],
                        "name": row["channel"] if pd.notna(row["channel"]) else "",
                        "error": None,  # No error field in current schema
                        "interrupts": [],  # Empty interrupts array
                        "checkpoint": {
                            "thread_id": row["thread_id"],
                            "checkpoint_ns": row["checkpoint_ns"],
                            "checkpoint_id": row["checkpoint_id"],
                            "checkpoint_map": {},
                        },
                        "state": {
                            "values": [{}],
                            "next": [],
                            "tasks": [],  # Avoid circular reference
                            "checkpoint": {
                                "thread_id": row["thread_id"],
                                "checkpoint_ns": row["checkpoint_ns"],
                                "checkpoint_id": row["checkpoint_id"],
                                "checkpoint_map": {},
                            },
                            "metadata": {},
                            "created_at": (
                                row["created_at"].isoformat()
                                if pd.notna(row["created_at"])
                                else datetime.now().isoformat()
                            ),
                            "parent_checkpoint": {},
                        },
                    }
                    current_tasks.append(task_item)

            # Don't forget the last checkpoint
            if current_checkpoint is not None:
                current_checkpoint["tasks"] = current_tasks
                history_items.append(current_checkpoint)

            engine.dispose()
            return history_items

    except Exception as e:
        engine.dispose()
        raise Exception(f"Database error getting thread history: {e}")


def search_threads(
    metadata_filter: Optional[Dict[str, Any]] = None,
    values_filter: Optional[Dict[str, Any]] = None,
    status: Optional[str] = None,
    limit: int = 10,
    offset: int = 0,
    sort_by: str = "thread_id",
    sort_order: str = "asc",
    checkpoint_ns: Optional[str] = None,  # Changed default to None
) -> List[Dict[str, Any]]:
    """
    Search threads with advanced filtering, sorting and pagination.

    Args:
        metadata_filter: Filter by metadata fields
        values_filter: Filter by values fields
        status: Filter by status (not used in current schema)
        limit: Maximum number of threads to return
        offset: Number of threads to skip for pagination
        sort_by: Field to sort by (thread_id, created_at, etc.)
        sort_order: Sort order ('asc' or 'desc')
        checkpoint_ns: Checkpoint namespace filter (optional)

    Returns:
        List of thread dictionaries with full thread information
    """
    engine = get_db_connection()

    # Initialize params and dynamic WHERE conditions
    params = {"limit": limit, "offset": offset}
    where_conditions = []

    # Get latest checkpoint for each thread with full state
    base_query = """
    WITH filtered_checkpoints AS (
        SELECT 
            thread_id,
            checkpoint_ns,
            checkpoint_id,
            parent_checkpoint_id,
            type,
            checkpoint,
            metadata,
            created_at
        FROM checkpoints
    """

    # Conditionally add checkpoint_ns filter
    if checkpoint_ns:
        where_conditions.append("checkpoint_ns = :checkpoint_ns")
        params["checkpoint_ns"] = checkpoint_ns

    # Add metadata filter using the @> operator for JSONB containment
    if metadata_filter:
        metadata_filter_json = {
            k: str(v) for k, v in metadata_filter.items() if v is not None
        }
        if metadata_filter_json:
            where_conditions.append("metadata @> :metadata_filter")
            params["metadata_filter"] = json.dumps(metadata_filter_json)

    # Add values filter if provided
    if values_filter:
        for key, value in values_filter.items():
            if value is not None:
                where_conditions.append(
                    f" AND checkpoint->'channel_values'->'{key}' @> :values_{key}"
                )
                params[f"values_{key}"] = json.dumps(value)

    # Append WHERE clause if any conditions exist
    if where_conditions:
        base_query += " WHERE " + " AND ".join(where_conditions)

    # Complete the CTE and get latest for each thread
    query = (
        base_query
        + """
    ),
    latest_checkpoints AS (
        SELECT DISTINCT ON (thread_id)
            thread_id,
            checkpoint_ns,
            checkpoint_id,
            parent_checkpoint_id,
            type,
            checkpoint,
            metadata,
            created_at
        FROM filtered_checkpoints
        ORDER BY thread_id, checkpoint_id DESC
    )
    SELECT 
        lc.*
    FROM latest_checkpoints lc
    """
    )

    # Add sorting
    valid_sort_fields = ["thread_id", "created_at", "checkpoint_id"]
    if sort_by not in valid_sort_fields:
        sort_by = "thread_id"

    sort_direction = "ASC" if sort_order.lower() == "asc" else "DESC"
    query += f" ORDER BY {sort_by} {sort_direction}"

    # Add pagination
    query += " LIMIT :limit OFFSET :offset"

    print("Executing query:", query)
    print("With params:", params)

    try:
        with engine.connect() as conn:
            df = pd.read_sql(sqlalchemy.text(query), conn, params=params)
            results = []

            for _, row in df.iterrows():
                # Extract checkpoint data
                checkpoint_data = (
                    row["checkpoint"] if pd.notna(row["checkpoint"]) else {}
                )
                metadata = row["metadata"] if pd.notna(row["metadata"]) else {}

                # Build thread item matching the API spec, without hardcoded values
                thread_item = {
                    "thread_id": row["thread_id"],
                    "created_at": (
                        row["created_at"].isoformat()
                        if pd.notna(row["created_at"])
                        else None
                    ),
                    "updated_at": (
                        row["created_at"].isoformat()
                        if pd.notna(row["created_at"])
                        else None
                    ),
                    "metadata": metadata,
                    "status": None,  # Status is not stored in the DB
                    "config": None,  # Config is not stored in the DB
                    "values": {
                        "messages": [],
                        "user": None,
                        "thread_id": {"thread_id": row["thread_id"]},
                        "dialog_state": None,
                    },
                    "interrupts": {},
                    "error": None,
                }

                # Extract messages from checkpoint data if available
                if isinstance(checkpoint_data, dict):
                    if "channel_values" in checkpoint_data:
                        channel_values = checkpoint_data["channel_values"]
                        if (
                            isinstance(channel_values, dict)
                            and "messages" in channel_values
                        ):
                            thread_item["values"]["messages"] = channel_values[
                                "messages"
                            ]
                        if (
                            isinstance(channel_values, dict)
                            and "user" in channel_values
                        ):
                            thread_item["values"]["user"] = channel_values["user"]
                        if (
                            isinstance(channel_values, dict)
                            and "dialog_state" in channel_values
                        ):
                            thread_item["values"]["dialog_state"] = channel_values[
                                "dialog_state"
                            ]
                    elif "values" in checkpoint_data:
                        values = checkpoint_data["values"]
                        if isinstance(values, dict):
                            if "messages" in values:
                                thread_item["values"]["messages"] = values["messages"]
                            if "user" in values:
                                thread_item["values"]["user"] = values["user"]
                            if "dialog_state" in values:
                                thread_item["values"]["dialog_state"] = values[
                                    "dialog_state"
                                ]

                results.append(thread_item)

            engine.dispose()
            return results

    except Exception as e:
        engine.dispose()
        raise Exception(f"Database error searching threads: {e}")


def get_latest_checkpoint_for_thread(
    thread_id: str, checkpoint_ns: str = ""
) -> Optional[Dict[str, Any]]:
    """
    Get the latest checkpoint for a specific thread.

    Args:
        thread_id: The thread ID to get the latest checkpoint for
        checkpoint_ns: Checkpoint namespace filter (default: empty string)

    Returns:
        Latest checkpoint dictionary or None if not found
    """
    engine = get_db_connection()

    query = """
    SELECT 
        thread_id,
        checkpoint_ns,
        checkpoint_id,
        parent_checkpoint_id,
        type,
        checkpoint,
        metadata,
        created_at
    FROM checkpoints
    WHERE thread_id = :thread_id 
        AND checkpoint_ns = :checkpoint_ns
    ORDER BY checkpoint_id DESC
    LIMIT 1
    """

    params = {"thread_id": thread_id, "checkpoint_ns": checkpoint_ns}

    try:
        with engine.connect() as conn:
            df = pd.read_sql(sqlalchemy.text(query), conn, params=params)

            if df.empty:
                return None

            result = df.to_dict("records")[0]

            # Convert timestamp to string if needed
            if "created_at" in result and pd.notna(result["created_at"]):
                result["created_at"] = result["created_at"].isoformat()
            elif "created_at" not in result or pd.isna(result["created_at"]):
                result["created_at"] = datetime.now().isoformat()

            engine.dispose()
            return result

    except Exception as e:
        engine.dispose()
        raise Exception(f"Database error getting latest checkpoint: {e}")
