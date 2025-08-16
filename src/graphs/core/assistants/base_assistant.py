from __future__ import annotations

import logging
from typing import Any
from datetime import datetime

from langchain_core.messages import AIMessage
from langchain_core.runnables import Runnable, RunnableConfig

from src.core.logging_config import log_exception_details
from src.graphs.state.state import RagState


class BaseAssistant:
    def __init__(self, runnable: Runnable):
        self.runnable = runnable

    def binding_prompt(self, state: RagState) -> dict[str, Any]:
        """Binds state to the prompt, adding necessary context."""
        logging.debug(f"🔍 BaseAssistant.binding_prompt - START with state keys: {list(state.keys())}")
        print(f"------------state{state}")
        
        running_summary = ""
        if state.get("context") and isinstance(state["context"], dict):
            summary_obj = state["context"].get("running_summary")
            if summary_obj and hasattr(summary_obj, "summary"):
                running_summary = summary_obj.summary
                logging.debug(f"Running summary found for prompt: {running_summary[:100]}...")

        # FIXED: Tương thích với code cũ - state.user chứa user_info và user_profile
        user_data = state.get("user")
        print(f"------------user_data:{user_data}")
        logging.debug(f"🔍 BaseAssistant.binding_prompt - user_data type: {type(user_data)}, value: {user_data}")
        
        if user_data and hasattr(user_data, 'user_info') and hasattr(user_data, 'user_profile'):
            # Code cũ - user là User object với user_info và user_profile attributes
            user_info = user_data.user_info if hasattr(user_data.user_info, '__dict__') else user_data.user_info.__dict__ if user_data.user_info else {"user_id": "unknown"}
            user_profile = user_data.user_profile if hasattr(user_data.user_profile, '__dict__') else user_data.user_profile.__dict__ if user_data.user_profile else {}
            logging.debug(f"BaseAssistant: Using User object format - user_info: {user_info}, user_profile: {user_profile}")
        elif user_data and isinstance(user_data, dict) and "user_info" in user_data:
            # Code mới - user là dict với user_info và user_profile keys (MOST COMMON CASE)
            user_info = user_data.get("user_info", {"user_id": "unknown"})
            user_profile = user_data.get("user_profile", {})
            logging.debug(f"BaseAssistant: Using dict format - user_info: {user_info}, user_profile: {user_profile}")
        elif user_data and isinstance(user_data, dict):
            # Fallback cho dict format khác (có thể có trực tiếp user_id)
            user_id = user_data.get("user_id", "unknown")
            user_name = user_data.get("name", "anh/chị")
            user_info = {"user_id": user_id, "name": user_name}
            user_profile = {}
            logging.debug(f"BaseAssistant: Using fallback dict format - user_info: {user_info}")
        else:
            # Fallback cuối cùng - tạo defaults từ user_id trong state hoặc config
            logging.warning(f"No proper user data found in state, user_data: {user_data}, creating defaults from user_id")
            user_id = state.get("user_id", "unknown")
            user_info = {"user_id": user_id, "name": "anh/chị"}
            user_profile = {}
            logging.debug(f"BaseAssistant: Using ultimate fallback - user_info: {user_info}")

        image_contexts = state.get("image_contexts", [])
        if image_contexts:
            logging.info(f"🖼️ Binding prompt with {len(image_contexts)} image contexts.")
        
        # CRITICAL: Log state data extraction for DocGrader
        if "document" in state:
            logging.debug(f"🔍 BaseAssistant.binding_prompt - found document in state: {state['document'][:100] if state['document'] else 'EMPTY'}...")
        
        prompt = {
            **state,
            "user_info": user_info,
            "user_profile": user_profile,
            "conversation_summary": running_summary,
            "image_contexts": image_contexts,
            # Add default values for common template variables
            "current_date": datetime.now().strftime("%d/%m/%Y"),
            "domain_context": "Nhà hàng lẩu bò tươi Tian Long",
        }
        
        if not prompt.get("messages"):
            logging.error("No messages found in prompt data during binding.")
            prompt["messages"] = [] # Ensure messages is always a list

        logging.debug(f"🔍 BaseAssistant.binding_prompt - FINAL prompt keys: {list(prompt.keys())}")
        return prompt

    def __call__(self, state: RagState, config: RunnableConfig) -> dict[str, Any]:
        """Executes the assistant's runnable."""
        logging.debug(f"🔍 BaseAssistant.__call__ - START")
        try:
            # FIXED: Tương thích với cả User object và dict format
            user_data = state.get("user")
            if user_data and hasattr(user_data, 'user_info'):
                # User object format (code cũ)
                user_info = user_data.user_info if hasattr(user_data.user_info, '__dict__') else user_data.user_info.__dict__ if user_data.user_info else {}
                user_id = user_info.get("user_id", "unknown") if isinstance(user_info, dict) else getattr(user_info, "user_id", "unknown")
            elif user_data and isinstance(user_data, dict):
                # Dict format (code mới)
                user_info = user_data.get("user_info", {})
                user_id = user_info.get("user_id", "unknown") if user_info else "unknown"
            else:
                # Fallback
                user_id = state.get("user_id", "unknown")
                
            logging.debug(f"🔍 BaseAssistant.__call__ - user_id: {user_id}")

            if "configurable" not in config:
                config["configurable"] = {}
            config["configurable"]["user_id"] = user_id

            logging.debug(f"🔍 BaseAssistant.__call__ - calling binding_prompt")
            prompt = self.binding_prompt(state)
            
            # CRITICAL: Log the exact prompt data being sent to LLM for DocGrader analysis
            if "DocGrader" in str(type(self)):
                logging.info(f"🔬 DOCGRADER PROMPT DATA TO LLM:")
                logging.info(f"   📄 document: {prompt.get('document', 'MISSING')[:200] if prompt.get('document') else 'MISSING'}...")
                logging.info(f"   ❓ messages: {prompt.get('messages', 'MISSING')}")
                logging.info(f"   📝 conversation_summary: {prompt.get('conversation_summary', 'MISSING')[:100] if prompt.get('conversation_summary') else 'MISSING'}...")
                logging.info(f"   🏢 domain_context: {prompt.get('domain_context', 'MISSING')}")
                logging.info(f"   📅 current_date: {prompt.get('current_date', 'MISSING')}")
                logging.info(f"   👤 user_info: {prompt.get('user_info', 'MISSING')}")
                logging.info(f"   📋 user_profile: {prompt.get('user_profile', 'MISSING')}")
                
            logging.debug(f"🔍 BaseAssistant.__call__ - prompt keys: {list(prompt.keys()) if prompt else 'None'}")
            
            if not prompt or not prompt.get("messages"):
                logging.error("❌ BaseAssistant: Aborting LLM call due to empty or invalid prompt data.")
                raise ValueError("Prompt data is empty or missing required 'messages' field.")

            logging.debug(f"🔍 BaseAssistant.__call__ - invoking runnable")
            result = self.runnable.invoke(prompt, config)
            logging.debug(f"🔍 BaseAssistant.__call__ - runnable returned type: {type(result)}")
            logging.debug(f"🔍 BaseAssistant.__call__ - runnable returned content: {result}")

            logging.debug(f"🔍 BaseAssistant.__call__ - checking if response is valid")
            if self._is_valid_response(result):
                logging.debug("✅ BaseAssistant: Assistant returned a valid response.")
                return result
            else:
                logging.warning("⚠️ BaseAssistant: Assistant returned an invalid or empty response. Providing fallback.")
                fallback = self._create_fallback_response(state)
                logging.debug(f"🔍 BaseAssistant.__call__ - fallback response: {fallback}")
                return fallback

        except Exception as e:
            # FIXED: Tương thích với cả User object và dict format 
            user_data = state.get("user")
            if user_data and hasattr(user_data, 'user_info'):
                user_info = user_data.user_info if hasattr(user_data.user_info, '__dict__') else user_data.user_info.__dict__ if user_data.user_info else {}
                user_id = user_info.get("user_id", "unknown") if isinstance(user_info, dict) else getattr(user_info, "user_id", "unknown")
            elif user_data and isinstance(user_data, dict):
                user_info = user_data.get("user_info", {})
                user_id = user_info.get("user_id", "unknown") if user_info else "unknown"
            else:
                user_id = state.get("user_id", "unknown")
                
            logging.error(f"❌ BaseAssistant.__call__ - Exception: {type(e).__name__}: {str(e)}")
            log_exception_details(
                exception=e,
                context="Assistant LLM call failed",
                user_id=user_id
            )
            logging.error(f"❌ BaseAssistant: Assistant exception, providing fallback: {e}")
            fallback = self._create_fallback_response(state)
            logging.debug(f"🔍 BaseAssistant.__call__ - exception fallback: {fallback}")
            return fallback

    def _is_valid_response(self, result: Any) -> bool:
        """Checks if the LLM response is meaningful."""
        logging.debug(f"🔍 BaseAssistant._is_valid_response - checking result type: {type(result)}")
        
        if hasattr(result, "tool_calls") and result.tool_calls:
            logging.debug(f"✅ BaseAssistant._is_valid_response - has tool_calls: {len(result.tool_calls)}")
            return True
        
        content = getattr(result, "content", None)
        logging.debug(f"🔍 BaseAssistant._is_valid_response - content: {content}")
        
        if not content:
            logging.debug(f"❌ BaseAssistant._is_valid_response - no content")
            return False
        
        if isinstance(content, str):
            is_valid = content.strip() != ""
            logging.debug(f"🔍 BaseAssistant._is_valid_response - string content valid: {is_valid}")
            return is_valid
        
        if isinstance(content, list):
            is_valid = any(
                isinstance(item, dict) and item.get("text", "").strip()
                for item in content
            )
            logging.debug(f"🔍 BaseAssistant._is_valid_response - list content valid: {is_valid}")
            return is_valid
        
        is_valid = bool(content)
        logging.debug(f"🔍 BaseAssistant._is_valid_response - general content valid: {is_valid}")
        return is_valid

    def _create_fallback_response(self, state: RagState) -> AIMessage:
        """Creates a graceful fallback AIMessage."""
        # FIXED: Tương thích với cả User object và dict format
        user_data = state.get("user")
        if user_data and hasattr(user_data, 'user_info'):
            # User object format (code cũ)
            user_info = user_data.user_info if hasattr(user_data.user_info, '__dict__') else user_data.user_info.__dict__ if user_data.user_info else {}
            user_name = user_info.get("name", "anh/chị") if isinstance(user_info, dict) else getattr(user_info, "name", "anh/chị")
            user_id_for_log = user_info.get("user_id", "unknown") if isinstance(user_info, dict) else getattr(user_info, "user_id", "unknown")
        elif user_data and isinstance(user_data, dict):
            # Dict format (code mới)
            user_info = user_data.get("user_info", {})
            user_name = user_info.get("name", "anh/chị")
            user_id_for_log = user_info.get("user_id", "unknown")
        else:
            # Fallback
            user_name = "anh/chị"
            user_id_for_log = "unknown"
        
        fallback_content = (
            f"Xin lỗi {user_name}, em đang gặp vấn đề kỹ thuật tạm thời. "
            f"Vui lòng thử lại sau hoặc liên hệ hotline 1900 636 886 để được hỗ trợ trực tiếp. "
            f"Em rất xin lỗi vì sự bất tiện này! 🙏"
        )
        
        logging.info(f"Providing fallback response for user: {user_id_for_log}")
        
        return AIMessage(
            content=fallback_content,
            additional_kwargs={"fallback_response": True}
        )
