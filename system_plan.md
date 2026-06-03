# Kế hoạch Xây dựng Hệ thống Chi tiết - Cập nhật 30 ngày (System Plan)

Tài liệu này vạch ra lộ trình thực hiện rút gọn dự án **Hệ thống Khảo thí và Chấm thi Tự động Đa ngôn ngữ (AI-Powered)** cho Đại học Thành Đông trong vòng **30 ngày (1 tháng)**. Dự kiến nghiệm thu và bàn giao chính thức vào đầu tháng 7/2026 (khoảng ngày 03/07/2026).

---

## Mốc Thời gian và Kế hoạch Thực hiện (Rút gọn 30 ngày)

### Giai đoạn 1: Thiết lập Hệ thống, Cơ sở Dữ liệu & Xác thực (Ngày 1 - Ngày 7)
* **Nội dung công việc:**
  1. Khởi tạo môi trường, thiết lập Git, cấu hình an toàn cho Agent & liên kết GitHub (Đã hoàn thành).
  2. Xây dựng cấu trúc thư mục, Database Connection Pool cục bộ & thiết lập SQLAlchemy Models (Đã hoàn thành).
  3. Cấu hình Alembic để quản lý các phiên bản migration cơ sở dữ liệu trên SQLite (local) và PostgreSQL (chạy thử).
  4. Triển khai API đăng ký, đăng nhập và xác thực phân quyền sử dụng JWT (JSON Web Token) cho 3 nhóm đối tượng: Admin, Giáo viên, Thí sinh.
  5. Cài đặt middleware ngôn ngữ (i18n) cho cả giao diện Frontend và API Backend.
* **Thời hạn hoàn thành:** **10/06/2026 (Hết Ngày 7)**

---

### Giai đoạn 2: Quản lý Đề thi, Ngân hàng Câu hỏi & Giám sát - Module 1 (Ngày 8 - Ngày 14)
* **Nội dung công việc:**
  1. Phát triển giao diện và API quản lý ngân hàng câu hỏi đa ngôn ngữ (Chống lỗi hiển thị font chữ tiếng Trung HSK bằng định dạng UTF-8).
  2. Phát triển thuật toán trộn đề thi ngẫu nhiên và phân phát đề tự động không trùng lặp cho thí sinh.
  3. Phát triển giao diện làm bài thi trắc nghiệm mượt mà ở Frontend.
  4. Tích hợp bộ công cụ giám sát (Proctoring): khóa toàn màn hình (Fullscreen API), cảnh báo chuyển tab (Visibility API), thu luồng webcam giám sát ngẫu nhiên.
  5. Triển khai cơ chế **Auto-save** (Tự động lưu bài làm của thí sinh xuống Database mỗi 30 giây) đề phòng sự cố cúp điện hoặc mất kết nối mạng. Mã hóa bài thi ngay khi nộp.
* **Thời hạn hoàn thành:** **17/06/2026 (Hết Ngày 14) - Hoàn thành Mốc thanh toán 1 (30%)**

---

### Giai đoạn 3: Triển khai Module Chấm điểm AI Bài Nói & Bài Viết - Module 2 & 3 (Ngày 15 - Ngày 22)
* **Nội dung công việc:**
  1. Xây dựng màn hình phòng thi bài Viết (Rich Text editor) và bài Nói (ghi âm nén Opus/WebM/MP3 trực tiếp tại trình duyệt để tối ưu băng thông).
  2. Thiết lập cấu trúc Prompt chấm thi trên Gemini API dựa trên khung chuẩn VSTEP (B1-C1) và HSK (1-6) hướng tới độ chính xác >90%.
  3. Tích hợp hàng đợi Celery + Redis ở Backend để tiếp nhận bài làm nói/viết của thí sinh, đưa vào hàng đợi chấm ngầm, gửi audio trực tiếp sang Gemini 1.5 Flash để transcribe và chấm điểm chi tiết.
  4. Lưu kết quả chấm thi (điểm số phân đoạn + nhận xét chi tiết JSON) về database.
* **Thời hạn hoàn thành:** **25/06/2026 (Hết Ngày 22) - Hoàn thành Mốc thanh toán 2 (40%)**

---

### Giai đoạn 4: Tích hợp Hệ thống, Kiểm thử Tải 500 CCU, Chạy thử Pilot & Bàn giao - Module 4 (Ngày 23 - Ngày 30)
* **Nội dung công việc:**
  1. Tích hợp toàn diện các chức năng Frontend và Backend lên server thử nghiệm trên Google Cloud.
  2. Thực hiện **Kiểm thử tải (Load Testing)** giả lập **500 thí sinh đồng thời nộp file ghi âm bài Nói** bằng k6/Locust để tối ưu hóa hiệu năng hàng đợi Redis/Celery worker trên Google Cloud.
  3. Tổ chức kỳ thi thử nghiệm **Pilot Run** với 10-20 thí sinh thật tại Đại học Thành Đông để đánh giá hiệu năng thực tế.
  4. Viết tài liệu hướng dẫn vận hành hệ thống chi tiết cho cán bộ kỹ thuật và giảng viên.
  5. Đào tạo trực tiếp cách quản lý đề và coi thi cho 3 giảng viên của trường.
  6. Bàn giao 100% mã nguồn dự án, cơ sở dữ liệu và chuyển giao tài khoản Google Cloud / Gemini API cho Đại học Thành Đông.
* **Thời hạn hoàn thành:** **03/07/2026 (Hết Ngày 30) - Hoàn thành Mốc thanh toán 3 (30%)**
