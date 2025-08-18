"""
Helper tools for intelligent user information collection workflow
"""
from langchain_core.tools import tool
from typing import List, Dict, Any
import logging

from src.models.user_profile_models import (
    RequiredUserInfo, 
    profile_manager,
    UserInfoExtractor
)

@tool
def analyze_conversation_for_user_info(user_id: str, conversation_content: str) -> str:
    """
    Silently analyze conversation content to detect user information for background collection.
    
    This tool operates in PASSIVE MODE - it only detects and reports information,
    it does NOT suggest asking users for missing information unless specifically requested.
    
    Args:
        user_id: User identifier
        conversation_content: The conversation text to analyze
        
    Returns:
        Analysis results for background information collection
        
    When to use:
        - After processing user input to passively detect information
        - For silent information extraction without bothering the user
        - To log what information was naturally provided by the user
    """
    try:
        # Get current profile completeness
        from src.tools.memory_tools import get_user_profile
        
        # This will update the completeness status
        profile_info = get_user_profile.invoke({"user_id": user_id})
        
        # Get what's specifically missing
        completeness = profile_manager.get_profile_completeness(user_id)
        
        # Analyze conversation content
        detected_info_type = UserInfoExtractor.extract_info_type(conversation_content)
        
        analysis_results = []
        
        # Check if we detected useful information
        if detected_info_type:
            if detected_info_type in completeness.missing_info:
                # This is missing info we need!
                if UserInfoExtractor.validate_info_content(detected_info_type, conversation_content):
                    analysis_results.append(f"🔍 Detected missing {detected_info_type.value}: ready for silent collection")
                else:
                    analysis_results.append(f"⚠️ Detected {detected_info_type.value} but format invalid")
            else:
                analysis_results.append(f"ℹ️ Detected {detected_info_type.value}: already collected")
        else:
            analysis_results.append("ℹ️ No specific user information detected")
        
        # Include completion status for logging
        status = f"📊 Profile completeness: {completeness.completion_percentage:.1f}%"
        analysis_results.append(status)
        
        return "\n".join(analysis_results)
        
    except Exception as e:
        logging.error(f"❌ Error analyzing conversation: {e}")
        return f"Error analyzing conversation: {e}"


@tool
def get_suggested_questions_for_missing_info(user_id: str) -> str:
    """
    ONLY use this tool when you have a BUSINESS REQUIREMENT to collect specific information.
    
    This should NOT be used for general information collection - only when:
    - Booking requires phone number for confirmation
    - Age verification needed for specific services  
    - Gender required for personalized recommendations
    - Birth year needed for age-restricted services
    
    Args:
        user_id: User identifier
        
    Returns:
        Contextual questions for REQUIRED business information only
        
    When to use:
        - When business logic requires specific information to proceed
        - NOT for general profile completion
        - NOT for optional information collection
    """
    try:
        # Update completeness status
        from src.tools.memory_tools import get_user_profile
        get_user_profile.invoke({"user_id": user_id})
        
        completeness = profile_manager.get_profile_completeness(user_id)
        
        if completeness.is_complete:
            return "✅ All required information available for business operations."
        
        # Only return business-contextual questions, not pushy collection
        business_context_questions = {
            RequiredUserInfo.PHONE_NUMBER: [
                "Để xác nhận đặt bàn, bạn có thể cung cấp số điện thoại không?",
                "Số điện thoại giúp chúng tôi thông báo khi bàn sẵn sàng."
            ],
            RequiredUserInfo.GENDER: [
                "Để phục vụ phù hợp hơn, anh/chị là nam hay nữ?",
                "Giúp chúng tôi xưng hô cho đúng - anh hay chị ạ?"
            ],
            RequiredUserInfo.AGE: [
                "Để đề xuất món phù hợp, bạn có thể cho biết độ tuổi không?",
                "Biết độ tuổi giúp chúng tôi tư vấn món ăn phù hợp hơn."
            ],
            RequiredUserInfo.BIRTH_YEAR: [
                "Để có ưu đãi sinh nhật, bạn sinh năm nào?"
            ]
        }
        
        # Return business-justified questions only
        result = "💼 Business-contextual information collection:\n"
        
        for missing_info in completeness.missing_info:
            questions = business_context_questions.get(missing_info, [])
            if questions:
                result += f"• {missing_info.value}: {questions[0]}\n"
        
        result += f"\n📊 Current completion: {completeness.completion_percentage:.1f}%"
        result += "\n⚠️ Only ask when business logic requires this information!"
        
        return result
        
    except Exception as e:
        logging.error(f"❌ Error getting business questions: {e}")
        return f"Error getting questions: {e}"


@tool
def check_and_save_user_info_from_message(user_id: str, message: str, context: str = "") -> str:
    """
    PASSIVE information collection: silently extract and save user information from natural conversation.
    
    This operates in background mode - it only collects information that users naturally provide,
    without prompting them or interrupting the conversation flow.
    
    Args:
        user_id: User identifier
        message: User's message to analyze
        context: Optional context about the conversation
        
    Returns:
        Silent collection result (for logging purposes)
        
    When to use:
        - After every user message for silent information extraction
        - For background profile enhancement without user interruption
        - To capture naturally occurring user information
    """
    try:
        # First analyze what we found (passive mode)
        analysis = analyze_conversation_for_user_info.invoke({
            "user_id": user_id,
            "conversation_content": message
        })
        
        # If we found valid missing info, save it silently
        if "ready for silent collection" in analysis:
            from src.tools.memory_tools import smart_save_user_info
            
            save_result = smart_save_user_info.invoke({
                "user_id": user_id,
                "content": message,
                "context": context
            })
            
            logging.info(f"🔍 Silent collection: {save_result}")
            return f"� Background Analysis: {analysis}\n💾 Silent Collection: {save_result}"
        else:
            logging.info(f"🔍 Analysis: {analysis}")
            return f"� Background Analysis: {analysis}\n💾 No collection needed."
            
    except Exception as e:
        logging.error(f"❌ Error in silent collection: {e}")
        return f"Error in background processing: {e}"
