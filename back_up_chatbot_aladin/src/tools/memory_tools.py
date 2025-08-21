from langchain_core.tools import tool
from typing import Dict, List
import uuid
import os
from dotenv import load_dotenv

# Import QdrantStore instead of defining our own
from src.database.qdrant_store import qdrant_store

load_dotenv()

# Configuration constants
USER_MEMORY_NAMESPACE = os.getenv("USER_MEMORY_NAMESPACE", "user_memory")


class UserMemoryStore:
    """
    Store and manage personalized user memory using QdrantStore.

    This class provides methods to save and retrieve user preferences and profile information
    as vector embeddings, enabling personalized recommendations and context-aware responses.
    """

    def __init__(self, qdrant_store):
        """
        Initialize the UserMemoryStore.

        Args:
            qdrant_store: An instance of QdrantStore for database operations.
        """
        self.qdrant_store = qdrant_store

    def save_user_preference(
        self, user_id: str, preference_type: str, content: str, context: str = ""
    ):
        """
        Save a user's personalized preference or habit to the vector database.

        This function creates an embedding for the user's preference and stores it in Qdrant,
        allowing future retrieval for personalization.

        Args:
            user_id: Unique identifier for the user.
            preference_type: The type of preference (e.g., 'dietary_preference', 'travel_style', 'budget_range', 'favorite_destination').
            content: The detailed content of the preference.
            context: Optional additional context for the preference.

        Returns:
            Confirmation message indicating the preference has been saved.
        """
        text_to_embed = f"User {user_id} {preference_type}: {content}"
        if context:
            text_to_embed += f" Context: {context}"

        # Create unique key for this user preference
        preference_key = f"user_{user_id}_pref_{str(uuid.uuid4())[:8]}"
        
        # Prepare data to store
        preference_data = {
            "user_id": user_id,
            "preference_type": preference_type,
            "content": content,
            "context": context,
            "text_content": text_to_embed,
            "timestamp": str(uuid.uuid1().time),  # Simple timestamp
        }

        # Store using QdrantStore
        self.qdrant_store.put(
            namespace=USER_MEMORY_NAMESPACE,
            key=preference_key,
            value=preference_data
        )

        return f"Saved {preference_type} for user {user_id}"

    def get_user_profile(
        self, user_id: str, query_context: str = "", k: int = 5
    ) -> str:
        """
        Retrieve a user's personalized profile information from the vector database.

        This function searches for the most relevant preferences or habits for the user,
        optionally filtered by a query context, and summarizes them for downstream use.

        Args:
            user_id: Unique identifier for the user.
            query_context: Optional context to filter or focus the search (e.g., 'travel', 'diet').
            k: The maximum number of preferences to retrieve.

        Returns:
            A summary string of the user's personalized information.
            If no information is found, returns a message indicating so.
        """
        search_query = f"User {user_id}"
        if query_context:
            search_query += f" {query_context}"

        # Search using QdrantStore
        search_results = self.qdrant_store.search(
            namespace=USER_MEMORY_NAMESPACE,
            query=search_query,
            limit=k
        )

        if not search_results:
            return "No personalized information found for this user."

        # Filter results to only include this user's data
        user_results = []
        for key, value, score in search_results:
            if isinstance(value, dict) and value.get("user_id") == user_id:
                user_results.append((key, value, score))

        if not user_results:
            return "No personalized information found for this user."

        profile_parts = []
        for key, value, score in user_results:
            profile_parts.append(
                f"- {value['preference_type']}: {value['content']}"
                + (
                    f" (Context: {value['context']})"
                    if value.get("context")
                    else ""
                )
            )

        return "User's personalized information:\n" + "\n".join(profile_parts)


# Initialize the user memory store using the global qdrant_store instance
user_memory_store = UserMemoryStore(qdrant_store)


@tool
def save_user_preference(
    user_id: str, preference_type: str, content: str, context: str = ""
) -> str:
    """
    Save a user's preference or habit for future personalization.

    Use this tool to store any information about a user's preferences, habits, or interests
    that can help personalize their experience in future interactions.

    Args:
        user_id: Unique identifier for the user.
        preference_type: The type of preference (e.g., 'dietary_preference', 'travel_style', 'budget_range', 'favorite_destination').
        content: The detailed content of the preference.
        context: Optional additional context for the preference.

    Returns:
        A confirmation message indicating the information has been saved.

    When to use:
        - When the user provides new information about their preferences, habits, or interests.
        - When you want to remember user-specific details for future recommendations or personalization.
    """
    try:
        return user_memory_store.save_user_preference(
            user_id, preference_type, content, context
        )
    except Exception as e:
        return f"Error saving user information: {e}"


@tool
def get_user_profile(user_id: str, query_context: str = "") -> str:
    """
    Retrieve a user's personalized profile information for better service.

    Use this tool to fetch the user's stored preferences, habits, or interests,
    which can be used to tailor responses, recommendations, or services.

    Args:
        user_id: Unique identifier for the user.
        query_context: Optional context to focus the search (e.g., 'travel', 'diet').

    Returns:
        A summary string of the user's personalized information.

    When to use:
        - When you need to personalize responses or recommendations for a user.
        - When you want to understand the user's preferences or context before answering.
    """
    try:
        return user_memory_store.get_user_profile(user_id, query_context)
    except Exception as e:
        return f"Error retrieving user information: {e}"