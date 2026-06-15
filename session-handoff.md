# Session Handoff — cập nhật 15/06/2026 (Claude, sau DEMO TOEIC end-to-end — API + giao diện trên dữ liệu thật)

## Current State & Achievements

1. **Kiến trúc đã chốt**: `docs/kien_truc_he_thong_v2.html` (tổng thể) + `docs/kien_truc_phan_he_ra_de_tieng_anh.html/.md` (phân hệ Ra đề EN — trọng tâm M2). Tài liệu v1 đông lạnh tham chiếu.
2. **Harness hoạt động**: **33 spec** trong `specs/specs.json` (**28 active / 2 gap / 3 planned** sau demo) ↔ 8 file test; suite **35 passed / 2 skipped / 2 xfailed / 0 failed**; meta-test traceability xanh; `scripts/check-architecture.sh` PASS. **Baseline 15/06: `origin/Dat` @ `44f638b` (DEMO TOEIC) + commit harness Session 22, clean-state toàn xanh.**
3. **DỮ LIỆU INPUT THẬT đã đọc được** (`docs/du_lieu_input_links.md`): tải bằng `PYTHONUTF8=1 python -m gdown` về `D:\Dat-Antigravity\drive_input\` (ngoài repo) + parse openpyxl/python-docx; Sheet→export xlsx; bỏ MP3. Ma trận TOEIC (Sheet) XÁC NHẬN blueprint + luật ta đã code. Đáp án=xlsx lưới Câu/Đáp án; đề=Word tables+ảnh (đã map cấu trúc).
4. **Real Parser Track (PARSE-006 → 011) — 🎉 HOÀN TẤT (Nghe+Đọc · đề+đáp án+audio → bank, dữ liệu đối tác thật)**:
   - **A3 (`d2388e8`)**: `parse_answer_key(filepath)->dict[int,str]` (openpyxl, quét header, gộp 5 block).
   - **PARSE-006 (`8239a88` + `c65eb57`)**: `parse_listening_docx(filepath)->{set_id, items}` — bóc tách table-based `.docx` theo document order, split nhóm P3/P4 bằng line `---` trong cell, ghép wrap option/câu qua nhiều paragraph (state-machine), P1 ghi image index.
   - **PARSE-007 (`c8948fa` + vá `a6fdf99`)**: `import_listening_set(db, docx_path, key_path, audio_dir=None)` — trộn đáp án từ tệp Excel vào câu hỏi Word theo số câu, validation gate (all-or-nothing), set_id docx khớp KEY, lưu ImportBatch và commit ngân hàng ở trạng thái `draft` (save bọc try/except + rollback).
   - **Bug Question Hash Collision — Claude bắt lúc nghiệm thu trên dữ liệu THẬT**: fixture xanh nhưng `import_listening_set` trên cặp thật LT2601 chỉ ghi 75/100 câu (P1/P2 content giống nhau + options rỗng → trùng hash → nuốt 25 câu). Vá: đưa `set_id`+`number` vào `calculate_question_hash`, `set_id` vào `calculate_group_hash` (path cũ → None → tương thích ngược). **Claude verify lại file thật: 100/100 câu + 23/23 nhóm, 0 skip, idempotent ✓.** Bài học: pytest fixture xanh KHÔNG đủ — verify file thật là bắt buộc.
   - **PARSE-008 (`cfd5431`)**: `convert_doc_to_docx(filepath, out_dir=None)` — `.doc` legacy → `.docx` qua LibreOffice headless (passthrough/cache/missing-tool error). Verify thật: round-trip giữ 15 tables (cần LibreOffice; Đạt đã cài 26.2).
   - **PARSE-009 (`4668e44` + vá `0712a8a`)**: `parse_reading_docx(filepath)->{set_id, items}` — Reading parse-only, số câu 1-100 (P5 đơn / P6 4-blank / P7 passage đơn-đôi-ba + ảnh). Option extraction chắc (inline-A, all-inline `re.DOTALL`+split, sandwich, 4x2 table). **2 bug Claude bắt lúc nghiệm thu** (treo vô hạn ở inner loop + mất options 30/70 câu) — đã vá. Verify RT2605 thật: **100 câu / 0 thiếu options**.
   - **PARSE-010 (`e2941f3`)**: tổng quát `import_listening_set` → `import_exam_set(db, docx_path, key_path, exam_type, audio_dir=None)` (dispatch parser theo exam_type + set_id `(LT|RT)`); `import_listening_set`/`import_reading_set` là wrapper mỏng. **Verify dữ liệu THẬT (Claude)**: LT2601→100 câu/23 nhóm, RT2605→100 câu/20 nhóm, idempotent; LT+RT coexist 1 DB = **200 câu/43 nhóm/0 thiếu đáp án**. 🏗️ pipeline Parser thật ĐỦ Nghe+Đọc→bank.
   - **PARSE-011 (`ef2ced4`)**: `find_audio_file` + `import_exam_set` link MP3 gộp vào `audio_url` **cấp FILE** (dải/đơn, anchored regex, non-fatal, report `audio_ambiguous`). **KHÔNG cắt** (quyết định Đạt: ma trận không yêu cầu, đối tác không có timestamp, models đóng băng). Verify 15 tên file THẬT: 15/15 set map được, chỉ LT2603/LT2605 ambiguous (3 file đầu đè dải). 🎉 **Track Parser HOÀN TẤT** — `feature_list.docx-parser` → active.
4c. **DEMO TOEIC end-to-end — XONG (`44f638b`, SPEC-EXAM-001 active) — TOEIC chạy được CÓ GIAO DIỆN trên dữ liệu thật**:
   - **Backend Exam API**: `app/api/exams.py` + `app/services/exam_admin.py` + `app/schemas/exam.py` — `POST /api/v1/exams/generate`, `GET /api/v1/exams`, `GET /api/v1/exams/{id}` (đề theo part → standalone/groups → questions + options/audio/ảnh). `main.py` mount `/audio` (tùy chọn `AUDIO_DIR`). Test `tests/test_specs_exam.py` (TestClient, 200 câu).
   - **Seed `scripts/seed_toeic_demo.py`**: import THẬT LT2601+RT2605 → **backfill độ khó/topic khớp blueprint** (CHỐT CHẶN là TOPIC: parser gán all medium/None; generator đòi đa dạng topic — độ khó tự shortfall-fill) → approve 200 → sinh đề. DB demo SQLite gitignored.
   - **Frontend (Next.js 16, `params` async)**: `/` landing, `/admin` (stats + sinh đề + list), `/exam/[id]` (xem đề, đáp án tô xanh). API client `src/lib/api.ts`.
   - **Verify trình duyệt trên dữ liệu THẬT**: sinh đề từ UI (count 1→2), xem 200 câu thật (Part 5 câu + 4 options + đáp án). Console 0 lỗi. Audio/ảnh chưa bật (MP3 chưa tải/ảnh chưa trích — non-blocking). Hướng dẫn: `docs/demo_toeic_huong_dan.md`.
   - **Cách chạy nhanh**: seed (`DATABASE_URL=sqlite:///./demo_toeic.db python scripts/seed_toeic_demo.py`) → uvicorn cùng DATABASE_URL :8000 → `cd frontend && npm run dev` :3000.
4b. **A5 Bank-Admin API — XONG (`696201e`, SPEC-BANK-003 active) — router REST ĐẦU TIÊN của dự án** (`app/api/` + `app/schemas/` trước đó rỗng):
   - `app/api/bank.py` prefix `/api/v1/bank`: `GET /questions` (filter part/status/topic/difficulty + phân trang, chỉ `exam_id IS NULL`), `PATCH /questions/{id}` (sửa bank item; 404 cho clone `exam_id IS NOT NULL` / không tồn tại), `POST /questions/approve` (bulk draft→approved + **propagate nhóm cha**), `GET /stats` (đếm part×status đối chiếu `TOEIC_BLUEPRINT`).
   - `app/services/bank_admin.py` logic thuần (API mỏng) + `app/schemas/bank.py` Pydantic v2. Endpoints CHƯA auth (auth-api not_started) — có TODO marker.
   - **Propagate nhóm cha là bắt buộc**: parser ghi cả Question lẫn QuestionGroup `status="draft"`; generator lọc CẢ HAI `==approved`. Test SPEC-BANK-003 non-tautological (stats trước seed → seed 2 draft → filter/approve → chứng minh lật nhóm cha). Nghiệm thu: 34/2/2 ×2, ruff/architecture/traceability xanh, no dep mới.
   - **conftest đổi `StaticPool`** (cần cho `:memory:` cross-thread dưới TestClient — verify thực nghiệm bỏ ra thì gãy). `feature_list.exam-admin-api` → in_progress (còn Exam CRUD + auth).
5. **SETUP (0a+0b+0c) XONG**: 0a (`2cd7988`); 0b (PR #15 → `1e139c2`) CI+ruff+pytest-cov; 0c (PR #16 → `0c265c9`) Alembic, chạy thật trên PostgreSQL 17. **MODELS ĐÓNG BĂNG từ 0c.**
6. **Pipeline Ra đề EN (B1+B2+B3+GEN-002) — generator gần hoàn chỉnh**:
   - **B1 (`45ccd09`)**: filter `approved` (BANK-001), `InsufficientBankError` + pre-check (GEN-006), `seed` qua `local_random`+`.order_by(id)` (GEN-005), `source_question_id`.
   - **B2 (`977d4d0`)**: Part 7 subset-sum đúng 54 → đề đủ 200 (GEN-001).
   - **B3 (`3c7be1f`)**: đa dạng topic, cap thích ứng `max(0.20, nhóm_lớn_nhất/tổng)` (GEN-003).
   - **GEN-002 (`ca2ce48`)**: cân bằng đáp án A/B/C/D 20-28% qua hoán vị clone.
   - → Đề sinh ra: đúng 200 câu · ma trận độ khó per-part · đa dạng topic · cân bằng đáp án · tái lập theo seed · chỉ câu approved · bank bất biến.
7. **Hạ tầng máy Đạt**: PostgreSQL 17 tại `D:\Postgres\17` (port 5432, user postgres). `psql`/`createdb` tại `D:\Postgres\17\bin\` (chưa vào PATH).
8. **Đồng bộ git**: `origin/Dat` @ `44f638b` (DEMO TOEIC merged) + commit chốt sổ Session 22. Nhánh `feat/toeic-demo` + `feat/bank-admin-api` + `feat/parser-audio-link` đều đã xoá. Working tree sạch. Demo dùng `feat`-flow như cũ; phiên này Claude code trực tiếp (Đạt chốt, vì deadline demo).

## Current Gaps / In Progress

- **Generator — chỉ còn 2 hạng mục**:
  - **SPEC-MATRIX-002 toàn-đề (gap/xfail)**: tỷ lệ độ khó 25/50/25 toàn đề. ⚠️ **Giờ VƯỚNG**: sau B3, P7 có nghiệm subset-sum DUY NHẤT → độ khó P7 cố định (4E/30M/20H) → toàn đề lệch (Easy=39<45, Hard=56>55). Cần **rebalance conftest P7 difficulty** (giữ topic+size đã chốt ở B2/B3) hoặc nới nghiệm P7. Task này sửa conftest rất cẩn thận.
  - **SPEC-GEN-004 (planned, B6)**: độ trùng giữa các đề trong lô ≤40% — `source_question_id` đã sẵn từ B1; cần API/đường dẫn generate LÔ nhiều đề rồi so source giữa các cặp.
- ✅ **Parser track HOÀN TẤT (PARSE-006→011)**: parse Nghe/Đọc + convert `.doc` (LibreOffice) + merge+import chung (`import_exam_set`) + link audio cấp file. Verify dữ liệu đối tác thật (LT2601 + RT2605 = 200 câu + audio vào bank, idempotent, coexist). Audio để CẢ FILE (không cắt — quyết định Đạt); tuỳ chọn tương lai: segment theo đoạn nếu tầng thi cần.
- ⚠️ **FIXTURE conftest RẤT NHẠY (bảo trì)** — KHÔNG "dọn" thành đơn giản:
  - **Part 7**: topic+size có **nghiệm subset-sum DUY NHẤT** (loại G2+G3). Sửa phải verify lại (chứng minh trong commit `3c7be1f`).
  - **Part 4**: 3 nhóm medium "Talk" (chủ ý để GEN-003 test không tautology).
- **CI chưa test migration** (SQLite). **Celery chưa nối API** (GRADE-003) + GRADE-002 — milestone Chấm, NGOÀI M2.
- **Chờ bên ngoài**: chỉ còn **sếp xác nhận quy đổi độ khó câu→nhóm**. *(Quy ước MP3 đã chốt nội bộ.)*

## Next Session Objectives

1. **Lộ trình tiếp theo — ưu tiên đánh bóng DEMO TOEIC (nếu sếp cần)**:
   - **Audio**: tải MP3 gộp → seed+backend với `AUDIO_DIR` → player phát trong `/exam/[id]`.
   - **Ảnh Part 1/7**: trích ảnh từ `.docx` ra file tĩnh + set `image_url` thật.
   - **auth-api**: bịt endpoint bank + exams (đang mở, chỉ TODO marker).
   - **A6 UI duyệt bank**: approve draft→approved trên web.
   - 💡 Đối chiếu `TOEIC_BLUEPRINT` ↔ Ma trận TOEIC Sheet thật → cập nhật data.
   - **Để sau (giữ nguyên)**: B1/VSTEP·HSK; phân hệ Chấm; generator gaps (MATRIX-002 vướng P7, GEN-004); SCALE.
2. Quy trình giữ nguyên: plan → Claude review → `DUYỆT <mã>` → code nhánh riêng → **Claude nghiệm thu XONG mới push** → merge. KHÔNG đụng `backend/app/models/`, phân hệ Chấm, `claude-progress.md`/`session-handoff.md`. ⚠️ Phiên PARSE-007 Anti lại (a) push trước khi Claude nghiệm thu, (b) tự sửa 2 file nhật ký của Claude — nhắc giữ đúng ranh giới lần sau.
3. Hạ tầng (khi rảnh): postgres service vào `ci.yml`; "Require status checks" cho `main`; hardening PARSE-002.
4. Chờ sếp xác nhận quy đổi độ khó câu→nhóm.
