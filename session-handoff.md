# Session Handoff — cập nhật 14/06/2026 (Claude, sau khi nghiệm thu + merge B1 & A1 — XONG GENERATOR HARDENING + PARSER CORE)

## Current State & Achievements

1. **Kiến trúc đã chốt**: `docs/kien_truc_he_thong_v2.html` (tổng thể) + `docs/kien_truc_phan_he_ra_de_tieng_anh.html/.md` (phân hệ Ra đề EN — trọng tâm M2). Tài liệu v1 `system_architecture.html` đông lạnh làm tham chiếu.
2. **Harness hoạt động**: 23 spec trong `specs/specs.json` (**14 active / 5 gap / 4 planned** sau A1) ↔ 7 file test; suite hiện tại **21 passed / 3 skipped / 5 xfailed / 0 failed**; meta-test traceability 2 chiều xanh; `scripts/check-architecture.sh` PASS.
3. **SETUP CHUNG (0a + 0b + 0c) ĐÃ XONG**: 0a (`2cd7988`) PR template + labels/milestone/issues; 0b (PR #15 → `1e139c2`) CI + ruff + pytest-cov; 0c (PR #16 → `0c265c9`) Alembic foundation, `alembic upgrade head` chạy thật trên PostgreSQL 17. **MODELS ĐÓNG BĂNG từ 0c.**
4. **B1 (`feat/generator-hardening`) ĐÃ XONG** — commit `45ccd09` (CHƯA push). Thắt chặt `toeic_generator.py`: filter `status=="approved"` (BANK-001); `InsufficientBankError` + pre-check tồn kho trước khi tạo Exam (GEN-006); `seed` cô lập qua `local_random` + `.order_by(id)` (GEN-005); ghi `source_question_id` (nền GEN-004/B6); SQLAlchemy 2.0 + gỡ E711. Greedy Part 7 GIỮ NGUYÊN (52 câu) → GEN-001 vẫn `gap`.
5. **A1 (`feat/parser-core`) ĐÃ XONG** — commit `fe11fa3` (CHƯA push). File mới `backend/app/services/parser.py`:
   - `import_file(db, filepath)` parse `.docx` (python-docx) → block `[Group]`/`[Question]` → validation gate → lưu nguyên tử qua `ImportBatch` → idempotent qua `content_hash` (bank exam_id IS NULL) → item `status="draft"`.
   - Exception `ImportError(.report)` đúng hợp đồng test; validate fail → raise TRƯỚC khi tạo batch (all-or-nothing).
   - **PARSE-001 / 003 / 004 → active**. `requirements.txt` thêm `python-docx`; fixtures `.docx`/`.mp3` sinh tự động qua fixture `autouse` trong `test_specs_parser.py` (CI tự sinh; `tests/fixtures/parser/` đã gitignore).
6. **Hạ tầng máy Đạt**: PostgreSQL 17 cài tại `D:\Postgres\17` (port 5432, user postgres). Bản 15 cũ đã hỏng/gỡ. `psql`/`createdb` tại `D:\Postgres\17\bin\` (chưa vào PATH).
7. **Giao thức làm việc đã ổn định**: Anti nộp plan từng việc → Đạt gửi Claude review → Đạt gõ `DUYỆT <mã việc>` (machine-checkable) → Anti code nhánh riêng → Claude nghiệm thu độc lập (diff + ranh giới file + ruff + pytest ×2) → merge fast-forward vào `Dat`. Bí mật (token/password) do Đạt tự chạy, không vào chat/file/commit.
   - ⚠️ **Ranh giới file**: `claude-progress.md` + `session-handoff.md` là **Claude ghi**, KHÔNG phải Anti. Quy tắc đã chốt với Anti: chỉ sửa file liệt kê trong "Proposed Changes" của plan; nhật ký thực thi để trong `task.md`/`walkthrough.md` workspace riêng. (A1 Anti đã tuân thủ đúng.)

## Current Gaps / In Progress

- **Parser Engine (đang dở)**: lõi `.docx` xong (PARSE-001/003/004 active). CÒN: PARSE-002 (mapping MP3 — skip, chờ quy ước tên file đối tác → CHẶN A2), parse Excel đáp án, convert `.doc`→`.docx` cho bộ Reading (RT26xx.doc). Feature `docx-parser` = `in_progress`.
- **Generator — gap còn lại (xfail)**: SPEC-GEN-001 (Part 7 = 52/54 câu), SPEC-MATRIX-002 toàn-đề (tỷ lệ 25/50/25), SPEC-GEN-002 (cân bằng đáp án A/B/C/D), SPEC-GEN-003 (đa dạng topic). SPEC-GEN-004 (độ trùng giữa đề, `planned`) — cột `source_question_id` đã sẵn sàng từ B1, chờ B6.
- ⚠️ **BẪY FIXTURE cho B2/B3 (cực kỳ quan trọng — đừng gỡ xfail trước khi sửa)**: `tests/conftest.py` tạo Part 7 = **15 nhóm TOÀN 4 câu** (mọi tổ hợp là bội số của 4 → KHÔNG ráp được đúng 54; greedy chỉ đạt 52) và **topic đơn điệu** (P7 toàn "Article", P3 "Meetings", P4 "Talk"). Gỡ xfail cho GEN-001/GEN-002/GEN-003 **CẦN một PR mở rộng `conftest.py` được Đạt duyệt TRƯỚC** (thêm nhóm P7 số câu đa dạng 2-5, đa dạng topic).
- **CI chưa test migration**: `ci.yml` chỉ chạy pytest trên SQLite — KHÔNG bắt lỗi migration PG-specific. Cân nhắc thêm postgres service vào CI sau.
- **Celery chưa nối API** (SPEC-GRADE-003) + SPEC-GRADE-002 (tên trường điểm) — thuộc milestone Chấm, NGOÀI phạm vi M2.
- **Chờ bên ngoài**: quy ước tên file MP3 với đối tác (CHẶN A2 + PARSE-002); sếp xác nhận quy đổi độ khó câu→nhóm (±1 trong dung sai ±2).

## Next Session Objectives

1. **Push `Dat` lên `origin`** (3 commit local: `45ccd09` B1, `d07f345` harness, `fe11fa3` A1).
2. **Việc tiếp theo**: A3/A4 (parser nâng cao, KHÔNG chờ MP3) hoặc Generator B2-B6 (nhưng B2/B3 cần PR conftest trước — xem bẫy fixture). A2 CHẶN tới khi có quy ước MP3.
3. Quy trình mỗi việc giữ nguyên: plan → Claude review → `DUYỆT <mã việc>` → code nhánh riêng → Claude nghiệm thu → merge. KHÔNG đụng `backend/app/models/` (đóng băng), không đụng phân hệ Chấm, không đụng `claude-progress.md`/`session-handoff.md`.
4. Bổ sung hạ tầng (khi rảnh): thêm postgres service vào `ci.yml`; bật "Require status checks" cho `main` nếu repo chuyển public/nâng gói.
5. Chờ bên ngoài: quy ước tên file MP3 (chặn A2/PARSE-002); sếp xác nhận quy đổi độ khó câu→nhóm.
