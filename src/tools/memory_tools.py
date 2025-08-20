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
from src.models.user_profile_models import (
    RequiredUserInfo, 
    UserProfileCompleteness, 
    UserInfoExtractor, 
    profile_manager
)

load_dotenv()

# Khởi tạo clients
QDRANT_HOST = os.getenv("QDRANT_HOST", "69.197.187.234")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
USER_MEMORY_COLLECTION = os.getenv("USER_MEMORY_COLLECTION", "tianlong_marketing")
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

    def _check_existing_preference(self, user_id: str, preference_type: str, content: str) -> str:
        """
        Check if a similar preference already exists for the user.
        
        Args:
            user_id: User identifier
            preference_type: Type of preference (e.g., 'phone_number', 'dietary_preference')
            content: Content to check for duplicates
            
        Returns:
            existing_point_id if duplicate found, None otherwise
        """
        try:
            # For phone numbers, do exact match to avoid duplicates
            if preference_type == "phone_number":
                # Clean phone number for comparison
                clean_new_phone = ''.join(filter(str.isdigit, content))
                
                # Use scroll API to get all phone preferences for user
                scroll_result = self.qdrant_client.scroll(
                    collection_name=self.collection_name,
                    scroll_filter={
                        "must": [
                            {"key": "namespace", "match": {"value": USER_MEMORY_NAMESPACE}},
                            {"key": "user_id", "match": {"value": user_id}},
                            {"key": "preference_type", "match": {"value": "phone_number"}},
                        ]
                    },
                    limit=100,
                    with_payload=True,
                )
                
                # Check each result for exact phone match
                for point in scroll_result[0]:  # scroll_result is (points, next_page_offset)
                    existing_content = point.payload.get('content', '')
                    clean_existing_phone = ''.join(filter(str.isdigit, existing_content))
                    
                    if clean_existing_phone == clean_new_phone:
                        logging.info(f"🔍 Found existing phone number for user {user_id}: {existing_content}")
                        return str(point.id)
                        
            # For other preference types, use semantic similarity
            else:
                text_to_embed = f"User {user_id} {preference_type}: {content}"
                query_embedding = self._get_embedding(text_to_embed)
                
                search_results = self.qdrant_client.search(
                    collection_name=self.collection_name,
                    query_vector=query_embedding,
                    limit=5,
                    with_payload=True,
                    query_filter={
                        "must": [
                            {"key": "namespace", "match": {"value": USER_MEMORY_NAMESPACE}},
                            {"key": "user_id", "match": {"value": user_id}},
                            {"key": "preference_type", "match": {"value": preference_type}},
                        ]
                    },
                )
                
                # Check for high similarity (>0.95) to detect near-duplicates
                for result in search_results:
                    if result.score > 0.95:
                        logging.info(f"🔍 Found similar preference for user {user_id}: {result.payload.get('content')}")
                        return str(result.id)
                        
            return None
            
        except Exception as e:
            logging.error(f"Error checking existing preference: {e}")
            return None

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
        Now uses intelligent extraction and duplicate checking to avoid redundant storage.
        Integrates with profile completeness tracking for required user information.

        Args:
            user_id: Unique identifier for the user.
            preference_type: The type of preference (e.g., 'phone_number', 'dietary_preference', 'travel_style').
            content: The raw content of the preference (will be processed).
            context: Optional additional context for the preference.

        Returns:
            Confirmation message indicating the preference has been saved or updated.
        """
        
        # 🎯 CHECK IF THIS IS REQUIRED INFO AND WHETHER WE SHOULD SAVE IT
        try:
            # Map preference_type to RequiredUserInfo enum
            required_info_map = {
                "phone_number": RequiredUserInfo.PHONE_NUMBER,
                "gender": RequiredUserInfo.GENDER,
                "age": RequiredUserInfo.AGE,
                "birth_year": RequiredUserInfo.BIRTH_YEAR,
            }
            
            required_info = required_info_map.get(preference_type)
            
            if required_info:
                # Check if we should save this info (based on completeness flags)
                if not profile_manager.should_save_info(user_id, required_info):
                    return f"Skipped {preference_type} for user {user_id}: already exists"
                
                # Validate content before saving
                if not UserInfoExtractor.validate_info_content(required_info, content):
                    return f"Invalid {preference_type} format for user {user_id}: {content}"
                    
        except Exception as e:
            logging.error(f"❌ Error in required info checking: {e}")
        
        # 🔍 CHECK FOR EXISTING DUPLICATES
        existing_id = self._check_existing_preference(user_id, preference_type, content)
        
        if existing_id:
            # Update existing preference instead of creating duplicate
            logging.info(f"🔄 Updating existing {preference_type} for user {user_id}")
            action = "updated"
        else:
            # Create new preference
            logging.info(f"➕ Creating new {preference_type} for user {user_id}")
            action = "saved"
        
        # 🧠 INTELLIGENT PREFERENCE EXTRACTION
        # Skip extraction for phone numbers and basic info - store them directly
        if preference_type in ["phone_number", "gender", "age", "birth_year"]:
            processed_content = content
            logging.info(f"📞 Basic info stored directly: {preference_type} = {processed_content}")
        else:
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
        
        # Use existing ID if updating, generate new if creating
        preference_id = existing_id if existing_id else str(uuid.uuid4())

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
                "action": action,  # Track if this was an update or new save
                "required_info": required_info.value if required_info else None,  # Track if this is required info
            },
        )

        self.qdrant_client.upsert(collection_name=self.collection_name, points=[point])
        
        # 🎯 UPDATE PROFILE COMPLETENESS IF THIS WAS REQUIRED INFO
        if required_info and action == "saved":
            profile_manager.mark_info_saved(user_id, required_info)
            logging.info(f"✅ Marked {required_info.value} as completed for user {user_id}")

        return f"{action.title()} {preference_type} for user {user_id}: {processed_content}"
    
    def get_user_profile(
        self, user_id: str, query_context: str = "", k: int = 5
    ) -> str:
        """
        Retrieve a user's personalized profile information from the vector database.
        Now includes intelligent profile completeness checking and missing info flags.

        Args:
            user_id: Unique identifier for the user.
            query_context: Optional context to filter or focus the search (e.g., 'travel', 'diet').
            k: The maximum number of preferences to retrieve.

        Returns:
            A clean, structured summary of the user's personalized information with completeness status.
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

        # 🎯 ANALYZE PROFILE COMPLETENESS
        profile_data = "No personalized information found for this user."
        
        if search_results:
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
                    profile_data = f"User's personalized information:\n{cleaned_preferences[0]}"
                elif len(cleaned_preferences) > 1:
                    # Combine multiple preferences intelligently
                    combined_summary = self._merge_preference_summaries(cleaned_preferences)
                    profile_data = f"User's personalized information:\n{combined_summary}"
                    
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

                profile_data = "User's personalized information:\n" + "\n".join(profile_parts)

        # 🏁 UPDATE PROFILE COMPLETENESS TRACKING
        profile_completeness = profile_manager.update_profile_completeness(user_id, profile_data)
        
        # 📊 ADD COMPLETENESS INFO TO RESPONSE
        completeness_info = f"\n\n📊 Profile Status: {profile_completeness.completion_percentage:.1f}% complete"
        
        if not profile_completeness.is_complete:
            missing_info = profile_completeness.get_missing_info_message()
            completeness_info += f"\n🎯 {missing_info}"
            
            # Log missing info for agent awareness
            logging.info(f"🎯 User {user_id} missing info: {[info.value for info in profile_completeness.missing_info]}")
        else:
            completeness_info += "\n✅ All required information collected!"

        return profile_data + completeness_info
    
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
    Now includes intelligent handling of required user information (gender, phone, age, birth_year).

    Use this tool to store any information about a user's preferences, habits, or interests
    that can help personalize their experience in future interactions.

    Args:
        user_id: Unique identifier for the user.
        preference_type: The type of preference. Required types: 'gender', 'phone_number', 'age', 'birth_year'. 
                        Optional types: 'dietary_preference', 'travel_style', 'budget_range', 'favorite_destination', etc.
        content: The detailed content of the preference.
        context: Optional additional context for the preference.

    Returns:
        A confirmation message indicating the information has been saved, updated, or skipped.

    When to use:
        - When the user provides new information about their preferences, habits, or interests.
        - When you detect required information (gender, phone, age, birth_year) in conversation.
        - When you want to remember user-specific details for future recommendations or personalization.
        
    Note: The system will automatically check if required info already exists to avoid duplicates.
    """
    try:
        print(f"-------------------------------tool call save_user_preference---------------------------")
        return user_memory_store.save_user_preference(
            user_id, preference_type, content, context
        )
    except Exception as e:
        return f"Error saving user information: {e}"


@tool  
def smart_save_user_info(user_id: str, content: str, context: str = "") -> str:
    """
    Intelligently analyze conversation content and automatically save detected user information.
    
    This tool will:
    1. Analyze the content to detect what type of information is provided
    2. Check if this info is missing from the user's profile
    3. Validate the information format  
    4. Save only if needed (avoid duplicates)
    
    Args:
        user_id: Unique identifier for the user
        content: The conversation content to analyze for user information
        context: Optional context about the conversation
        
    Returns:
        A message about what information was detected and saved
        
    When to use:
        - When user provides information in natural conversation
        - When you're not sure what type of info the user provided
        - To automatically capture and organize user information
    """
    try:
        from src.models.user_profile_models import UserInfoExtractor
        
        # Extract the type of information from content
        info_type = UserInfoExtractor.extract_info_type(content)
        
        if not info_type:
            return f"No recognizable user information found in: {content[:50]}..."
            
        # Convert enum to string for the existing save function
        preference_type = info_type.value
        
        # Use the existing save_user_preference function
        result = user_memory_store.save_user_preference(
            user_id, preference_type, content, context
        )
        
        return f"🎯 Detected {info_type.value}: {result}"
        
    except Exception as e:
        logging.error(f"❌ Error in smart_save_user_info: {e}")
        return f"Error analyzing user information: {e}"


@tool
def get_user_profile(user_id: str, query_context: str = "") -> str:
    """
    Retrieve a user's personalized profile information for better service.
    Now includes profile completeness tracking and missing information flags.

    Use this tool to fetch the user's stored preferences, habits, or interests,
    which can be used to tailor responses, recommendations, or services.

    Args:
        user_id: Unique identifier for the user.
        query_context: Optional context to focus the search (e.g., 'travel', 'diet').

    Returns:
        A summary string of the user's personalized information plus completion status.
        Includes flags for missing required information (gender, phone, age, birth_year).

    When to use:
        - At the beginning of conversations to check what info is missing
        - When you need to personalize responses or recommendations for a user.
        - When you want to understand the user's preferences or context before answering.
        
    Note: The response will include completion percentage and list missing required info.
    """
    try:
        return user_memory_store.get_user_profile(user_id, query_context)
    except Exception as e:
        return f"Error retrieving user information: {e}"


@tool
def get_missing_user_info(user_id: str) -> str:
    """
    Get specifically what required information is missing for a user.
    
    Args:
        user_id: Unique identifier for the user
        
    Returns:
        A detailed message about missing required information
        
    When to use:
        - To check what information you should ask the user for
        - To determine if profile is complete before proceeding
        - To generate targeted questions for information collection
    """
    try:
        from src.models.user_profile_models import profile_manager
        
        # First, get current profile to update completeness
        user_memory_store.get_user_profile(user_id)
        
        # Then check what's missing
        completeness = profile_manager.get_profile_completeness(user_id)
        
        if completeness.is_complete:
            return f"✅ User {user_id} profile is complete ({completeness.completion_percentage:.1f}%)"
        
        missing_info = completeness.get_missing_info_message()
        return f"📋 User {user_id} profile status: {completeness.completion_percentage:.1f}% complete\n{missing_info}"
        
    except Exception as e:
        return f"Error checking missing info: {e}"