# Deploy demo TOEIC lên Cloud (Render + Vercel) — free, không cần CLI

Kiến trúc: **Backend FastAPI → Render**, **Frontend Next.js → Vercel**. Backend tự tải
dữ liệu đối tác (đề/đáp án/audio) từ Google Drive lúc build rồi seed — **repo KHÔNG chứa
dữ liệu đối tác**. Code đã ở GitHub nhánh `main`.

> Vì sao cần bạn: Render/Vercel deploy từ GitHub qua tài khoản của bạn (đăng nhập bằng
> chính GitHub). Claude không có credentials nên không tự đăng nhập thay được. Mọi cấu hình
> đã chuẩn bị sẵn trong repo (`render.yaml`, env-based config); bạn chỉ cần bấm theo các bước.

---

## A. Backend lên Render (làm trước để lấy URL)

1. Vào https://render.com → **Sign in with GitHub** (cho phép truy cập repo
   `he-thong-khao-thi-va-cham-thi-tu-dong-da-ngon-ngu`).
2. **New +** → **Blueprint** → chọn repo trên → Render đọc `render.yaml` → **Apply**.
   - (Nếu không dùng Blueprint: **New + → Web Service** → chọn repo → Root Directory = `backend`,
     Runtime = Python, Build = `pip install -r requirements.txt && python scripts/cloud_bootstrap.py`,
     Start = `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, Plan = Free.)
3. Chờ build (lần đầu lâu hơn: cài deps + tải audio ~105MB + seed). Khi xong, copy URL dạng
   `https://toeic-backend-xxxx.onrender.com`.
4. Kiểm tra: mở `<URL>/health` (phải trả `{"status":"healthy"}`) và `<URL>/api/v1/exams`
   (phải thấy đề demo).

> Lưu ý gói Free: dịch vụ "ngủ" sau ~15 phút không dùng → lần mở kế tiếp chờ ~30–60s khởi động lại.
> Trước khi trình sếp, mở `<URL>/health` 1 lần để đánh thức.

## B. Frontend lên Vercel

1. Vào https://vercel.com → **Sign in with GitHub** → **Add New… → Project** → chọn repo.
2. **Root Directory** = `frontend` (bấm Edit để chọn). Framework tự nhận **Next.js**.
3. **Environment Variables** → thêm:
   - `NEXT_PUBLIC_API_BASE` = URL backend Render ở bước A (vd `https://toeic-backend-xxxx.onrender.com`)
4. **Deploy**. Khi xong được URL dạng `https://xxx.vercel.app`.

## C. Nối CORS (backend cho phép frontend)

1. Quay lại Render → service backend → **Environment** → sửa `ALLOWED_ORIGINS` =
   URL Vercel (vd `https://xxx.vercel.app`) → **Save** (backend tự deploy lại).
2. Mở `https://xxx.vercel.app` → **Vào trang quản trị** → **Sinh đề** → **Xem đề**. Xong.

---

## Kiểm thử sau deploy (checklist)
- `<backend>/health` = healthy; `<backend>/api/v1/exams` có đề.
- `<backend>/static/img/LT2601/q1.png` mở được (ảnh Part 1).
- Trang Vercel: /admin hiện tồn kho 7 part "đủ"; nút Sinh đề tạo đề mới; /exam/[id] hiện
  ảnh Part 1 + player audio; mặc định ẩn đáp án; nút "Hiện đáp án" hoạt động.

## Ghi chú
- Đổi đề khác: sửa file id trong `backend/scripts/cloud_bootstrap.py` (FILES + AUDIO_FILE).
- Muốn dùng PostgreSQL thay SQLite: đặt `DATABASE_URL` = chuỗi Postgres của Render (tạo Render
  PostgreSQL free) — schema tự tạo qua `create_all()`.
- Nâng độ ổn định (không "ngủ"): nâng plan Render, hoặc thêm cron ping `/health`.
