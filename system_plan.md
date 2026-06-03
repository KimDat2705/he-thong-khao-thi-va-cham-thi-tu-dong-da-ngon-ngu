# Kế hoạch Xây dựng Hệ thống Chi tiết (System Plan)

Tài liệu này vạch ra lộ trình thực hiện dự án **Hệ thống Khảo thí và Chấm thi Tự động Đa ngôn ngữ (AI-Powered)** cho Đại học Thành Đông trong vòng **90 ngày** (75 ngày chạy thử nghiệm Pilot, 15 ngày hoàn thiện và bàn giao).

---

## Mốc Thời gian và Kế hoạch Thực hiện

### Giai đoạn 1: Thiết lập Hệ thống, Cơ sở Dữ liệu & Xác thực (Ngày 1 - Ngày 15)
* **Nội dung công việc:**
  1. Khởi tạo môi trường, thiết lập Git & cấu hình an toàn cho Agent (Đã hoàn thành).
  2. Xây dựng cấu trúc thư mục, Database Connection Pool và khai báo các Database Models (Đã hoàn thành).
  3. Cấu hình Alembic để quản lý database migrations trên PostgreSQL.
  4. Triển khai API đăng ký, đăng nhập và xác thực phân quyền sử dụng JWT (JSON Web Token) cho 3 nhóm đối tượng: Admin, Giáo viên, Thí sinh.
  5. Cài đặt middleware dịch thuật (i18n) cho cả Frontend và Backend.
* **Thời hạn hoàn thành:** **Ngày 15**

---

### Giai đoạn 2: Quản lý Đề thi, Ngân hàng Câu hỏi & Giám sát - Module 1 (Ngày 16 - Ngày 35)
* **Nội dung công việc:**
  1. Phát triển tính năng quản lý ngân hàng câu hỏi đa ngôn ngữ (Đặc biệt xử lý mã hóa UTF-8 để hiển thị ký tự tiếng Trung HSK chuẩn xác không bị lỗi).
  2. Viết thuật toán trộn đề thi ngẫu nhiên và phân phát đề tự động không trùng lặp.
  3. Phát triển giao diện thi trắc nghiệm mượt mà, không giật lag ở Frontend.
  4. Tích hợp bộ công cụ giám sát proctoring: khóa chế độ toàn màn hình, cảnh báo thí sinh nếu chuyển tab/thoát màn hình, thu luồng webcam giám sát ngẫu nhiên.
  5. Triển khai cơ chế **Auto-save** (Tự động lưu bài làm của thí sinh xuống Database mỗi 30 giây) đề phòng sự cố cúp điện hoặc mất kết nối mạng. Mã hóa bài thi ngay khi nộp.
* **Thời hạn hoàn thành:** **Ngày 35 (Hoàn thành Mốc thanh toán 1 - 30%)**

---

### Giai đoạn 3: Triển khai Engine Chấm điểm AI Bài Viết - Module 3 (Ngày 36 - Ngày 50)
* **Nội dung công việc:**
  1. Xây dựng giao diện phòng thi bài Viết (Hỗ trợ trình biên tập Rich Text đa ngôn ngữ).
  2. Thiết lập cấu trúc Prompt chấm thi trên Gemini API dựa trên khung chuẩn VSTEP (B1-C1) và HSK (1-6).
  3. Xây dựng worker xử lý ngầm (Celery) để đẩy bài viết lên Gemini API chấm điểm, phân loại lỗi ngữ pháp, từ vựng và trả về lời khuyên khắc phục dưới dạng JSON.
  4. Kiểm thử chất lượng chấm bài viết của AI để đảm bảo độ chính xác >90% so với giảng viên chấm thủ công.
* **Thời hạn hoàn thành:** **Ngày 50**

---

### Giai đoạn 4: Triển khai Engine Ghi âm & Chấm điểm AI Bài Nói - Module 2 (Ngày 51 - Ngày 65)
* **Nội dung công việc:**
  1. Thiết kế giao diện phòng thi bài Nói (Tích hợp bộ đếm ngược thời gian ghi âm và chuẩn bị câu trả lời).
  2. Sử dụng hook `useMediaRecorder` để ghi âm, nén âm thanh (Opus/WebM/MP3) trực tiếp tại trình duyệt thí sinh để giảm dung lượng tải lên.
  3. Viết task worker Celery tải file ghi âm nộp lên, truyền trực tiếp luồng audio vào Gemini 1.5 Flash để dịch tự động (transcribe) và chấm điểm dựa trên phát âm, độ trôi chảy và tone tiếng Trung.
  4. Kiểm thử chất lượng chấm bài nói đạt độ chính xác tương đồng >90% so với thang điểm người chấm.
* **Thời hạn hoàn thành:** **Ngày 65 (Hoàn thành Mốc thanh toán 2 - 40%)**

---

### Giai đoạn 5: Tích hợp Hệ thống, Kiểm thử Tải & Chạy thử nghiệm Pilot - Module 4 (Ngày 66 - Ngày 75)
* **Nội dung công việc:**
  1. Tích hợp toàn diện các cấu phần độc lập thành một hệ thống thống nhất.
  2. Thực hiện **Kiểm thử tải (Load Testing)** giả lập kịch bản **500 thí sinh đồng thời nộp file ghi âm bài Nói** bằng các công cụ k6/Locust để tinh chỉnh tài nguyên Redis/Celery worker trên Google Cloud Server.
  3. Cài đặt hệ thống backup dữ liệu định kỳ trên Cloud.
  4. Tổ chức kỳ thi thử nghiệm **Pilot Run** với 10-20 thí sinh thật tại Đại học Thành Đông để đánh giá hiệu năng thực tế.
* **Thời hạn hoàn thành:** **Ngày 75**

---

### Giai đoạn 6: Tinh chỉnh, Đào tạo và Bàn giao (Ngày 76 - Ngày 90)
* **Nội dung công việc:**
  1. Khắc phục các lỗi phát sinh (nếu có) sau kỳ thi thử nghiệm Pilot.
  2. Viết tài liệu hướng dẫn vận hành hệ thống chi tiết cho cán bộ kỹ thuật và giảng viên.
  3. Tổ chức buổi tập huấn, đào tạo trực tiếp cách quản lý đề và coi thi cho 3 giảng viên của trường.
  4. Bàn giao 100% mã nguồn dự án, cơ sở dữ liệu và chuyển quyền quản lý Google Cloud Server/Gemini API cho Đại học Thành Đông.
* **Thời hạn hoàn thành:** **Ngày 90 (Hoàn thành Mốc thanh toán 3 - 30%)**
