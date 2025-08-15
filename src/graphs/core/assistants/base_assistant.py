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
        running_summary = ""
        if state.get("context") and isinstance(state["context"], dict):
            summary_obj = state["context"].get("running_summary")
            if summary_obj and hasattr(summary_obj, "summary"):
                running_summary = summary_obj.summary
                logging.debug(f"Running summary found for prompt: {running_summary[:100]}...")

        user_data = state.get("user", {})
        if not user_data:
            logging.warning("No user data found in state, using defaults.")
            user_data = {"user_info": {"user_id": "unknown"}, "user_profile": {}}

        user_info = user_data.get("user_info", {"user_id": "unknown"})
        user_profile = user_data.get("user_profile", {})
        image_contexts = state.get("image_contexts", [])

        if image_contexts:
            logging.info(f"🖼️ Binding prompt with {len(image_contexts)} image contexts.")
        
        prompt = {
            **state,
            "user_info": user_info,
            "user_profile": user_profile,
            "conversation_summary": running_summary,
            "image_contexts": image_contexts
            
        }
        
        if not prompt.get("messages"):
            logging.error("No messages found in prompt data during binding.")
            prompt["messages"] = [] # Ensure messages is always a list

        return prompt

    def __call__(self, state: RagState, config: RunnableConfig) -> dict[str, Any]:
        """Executes the assistant's runnable."""
        try:
            user_data = state.get("user", {})
            user_info = user_data.get("user_info", {}) if user_data else {}
            user_id = user_info.get("user_id", "unknown") if user_info else "unknown"

            if "configurable" not in config:
                config["configurable"] = {}
            config["configurable"]["user_id"] = user_id

            prompt = self.binding_prompt(state)
            
            if not prompt or not prompt.get("messages"):
                logging.error("Aborting LLM call due to empty or invalid prompt data.")
                raise ValueError("Prompt data is empty or missing required 'messages' field.")

            result = self.runnable.invoke(prompt, config)

            if self._is_valid_response(result):
                logging.debug("Assistant returned a valid response.")
                return result
            else:
                logging.warning("Assistant returned an invalid or empty response. Providing fallback.")
                return self._create_fallback_response(state)

        except Exception as e:
            user_id = state.get("user", {}).get("user_info", {}).get("user_id", "unknown")
            log_exception_details(
                exception=e,
                context="Assistant LLM call failed",
                user_id=user_id
            )
            logging.error(f"Assistant exception, providing fallback: {e}")
            return self._create_fallback_response(state)

    def _is_valid_response(self, result: Any) -> bool:
        """Checks if the LLM response is meaningful."""
        if hasattr(result, "tool_calls") and result.tool_calls:
            return True
        
        content = getattr(result, "content", None)
        if not content:
            return False
        
        if isinstance(content, str):
            return content.strip() != ""
        
        if isinstance(content, list):
            return any(
                isinstance(item, dict) and item.get("text", "").strip()
                for item in content
            )
        
        return bool(content)

    def _create_fallback_response(self, state: RagState) -> AIMessage:
        """Creates a graceful fallback AIMessage."""
        user_info = state.get("user", {}).get("user_info", {})
        user_name = user_info.get("name", "anh/chị")
        
        fallback_content = (
            f"Xin lỗi {user_name}, em đang gặp vấn đề kỹ thuật tạm thời. "
            f"Vui lòng thử lại sau hoặc liên hệ hotline 1900 636 886 để được hỗ trợ trực tiếp. "
            f"Em rất xin lỗi vì sự bất tiện này! 🙏"
        )
        
        logging.info(f"Providing fallback response for user: {user_info.get('user_id', 'unknown')}")
        
        return AIMessage(
            content=fallback_content,
            additional_kwargs={"fallback_response": True}
        )
