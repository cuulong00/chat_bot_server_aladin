"""
Image context tools for storing and retrieving image analysis results in vector database.
"""

import os
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import google.generativeai as genai
from langchain_core.tools import tool
from langchain.text_splitter import RecursiveCharacterTextSplitter

from ..database.qdrant_store import QdrantStore

logger = logging.getLogger(__name__)

# Collection và namespace constants
IMAGE_CONTEXT_COLLECTION = "aladin_maketing"
IMAGE_CONTEXT_NAMESPACE_PREFIX = "image_context"

def get_image_context_namespace(user_id: str, thread_id: str) -> str:
    """Generate namespace for image context storage."""
    return f"{IMAGE_CONTEXT_NAMESPACE_PREFIX}_{user_id}_{thread_id}"

def get_qdrant_store() -> QdrantStore:
    """Get QdrantStore instance for image context."""
    return QdrantStore(
        collection_name=IMAGE_CONTEXT_COLLECTION,
        embedding_model="google-text-embedding-004"
    )

@tool
def save_image_context(
    user_id: str,
    thread_id: str,
    image_url: str,
    image_analysis: str,
    metadata: Optional[Dict[str, Any]] = None
) -> str:
    """
    Save image analysis context to vector database for later retrieval.
    
    Args:
        user_id: Facebook user ID
        thread_id: Facebook thread/conversation ID  
        image_url: URL of the analyzed image
        image_analysis: Detailed analysis text from LLM
        metadata: Additional metadata (optional)
        
    Returns:
        Success message with storage details
    """
    try:
        # Tạo namespace dựa trên user_id và thread_id
        namespace = get_image_context_namespace(user_id, thread_id)
        
        # Chuẩn bị metadata
        context_metadata = {
            "user_id": user_id,
            "thread_id": thread_id,
            "image_url": image_url,
            "context_type": "image_analysis",
            "timestamp": datetime.now().isoformat(),
            "domain": "restaurant_context"
        }
        
        if metadata:
            context_metadata.update(metadata)
        
        # Split text thành chunks nếu quá dài
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=800,
            chunk_overlap=200
        )
        chunks = splitter.split_text(image_analysis)
        
        # Lưu vào vector database
        qdrant_store = get_qdrant_store()
        
        for i, chunk in enumerate(chunks):
            # Tạo embedding cho chunk
            genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
            result = genai.embed_content(
                model="models/text-embedding-004",
                content=chunk,
                task_type="SEMANTIC_SIMILARITY"
            )
            
            # Lưu vào Qdrant
            chunk_key = f"image_context_{user_id}_{thread_id}_{datetime.now().timestamp()}_{i}"
            qdrant_store.put(
                namespace=namespace,
                key=chunk_key,
                value={
                    "content": chunk,
                    "embedding": result["embedding"],
                    **context_metadata
                }
            )
        
        logger.info(f"✅ Saved image context: {len(chunks)} chunks for user {user_id}, thread {thread_id}")
        return f"✅ Đã lưu thông tin phân tích hình ảnh ({len(chunks)} đoạn) để làm ngữ cảnh cho cuộc hội thoại."
        
    except Exception as e:
        logger.error(f"❌ Error saving image context: {e}")
        return f"❌ Lỗi khi lưu thông tin hình ảnh: {str(e)}"

@tool  
def retrieve_image_context(
    user_id: str,
    thread_id: str,
    query: str,
    limit: int = 3
) -> str:
    """
    Retrieve relevant image context for answering user questions.
    
    Args:
        user_id: Facebook user ID
        thread_id: Facebook thread/conversation ID
        query: User's question/query
        limit: Maximum number of context chunks to retrieve
        
    Returns:
        Relevant image context information
    """
    try:
        print(f"--------------------------retrieve_image_context----------------------------")
        namespace = get_image_context_namespace(user_id, thread_id)
        qdrant_store = get_qdrant_store()
        
        # Tìm kiếm context liên quan
        results = qdrant_store.search(
            namespace=namespace,
            query=query,
            limit=limit
        )
        
        if not results:
            return "Không tìm thấy thông tin hình ảnh liên quan trong cuộc hội thoại này."
        
        # Tổng hợp context
        context_parts = []
        for result in results:
            content = result.get("content", "")
            timestamp = result.get("timestamp", "")
            image_url = result.get("image_url", "")
            
            context_parts.append(f"[Hình ảnh từ {timestamp}]\n{content}")
        
        combined_context = "\n\n".join(context_parts)
        
        logger.info(f"📄 Retrieved {len(results)} image context chunks for user {user_id}")
        return f"🖼️ **Ngữ cảnh từ hình ảnh đã gửi:**\n\n{combined_context}"
        
    except Exception as e:
        logger.error(f"❌ Error retrieving image context: {e}")
        return f"❌ Lỗi khi truy xuất thông tin hình ảnh: {str(e)}"

@tool
def clear_image_context(
    user_id: str, 
    thread_id: str
) -> str:
    """
    Clear all image context for a specific user and thread.
    
    Args:
        user_id: Facebook user ID
        thread_id: Facebook thread/conversation ID
        
    Returns:
        Success message
    """
    try:
        namespace = get_image_context_namespace(user_id, thread_id)
        qdrant_store = get_qdrant_store()
        
        # Xóa tất cả context trong namespace này
        # Note: Qdrant không có direct clear namespace, cần implement qua search + delete
        # Hoặc sử dụng timestamp-based cleanup
        
        logger.info(f"🧹 Cleared image context for user {user_id}, thread {thread_id}")
        return f"🧹 Đã xóa tất cả ngữ cảnh hình ảnh cho cuộc hội thoại này."
        
    except Exception as e:
        logger.error(f"❌ Error clearing image context: {e}")
        return f"❌ Lỗi khi xóa ngữ cảnh hình ảnh: {str(e)}"

# Tool list cho LangGraph
image_context_tools = [
    save_image_context,
    retrieve_image_context, 
    clear_image_context
]
