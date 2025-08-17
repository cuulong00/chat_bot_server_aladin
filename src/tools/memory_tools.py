from langchain_core.tools import tool
from typing import Dict, List
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct
import google.generativeai as genai
from google.generativeai import types
import uuid
import os
import logging
from dotenv import load_dotenv

load_dotenv()

# Khởi tạo clients
QDRANT_HOST = os.getenv("QDRANT_HOST", "69.197.187.234")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
USER_MEMORY_COLLECTION = os.getenv("USER_MEMORY_COLLECTION", "aladin_maketing")
USER_MEMORY_NAMESPACE = os.getenv("USER_MEMORY_NAMESPACE", "user_ref")

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
        Now uses intelligent extraction to create clean, structured preferences.

        Args:
            user_id: Unique identifier for the user.
            preference_type: The type of preference (e.g., 'dietary_preference', 'travel_style', 'budget_range', 'favorite_destination').
            content: The raw content of the preference (will be processed).
            context: Optional additional context for the preference.

        Returns:
            Confirmation message indicating the preference has been saved.
        """
        
        # 🧠 INTELLIGENT PREFERENCE EXTRACTION
        try:
            from src.tools.user_profile_extractor import get_profile_extractor
            
            extractor = get_profile_extractor()
            logging.info(f"🔍 Raw content to extract: {content[:200]}...")
            
            # Extract structured preferences
            extracted = extractor.extract_preferences(
                raw_conversation=content,
                preference_type=preference_type,
                context_info=context
            )
            
            # Create clean summary for storage
            clean_summary = extractor.create_clean_summary(extracted)
            logging.info(f"✅ Cleaned summary: {clean_summary}")
            
            # Use clean summary instead of raw content
            processed_content = clean_summary
            
        except Exception as e:
            logging.error(f"❌ Preference extraction failed, using raw content: {e}")
            processed_content = content
        
        # Create embedding from processed content
        text_to_embed = f"User {user_id} {preference_type}: {processed_content}"
        if context:
            text_to_embed += f" Context: {context}"

        embedding = self._get_embedding(text_to_embed)
        preference_id = str(uuid.uuid4())

        # Store in collection with enhanced payload
        point = PointStruct(
            id=preference_id,
            vector=embedding,
            payload={
                "namespace": USER_MEMORY_NAMESPACE,
                "user_id": user_id,
                "preference_type": preference_type,
                "content": processed_content,  # Store processed, not raw
                "raw_content": content,       # Keep raw for debugging
                "context": context,
                "text_content": text_to_embed,
                "timestamp": str(uuid.uuid1().time),
                "extraction_method": "intelligent" if processed_content != content else "raw",
            },
        )

        self.qdrant_client.upsert(collection_name=self.collection_name, points=[point])

        return f"Saved {preference_type} for user {user_id}: {processed_content}"

    def get_user_profile(
        self, user_id: str, query_context: str = "", k: int = 5
    ) -> str:
        """
        Retrieve a user's personalized profile information from the vector database.
        Now returns clean, structured summaries from intelligent extraction.

        Args:
            user_id: Unique identifier for the user.
            query_context: Optional context to filter or focus the search (e.g., 'travel', 'diet').
            k: The maximum number of preferences to retrieve.

        Returns:
            A clean, structured summary of the user's personalized information.
            If no information is found, returns a message indicating so.
        """
        search_query = f"User {user_id}"
        if query_context:
            search_query += f" {query_context}"

        query_embedding = self._get_embedding(search_query)

        # Filter by namespace and user_id to read back only personalized memory
        search_results = self.qdrant_client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            limit=k,
            with_payload=True,
            query_filter={
                "must": [
                    {"key": "namespace", "match": {"value": USER_MEMORY_NAMESPACE}},
                    {"key": "user_id", "match": {"value": user_id}},
                ]
            },
        )

        if not search_results:
            return "No personalized information found for this user."

        # 🧠 INTELLIGENT PROFILE AGGREGATION
        try:
            from src.tools.user_profile_extractor import get_profile_extractor
            
            extractor = get_profile_extractor()
            
            # Collect all cleaned preferences
            cleaned_preferences = []
            for result in search_results:
                payload = result.payload
                content = payload.get('content', '')
                
                # Prefer cleaned content over raw
                if payload.get('extraction_method') == 'intelligent':
                    cleaned_preferences.append(content)
                else:
                    # Try to extract from raw content if available
                    raw_content = payload.get('raw_content', content)
                    try:
                        extracted = extractor.extract_preferences(raw_content, payload.get('preference_type', 'general'))
                        clean_summary = extractor.create_clean_summary(extracted)
                        cleaned_preferences.append(clean_summary)
                    except:
                        # Fallback to original content
                        cleaned_preferences.append(content)
            
            # Merge all preferences into a unified profile
            if len(cleaned_preferences) == 1:
                return f"User's personalized information:\n{cleaned_preferences[0]}"
            elif len(cleaned_preferences) > 1:
                # Combine multiple preferences intelligently
                combined_summary = self._merge_preference_summaries(cleaned_preferences)
                return f"User's personalized information:\n{combined_summary}"
                
        except Exception as e:
            logging.error(f"❌ Profile aggregation failed, using legacy format: {e}")
            
        # Fallback to legacy format
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
    
    def _merge_preference_summaries(self, summaries: List[str]) -> str:
        """Merge multiple preference summaries into a unified profile."""
        
        # Parse all summaries
        merged_parts = {}
        
        for summary in summaries:
            if "|" in summary:
                # Structured format: "Category: value | Category2: value2"
                parts = summary.split(" | ")
                for part in parts:
                    if ":" in part:
                        key, value = part.split(":", 1)
                        key = key.strip()
                        value = value.strip()
                        
                        if key in merged_parts:
                            # Merge values, avoid duplication
                            existing_values = set(merged_parts[key].split(", "))
                            new_values = set(value.split(", "))
                            combined_values = existing_values.union(new_values)
                            merged_parts[key] = ", ".join(sorted(combined_values))
                        else:
                            merged_parts[key] = value
            else:
                # Unstructured format, add as general info
                if "Thông tin chung" not in merged_parts:
                    merged_parts["Thông tin chung"] = summary
                else:
                    merged_parts["Thông tin chung"] += f"; {summary}"
        
        # Rebuild unified summary
        parts = [f"{key}: {value}" for key, value in merged_parts.items() if value.strip()]
        return " | ".join(parts) if parts else "Chưa có thông tin chi tiết"


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