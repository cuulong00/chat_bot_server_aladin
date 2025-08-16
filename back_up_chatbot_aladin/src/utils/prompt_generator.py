"""
Dynamic prompt generation utilities for adaptive RAG.
This module generates context-aware prompts based on query classification
instead of using hardcoded keywords.
"""

from typing import Dict
from src.utils.query_classifier import QueryClassifier

def generate_doc_grader_prompt(domain_context: str, query: str = "") -> str:
    """
    Generate document grader prompt with dynamic relevance boosts.
    
    Args:
        domain_context: Domain context string
        query: User query for context-aware prompt generation
        
    Returns:
        Generated document grader prompt
    """
    base_prompt = f"""You are an expert at evaluating if a document is topically relevant to a user's question.
Your task is to determine if the document discusses the same general topic as the question, even if it doesn't contain the exact answer.
Current date for context is: {{current_date}}
Domain context: {domain_context}

--- CONVERSATION CONTEXT ---
Previous conversation summary: {{conversation_summary}}
Use this context to better understand what the user is asking about and whether the document is relevant to the ongoing conversation.

"""

    # Add dynamic relevance boosts based on query classification
    if query:
        classifier = QueryClassifier(domain="restaurant")
        classification = classifier.classify_query(query)
        
        category = classification["primary_category"]
        signals = classification["signals"]
        
        if category in ["menu", "location", "promotion"] and signals:
            boost_section = f"""
RELEVANCE BOOST FOR {category.upper()} QUERIES: Documents containing {category} signals are highly relevant.
Key signals include: {', '.join(signals[:10])}...

"""
            base_prompt += boost_section
    
    base_prompt += """Does the document mention keywords or topics related to the user's question or the conversation context?
For example, if the question is about today's date, any document discussing calendars, dates, or 'today' is relevant.
Consider both the current question AND the conversation history when determining relevance.
Respond with only 'yes' or 'no'."""
    
    return base_prompt

def generate_rewrite_prompt(domain_context: str, query: str = "") -> str:
    """
    Generate query rewrite prompt with dynamic keyword suggestions.
    
    Args:
        domain_context: Domain context string
        query: User query for context-aware prompt generation
        
    Returns:
        Generated rewrite prompt
    """
    base_prompt = f"""You are a domain expert at rewriting user questions to optimize for document retrieval.
Domain context: {domain_context}

--- CONVERSATION CONTEXT ---
Previous conversation summary: {{conversation_summary}}
Use this context to understand what has been discussed before and rewrite the question to include relevant context that will help with document retrieval.

Original question: {{messages}}
Rewrite this question to be more specific and include relevant context from the conversation history that would help find better documents.

"""

    # Add dynamic keyword suggestions based on query classification
    if query:
        classifier = QueryClassifier(domain="restaurant")
        classification = classifier.classify_query(query)
        
        expansion_keywords = classification["expansion_keywords"]
        if expansion_keywords:
            keyword_section = f"""
For this type of query, consider including these relevant keywords: {', '.join(expansion_keywords[:8])}...

"""
            base_prompt += keyword_section
    
    base_prompt += "Make sure the rewritten question is clear and contains keywords that would match relevant documents."
    
    return base_prompt

def generate_generation_prompt_sections(domain_context: str) -> Dict[str, str]:
    """
    Generate sections for the main generation prompt.
    
    Args:
        domain_context: Domain context string
        
    Returns:
        Dictionary containing prompt sections
    """
    return {
        "persona_section": f"""Bạn là Vy – trợ lý ảo thân thiện và chuyên nghiệp của nhà hàng lẩu bò tươi Tian Long (domain context: {domain_context}). 
Bạn luôn ưu tiên thông tin từ tài liệu được cung cấp (context) và cuộc trò chuyện. Nếu tài liệu xung đột với kiến thức trước đó, BẠN PHẢI tin tưởng tài liệu.""",
        
        "greeting_logic": """🎯 **VAI TRÒ VÀ PHONG CÁCH GIAO TIẾP:**
- Bạn là nhân viên chăm sóc khách hàng chuyên nghiệp, lịch sự và nhiệt tình
- **LOGIC CHÀO HỎI THÔNG MINH:**
  • **Lần đầu tiên trong cuộc hội thoại:** Chào hỏi đầy đủ với tên khách hàng (nếu có) + giới thiệu nhà hàng
    Ví dụ: 'Chào anh Tuấn Dương! Nhà hàng lẩu bò tươi Tian Long hiện có tổng cộng 8 chi nhánh...'
  • **Từ câu thứ 2 trở đi:** Chỉ cần lời chào ngắn gọn lịch sự
    Ví dụ: 'Dạ anh/chị', 'Dạ ạ', 'Vâng ạ'
- Sử dụng ngôn từ tôn trọng: 'anh/chị', 'dạ', 'ạ', 'em Vy'
- Thể hiện sự quan tâm chân thành đến nhu cầu của khách hàng
- Luôn kết thúc bằng câu hỏi thân thiện để tiếp tục hỗ trợ""",
        
        "format_freedom": """🎨 **QUYỀN TỰDO SÁNG TẠO ĐỊNH DẠNG:**
- Bạn có TOÀN QUYỀN sử dụng bất kỳ định dạng nào: markdown, HTML, emoji, bảng, danh sách, in đậm, in nghiêng
- Hãy SÁNG TẠO và làm cho nội dung ĐẸP MẮT, SINH ĐỘNG và DỄ ĐỌC
- Sử dụng emoji phong phú để trang trí và làm nổi bật thông tin
- Tạo layout đẹp mắt với tiêu đề, phân đoạn rõ ràng
- Không có giới hạn về format - hãy tự do sáng tạo!""",
        
        "quality_requirements": """🔍 **YÊU CẦU CHẤT LƯỢNG:**
- **QUAN TRỌNG:** Kiểm tra lịch sử cuộc hội thoại để xác định loại lời chào phù hợp:
  • Nếu đây là tin nhắn đầu tiên (ít tin nhắn trong lịch sử) → chào hỏi đầy đủ
  • Nếu đã có cuộc hội thoại trước đó → chỉ cần 'Dạ anh/chị' ngắn gọn
- Sử dụng `[source_id]` để trích dẫn thông tin từ tài liệu
- Không bịa đặt thông tin
- Sử dụng định dạng markdown/HTML để tạo nội dung đẹp mắt
- Emoji phong phú và phù hợp
- Kết thúc bằng câu hỏi hỗ trợ tiếp theo"""
    }
