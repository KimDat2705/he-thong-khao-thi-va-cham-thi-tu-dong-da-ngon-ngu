# Session Handoff — cập nhật 14/06/2026 (Claude, sau khi nghiệm thu + merge B1 + A1 + A2 + B2 — đề TOEIC đủ 200 câu)

## Current State & Achievements

1. **Kiến trúc đã chốt**: `docs/kien_truc_he_thong_v2.html` (tổng thể) + `docs/kien_truc_phan_he_ra_de_tieng_anh.html/.md` (phân hệ Ra đề EN — trọng tâm M2). Tài liệu v1 `system_architecture.html` đông lạnh làm tham chiếu.
2. **Harness hoạt động**: 23 spec trong `specs/specs.json` (**16 active / 4 gap / 3 planned** sau B2) ↔ 7 file test; suite hiện tại **23 passed / 2 skipped / 4 xfailed / 0 failed**; meta-test traceability 2 chiều xanh; `scripts/check-architecture.sh` PASS.
3. **SETUP CHUNG (0a + 0b + 0c) ĐÃ XONG**: 0a (`2cd7988`) PR template + labels/milestone/issues; 0b (PR #15 → `1e139c2`) CI + ruff + pytest-cov; 0c (PR #16 → `0c265c9`) Alembic foundation, `alembic upgrade head` chạy thật trên PostgreSQL 17. **MODELS ĐÓNG BĂNG từ 0c.**
4. **B1 (`feat/generator-hardening`, `45ccd09`)**: `toeic_generator.py` — filter `status=="approved"` (BANK-001); `InsufficientBankError` + pre-check tồn kho trước khi tạo Exam (GEN-006); `seed` cô lập qua `local_random` + `.order_by(id)` (GEN-005); ghi `source_question_id` (nền GEN-004/B6); SQLAlchemy 2.0 + gỡ E711.
5. **A1 (`feat/parser-core`, `fe11fa3`)**: `backend/app/services/parser.py` — `import_file` parse `.docx` → validation gate → lưu nguyên tử qua `ImportBatch` → idempotent qua `content_hash` → item `status="draft"`. `ImportError(.report)`, raise trước batch (all-or-nothing). **PARSE-001/003/004 active**. `python-docx` vào requirements; fixtures `.docx`/`.mp3` sinh tự động qua fixture `autouse` (`tests/fixtures/parser/` gitignore).
6. **A2 (`feat/parser-audio`, `c019be0`)**: `parser.py` — `import_file(db, filepath, audio_dir=None)`; kiểm tồn tại file audio cho block Listening (Part 1-4) có trường Audio, trong validation phase → all-or-nothing; thiếu → `ImportError` chứa "MP3". **PARSE-002 active**. Quy ước tên MP3 (quyết định NỘI BỘ): `{SetID}_P{Part}_{NN}.mp3` (per-câu P1/P2, per-nhóm P3/P4) — parser kiểm TỒN TẠI theo trường `Audio`.
7. **B2 (`feat/generator-part7`, `977d4d0`)**: `toeic_generator.py` — thay greedy Part 7 (52 câu) bằng **subset-sum backtracking** tìm tổ hợp nhóm tổng ĐÚNG 54 câu; trộn bằng `local_random.shuffle` (sau `.order_by(id)`) → tái lập theo seed; không có tổ hợp → `InsufficientBankError`. **Đề TOEIC giờ đủ 200 câu. SPEC-GEN-001 active.** Đã mở rộng `conftest.py` Part 7 sang nhóm 2/3/4/5 câu (tổng 60); Part 1-6 giữ nguyên.
8. **Hạ tầng máy Đạt**: PostgreSQL 17 cài tại `D:\Postgres\17` (port 5432, user postgres). Bản 15 cũ đã hỏng/gỡ. `psql`/`createdb` tại `D:\Postgres\17\bin\` (chưa vào PATH).
9. **Đồng bộ git**: `origin/Dat` @ `977d4d0` (B1+A1+A2+B2 + harness đều đã push). Nhánh feature đã merge được xoá sau mỗi việc. Working tree sạch.
10. **Giao thức làm việc đã ổn định**: Anti nộp plan từng việc → Đạt gửi Claude review → Đạt gõ `DUYỆT <mã việc>` (machine-checkable) → Anti code nhánh riêng → Claude nghiệm thu độc lập (diff + ranh giới file + ruff + pytest ×2) → merge fast-forward vào `Dat` → push.
    - ⚠️ **Ranh giới file**: `claude-progress.md` + `session-handoff.md` là **Claude ghi**, KHÔNG phải Anti. Anti chỉ sửa file trong "Proposed Changes"; nhật ký để trong `task.md`/`walkthrough.md` riêng. (A1/A2/B2 Anti tuân thủ đúng.)

## Current Gaps / In Progress

- **Generator — gap còn lại (xfail)**: SPEC-GEN-002 (cân bằng đáp án A/B/C/D 20-28%), SPEC-GEN-003 (đa dạng topic ≤20%/part), SPEC-MATRIX-002 toàn-đề (tỷ lệ 25/50/25). SPEC-GEN-004 (độ trùng giữa đề, `planned`) — cột `source_question_id` đã sẵn từ B1, chờ B6.
- ⚠️ **BẪY FIXTURE còn lại cho B3 (chưa xử lý)**: `tests/conftest.py` hiện **topic đơn điệu** (P7 toàn "Article", P3 "Meetings", P4 "Talk") + **đáp án skewed** (P3 toàn "D", P5 toàn "C", P6 toàn "A"...). Gỡ xfail GEN-002/GEN-003 **CẦN mở rộng conftest (đa dạng topic + đáp án), KHAI BÁO trong plan và được duyệt**. (Phần Part 7 size đã xử lý xong ở B2.)
- **Parser**: lõi `.docx` + audio xong (PARSE-001/002/003/004 active). CÒN: parse **Excel đáp án**, convert `.doc`→`.docx` cho bộ Reading (RT26xx.doc). Hardening PARSE-002 (bắt buộc Audio present) tuỳ chọn. Feature `docx-parser` = `in_progress`.
- **CI chưa test migration**: `ci.yml` chỉ chạy pytest SQLite — không bắt lỗi migration PG-specific. Cân nhắc thêm postgres service.
- **Celery chưa nối API** (SPEC-GRADE-003) + SPEC-GRADE-002 (tên trường điểm) — milestone Chấm, NGOÀI phạm vi M2.
- **Chờ bên ngoài**: chỉ còn **sếp xác nhận quy đổi độ khó câu→nhóm** (±1 trong dung sai ±2). *(Quy ước MP3 đã chốt nội bộ — KHÔNG chờ đối tác.)*

## Next Session Objectives

1. **Việc tiếp theo**: **B3 (GEN-002 + GEN-003)** hoặc A3/A4 (parser: Excel, `.doc`→`.docx`). B3 cần mở rộng conftest (đa dạng topic + đáp án) — khai báo trong plan.
2. Quy trình mỗi việc giữ nguyên: plan → Claude review → `DUYỆT <mã việc>` → code nhánh riêng → Claude nghiệm thu → merge → push. KHÔNG đụng `backend/app/models/` (đóng băng), không đụng phân hệ Chấm, không đụng `claude-progress.md`/`session-handoff.md`.
3. Bổ sung hạ tầng (khi rảnh): postgres service vào `ci.yml`; "Require status checks" cho `main` nếu repo public/nâng gói; hardening PARSE-002.
4. Chờ sếp xác nhận quy đổi độ khó câu→nhóm.
