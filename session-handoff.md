# Session Handoff — cập nhật 13/06/2026 (Claude, sau khi hoàn thành 0a + 0b + 0c — XONG SETUP)

## Current State & Achievements

1. **Kiến trúc đã chốt**: `docs/kien_truc_he_thong_v2.html` (tổng thể) + `docs/kien_truc_phan_he_ra_de_tieng_anh.html/.md` (phân hệ Ra đề EN — trọng tâm M2). Tài liệu v1 `system_architecture.html` đông lạnh làm tham chiếu.
2. **Harness hoạt động**: 23 spec trong `specs/specs.json` (8 active / 7 gap / 8 planned) ↔ 7 file test; suite baseline **15 passed / 7 skipped / 7 xfailed / 0 failed**; meta-test traceability 2 chiều xanh; `scripts/check-architecture.sh` PASS.
3. **TOÀN BỘ SETUP CHUNG (0a + 0b + 0c) ĐÃ XONG** — nhánh `Dat` đồng bộ `origin/Dat`, HEAD `0c265c9`:
   - **0a** (`2cd7988`): PR template; 6 labels + milestone M2 + 14 issues (0b→B6) trên GitHub; branch protection `main` (Not enforced — private repo gói Free).
   - **0b** (PR #15 → `1e139c2`): CI GitHub Actions (push/PR vào main+Dat), ruff (`.ruff.toml` per-file-ignores), pytest-cov (report, chưa gate 85%). CI xanh.
   - **0c** (PR #16 → `0c265c9`): Alembic foundation. 2 migration (baseline + M2: blueprints/import_batches + cột content_hash/source_question_id/import_batch_id). `alembic upgrade head` đã chạy thật trên PostgreSQL 17 trống (DoD đạt). **MODELS ĐÓNG BĂNG từ đây.**
4. **Hạ tầng máy Đạt**: PostgreSQL 17 cài tại `D:\Postgres\17` (port 5432, user postgres). Bản 15 cũ đã hỏng/gỡ. `psql`/`createdb` tại `D:\Postgres\17\bin\` (chưa vào PATH).
5. **Giao thức làm việc đã ổn định**: Anti nộp plan từng việc → Đạt gửi Claude review → Đạt gõ `DUYỆT <mã việc>` → Anti code nhánh riêng → PR vào `Dat` → Claude nghiệm thu độc lập (worktree: diff + ranh giới file + ruff + pytest ×2) → Đạt squash merge. Bí mật (token/password) do Đạt tự chạy, không vào chat/file/commit.

## Current Gaps / In Progress

- **Parser Engine**: chưa tồn tại — hợp đồng nằm trong 4 test skip của `tests/test_specs_parser.py` + đặc tả mục 3 tài liệu phân hệ (việc A1→A4).
- **Generator**: 6 gap có chủ đích (xfail/skip): lọc approved, fail-fast, seed, Part 7 = 52/54 câu, cân bằng đáp án, topic. Bẫy fixture cho B2/B3 đã ghi trong brief (P7 toàn nhóm 4 câu; topic đơn điệu) — cần PR mở rộng `conftest.py` được duyệt trước khi gỡ xfail.
- **CI chưa test migration**: `ci.yml` chỉ chạy pytest trên SQLite (dùng create_all) — KHÔNG bắt được lỗi migration PG-specific. Cân nhắc thêm postgres service vào CI sau.
- **Celery chưa nối API** (SPEC-GRADE-003, thuộc milestone Chấm — NGOÀI phạm vi M2).
- **Chờ bên ngoài**: quy ước tên file MP3 với đối tác (chặn A2); sếp xác nhận quy đổi độ khó câu→nhóm (±1 trong dung sai ±2).

## Next Session Objectives

1. **Việc tiếp theo: B1 (`feat/generator-hardening`)** [SPEC-BANK-001, GEN-006, GEN-005] hoặc **A1 (`feat/parser-core`)** [SPEC-PARSE-001/003/004]. B1 thuần thuật toán, không chờ dữ liệu đối tác → ưu tiên làm trước trong lúc chờ MP3. B1 nhớ: lọc `status=="approved"`, fail-fast `InsufficientBankError` (kiểm tồn kho TRƯỚC khi tạo Exam), `seed` qua `random.Random(seed)`, ghi `source_question_id`; **gỡ ignore E711 trong `.ruff.toml`** khi viết lại query theo SQLAlchemy 2.0 style.
2. Quy trình mỗi việc giữ nguyên: plan → Claude review → `DUYỆT <mã việc>` → code nhánh riêng → PR vào `Dat` → Claude nghiệm thu → squash merge. KHÔNG đụng `backend/app/models/` (đã đóng băng), không đụng phân hệ Chấm.
3. Bổ sung hạ tầng (khi rảnh): thêm postgres service vào `ci.yml`; bật "Require status checks" cho `main` nếu repo chuyển public/nâng gói.
4. Chờ bên ngoài: quy ước tên file MP3 (chặn A2); sếp xác nhận quy đổi độ khó câu→nhóm.
