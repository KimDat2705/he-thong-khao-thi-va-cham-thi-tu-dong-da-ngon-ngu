# Báo cáo Trạng thái Dự án (Project Status)

File này lưu trữ trạng thái hiện tại của dự án **Hệ thống Khảo thí và Chấm thi Tự động Đa ngôn ngữ (AI-Powered)** cho Đại học Thành Đông. Vui lòng đọc file này khi bắt đầu phiên làm việc mới để nắm bắt tiến độ mà không cần đọc lại toàn bộ mã nguồn.

---

## 1. Trạng thái Hiện tại (Tính đến ngày 03/06/2026)

Dự án đã hoàn thành khởi tạo cấu trúc thư mục phân tách (Decoupled Architecture) và thiết lập khung xương kỹ thuật cơ bản cho cả Frontend và Backend.

### Cấu trúc Thư mục chính
```text
/HeThongKhaoThiVaChamThiTuDongDaNgonNgu(AI-Powered)
├── /backend                    # FastAPI (Python)
│   ├── /app
│   │   ├── /api                # Router điều phối các API endpoint
│   │   ├── /core               # Cấu hình cài đặt (config.py), kết nối DB (database.py), Celery (celery.py)
│   │   ├── /models             # Các bảng cơ sở dữ liệu SQLAlchemy
│   │   ├── /schemas            # Pydantic schema xác thực dữ liệu
│   │   ├── /services           # Engine chấm thi AI (ai_grading.py) kết nối Gemini API
│   │   └── /workers            # Celery task chạy ngầm (tasks.py) xử lý chấm thi tự động
│   └── requirements.txt        # Các thư viện phụ thuộc của Python
│
├── /frontend                   # Next.js 15 (TypeScript, Tailwind CSS)
│   ├── /src
│   │   ├── /app                # Các trang giao diện (App Router)
│   │   └── /hooks              # Custom hooks xử lý ghi âm (useMediaRecorder.ts) & giám sát (useProctoring.ts)
```

---

## 2. Các phần việc Đã Hoàn Thành (Details of Completed Work)

### 2.1 Cấu hình Luật Hoạt động Agent & Git
* Tạo các file luật tự trị an toàn [.clinerules](file:///d:/Dat-Antigravity/HeThongKhaoThiVaChamThiTuDongDaNgonNgu(AI-Powered)/.clinerules) và [.cursorrules](file:///d:/Dat-Antigravity/HeThongKhaoThiVaChamThiTuDongDaNgonNgu(AI-Powered)/.cursorrules) ở thư mục gốc (giới hạn 5 lần sửa lỗi vòng lặp, commit cục bộ cho từng task, tự động rollback nếu gặp lỗi nặng).
* Liên kết Repository với GitHub: `https://github.com/KimDat2705/he-thong-khao-thi-va-cham-thi-tu-dong-da-ngon-ngu.git` ở nhánh chính `main`.

### 2.2 Backend (`/backend`)
* **Khung dự án FastAPI:** Thiết lập thành công luồng CORS và Endpoint sức khỏe tại [main.py](file:///d:/Dat-Antigravity/HeThongKhaoThiVaChamThiTuDongDaNgonNgu(AI-Powered)/backend/app/main.py).
* **Database Models (SQLAlchemy):** Tạo các model ánh xạ bảng dữ liệu chuẩn UTF-8 tránh lỗi font chữ tiếng Trung tại thư mục [models](file:///d:/Dat-Antigravity/HeThongKhaoThiVaChamThiTuDongDaNgonNgu(AI-Powered)/backend/app/models):
  * [user.py](file:///d:/Dat-Antigravity/HeThongKhaoThiVaChamThiTuDongDaNgonNgu(AI-Powered)/backend/app/models/user.py): Định nghĩa người dùng (admin, teacher, candidate).
  * [exam.py](file:///d:/Dat-Antigravity/HeThongKhaoThiVaChamThiTuDongDaNgonNgu(AI-Powered)/backend/app/models/exam.py): Lưu thông tin cấu hình kỳ thi (Anh/Trung, VSTEP/HSK).
  * [question.py](file:///d:/Dat-Antigravity/HeThongKhaoThiVaChamThiTuDongDaNgonNgu(AI-Powered)/backend/app/models/question.py): Thiết kế các dạng câu hỏi trắc nghiệm, viết essay hoặc nói ghi âm.
  * [submission.py](file:///d:/Dat-Antigravity/HeThongKhaoThiVaChamThiTuDongDaNgonNgu(AI-Powered)/backend/app/models/submission.py): Quản lý bài nộp và chi tiết câu trả lời/file ghi âm của học viên.
  * [grade.py](file:///d:/Dat-Antigravity/HeThongKhaoThiVaChamThiTuDongDaNgonNgu(AI-Powered)/backend/app/models/grade.py): Điểm số chi tiết và nhận xét JSON từ AI.
* **Celery & Redis Worker:** Thiết lập hệ thống xếp hàng chấm thi tự động tại [celery.py](file:///d:/Dat-Antigravity/HeThongKhaoThiVaChamThiTuDongDaNgonNgu(AI-Powered)/backend/app/core/celery.py) và [tasks.py](file:///d:/Dat-Antigravity/HeThongKhaoThiVaChamThiTuDongDaNgonNgu(AI-Powered)/backend/app/workers/tasks.py).
* **AI Grading Service:** Triển khai khung kết nối Gemini 1.5 Flash tại [ai_grading.py](file:///d:/Dat-Antigravity/HeThongKhaoThiVaChamThiTuDongDaNgonNgu(AI-Powered)/backend/app/services/ai_grading.py) phục vụ chấm điểm Viết và đọc/chấm phát âm file ghi âm bài Nói.

### 2.3 Frontend (`/frontend`)
* **Khung dự án Next.js:** Khởi tạo thành công với cấu trúc App Router, TypeScript và Tailwind CSS. Biên dịch thành công 100%.
* **Custom Proctoring Hook ([useProctoring.ts](file:///d:/Dat-Antigravity/HeThongKhaoThiVaChamThiTuDongDaNgonNgu(AI-Powered)/frontend/src/hooks/useProctoring.ts)):** Lắng nghe sự kiện chuyển tab (Visibility API), ép chế độ toàn màn hình (Fullscreen API), đếm số lần vi phạm và kích hoạt webcam giám sát thi sinh.
* **Custom Media Recorder Hook ([useMediaRecorder.ts](file:///d:/Dat-Antigravity/HeThongKhaoThiVaChamThiTuDongDaNgonNgu(AI-Powered)/frontend/src/hooks/useMediaRecorder.ts)):** Hỗ trợ ghi âm lời nói trực tiếp trên trình duyệt, tự động nén dữ liệu sang định dạng **Opus/WebM** hoặc **MP3** dung lượng nhẹ để hạn chế tối đa nghẽn mạng khi 500 thí sinh tải file lên đồng thời.

---

## 3. Định hướng Công việc Tiếp theo (Next Steps)

1. **Authentication API:** Tạo luồng đăng ký, đăng nhập và xác thực JWT token phục vụ phân quyền.
2. **Database Migration:** Cấu hình Alembic để khởi tạo các bảng dữ liệu PostgreSQL trên môi trường phát triển.
3. **Exam & Questions Administration API:** Phát triển các API CRUD cho giáo viên tạo đề thi và import câu hỏi HSK/VSTEP.
4. **Candidate Exam Room UI:** Thiết kế màn hình phòng thi cho thí sinh tại Frontend (tích hợp các Hook ghi âm và Proctoring chống gian lận).
5. **AI Grading Prompt Engineering:** Tối ưu hóa prompt chấm thi trên Gemini API để đạt độ chính xác >90% theo quy chuẩn.
6. **Celery Worker Integration:** Test tích hợp luồng nộp bài -> Đẩy hàng đợi Celery -> Chấm điểm bằng Gemini -> Ghi nhận kết quả.
7. **Load Testing:** Thực hiện kiểm thử tải giả lập 500 candidate nộp file audio đồng thời.
