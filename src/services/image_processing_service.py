"""
Image Processing Service for Facebook Messenger
Handles image analysis using various AI services.
"""
import logging
import httpx
import base64
import os
import asyncio
from typing import Optional, Dict, Any, List
from io import BytesIO
from PIL import Image
import google.generativeai as genai

logger = logging.getLogger(__name__)


class ImageProcessingService:
    """Service to analyze images from URLs using AI models."""
    
    def __init__(self):
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        if self.google_api_key:
            genai.configure(api_key=self.google_api_key)
            self.model = genai.GenerativeModel('gemini-1.5-flash')
        else:
            self.model = None
            logger.warning("No GOOGLE_API_KEY found, image analysis will be limited")
    
    async def analyze_image_from_url(self, image_url: str, context: str = "") -> str:
        """
        Analyze an image from URL and return description.
        
        Args:
            image_url: URL of the image to analyze
            context: Additional context about the image
            
        Returns:
            Description of the image content
        """
        try:
            # Download image
            image_data = await self._download_image(image_url)
            if not image_data:
                return "Không thể tải xuống hình ảnh để phân tích."
            
            # Analyze with Google Gemini if available
            if self.model:
                return await self._analyze_with_gemini(image_data, context)
            else:
                return await self._basic_image_info(image_data)
                
        except Exception as e:
            logger.error(f"Error analyzing image: {e}")
            return f"Đã xảy ra lỗi khi phân tích hình ảnh: {str(e)}"
    
    async def _download_image(self, url: str) -> Optional[bytes]:
        """Download image from URL."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    return response.content
                else:
                    logger.warning(f"Failed to download image: HTTP {response.status_code}")
                    return None
        except Exception as e:
            logger.error(f"Error downloading image: {e}")
            return None
    
    async def _analyze_with_gemini(self, image_data: bytes, context: str) -> str:
        """Analyze image using Google Gemini Vision."""
        try:
            # Move blocking operations to a separate thread
            def _sync_gemini_analysis():
                # Convert to PIL Image
                image = Image.open(BytesIO(image_data))
                
                # Prepare prompt for restaurant context
                prompt = f"""
                Bạn là trợ lý AI của nhà hàng Aladdin. Hãy phân tích hình ảnh này và mô tả nội dung một cách chi tiết.
                
                Nếu đây là:
                - Hình ảnh món ăn: Mô tả món ăn, nguyên liệu, cách trình bày
                - Menu/thực đơn: Liệt kê các món ăn và giá cả nếu có thể đọc được
                - Hình ảnh nhà hàng: Mô tả không gian, bàn ghế, trang trí
                - Hóa đơn/bill: Đọc thông tin chi tiết về các món đã đặt
                - Khác: Mô tả nội dung hình ảnh một cách chính xác
                
                Bối cảnh thêm: {context}
                
                Hãy trả lời bằng tiếng Việt một cách thân thiện và chi tiết.
                """
                
                # Generate response (this might make blocking calls internally)
                response = self.model.generate_content([prompt, image])
                return response.text if response.text else None
            
            # Run the blocking operation in a thread pool
            result = await asyncio.to_thread(_sync_gemini_analysis)
            
            if result:
                return f"📸 **Phân tích hình ảnh:**\n{result}"
            else:
                return "Không thể phân tích nội dung hình ảnh."
                
        except Exception as e:
            logger.error(f"Error in Gemini analysis: {e}")
            return f"Lỗi khi phân tích hình ảnh bằng AI: {str(e)}"
    
    async def _basic_image_info(self, image_data: bytes) -> str:
        """Basic image info when AI analysis is not available."""
        try:
            # Move PIL operations to a separate thread to avoid blocking calls
            def _get_image_info():
                image = Image.open(BytesIO(image_data))
                width, height = image.size
                format_name = image.format or "Unknown"
                return width, height, format_name
            
            width, height, format_name = await asyncio.to_thread(_get_image_info)
            size_kb = len(image_data) // 1024
            
            return f"""📸 **Thông tin hình ảnh:**
- Định dạng: {format_name}
- Kích thước: {width}x{height} pixels
- Dung lượng: {size_kb} KB

Em đã nhận được hình ảnh của anh/chị. Tuy nhiên, để phân tích nội dung chi tiết, em cần được cấu hình thêm dịch vụ AI. 
Anh/chị có thể mô tả nội dung hình ảnh để em hỗ trợ tốt hơn không ạ?"""
            
        except Exception as e:
            logger.error(f"Error getting basic image info: {e}")
            return "Đã nhận được hình ảnh nhưng không thể đọc thông tin chi tiết."


# Global instance
_image_service = None


def get_image_processing_service() -> ImageProcessingService:
    """Get the global image processing service instance."""
    global _image_service
    if _image_service is None:
        _image_service = ImageProcessingService()
    return _image_service
