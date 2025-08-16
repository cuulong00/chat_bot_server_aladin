"""
Image Analysis Tool for AI Agent
Allows the agent to analyze images from URLs.
"""
import logging
from typing import Dict, Any
from langchain_core.tools import tool
from src.services.image_processing_service import get_image_processing_service

logger = logging.getLogger(__name__)


@tool
async def analyze_image(image_url: str, context: str = "") -> str:
    """
    Phân tích nội dung hình ảnh từ URL.
    
    Args:
        image_url: URL của hình ảnh cần phân tích  
        context: Bối cảnh hoặc mục đích phân tích hình ảnh
        
    Returns:
        Mô tả chi tiết nội dung hình ảnh
    """
    try:
        image_service = get_image_processing_service()
        result = await image_service.analyze_image_from_url(image_url, context)
        logger.info(f"Image analysis completed for URL: {image_url[:100]}...")
        return result
    except Exception as e:
        logger.error(f"Error in image analysis tool: {e}")
        return f"Không thể phân tích hình ảnh: {str(e)}"
