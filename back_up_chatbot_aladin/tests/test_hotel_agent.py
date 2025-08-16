import os
from langgraph_api import Client

# Đảm bảo biến môi trường kết nối DB đã được thiết lập
os.environ["DATABASE_CONNECTION"] = "postgresql://chatbot:Tho%40123SS@69.197.187.234:5432/chatbot_db?sslmode=disable"

# Khởi tạo client LangGraph API (hoặc import graph trực tiếp nếu chạy local)
client = Client(base_url="http://127.0.0.1:2024")  # Sửa lại nếu API chạy port khác

def test_hotel_booking_flow():
    # 1. Khởi tạo hội thoại mới
    thread = client.threads.create()
    thread_id = thread.id

    # 2. Gửi yêu cầu tìm khách sạn
    user_message_1 = "Tôi muốn đặt phòng khách sạn ở Hà Nội từ ngày 10/07/2025 đến 12/07/2025, giá tầm trung."
    event_1 = client.messages.create(
        thread_id=thread_id,
        role="user",
        content=user_message_1,
    )
    print("User:", user_message_1)

    # 3. Lấy phản hồi từ assistant (nên trả về danh sách khách sạn)
    run = client.runs.create_and_poll(
        thread_id=thread_id,
        assistant_id="agent",  # ID của graph assistant
        instructions="Test hotel booking flow"
    )
    events = list(client.runs.list_events(run_id=run.id))
    for e in events:
        if e.type == "message":
            print("Assistant:", e.data.content)

    # 4. Gửi yêu cầu đặt phòng với hotel_id cụ thể (giả sử assistant trả về hotel_id=1)
    user_message_2 = "Tôi chọn khách sạn có mã số 1, hãy đặt phòng cho tôi."
    event_2 = client.messages.create(
        thread_id=thread_id,
        role="user",
        content=user_message_2,
    )
    print("User:", user_message_2)

    # 5. Lấy phản hồi xác nhận đặt phòng
    run2 = client.runs.create_and_poll(
        thread_id=thread_id,
        assistant_id="agent",
        instructions="Test hotel booking flow"
    )
    events2 = list(client.runs.list_events(run_id=run2.id))
    for e in events2:
        if e.type == "message":
            print("Assistant:", e.data.content)

    # 6. (Optional) Kiểm tra trạng thái booking trong database nếu cần

if __name__ == "__main__":
    test_hotel_booking_flow()