# LangGraph Multi-Subgraph Chatbot Architecture

## 1. Tổng quan kiến trúc

Hệ thống này sử dụng kiến trúc multi-subgraph với LangGraph (Python) ở server và React ở client. Mỗi domain (accounting, insurance, travel, wolt_food) là một subgraph riêng biệt, được điều phối bởi một main graph (router).

## 2. Luồng hoạt động tổng thể

### 2.1. User chọn Agent và nhập dữ liệu chat
- Người dùng chọn Agent (domain) trên giao diện React (client).
- Khi nhập tin nhắn và gửi, client sẽ gửi request (thường là streaming) lên server, kèm theo thông tin context (domain, user, v.v.).

### 2.2. Server xử lý request
- Server nhận request, khởi tạo một state (MainState) chứa domain, context, messages.
- Main graph có node đầu vào là `router`.
- Hàm `get_domain_from_state` sẽ xác định domain từ context (nếu không có sẽ mặc định là 'travel').
- Dựa vào domain, graph sẽ route sang subgraph tương ứng: accounting, insurance, travel, wolt_food.
- Mỗi subgraph sẽ thực hiện các bước xử lý chuyên biệt (retrieval, reasoning, tool call, v.v.)
- Sau khi subgraph xử lý xong, graph sẽ kết thúc (END).

### 2.3. Trả kết quả về client
- Server stream kết quả từng bước (nếu có) hoặc trả về kết quả cuối cùng.
- Client nhận kết quả, cập nhật UI, hiển thị phản hồi cho người dùng.

## 3. Chi tiết các thành phần

### 3.1. Main Graph (main_graph.py)
- Quản lý state toàn cục: domain, context, messages.
- Node `router`: xác định domain và điều hướng sang subgraph phù hợp.
- Các node subgraph: accounting_graph, insurance_graph, travel_graph, wolt_food_graph.
- Kết thúc ở END.

### 3.2. Subgraph (ví dụ: travel_graph)
- Xử lý logic chuyên biệt cho từng domain: truy xuất tri thức, tóm tắt, reasoning, tool call, v.v.
- Có thể sử dụng các node như: summarizer, retriever, generator, tool executor, ...

### 3.3. Client (React)
- Quản lý state hội thoại, agent, context.
- Gửi request lên server khi user gửi tin nhắn.
- Nhận stream kết quả, hiển thị từng bước reasoning/tool call nếu có.
- Hiển thị kết quả cuối cùng cho user.

## 4. Luồng hoạt động chi tiết

1. User chọn Agent (domain) trên UI.
2. User nhập tin nhắn, nhấn gửi.
3. Client gửi request (có domain, context, messages) lên server.
4. Server nhận, khởi tạo MainState, vào node `router`.
5. `router` xác định domain, chuyển sang subgraph tương ứng.
6. Subgraph xử lý logic (retrieval, reasoning, tool call, ...).
7. Kết quả (có thể stream từng bước) trả về client.
8. Client cập nhật UI, hiển thị reasoning/tool call (nếu có), và phản hồi cuối cùng cho user.

---

**File này dùng để tham khảo nhanh kiến trúc và luồng hoạt động của hệ thống LangGraph multi-subgraph chatbot.**

python3 -m uvicorn app:app --host 0.0.0.0 --port 2024

python3 test_mixed_content_analysis.py

python3 test_mixed_content_api.py

Note for Windows users:
- Use `python` instead of `python3` when running commands. For example:
	- `python -m uvicorn app:app --host 0.0.0.0 --port 2024`
	- `python test_mixed_content_analysis.py`
	- `python test_mixed_content_api.py`


.\.venv\Scripts\python.exe scripts\console_facebook_chat.py --base http://127.0.0.1:2024 --psid 24769757262629049 --app-secret "3a382791ab377abc0e622367b516e802"



.\.venv\Scripts\python.exe scripts\console_facebook_chat.py --base http://127.0.0.1:2024 --psid 24769757262629049 --app-secret 3a382791ab377abc0e622367b516e802