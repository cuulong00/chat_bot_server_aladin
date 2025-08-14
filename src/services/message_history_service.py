"""
Message History Service
Manages message history for Facebook Messenger conversations to support reply context.
"""
import json
import time
from typing import Dict, List, Optional, Any
from collections import defaultdict, deque
import logging

logger = logging.getLogger(__name__)


class MessageHistoryService:
    """
    In-memory message history service for Facebook Messenger.
    In production, this should be backed by Redis or a database.
    """
    
    def __init__(self, max_messages_per_user: int = 100, message_ttl: int = 3600 * 24):
        """
        Initialize message history service.
        
        Args:
            max_messages_per_user: Maximum messages to keep per user
            message_ttl: Time to live for messages in seconds (default: 24 hours)
        """
        self.max_messages_per_user = max_messages_per_user
        self.message_ttl = message_ttl
        
        # user_id -> deque of messages
        self._user_messages: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_messages_per_user))
        
        # message_id -> message content (for quick lookup)
        self._message_lookup: Dict[str, Dict[str, Any]] = {}
    
    def store_message(self, user_id: str, message_id: str, content: str, 
                     is_from_user: bool = True, attachments: Optional[List[Dict[str, Any]]] = None) -> None:
        """
        Store a message in history.
        
        Args:
            user_id: Facebook user ID
            message_id: Facebook message ID
            content: Message content
            is_from_user: True if message is from user, False if from bot
            attachments: List of attachment information
        """
        timestamp = time.time()
        
        message_data = {
            "message_id": message_id,
            "user_id": user_id,
            "content": content,
            "timestamp": timestamp,
            "is_from_user": is_from_user,
            "attachments": attachments or []
        }
        
        # Store in user's message history
        self._user_messages[user_id].append(message_data)
        
        # Store in lookup table
        self._message_lookup[message_id] = message_data
        
        logger.debug(f"Stored message {message_id} for user {user_id}")
    
    def get_message_by_id(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific message by its ID."""
        message = self._message_lookup.get(message_id)
        
        # Check if message is still valid (not expired)
        if message and (time.time() - message["timestamp"]) > self.message_ttl:
            self._cleanup_expired_message(message_id)
            return None
            
        return message
    
    def get_user_history(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent message history for a user.
        
        Args:
            user_id: Facebook user ID
            limit: Maximum number of messages to return
            
        Returns:
            List of recent messages, newest first
        """
        messages = list(self._user_messages[user_id])
        
        # Filter out expired messages
        now = time.time()
        valid_messages = [
            msg for msg in messages 
            if (now - msg["timestamp"]) <= self.message_ttl
        ]
        
        # Return newest first, limited
        return valid_messages[-limit:][::-1]
    
    def get_conversation_context(self, user_id: str, replied_message_id: str, 
                               context_length: int = 3) -> str:
        """
        Get conversation context for a reply message.
        
        Args:
            user_id: Facebook user ID
            replied_message_id: ID of the message being replied to
            context_length: Number of messages to include in context
            
        Returns:
            Formatted context string
        """
        # Get the specific message being replied to
        replied_message = self.get_message_by_id(replied_message_id)
        if not replied_message:
            return "[Tin nhắn được trả lời không còn khả dụng]"
        
        # Get recent conversation history
        history = self.get_user_history(user_id, context_length)
        
        # Build context
        context_parts = ["=== Bối cảnh cuộc trò chuyện ==="]
        
        # Add recent messages for context
        for msg in history:
            sender = "Người dùng" if msg["is_from_user"] else "Bot"
            timestamp_str = time.strftime("%H:%M", time.localtime(msg["timestamp"]))
            content = msg["content"][:100] + "..." if len(msg["content"]) > 100 else msg["content"]
            
            context_parts.append(f"[{timestamp_str}] {sender}: {content}")
        
        # Highlight the message being replied to
        replied_content = replied_message["content"][:100] + "..." if len(replied_message["content"]) > 100 else replied_message["content"]
        replied_sender = "Người dùng" if replied_message["is_from_user"] else "Bot"
        context_parts.append(f"\n>>> TIN NHẮN ĐƯỢC TRẢ LỜI: {replied_sender}: {replied_content}")
        context_parts.append("=== Kết thúc bối cảnh ===\n")
        
        return "\n".join(context_parts)
    
    def cleanup_expired_messages(self) -> None:
        """Clean up expired messages from memory."""
        now = time.time()
        expired_message_ids = []
        
        # Find expired messages
        for message_id, message_data in self._message_lookup.items():
            if (now - message_data["timestamp"]) > self.message_ttl:
                expired_message_ids.append(message_id)
        
        # Remove expired messages
        for message_id in expired_message_ids:
            self._cleanup_expired_message(message_id)
        
        logger.debug(f"Cleaned up {len(expired_message_ids)} expired messages")
    
    def _cleanup_expired_message(self, message_id: str) -> None:
        """Remove a specific expired message."""
        if message_id in self._message_lookup:
            del self._message_lookup[message_id]


# Global instance
_message_history_service = None


def get_message_history_service() -> MessageHistoryService:
    """Get the global message history service instance."""
    global _message_history_service
    if _message_history_service is None:
        _message_history_service = MessageHistoryService()
    return _message_history_service
