Cách B: Chuẩn production (ít/không hết hạn) bằng System User (khuyến nghị)

Vào business.facebook.com → Business Settings (Cài đặt Doanh nghiệp).
Users → System Users → Add để tạo System User (System User Type: Admin).
Assign assets: gán Page của bạn cho System User này với quyền Full Control.
Ở System Users → chọn System User → Add Asset → chọn Page → Full Control.
Generate token:
Bấm “Generate New Token” → chọn App của bạn.
Chọn quyền: pages_messaging, pages_manage_metadata, pages_read_engagement (và các quyền cần thêm nếu có).
Chọn Page cần cấp token.
Sinh token. Token này thường là long-lived, ổn định cho production.
Đặt vào .env:
FB_PAGE_ACCESS_TOKEN=<system_user_page_token>
Ghi chú:

Nếu bạn không thấy Generate token, hãy đảm bảo App ở chế độ phù hợp và đã link với Business của bạn, Page đã được gán làm Asset cho System User.
Dùng FB_API_VERSION phù hợp (ví dụ v19.0). Trong .env hiện bạn đang để v18.0, có thể nâng lên theo App version: FB_API_VERSION=v19.0.
Đặt FB_VERIFY_TOKEN
Đây là chuỗi do bạn tự đặt, chỉ cần trùng khớp giữa server và phần cấu hình webhook trong Facebook App.
Đặt 1 chuỗi mạnh, ví dụ: FB_VERIFY_TOKEN=gauvatho (như bạn đã để), hoặc chuỗi khác khó đoán.
Khi cấu hình Webhooks trong Messenger → Settings → Webhooks → Add Callback URL:
Callback URL: https://ai-agent.onl/api/facebook/webhook
Verify Token: chính xác chuỗi bạn đặt ở FB_VERIFY_TOKEN
Server sẽ đối chiếu và trả về hub.challenge nếu verify token khớp.
Cập nhật .env và khởi động lại dịch vụ
Cập nhật 4 biến:
FB_PAGE_ACCESS_TOKEN=<…>
FB_APP_SECRET=<…>
FB_VERIFY_TOKEN=<…>
FB_API_VERSION=v19.0 (hoặc version App của bạn)
Khởi động lại ứng dụng để các biến có hiệu lực.
Kiểm tra nhanh
6.1) Kiểm tra verify webhook thủ công (tùy chọn)

Bạn có thể tự mô phỏng lời gọi verify của Facebook (thay VERIFY_TOKEN bằng FB_VERIFY_TOKEN bạn đặt):
Trình duyệt:
https://ai-agent.onl/api/facebook/webhook?hub.mode=subscribe&hub.verify_token=VERIFY_TOKEN&hub.challenge=123456
Nếu token khớp, API sẽ trả về 123456.
PowerShell:

6.2) Kiểm tra nhận/sent message

Vào Messenger → Settings → Webhooks → đảm bảo Page đã “Subscribed”.
Nhắn tin vào Page từ tài khoản tester/ngoài (nếu App Live).
Quan sát log server để thấy webhook POST đến và bot gửi trả lời.
Lỗi thường gặp và cách xử lý

400 “Field required hub.*”: Bạn đang mở webhook không có query (bình thường). Chỉ Facebook khi verify mới gửi các tham số này.
403/401 khi nhận POST: Sai FB_APP_SECRET → xác minh lại secret đúng App.
Không trả lời người dùng:
Kiểm tra App đã Live (nếu không phải tester), Page đã Subscribe Webhooks.
FB_PAGE_ACCESS_TOKEN đúng Page và còn hiệu lực.
Endpoint https và public, trả về nhanh (200 trong vài giây).
FB_API_VERSION mismatch: Dùng version khớp với App, ví dụ v19.0.
Nếu bạn muốn, mình có thể kiểm tra giúp cấu hình hiện tại trên App của bạn (bạn mô tả trạng thái App/Page, các quyền đã bật) và đề xuất lộ trình chuẩn production (System User token, quyền cần duyệt).