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
            
        running_summary = ""
        context_obj = state.get("context")
        logging.info(f"🔍 CONTEXT DEBUG: context type={type(context_obj)}, value={context_obj}")
        
        if context_obj and isinstance(context_obj, dict):
            # Try different possible keys for RunningSummary object
            summary_obj = None
            for possible_key in ["running_summary", "summary", context_obj.get("thread_id", "default")]:
                if possible_key in context_obj:
                    summary_obj = context_obj[possible_key]
                    logging.info(f"🔍 FOUND SUMMARY OBJ with key '{possible_key}': type={type(summary_obj)}")
                    break
            
            if summary_obj and hasattr(summary_obj, "summary"):
                running_summary = str(summary_obj.summary)
                logging.info(f"✅ FOUND RUNNING SUMMARY: {running_summary[:100]}...")
            elif summary_obj and isinstance(summary_obj, str):
                running_summary = summary_obj
                logging.info(f"✅ FOUND STRING SUMMARY: {running_summary[:100]}...")
            else:
                logging.warning(f"⚠️ No valid summary found in context object: {context_obj}")
        else:
            logging.warning(f"⚠️ No context dict found in state")

        # DIRECT ACCESS: user_data luôn có format dict với user_info và user_profile
        user_data = state.get("user", {})
        user_info = user_data.get("user_info", {"user_id": "unknown", "name": "anh/chị"})
        user_profile = user_data.get("user_profile", {})
        
        # CHECK USER_PROFILE_NEEDS_REFRESH FLAG
        user_profile_needs_refresh = state.get("user_profile_needs_refresh", False)
        if user_profile_needs_refresh:
            logging.info(f"🔄 BaseAssistant: user_profile_needs_refresh=True, calling get_user_profile for user_id: {user_info.get('user_id', 'unknown')}")
            try:
                from src.tools.memory_tools import get_user_profile
                updated_profile_str = get_user_profile(user_info.get('user_id', 'unknown'))
                if updated_profile_str and "No personalized information found" not in updated_profile_str:
                    user_profile = {"summary": updated_profile_str}
                    logging.info(f"✅ BaseAssistant: Successfully refreshed user_profile: {user_profile}")
                else:
                    logging.info(f"ℹ️ BaseAssistant: No updated profile found, keeping existing")
            except Exception as e:
                logging.error(f"❌ BaseAssistant: Failed to refresh user_profile: {e}")
     

        logging.info(f"✅ BaseAssistant: Direct access - user_info: {user_info}, user_profile: {user_profile}")

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
            "user_profile_needs_refresh": False,  # Reset flag after using
            # Add default values for common template variables
           
        }
        
        if not prompt.get("messages"):
            logging.error("No messages found in prompt data during binding.")
            prompt["messages"] = [] # Ensure messages is always a list
        
        return prompt

    def __call__(self, state: RagState, config: RunnableConfig) -> dict[str, Any]:
        """Executes the assistant's runnable."""
        logging.debug(f"🔍 BaseAssistant.__call__ - START")
        try:
            # DIRECT ACCESS: user_data luôn có format dict với user_info
            user_data = state.get("user", {})
            user_info = user_data.get("user_info", {"user_id": "unknown"})
            user_id = user_info.get("user_id", "unknown")
                
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

           
            result = self.runnable.invoke(prompt, config)
           
            if self._is_valid_response(result):
                logging.debug("✅ BaseAssistant: Assistant returned a valid response.")
                return result
            else:
                logging.warning("⚠️ BaseAssistant: Assistant returned an invalid or empty response. Providing fallback.")
                fallback = self._create_fallback_response(state)
                logging.debug(f"🔍 BaseAssistant.__call__ - fallback response: {fallback}")
                return fallback

        except Exception as e:
            # DIRECT ACCESS: user_data luôn có format dict với user_info
            user_data = state.get("user", {})
            user_info = user_data.get("user_info", {"user_id": "unknown"})
            user_id = user_info.get("user_id", "unknown")
                
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
        # DIRECT ACCESS: user_data luôn có format dict với user_info
        user_data = state.get("user", {})
        user_info = user_data.get("user_info", {"user_id": "unknown", "name": "anh/chị"})
        user_name = user_info.get("name", "anh/chị")
        user_id_for_log = user_info.get("user_id", "unknown")
        
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
