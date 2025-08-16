"""Memory nodes for user profile management."""

from src.graphs.state.state import State
from langchain_core.runnables import RunnableConfig


def retrieve_user_profile(state: State, config: RunnableConfig) -> dict:
    """
    Node to retrieve personalized user information from the vector database
    and update it into the state for assistants to use.
    """
    try:
        from src.tools.memory_tools import get_user_profile
    except ImportError:
        return {"user_profile": "Memory tools not available"}

    # Get user_id from config or from the first message
    user_id = config.get("configurable", {}).get("user_id", "default_user")

    # If user_id is not in config, try to get it from other context
    if user_id == "default_user" and state.get("messages"):
        # You can implement logic here to extract user_id from messages if needed
        pass

    # Create query context based on recent messages
    query_context = ""
    if state.get("messages"):
        recent_messages = state["messages"][-3:]  # Get the 3 most recent messages
        query_context = " ".join(
            [
                msg.content
                for msg in recent_messages
                if hasattr(msg, "content") and isinstance(msg.content, str)
            ]
        )

    # Retrieve user profile
    try:
        user_profile = get_user_profile.invoke(
            {"user_id": user_id, "query_context": query_context}
        )
    except Exception as e:
        user_profile = f"Unable to retrieve user information: {e}"

    return {"user_profile": user_profile}


def should_retrieve_user_profile(state: State) -> bool:
    """
    Condition to decide whether to retrieve the user profile or not.
    Returns True if retrieval is needed, False otherwise.
    """
    # Always retrieve if user_profile does not exist or is empty
    current_profile = state.get("user_profile", "")
    if not current_profile or current_profile.strip() == "":
        return True

    # You can add more complex logic here to decide when to refresh the profile
    # For example: after a certain number of messages, or when a new intent is detected

    return False
