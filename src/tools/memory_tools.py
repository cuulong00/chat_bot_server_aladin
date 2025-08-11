from langchain_core.tools import tool
from typing import Dict, List
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct
import google.generativeai as genai
from google.generativeai import types
import uuid
import os
from dotenv import load_dotenv

load_dotenv()

# Khởi tạo clients
QDRANT_HOST = os.getenv("QDRANT_HOST", "69.197.187.234")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
USER_MEMORY_COLLECTION = "user_memory"

qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
# Configure the Google GenAI library directly
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
embedding_model = os.getenv("EMBEDDING_MODEL", "gemini-embedding-exp-03-07")

# Gemini embedding size là 768
EXPECTED_VECTOR_SIZE = 768


class UserMemoryStore:
    """
    Store and manage personalized user memory in Qdrant vector database.

    This class provides methods to save and retrieve user preferences and profile information
    as vector embeddings, enabling personalized recommendations and context-aware responses.
    """

    def __init__(self, qdrant_client: QdrantClient, collection_name: str):
        """
        Initialize the UserMemoryStore.

        Args:
            qdrant_client: An instance of QdrantClient for database operations.
            collection_name: The name of the Qdrant collection to use for storing user memory.
        """
        self.qdrant_client = qdrant_client
        self.collection_name = collection_name
        self.vector_size = EXPECTED_VECTOR_SIZE
        self._ensure_correct_collection()

    def _get_embedding(self, text: str) -> List[float]:
        """
        Generate an embedding vector for the given text using the Gemini embedding model.

        Args:
            text: The input text to embed.

        Returns:
            A list of floats representing the embedding vector.
            If embedding fails, returns a zero vector of the expected size.
        """
        try:
            result = genai.embed_content(
                model=embedding_model,
                content=text,
                task_type="SEMANTIC_SIMILARITY",
            )
            embedding = result["embedding"]
            if len(embedding) != self.vector_size:
                print(
                    f"⚠️ Warning: Expected vector size {self.vector_size}, got {len(embedding)}"
                )
            return embedding
        except Exception as e:
            print(f"Error generating embedding: {e}")
            return [0.0] * self.vector_size

    def _ensure_correct_collection(self):
        """
        Ensure that the Qdrant collection exists and has the correct vector size.

        If the collection does not exist, it will be created.
        If the collection exists but has the wrong vector size, it will be recreated.
        """
        try:
            print(f"self.collection_name:{self.collection_name}")
            collection_info = self.qdrant_client.get_collection(self.collection_name)
            current_size = collection_info.config.params.vectors.size

            if current_size != self.vector_size:
                print(
                    f"❌ Collection has incorrect vector size: {current_size}, expected: {self.vector_size}"
                )
                print("🔧 Recreating collection with correct size...")
                self._recreate_collection()
            else:
                print(f"✅ Collection has correct vector size: {current_size}")

        except Exception as e:
            if "not found" in str(e).lower():
                print(f"Collection not found, creating new with size {self.vector_size}")
                self._create_collection()
            else:
                print(f"Error checking collection: {e}")

    def _create_collection(self):
        """
        Create a new Qdrant collection with the expected vector size.
        """
        self.qdrant_client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(
                size=self.vector_size, distance=Distance.COSINE
            ),
        )
        print(
            f"✅ Created collection '{self.collection_name}' with vector size: {self.vector_size}"
        )

    def _recreate_collection(self):
        """
        Delete and recreate the Qdrant collection to ensure correct vector size.
        """
        try:
            self.qdrant_client.delete_collection(self.collection_name)
            print(f"🗑️ Deleted old collection '{self.collection_name}'")
        except Exception as e:
            print(f"Could not delete old collection: {e}")

        self._create_collection()

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

        embedding = self._get_embedding(text_to_embed)
        preference_id = str(uuid.uuid4())

        point = PointStruct(
            id=preference_id,
            vector=embedding,
            payload={
                "user_id": user_id,
                "preference_type": preference_type,
                "content": content,
                "context": context,
                "text_content": text_to_embed,
                "timestamp": str(uuid.uuid1().time),  # Simple timestamp
            },
        )

        self.qdrant_client.upsert(collection_name=self.collection_name, points=[point])

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

        query_embedding = self._get_embedding(search_query)

        search_results = self.qdrant_client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            limit=k,
            with_payload=True,
            query_filter={"must": [{"key": "user_id", "match": {"value": user_id}}]},
        )

        if not search_results:
            return "No personalized information found for this user."

        profile_parts = []
        for result in search_results:
            payload = result.payload
            profile_parts.append(
                f"- {payload['preference_type']}: {payload['content']}"
                + (
                    f" (Context: {payload['context']})"
                    if payload.get("context")
                    else ""
                )
            )

        return "User's personalized information:\n" + "\n".join(profile_parts)


# Initialize the user memory store
user_memory_store = UserMemoryStore(qdrant_client, USER_MEMORY_COLLECTION)


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