# Session Handoff — cập nhật 14/06/2026 (Claude, sau B1+A1+A2+B2+B3+GEN-002 — Generator gần hoàn chỉnh)

## Current State & Achievements

1. **Kiến trúc đã chốt**: `docs/kien_truc_he_thong_v2.html` (tổng thể) + `docs/kien_truc_phan_he_ra_de_tieng_anh.html/.md` (phân hệ Ra đề EN — trọng tâm M2). Tài liệu v1 đông lạnh tham chiếu.
2. **Harness hoạt động**: 23 spec trong `specs/specs.json` (**18 active / 2 gap / 3 planned** sau GEN-002) ↔ 7 file test; suite **25 passed / 2 skipped / 2 xfailed / 0 failed**; meta-test traceability xanh; `scripts/check-architecture.sh` PASS.
3. **SETUP (0a+0b+0c) XONG**: 0a (`2cd7988`); 0b (PR #15 → `1e139c2`) CI+ruff+pytest-cov; 0c (PR #16 → `0c265c9`) Alembic, chạy thật trên PostgreSQL 17. **MODELS ĐÓNG BĂNG từ 0c.**
4. **Pipeline Ra đề EN (B1+B2+B3+GEN-002) — generator gần hoàn chỉnh**:
   - **B1 (`45ccd09`)**: filter `approved` (BANK-001), `InsufficientBankError` + pre-check (GEN-006), `seed` qua `local_random`+`.order_by(id)` (GEN-005), `source_question_id`.
   - **B2 (`977d4d0`)**: Part 7 subset-sum đúng 54 → đề đủ 200 (GEN-001).
   - **B3 (`3c7be1f`)**: đa dạng topic, cap thích ứng `max(0.20, nhóm_lớn_nhất/tổng)` (GEN-003).
   - **GEN-002 (`ca2ce48`)**: cân bằng đáp án A/B/C/D 20-28% qua hoán vị clone.
   - → Đề sinh ra: đúng 200 câu · ma trận độ khó per-part · đa dạng topic · cân bằng đáp án · tái lập theo seed · chỉ câu approved · bank bất biến.
5. **Parser (A1+A2)**:
   - **A1 (`fe11fa3`)**: `parser.py` `import_file` parse `.docx`, validation gate, lưu nguyên tử qua `ImportBatch`, idempotent qua `content_hash`, `status="draft"`. all-or-nothing. PARSE-001/003/004 active. fixtures sinh tự động qua `autouse` (`tests/fixtures/parser/` gitignore).
   - **A2 (`c019be0`)**: kiểm tồn tại audio Listening, thiếu → `ImportError` "MP3". PARSE-002 active. Quy ước MP3 (NỘI BỘ): `{SetID}_P{Part}_{NN}.mp3`.
6. **Hạ tầng máy Đạt**: PostgreSQL 17 tại `D:\Postgres\17` (port 5432, user postgres). `psql`/`createdb` tại `D:\Postgres\17\bin\` (chưa vào PATH).
7. **Đồng bộ git**: `origin/Dat` @ `ca2ce48` + commit harness Session 12 (đang push). Nhánh feature merge xong là xoá. Working tree sạch.
8. **Giao thức**: Anti nộp plan → Claude review → Đạt `DUYỆT <mã>` → Anti code nhánh riêng → Claude nghiệm thu độc lập (diff + ranh giới + ruff + pytest ×2) → merge FF vào `Dat` → push.
   - ⚠️ **Ranh giới file**: `claude-progress.md` + `session-handoff.md` là Claude ghi. Anti chỉ sửa file trong "Proposed Changes"; nhật ký để `task.md`/`walkthrough.md`. (B1→GEN-002 tuân thủ đúng.)

## Current Gaps / In Progress

- **Generator — chỉ còn 2 hạng mục**:
  - **SPEC-MATRIX-002 toàn-đề (gap/xfail)**: tỷ lệ độ khó 25/50/25 toàn đề. ⚠️ **Giờ VƯỚNG**: sau B3, P7 có nghiệm subset-sum DUY NHẤT → độ khó P7 cố định (4E/30M/20H) → toàn đề lệch (Easy=39<45, Hard=56>55). Cần **rebalance conftest P7 difficulty** (giữ topic+size đã chốt ở B2/B3) hoặc nới nghiệm P7. Task này sửa conftest rất cẩn thận.
  - **SPEC-GEN-004 (planned, B6)**: độ trùng giữa các đề trong lô ≤40% — `source_question_id` đã sẵn từ B1; cần API/đường dẫn generate LÔ nhiều đề rồi so source giữa các cặp.
- **Parser**: lõi `.docx`+audio xong. CÒN: parse **Excel đáp án**, convert `.doc`→`.docx` (RT26xx) — **chưa có spec PARSE** → cần viết spec+test mới. Hardening PARSE-002 (bắt buộc Audio) tuỳ chọn. Feature `docx-parser` = `in_progress`.
- ⚠️ **FIXTURE conftest RẤT NHẠY (bảo trì)** — KHÔNG "dọn" thành đơn giản:
  - **Part 7**: topic+size có **nghiệm subset-sum DUY NHẤT** (loại G2+G3). Sửa phải verify lại (chứng minh trong commit `3c7be1f`).
  - **Part 4**: 3 nhóm medium "Talk" (chủ ý để GEN-003 test không tautology).
  - Đáp án gốc trong conftest skewed nhưng KHÔNG sao (GEN-002 hoán vị trên clone).
- **CI chưa test migration** (SQLite). **Celery chưa nối API** (GRADE-003) + GRADE-002 — milestone Chấm, NGOÀI M2.
- **Chờ bên ngoài**: chỉ còn **sếp xác nhận quy đổi độ khó câu→nhóm**. *(Quy ước MP3 đã chốt nội bộ.)*

## Next Session Objectives

1. **Việc tiếp theo (gợi ý)**: MATRIX-002 toàn-đề (cần rebalance conftest P7 difficulty — cẩn thận) hoặc GEN-004/B6 (generate lô) hoặc A3/A4 parser (cần viết spec mới trước).
2. Quy trình giữ nguyên: plan → Claude review → `DUYỆT <mã>` → code nhánh riêng → Claude nghiệm thu → merge → push. KHÔNG đụng `backend/app/models/`, phân hệ Chấm, `claude-progress.md`/`session-handoff.md`.
3. Hạ tầng (khi rảnh): postgres service vào `ci.yml`; "Require status checks" cho `main`; hardening PARSE-002.
4. Chờ sếp xác nhận quy đổi độ khó câu→nhóm.
