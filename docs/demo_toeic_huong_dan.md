# Hướng dẫn chạy DEMO TOEIC (end-to-end)

Demo: nạp đề THẬT (LT2601 + RT2605) → ngân hàng câu hỏi → sinh đề TOEIC 200 câu → xem đề trên giao diện.

Pipeline: parse `.docx` + đáp án `.xlsx` → bank (draft) → backfill độ khó/topic → duyệt (approved) → `generate_toeic_exam` → API → frontend.

## Yêu cầu
- Python (đã cài deps backend: `pip install -r backend/requirements.txt`).
- Node.js + đã `npm install` trong `frontend/`.
- Dữ liệu thật ở `D:\Dat-Antigravity\drive_input` (đổi qua biến `DRIVE_INPUT` nếu khác).

## Bước 1 — Seed dữ liệu thật vào DB demo (SQLite)

Git Bash:
```bash
cd backend
DATABASE_URL="sqlite:///./demo_toeic.db" PYTHONUTF8=1 python scripts/seed_toeic_demo.py
```
PowerShell:
```powershell
cd backend
$env:DATABASE_URL="sqlite:///./demo_toeic.db"; $env:PYTHONUTF8="1"; python scripts/seed_toeic_demo.py
```
Kết quả mong đợi: import LT2601 + RT2605 → backfill → "Approved 200 questions" → bank đủ 7 part → "Generated demo exam ... 200 questions".

## Bước 2 — Chạy backend (đọc đúng DB demo)

Git Bash:
```bash
cd backend
DATABASE_URL="sqlite:///./demo_toeic.db" python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
PowerShell:
```powershell
cd backend
$env:DATABASE_URL="sqlite:///./demo_toeic.db"; python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
Kiểm tra: http://127.0.0.1:8000/api/v1/exams (phải thấy đề demo).

## Bước 3 — Chạy frontend

```bash
cd frontend
npm run dev
```
Mở http://localhost:3000 → bấm **Vào trang quản trị** → **Sinh đề TOEIC mới** → **Xem đề**.

> Nếu backend không ở `localhost:8000`, đặt `NEXT_PUBLIC_API_BASE` (vd tạo `frontend/.env.local` với `NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000`).

## Các API chính (backend)
- `POST /api/v1/exams/generate` — sinh đề TOEIC 200 câu từ bank approved.
- `GET  /api/v1/exams` — danh sách đề đã sinh.
- `GET  /api/v1/exams/{id}` — đề đầy đủ theo part (câu, options, đáp án, audio, ảnh).
- `GET  /api/v1/bank/stats` — tồn kho bank đối chiếu blueprint.
- `GET/PATCH/POST /api/v1/bank/...` — quản trị/duyệt ngân hàng (A5).

## Audio (bài Nghe) — đầy đủ như đề thật

File MP3 gộp theo dải. Audio của LT2601 nằm trong file **"2601 - 2604.mp3"** (~105MB). Tải về `drive_input/audio/`:
```bash
cd D:\Dat-Antigravity
python -m gdown --id 15HV-VVmh6YZMRn-K1DxgFtBSIkOsL2Jc -O "drive_input/audio/2601 - 2604.mp3"
```
Rồi seed + chạy backend với `AUDIO_DIR` trỏ vào thư mục đó:
```bash
cd backend
# seed:
AUDIO_DIR="D:\Dat-Antigravity\drive_input\audio" DATABASE_URL="sqlite:///./demo_toeic.db" PYTHONUTF8=1 python scripts/seed_toeic_demo.py
# backend:
AUDIO_DIR="D:\Dat-Antigravity\drive_input\audio" DATABASE_URL="sqlite:///./demo_toeic.db" python -m uvicorn app.main:app --port 8000
```
Backend mount `/audio`; trang xem đề hiện 1 trình phát cho mỗi part Nghe (audio gộp ~45 phút, KHÔNG cắt — theo quyết định dự án).

## Ghi chú demo
- **Nội dung thật**: câu hỏi lấy từ bộ đề đối tác LT2601 (Nghe) + RT2605 (Đọc).
- **Ảnh Part 1**: seed tự **trích ảnh** từ `.docx` (`app/services/docx_images.py`) ra `backend/static/` và link vào câu → hiện ảnh thật. (Đồ hoạ Part 3/4/7 chưa map per-câu — bước sau.)
- **Đáp án**: ĐỀ MẶC ĐỊNH ẨN ĐÁP ÁN (chế độ thí sinh). Nút **"Hiện đáp án (giáo viên)"** ở trang xem đề bật chế độ giáo viên (gọi API `?include_answers=true`). API thí sinh KHÔNG trả đáp án.
- **Backfill độ khó/topic**: parser thật gán mọi câu `medium`/`topic=None`; seed backfill khớp ma trận blueprint để generator chạy được (production: dùng metadata thật từ đối tác/ma trận).
- DB demo `backend/demo_toeic.db` + `backend/static/` đã gitignore (không commit).
