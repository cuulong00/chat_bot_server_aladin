"""
Callback-based Message Processing System
Xử lý images trước, sau đó callback để xử lý text với context đã có
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class PendingTextMessage:
    """Text message đang chờ image context"""
    user_id: str
    thread_id: str
    text: str
    message_data: dict
    timestamp: float
    retry_count: int = 0
    max_retries: int = 3

@dataclass
class ProcessingResult:
    """Kết quả xử lý message"""
    success: bool
    message_type: str  # 'image' | 'text' 
    context_created: bool = False
    response_sent: bool = False
    error: Optional[str] = None

class CallbackMessageProcessor:
    """
    Processor sử dụng callback thay vì timeout:
    1. Image messages được xử lý ngay lập tức (priority cao)
    2. Text messages được hold lại nếu có khả năng liên quan đến image
    3. Sau khi image processed → callback để xử lý pending text messages
    """
    
    def __init__(self, facebook_service, redis_queue=None):
        self.facebook_service = facebook_service
        self.redis_queue = redis_queue
        
        # Pending text messages chờ image context
        self.pending_texts: Dict[str, List[PendingTextMessage]] = {}
        
        # Image processing callbacks
        self.image_callbacks: Dict[str, List[Callable]] = {}
        
        # Metrics
        self.stats = {
            'images_processed': 0,
            'texts_processed': 0,
            'callbacks_executed': 0,
            'pending_texts_resolved': 0
        }
        
    async def process_batch(self, user_id: str, thread_id: str, 
                           text: str = "", attachments: List[dict] = None, 
                           message_data: dict = None) -> ProcessingResult:
        """
        IMMEDIATE Entry point cho batch processing với callback system:
        1. Phân loại message thành image + text
        2. Xử lý image trước (nếu có) - NGAY LẬP TỨC
        3. Callback xử lý text sau (nếu có) - NGAY LẬP TỨC
        
        *** NO DELAYS - IMMEDIATE PROCESSING ***
        """
        attachments = attachments or []
        message_data = message_data or {}
        
        # Phân loại message trong batch
        image_attachments = [att for att in attachments if att.get('type') == 'image']
        has_images = len(image_attachments) > 0
        has_text = bool(text and text.strip())
        
        logger.info(f"📋 IMMEDIATE BATCH PROCESSING: {user_id} - Images: {len(image_attachments)}, Text: {'Yes' if has_text else 'No'}")
        
        try:
            if has_images and has_text:
                # BATCH có cả image và text → Image trước NGAY, Text callback NGAY sau
                logger.info(f"🔄 Mixed batch: IMMEDIATE processing - images first, then text callback")
                return await self._process_mixed_batch_immediate(user_id, thread_id, text, image_attachments, message_data)
            
            elif has_images and not has_text:
                # BATCH chỉ có image → Xử lý image NGAY
                logger.info(f"🖼️ Image-only batch: IMMEDIATE processing for context")
                return await self._process_image_only_batch(user_id, thread_id, image_attachments, message_data)
            
            elif has_text and not has_images:
                # BATCH chỉ có text → Xử lý text NGAY
                logger.info(f"📝 Text-only batch: IMMEDIATE processing")
                return await self._process_text_only_batch(user_id, thread_id, text, message_data)
            
            else:
                # BATCH rỗng
                return ProcessingResult(
                    success=False,
                    message_type='empty',
                    error="Empty batch - no content to process"
                )
                
        except Exception as e:
            logger.error(f"❌ Immediate batch processing error: {e}")
            return ProcessingResult(
                success=False,
                message_type='batch',
                error=str(e)
            )
    
    async def _process_mixed_batch_immediate(self, user_id: str, thread_id: str, 
                                            text: str, image_attachments: List[dict], 
                                            message_data: dict) -> ProcessingResult:
        """
        IMMEDIATE xử lý batch có cả image và text:
        1. Xử lý image trước để tạo context - NGAY LẬP TỨC
        2. Callback xử lý text với context đã có - NGAY LẬP TỨC TRONG CÙNG THREAD
        
        *** NO ASYNC DELAYS - SEQUENTIAL IMMEDIATE PROCESSING ***
        """
        try:
            # STEP 1: Xử lý image trước (KHÔNG gửi response) - NGAY LẬP TỨC
            logger.info(f"🖼️ STEP 1 IMMEDIATE: Processing {len(image_attachments)} images for context")
            
            context_data = {
                'user_id': user_id,
                'thread_id': thread_id,
                'text': '',  # Chỉ image
                'attachments': image_attachments,
                'message_data': message_data,
                'processing_priority': 'high',
                'immediate_processing': True  # Flag để báo xử lý ngay
            }
            
            # Xử lý image NGAY - không async delay
            await self.facebook_service._process_aggregated_context_from_queue(user_id, context_data)
            self.stats['images_processed'] += 1
            
            logger.info(f"📝 STEP 2 IMMEDIATE: Processing text with fresh image context")
            
            # STEP 2: Callback xử lý text với context đã có - NGAY LẬP TỨC
            text_context_data = {
                'user_id': user_id,
                'thread_id': thread_id,
                'text': text,
                'attachments': [],  # Chỉ text
                'message_data': message_data,
                'processing_priority': 'normal',
                'immediate_processing': True,  # Flag để báo xử lý ngay
                'has_fresh_image_context': True  # Context vừa mới tạo
            }
            
            # Xử lý text NGAY với context mới - không async delay
            await self.facebook_service._process_aggregated_context_from_queue(user_id, text_context_data)
            self.stats['texts_processed'] += 1
            self.stats['callbacks_executed'] += 1
            
            return ProcessingResult(
                success=True,
                message_type='mixed_immediate',
                context_created=True,
                response_sent=True  # Text response được gửi ngay
            )
            
        except Exception as e:
            logger.error(f"❌ Immediate mixed batch processing error: {e}")
            return ProcessingResult(
                success=False,
                message_type='mixed_immediate',
                error=str(e)
            )

    async def _process_mixed_batch(self, user_id: str, thread_id: str, 
                                  text: str, image_attachments: List[dict], 
                                  message_data: dict) -> ProcessingResult:
        """
        Xử lý batch có cả image và text:
        1. Xử lý image trước để tạo context
        2. Callback xử lý text với context đã có
        """
        try:
            # STEP 1: Xử lý image trước (KHÔNG gửi response)
            logger.info(f"🖼️ STEP 1: Processing {len(image_attachments)} images for context")
            
            context_data = {
                'user_id': user_id,
                'thread_id': thread_id,
                'text': '',  # Chỉ image
                'attachments': image_attachments,
                'message_data': message_data,
                'processing_priority': 'high'
            }
            
            await self.facebook_service._process_aggregated_context_from_queue(user_id, context_data)
            self.stats['images_processed'] += 1
            
            # STEP 2: Callback xử lý text với context đã có
            logger.info(f"📝 STEP 2: Callback processing text with image context")
            
            text_context_data = {
                'user_id': user_id,
                'thread_id': thread_id,
                'text': text,
                'attachments': [],  # Chỉ text
                'message_data': message_data,
                'processing_priority': 'normal'
            }
            
            await self.facebook_service._process_aggregated_context_from_queue(user_id, text_context_data)
            self.stats['texts_processed'] += 1
            self.stats['callbacks_executed'] += 1
            
            return ProcessingResult(
                success=True,
                message_type='mixed',
                context_created=True,
                response_sent=True  # Text response được gửi
            )
            
        except Exception as e:
            logger.error(f"❌ Mixed batch processing error: {e}")
            return ProcessingResult(
                success=False,
                message_type='mixed',
                error=str(e)
            )
    
    async def _process_image_only_batch(self, user_id: str, thread_id: str, 
                                       image_attachments: List[dict], 
                                       message_data: dict) -> ProcessingResult:
        """Xử lý batch chỉ có image - tạo context, KHÔNG gửi response"""
        try:
            context_data = {
                'user_id': user_id,
                'thread_id': thread_id,
                'text': '',
                'attachments': image_attachments,
                'message_data': message_data,
                'processing_priority': 'high'
            }
            
            await self.facebook_service._process_aggregated_context_from_queue(user_id, context_data)
            self.stats['images_processed'] += 1
            
            return ProcessingResult(
                success=True,
                message_type='image',
                context_created=True,
                response_sent=False  # Image không gửi response
            )
            
        except Exception as e:
            logger.error(f"❌ Image-only batch processing error: {e}")
            return ProcessingResult(
                success=False,
                message_type='image',
                error=str(e)
            )
    
    async def _process_text_only_batch(self, user_id: str, thread_id: str, 
                                      text: str, message_data: dict) -> ProcessingResult:
        """Xử lý batch chỉ có text"""
        try:
            context_data = {
                'user_id': user_id,
                'thread_id': thread_id,
                'text': text,
                'attachments': [],
                'message_data': message_data,
                'processing_priority': 'normal'
            }
            
            await self.facebook_service._process_aggregated_context_from_queue(user_id, context_data)
            self.stats['texts_processed'] += 1
            
            return ProcessingResult(
                success=True,
                message_type='text',
                response_sent=True
            )
            
        except Exception as e:
            logger.error(f"❌ Text-only batch processing error: {e}")
            return ProcessingResult(
                success=False,
                message_type='text',
                error=str(e)
            )
    
    def get_stats(self) -> dict:
        """Lấy statistics"""
        return {
            **self.stats,
            'active_processing': len(self.pending_texts) if hasattr(self, 'pending_texts') else 0
        }
