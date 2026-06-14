# Session Handoff — cập nhật 14/06/2026 (Claude, sau khi nghiệm thu + merge B1 — XONG GENERATOR HARDENING)

## Current State & Achievements

1. **Kiến trúc đã chốt**: `docs/kien_truc_he_thong_v2.html` (tổng thể) + `docs/kien_truc_phan_he_ra_de_tieng_anh.html/.md` (phân hệ Ra đề EN — trọng tâm M2). Tài liệu v1 `system_architecture.html` đông lạnh làm tham chiếu.
2. **Harness hoạt động**: 23 spec trong `specs/specs.json` (**11 active / 5 gap / 7 planned** sau B1) ↔ 7 file test; suite hiện tại **18 passed / 6 skipped / 5 xfailed / 0 failed**; meta-test traceability 2 chiều xanh; `scripts/check-architecture.sh` PASS.
3. **TOÀN BỘ SETUP CHUNG (0a + 0b + 0c) ĐÃ XONG**:
   - **0a** (`2cd7988`): PR template; 6 labels + milestone M2 + 14 issues (0b→B6) trên GitHub; branch protection `main` (Not enforced — private repo gói Free).
   - **0b** (PR #15 → `1e139c2`): CI GitHub Actions (push/PR vào main+Dat), ruff (`.ruff.toml` per-file-ignores), pytest-cov (report, chưa gate 85%). CI xanh.
   - **0c** (PR #16 → `0c265c9`): Alembic foundation. 2 migration (baseline + M2: blueprints/import_batches + cột content_hash/source_question_id/import_batch_id). `alembic upgrade head` đã chạy thật trên PostgreSQL 17 trống (DoD đạt). **MODELS ĐÓNG BĂNG từ đây.**
4. **VIỆC B1 (`feat/generator-hardening`) ĐÃ XONG** — merge fast-forward vào `Dat` tại máy, commit **`45ccd09`** (CHƯA push — Đạt push khi sẵn sàng). Sửa duy nhất `backend/app/services/toeic_generator.py` + 2 test + `.ruff.toml` + `specs.json` + `feature_list.json`:
   - **BANK-001**: lọc `status == "approved"` trong mọi query chọn câu/nhóm.
   - **GEN-006**: `InsufficientBankError(ValueError)` + pre-check tồn kho đã-duyệt đặt TRƯỚC khi tạo Exam (rollback sạch).
   - **GEN-005**: nhận `seed`, dùng `local_random = random.Random(seed)` cô lập + `.order_by(id)` → tái lập 100%.
   - **Nền GEN-004 (B6)**: ghi `source_question_id = orig_q.id` khi clone (GEN-004 VẪN `planned`).
   - SQLAlchemy 2.0 (`.is_(None)`), gỡ ignore `E711`. Greedy Part 7 GIỮ NGUYÊN (52 câu) → GEN-001 vẫn `gap`.
5. **Hạ tầng máy Đạt**: PostgreSQL 17 cài tại `D:\Postgres\17` (port 5432, user postgres). Bản 15 cũ đã hỏng/gỡ. `psql`/`createdb` tại `D:\Postgres\17\bin\` (chưa vào PATH).
6. **Giao thức làm việc đã ổn định**: Anti nộp plan từng việc → Đạt gửi Claude review → Đạt gõ `DUYỆT <mã việc>` (machine-checkable) → Anti code nhánh riêng → Claude nghiệm thu độc lập (diff + ranh giới file + ruff + pytest ×2) → merge vào `Dat`. Bí mật (token/password) do Đạt tự chạy, không vào chat/file/commit.
   - ⚠️ **Ranh giới file**: `claude-progress.md` + `session-handoff.md` là **Claude ghi**, KHÔNG phải Anti. B1 Anti đã tự sửa 2 file này (làm mất context) → Claude hoàn nguyên + viết lại. Khi review PR sau, luôn kiểm Anti có đụng 2 file này ngoài phạm vi không.

## Current Gaps / In Progress

- **Parser Engine**: chưa tồn tại — hợp đồng nằm trong 4 test skip của `tests/test_specs_parser.py` + đặc tả mục 3 tài liệu phân hệ (việc A1→A4).
- **Generator — gap còn lại (xfail)**: SPEC-GEN-001 (Part 7 = 52/54 câu), SPEC-MATRIX-002 toàn-đề (tỷ lệ 25/50/25), SPEC-GEN-002 (cân bằng đáp án A/B/C/D), SPEC-GEN-003 (đa dạng topic). SPEC-GEN-004 (độ trùng giữa đề, `planned`) — cột `source_question_id` đã sẵn sàng từ B1, chờ B6.
- ⚠️ **BẪY FIXTURE cho B2/B3 (cực kỳ quan trọng — đừng gỡ xfail trước khi sửa)**: `tests/conftest.py` hiện tạo Part 7 = **15 nhóm TOÀN 4 câu** (mọi tổ hợp là bội số của 4 → KHÔNG ráp được đúng 54; greedy chỉ đạt 52) và **topic đơn điệu** (P7 toàn "Article", P3 "Meetings", P4 "Talk"). Gỡ xfail cho GEN-001/GEN-002/GEN-003 **CẦN một PR mở rộng `conftest.py` được Đạt duyệt TRƯỚC** (thêm nhóm P7 với số câu đa dạng 2-5 câu, đa dạng topic). Nếu không, code đúng vẫn fail vì dữ liệu test không cho phép đạt blueprint.
- **CI chưa test migration**: `ci.yml` chỉ chạy pytest trên SQLite (dùng create_all) — KHÔNG bắt được lỗi migration PG-specific. Cân nhắc thêm postgres service vào CI sau.
- **Celery chưa nối API** (SPEC-GRADE-003, thuộc milestone Chấm — NGOÀI phạm vi M2). SPEC-GRADE-002 (tên trường điểm) cũng là gap thuộc Chấm.
- **Chờ bên ngoài**: quy ước tên file MP3 với đối tác (chặn A2); sếp xác nhận quy đổi độ khó câu→nhóm (±1 trong dung sai ±2).

## Next Session Objectives

1. **Push `Dat` lên `origin`** (commit `45ccd09` của B1 đang local).
2. **Việc tiếp theo: A1 (`feat/parser-core`)** [SPEC-PARSE-001/003/004] — lõi Parser Word/Excel; làm được ngay trong lúc chờ MP3 (A2 mới chờ). Hoặc các việc Generator B2-B6 (nhưng B2/B3 cần PR conftest trước — xem bẫy fixture ở trên).
3. Quy trình mỗi việc giữ nguyên: plan → Claude review → `DUYỆT <mã việc>` → code nhánh riêng → Claude nghiệm thu → merge. KHÔNG đụng `backend/app/models/` (đã đóng băng), không đụng phân hệ Chấm, không đụng `claude-progress.md`/`session-handoff.md` (file của Claude).
4. Bổ sung hạ tầng (khi rảnh): thêm postgres service vào `ci.yml`; bật "Require status checks" cho `main` nếu repo chuyển public/nâng gói.
5. Chờ bên ngoài: quy ước tên file MP3 (chặn A2); sếp xác nhận quy đổi độ khó câu→nhóm.
