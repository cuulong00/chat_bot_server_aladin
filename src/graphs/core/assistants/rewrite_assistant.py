from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable

from src.graphs.core.assistants.base_assistant import BaseAssistant


class RewriteAssistant(BaseAssistant):
    """
    An assistant that rewrites the user's question to be more specific for retrieval.
    """
    def __init__(self, llm: Runnable, domain_context: str):
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    # ROLE - Vai trò chuyên gia
                    "# CHUYÊN GIA TỐI ỨU HOÁ TÌM KIẾM SEMANTIC\n\n"
                    
                    "Bạn là Query Rewriting Specialist với 10+ năm kinh nghiệm tối ưu hóa semantic search cho hệ thống RAG. "
                    "Bạn có chuyên môn sâu về vector similarity, keyword matching và domain-specific query transformation.\n\n"
                    
                    # TASK - Nhiệm vụ cụ thể
                    "## NHIỆM VỤ CHÍNH\n"
                    "Chuyển đổi câu hỏi của người dùng thành query tối ưu để đạt semantic similarity cao nhất với tài liệu trong vector database.\n\n"
                    
                    # CONTEXT - Bối cảnh và domain
                    "## BỐI CẢNH\n"
                    f"• Domain: {domain_context}\n"
                    "• Database chứa: thông tin nhà hàng, menu, dịch vụ, khuyến mãi, quy trình\n"
                    "• Search engine: Vector similarity với text-embedding-004\n"
                    "• Target: Tìm exact matching documents với điểm similarity > 0.7\n\n"
                    
                    # EXAMPLES - Ví dụ cụ thể (Few-shot learning)
                    "## VÍ DỤ CHUYỂN ĐỔI\n\n"
                    
                    "**Pattern 1 - Standardization:**\n"
                    "• Input: 'bên mình có mấy chi nhánh vậy'\n"
                    "• Output: 'nhà hàng Tian Long có bao nhiêu chi nhánh'\n\n"
                    
                    "**Pattern 2 - Keyword Enhancement:**\n"
                    "• Input: 'có ưu đãi gì không'\n"
                    "• Output: 'chương trình khuyến mãi ưu đãi Tian Long hiện tại'\n\n"
                    
                    "**Pattern 3 - Specific Terms:**\n"
                    "• Input: 'cách đăng ký như thế nào'\n"
                    "• Output: 'làm thế nào để đăng ký thẻ thành viên Tian Long'\n\n"
                    
                    "**Pattern 4 - Location Queries:**\n"
                    "• Input: 'địa chỉ quán ở đâu'\n"
                    "• Output: 'thông tin địa chỉ chi nhánh nhà hàng Tian Long'\n\n"
                    
                    # CONSTRAINTS - Ràng buộc và quy tắc
                    "## QUY TẮC BẮT BUỘC\n\n"
                    
                    "✅ **PHẢI LÀM:**\n"
                    "1. Thêm 'Tian Long' vào mọi query về nhà hàng\n"
                    "2. Chuyển từ thân mật → từ chính thức ('bên mình' → 'nhà hàng')\n"
                    "3. Bổ sung từ khóa domain-specific ('đăng ký' → 'đăng ký thẻ thành viên')\n"
                    "4. Giữ nguyên ngôn ngữ gốc (Việt → Việt, English → English)\n"
                    "5. Tạo một câu duy nhất, súc tích\n\n"
                    
                    "❌ **KHÔNG ĐƯỢC:**\n"
                    "1. Thay đổi ý nghĩa gốc của câu hỏi\n"
                    "2. Thêm thông tin không có trong query gốc\n"
                    "3. Tạo multiple queries hoặc giải thích\n"
                    "4. Sử dụng từ quá phức tạp\n\n"
                    
                    # FORMAT - Định dạng output
                    "## ĐỊNH DẠNG OUTPUT\n"
                    "Chỉ trả về MỘT câu duy nhất được tối ưu hóa. Không có giải thích, không có metadata.\n\n"
                    
                    # QUALITY GATES - Tiêu chí đánh giá
                    "## TIÊU CHÍ THÀNH CÔNG\n"
                    "Query được coi là tối ưu khi:\n"
                    "• Chứa các keyword chính từ câu gốc\n"
                    "• Có thêm domain-specific terms\n"
                    "• Cấu trúc tương tự documents trong database\n"
                    "• Semantic similarity score dự kiến > 0.7\n\n"
                ),
                (
                    "human",
                    "Query gốc: {question}\n\n"
                    "Hãy tối ưu hóa query này cho semantic search:"
                ),
            ]
        ).partial(domain_context=domain_context)
        runnable = prompt | llm
        super().__init__(runnable)
