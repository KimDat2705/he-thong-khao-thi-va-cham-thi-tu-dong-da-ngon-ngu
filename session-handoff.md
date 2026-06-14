# Session Handoff — cập nhật 14/06/2026 (Claude, sau B1 + A1 + A2 + B2 + B3 — Generator: 200 câu + ma trận độ khó per-part + đa dạng topic)

## Current State & Achievements

1. **Kiến trúc đã chốt**: `docs/kien_truc_he_thong_v2.html` (tổng thể) + `docs/kien_truc_phan_he_ra_de_tieng_anh.html/.md` (phân hệ Ra đề EN — trọng tâm M2). Tài liệu v1 `system_architecture.html` đông lạnh làm tham chiếu.
2. **Harness hoạt động**: 23 spec trong `specs/specs.json` (**17 active / 3 gap / 3 planned** sau B3) ↔ 7 file test; suite hiện tại **24 passed / 2 skipped / 3 xfailed / 0 failed**; meta-test traceability 2 chiều xanh; `scripts/check-architecture.sh` PASS.
3. **SETUP CHUNG (0a + 0b + 0c) ĐÃ XONG**: 0a (`2cd7988`); 0b (PR #15 → `1e139c2`) CI + ruff + pytest-cov; 0c (PR #16 → `0c265c9`) Alembic, `alembic upgrade head` chạy thật trên PostgreSQL 17. **MODELS ĐÓNG BĂNG từ 0c.**
4. **B1 (`45ccd09`)**: `toeic_generator.py` — filter `status=="approved"` (BANK-001); `InsufficientBankError` + pre-check tồn kho (GEN-006); `seed` cô lập qua `local_random` + `.order_by(id)` (GEN-005); `source_question_id` (nền GEN-004/B6); SQLAlchemy 2.0.
5. **A1 (`fe11fa3`)**: `parser.py` — `import_file` parse `.docx`, validation gate, lưu nguyên tử qua `ImportBatch`, idempotent qua `content_hash`, item `status="draft"`. `ImportError(.report)`, all-or-nothing. **PARSE-001/003/004 active**. `python-docx` trong requirements; fixtures sinh tự động qua `autouse` (`tests/fixtures/parser/` gitignore).
6. **A2 (`c019be0`)**: `parser.py` — kiểm tồn tại file audio Listening (P1-4 có trường Audio) trong validation phase; thiếu → `ImportError` chứa "MP3". **PARSE-002 active**. Quy ước MP3 (NỘI BỘ): `{SetID}_P{Part}_{NN}.mp3`.
7. **B2 (`977d4d0`)**: Part 7 **subset-sum** đạt ĐÚNG 54 câu → **đề đủ 200 câu**. **GEN-001 active**. conftest P7 nhóm 2/3/4/5 câu.
8. **B3 (`3c7be1f`)**: **đa dạng topic thích ứng**. `cap = max(0.20, nhóm_lớn_nhất/tổng_part)` (P3/4/7=20%, P6=25%). Generator: `select_groups_for_part` (backtracking độ khó + lọc topic) + subset-sum P7 prune topic. **GEN-003 active**. conftest lặp topic có kiểm soát + test multi-seed (1-5 qua `seed=`).
9. **Hạ tầng máy Đạt**: PostgreSQL 17 tại `D:\Postgres\17` (port 5432, user postgres). `psql`/`createdb` tại `D:\Postgres\17\bin\` (chưa vào PATH).
10. **Đồng bộ git**: `origin/Dat` @ `3c7be1f` + commit harness Session 11 (đã/đang push). Nhánh feature đã merge được xoá sau mỗi việc. Working tree sạch.
11. **Giao thức**: Anti nộp plan → Claude review → Đạt gõ `DUYỆT <mã>` → Anti code nhánh riêng → Claude nghiệm thu độc lập (diff + ranh giới + ruff + pytest ×2) → merge FF vào `Dat` → push. Bí mật do Đạt tự chạy.
    - ⚠️ **Ranh giới file**: `claude-progress.md` + `session-handoff.md` là **Claude ghi**, KHÔNG phải Anti. Anti chỉ sửa file trong "Proposed Changes"; nhật ký để trong `task.md`/`walkthrough.md`. (A1/A2/B2/B3 tuân thủ đúng.)

## Current Gaps / In Progress

- **Generator — gap còn lại (xfail)**: SPEC-GEN-002 (cân bằng đáp án A/B/C/D 20-28% — cần hoán vị đáp án khi clone + có thể đa dạng đáp án trong conftest), SPEC-MATRIX-002 toàn-đề (tỷ lệ độ khó 25/50/25 — cần ràng buộc độ khó khi chọn P7). SPEC-GEN-004 (`planned`, B6 — cột `source_question_id` đã sẵn).
- **Parser**: lõi `.docx` + audio xong (PARSE-001..004 active). CÒN: parse **Excel đáp án**, convert `.doc`→`.docx` (RT26xx). Chưa có spec PARSE cho 2 việc này → cần viết spec+test mới. Hardening PARSE-002 (bắt buộc Audio) tuỳ chọn. Feature `docx-parser` = `in_progress`.
- ⚠️ **FIXTURE conftest GIỜ RẤT NHẠY (bảo trì)**:
  - **Part 7**: cấu hình topic+size có **lời giải subset-sum DUY NHẤT** (loại G2 Memo-3 + G3 Report-3; Memo=Report=11>cap buộc loại). Sửa P7 conftest tương lai phải verify lại tồn tại nghiệm (chứng minh trong commit `3c7be1f`).
  - **Part 4**: 3 nhóm medium "Talk" (ép generator chọn ≤2) — chủ ý để test GEN-003 có ý nghĩa. Đừng "dọn" thành all-distinct (sẽ làm test tautology).
- **CI chưa test migration**: `ci.yml` chỉ chạy pytest SQLite. Cân nhắc thêm postgres service.
- **Celery chưa nối API** (SPEC-GRADE-003) + SPEC-GRADE-002 — milestone Chấm, NGOÀI M2.
- **Chờ bên ngoài**: chỉ còn **sếp xác nhận quy đổi độ khó câu→nhóm** (±1 trong dung sai ±2). *(Quy ước MP3 đã chốt nội bộ.)*

## Next Session Objectives

1. **Việc tiếp theo (gợi ý)**: **GEN-002 (cân bằng đáp án)** hoặc MATRIX-002 toàn-đề (cả hai là gap generator khả thi) hoặc A3/A4 (parser Excel/`.doc` — cần viết spec mới trước).
2. Quy trình mỗi việc giữ nguyên: plan → Claude review → `DUYỆT <mã>` → code nhánh riêng → Claude nghiệm thu → merge → push. KHÔNG đụng `backend/app/models/` (đóng băng), không đụng phân hệ Chấm, không đụng `claude-progress.md`/`session-handoff.md`.
3. Bổ sung hạ tầng (khi rảnh): postgres service vào `ci.yml`; "Require status checks" cho `main`; hardening PARSE-002.
4. Chờ sếp xác nhận quy đổi độ khó câu→nhóm.
