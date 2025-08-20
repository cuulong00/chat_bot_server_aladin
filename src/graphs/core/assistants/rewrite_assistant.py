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
                    "🔄 **BẠN LÀ CHUYÊN GIA VIẾT LẠI CÂU HỎI ĐỂ TỐI ƯU HOÁ TÌM KIẾM TÀI LIỆU**\n\n"
                    "**NHIỆM VỤ:** Chuyển đổi câu hỏi thành dạng tối ưu cho vector search semantic similarity.\n\n"
                    "**CHIẾN LƯỢC VIẾT LẠI:**\n\n"
                    "1️⃣ **BRAND FORMALIZATION:**\n"
                    "• 'bên mình', 'quán mình', 'ở đây' → 'Tian Long'\n"
                    "• 'nhà hàng này' → 'nhà hàng Tian Long'\n"
                    "• Luôn thêm tên thương hiệu vào context\n\n"
                    "2️⃣ **KEYWORD ENHANCEMENT theo chủ đề:**\n"
                    "• **Chi nhánh/Địa chỉ:** → 'thông tin chi nhánh Tian Long', 'Tian Long có bao nhiêu chi nhánh', 'địa chỉ cơ sở Tian Long', 'chi nhánh Tian Long ở đâu', 'locations Tian Long'\n"
                    "• **Menu/Món ăn:** → 'thực đơn Tian Long', 'combo lẩu bò', 'giá món ăn Tian Long'\n" 
                    "• **Khuyến mãi:** → 'ưu đãi Tian Long', 'chương trình khuyến mãi', 'giảm giá sinh nhật'\n"
                    "• **Dịch vụ:** → 'dịch vụ Tian Long', 'đặt bàn', 'giao hàng'\n\n"
                    "3️⃣ **SEMANTIC MATCHING:**\n"
                    "• Thay thế từ thân mật bằng từ chính thức\n"
                    "• Thêm từ đồng nghĩa và từ khóa liên quan\n"
                    "• Sử dụng cấu trúc câu giống tài liệu gốc\n\n"
                    "4️⃣ **CONTEXT ENRICHMENT:**\n"
                    "Domain: {domain_context}\n"
                    "Conversation: {conversation_summary}\n\n"
                    "**VÍ DỤ CHUYỂN ĐỔI:**\n"
                    "• 'cho anh hỏi bên mình có bao nhiêu chi nhánh' → 'thông tin chi nhánh Tian Long có bao nhiêu cơ sở'\n"
                    "• 'quán có những món gì' → 'thực đơn món ăn Tian Long có gì'\n"
                    "• 'có ưu đãi gì không' → 'chương trình khuyến mãi ưu đãi Tian Long'\n"
                    "• 'địa chỉ cơ sở nào' → 'thông tin địa chỉ chi nhánh Tian Long ở đâu'\n"
                    "• 'vincom thảo điền' → 'chi nhánh Tian Long Vincom Thảo Điền địa chỉ'\n\n"
                    "**YÊU CẦU:** Viết lại để tăng semantic similarity với tài liệu trong database."
                ),
                (
                    "human",
                    "**CÂU HỎI GỐC:** {question}\n\n"
                    "**YÊU CẦU:** Viết lại thành một câu hỏi duy nhất, ngắn gọn, tối ưu cho tìm kiếm semantic (CÙNG NGÔN NGỮ với câu gốc).\n\n"
                    "**CHỈ TRẢ LỜI MỘT CÂU DUY NHẤT - KHÔNG GIẢI THÍCH:**"
                ),
            ]
        ).partial(domain_context=domain_context)
        runnable = prompt | llm
        super().__init__(runnable)
