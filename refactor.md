# Kế hoạch Refactor Code cho `adaptive_rag_graph.py`

## Mục tiêu

-   **Tăng tính module hóa (Modularity):** Tách logic của từng "trợ lý" (Assistant) trong graph ra các file riêng biệt để dễ quản lý, bảo trì và mở rộng.
-   **Cải thiện khả năng đọc (Readability):** Giảm độ dài và độ phức tạp của file `adaptive_rag_graph.py`, giúp file này chỉ tập trung vào việc xây dựng và kết nối các node trong graph.
-   **Tuân thủ PEP 8:** Đảm bảo code tuân thủ các tiêu chuẩn của Python, giúp code sạch sẽ và nhất quán.
-   **Không thay đổi nghiệp vụ:** Quá trình refactor chỉ thay đổi cấu trúc code, không làm ảnh hưởng đến luồng logic và hoạt động hiện tại của chatbot.

## Cấu trúc thư mục mới

Tất cả các Assistant sẽ được chuyển vào thư mục `src/graphs/assistants/`.

```
src/
└── graphs/
    ├── core/
    │   └── adaptive_rag_graph.py  # File chính, giờ sẽ gọn hơn
    ├── state/
    │   └── state.py
    └── assistants/                # <-- THƯ MỤC MỚI
        ├── __init__.py
        ├── base_assistant.py      # <-- Class Assistant cơ sở
        ├── router_assistant.py
        ├── doc_grader_assistant.py
        ├── rewrite_assistant.py
        ├── generation_assistant.py
        ├── suggestive_assistant.py
        ├── hallucination_grader.py
        ├── direct_answer_assistant.py
        └── document_processor.py
```

## Kế hoạch chi tiết

### Bước 1: Tạo Class `BaseAssistant`

1.  Tạo file `src/graphs/assistants/base_assistant.py`.
2.  Di chuyển class `Assistant` từ `adaptive_rag_graph.py` vào file này.
3.  Đổi tên class thành `BaseAssistant` để thể hiện rõ vai trò là class cơ sở.
4.  Thêm các import cần thiết cho class này (`Runnable`, `RunnableConfig`, `RagState`, `logging`, etc.).

### Bước 2: Tách từng Assistant ra file riêng

Với mỗi assistant logic trong `create_adaptive_rag_graph` (router, grader, generator...), thực hiện các bước sau:

1.  **Tạo file assistant tương ứng:** Ví dụ, tạo `src/graphs/assistants/router_assistant.py`.
2.  **Di chuyển Prompt:** Chuyển toàn bộ phần định nghĩa `ChatPromptTemplate` của assistant đó vào file mới.
3.  **Tạo Class Assistant chuyên biệt:**
    *   Tạo một class mới kế thừa từ `BaseAssistant` (ví dụ: `class RouterAssistant(BaseAssistant):`).
    *   Trong `__init__` của class này, nhận vào các `llm` và các tham số cần thiết (ví dụ: `llm_router`, `domain_context`).
    *   Xây dựng `runnable` hoàn chỉnh (prompt | llm | output_parser) bên trong `__init__` và gán nó cho `self.runnable`.

    **Ví dụ cho `router_assistant.py`:**
    ```python
    from .base_assistant import BaseAssistant
    from langchain_core.prompts import ChatPromptTemplate
    from ...models import RouteQuery # (Cần điều chỉnh import)

    class RouterAssistant(BaseAssistant):
        def __init__(self, llm_router, domain_context, domain_instructions):
            router_prompt = ChatPromptTemplate.from_messages(...) # <--- Định nghĩa prompt ở đây
            runnable = router_prompt | llm_router.with_structured_output(RouteQuery)
            super().__init__(runnable)
    ```

4.  Lặp lại quy trình này cho tất cả các assistants:
    *   `doc_grader_assistant`
    *   `rewrite_assistant`
    *   `generation_assistant`
    *   `suggestive_assistant`
    *   `hallucination_grader_assistant`
    *   `direct_answer_assistant`
    *   `document_processing_assistant`

### Bước 3: Refactor file `adaptive_rag_graph.py`

1.  **Xóa bỏ code thừa:**
    *   Xóa class `Assistant` gốc.
    *   Xóa tất cả các định nghĩa `ChatPromptTemplate` dài dòng đã được di chuyển.
2.  **Import các Assistant mới:**
    *   Thêm các câu lệnh import ở đầu file để import các class Assistant mới từ thư mục `src/graphs/assistants/`.
    ```python
    from ..assistants.router_assistant import RouterAssistant
    from ..assistants.direct_answer_assistant import DirectAnswerAssistant
    # ... và các assistant khác
    ```
3.  **Khởi tạo các Assistant:**
    *   Bên trong hàm `create_adaptive_rag_graph`, thay vì định nghĩa prompt và runnable tại chỗ, hãy khởi tạo các object từ class Assistant đã import.

    **Code "Trước":**
    ```python
    # ...
    router_prompt = ChatPromptTemplate.from_messages(...)
    router_runnable = router_prompt | llm_router.with_structured_output(RouteQuery)
    router_assistant = Assistant(router_runnable)
    # ...
    ```

    **Code "Sau":**
    ```python
    # ...
    router_assistant = RouterAssistant(llm_router, domain_context, domain_instructions)
    # ...
    ```
4.  **Giữ nguyên logic của Graph:** Các hàm node (`route_question`, `retrieve`, `grade_documents`, etc.) và các lệnh `graph.add_node`, `graph.add_conditional_edges` sẽ được giữ nguyên. Chúng sẽ sử dụng các object assistant đã được khởi tạo.

### Bước 4: Đảm bảo tuân thủ PEP 8

-   Sau khi hoàn tất việc di chuyển và refactor cấu trúc, sẽ tiến hành chạy công cụ auto-format (ví dụ: `black` hoặc `autopep8`) trên toàn bộ các file đã thay đổi để đảm bảo code sạch sẽ, đúng chuẩn.
-   Kiểm tra lại tên biến, tên hàm, và độ dài dòng.
