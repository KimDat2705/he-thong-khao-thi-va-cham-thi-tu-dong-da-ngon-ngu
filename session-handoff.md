# Session Handoff — cập nhật 15/06/2026 (Claude, sau PARSE-008 hoàn thành)

## Current State & Achievements

1. **Kiến trúc đã chốt**: `docs/kien_truc_he_thong_v2.html` (tổng thể) + `docs/kien_truc_phan_he_ra_de_tieng_anh.html/.md` (phân hệ Ra đề EN — trọng tâm M2). Tài liệu v1 đông lạnh tham chiếu.
2. **Harness hoạt động**: **28 spec** trong `specs/specs.json` (**23 active / 2 gap / 3 planned** sau PARSE-008) ↔ 7 file test; suite **30 passed / 2 skipped / 2 xfailed / 0 failed**; meta-test traceability xanh; `scripts/check-architecture.sh` PASS. **Baseline 15/06: `origin/Dat` @ `cfd5431`, clean-state toàn xanh.**
3. **DỮ LIỆU INPUT THẬT đã đọc được** (`docs/du_lieu_input_links.md`): tải bằng `PYTHONUTF8=1 python -m gdown` về `D:\Dat-Antigravity\drive_input\` (ngoài repo) + parse openpyxl/python-docx; Sheet→export xlsx; bỏ MP3. Ma trận TOEIC (Sheet) XÁC NHẬN blueprint + luật ta đã code. Đáp án=xlsx lưới Câu/Đáp án; đề=Word tables+ảnh (đã map cấu trúc).
4. **Real Parser Track (PARSE-006 & PARSE-007) — HOÀN THÀNH**:
   - **A3 (`d2388e8`)**: `parse_answer_key(filepath)->dict[int,str]` (openpyxl, quét header, gộp 5 block).
   - **PARSE-006 (`8239a88` + `c65eb57`)**: `parse_listening_docx(filepath)->{set_id, items}` — bóc tách table-based `.docx` theo document order, split nhóm P3/P4 bằng line `---` trong cell, ghép wrap option/câu qua nhiều paragraph (state-machine), P1 ghi image index.
   - **PARSE-007 (`c8948fa` + vá `a6fdf99`)**: `import_listening_set(db, docx_path, key_path, audio_dir=None)` — trộn đáp án từ tệp Excel vào câu hỏi Word theo số câu, validation gate (all-or-nothing), set_id docx khớp KEY, lưu ImportBatch và commit ngân hàng ở trạng thái `draft` (save bọc try/except + rollback).
   - **Bug Question Hash Collision — Claude bắt lúc nghiệm thu trên dữ liệu THẬT**: fixture xanh nhưng `import_listening_set` trên cặp thật LT2601 chỉ ghi 75/100 câu (P1/P2 content giống nhau + options rỗng → trùng hash → nuốt 25 câu). Vá: đưa `set_id`+`number` vào `calculate_question_hash`, `set_id` vào `calculate_group_hash` (path cũ → None → tương thích ngược). **Claude verify lại file thật: 100/100 câu + 23/23 nhóm, 0 skip, idempotent ✓.** Bài học: pytest fixture xanh KHÔNG đủ — verify file thật là bắt buộc.
5. **SETUP (0a+0b+0c) XONG**: 0a (`2cd7988`); 0b (PR #15 → `1e139c2`) CI+ruff+pytest-cov; 0c (PR #16 → `0c265c9`) Alembic, chạy thật trên PostgreSQL 17. **MODELS ĐÓNG BĂNG từ 0c.**
6. **Pipeline Ra đề EN (B1+B2+B3+GEN-002) — generator gần hoàn chỉnh**:
   - **B1 (`45ccd09`)**: filter `approved` (BANK-001), `InsufficientBankError` + pre-check (GEN-006), `seed` qua `local_random`+`.order_by(id)` (GEN-005), `source_question_id`.
   - **B2 (`977d4d0`)**: Part 7 subset-sum đúng 54 → đề đủ 200 (GEN-001).
   - **B3 (`3c7be1f`)**: đa dạng topic, cap thích ứng `max(0.20, nhóm_lớn_nhất/tổng)` (GEN-003).
   - **GEN-002 (`ca2ce48`)**: cân bằng đáp án A/B/C/D 20-28% qua hoán vị clone.
   - → Đề sinh ra: đúng 200 câu · ma trận độ khó per-part · đa dạng topic · cân bằng đáp án · tái lập theo seed · chỉ câu approved · bank bất biến.
7. **Hạ tầng máy Đạt**: PostgreSQL 17 tại `D:\Postgres\17` (port 5432, user postgres). `psql`/`createdb` tại `D:\Postgres\17\bin\` (chưa vào PATH).
8. **Đồng bộ git**: `origin/Dat` @ `6422e5e`. Nhánh feature merge xong là xoá. Working tree sạch.

## Current Gaps / In Progress

- **Generator — chỉ còn 2 hạng mục**:
  - **SPEC-MATRIX-002 toàn-đề (gap/xfail)**: tỷ lệ độ khó 25/50/25 toàn đề. ⚠️ **Giờ VƯỚNG**: sau B3, P7 có nghiệm subset-sum DUY NHẤT → độ khó P7 cố định (4E/30M/20H) → toàn đề lệch (Easy=39<45, Hard=56>55). Cần **rebalance conftest P7 difficulty** (giữ topic+size đã chốt ở B2/B3) hoặc nới nghiệm P7. Task này sửa conftest rất cẩn thận.
  - **SPEC-GEN-004 (planned, B6)**: độ trùng giữa các đề trong lô ≤40% — `source_question_id` đã sẵn từ B1; cần API/đường dẫn generate LÔ nhiều đề rồi so source giữa các cặp.
- **Parser — Đọc/Listening thật tiếp tục**:
  - ✅ **Converter `.doc`→`.docx` (PARSE-008, `cfd5431`) XONG** — `convert_doc_to_docx` qua LibreOffice headless (passthrough/cache/missing-tool error). ⚠️ Convert THẬT CHƯA verify (máy Đạt **chưa cài LibreOffice** — cài rồi convert thử RT*.doc, giống 0c PostgreSQL). **Kế tiếp: parser Reading `RT*.docx`** (P5/6/7, không audio — tương tự `parse_listening_docx`) rồi merge Key RT (reuse `import_listening_set`).
  - Audio thật là **MP3 gộp ~100MB theo dải** ("2601-2604.mp3") → quy ước A2 per-câu không khớp; mô hình audio (mapping đề→file+đoạn/timestamp) cần thiết kế lại.
- ⚠️ **FIXTURE conftest RẤT NHẠY (bảo trì)** — KHÔNG "dọn" thành đơn giản:
  - **Part 7**: topic+size có **nghiệm subset-sum DUY NHẤT** (loại G2+G3). Sửa phải verify lại (chứng minh trong commit `3c7be1f`).
  - **Part 4**: 3 nhóm medium "Talk" (chủ ý để GEN-003 test không tautology).
- **CI chưa test migration** (SQLite). **Celery chưa nối API** (GRADE-003) + GRADE-002 — milestone Chấm, NGOÀI M2.
- **Chờ bên ngoài**: chỉ còn **sếp xác nhận quy đổi độ khó câu→nhóm**. *(Quy ước MP3 đã chốt nội bộ.)*

## Next Session Objectives

1. **Lộ trình tiếp theo**:
   - **A4 `.doc`→`.docx`** convert (đề Đọc RT*).
   - **A2-rework audio gộp** (đề Nghe thật).
   - **CHỜ REDESIGN FIXTURE + đối chiếu Ma trận**: MATRIX-002 toàn-đề (reframe per-skill theo Ma trận), GEN-004 (vướng P7 nghiệm-duy-nhất + bank nhỏ).
   - 💡 Đối chiếu `TOEIC_BLUEPRINT` (hardcode) ↔ Ma trận TOEIC Sheet thật khi có content → cập nhật giá trị (data, không sửa code).
2. Quy trình giữ nguyên: plan → Claude review → `DUYỆT <mã>` → code nhánh riêng → **Claude nghiệm thu XONG mới push** → merge. KHÔNG đụng `backend/app/models/`, phân hệ Chấm, `claude-progress.md`/`session-handoff.md`. ⚠️ Phiên PARSE-007 Anti lại (a) push trước khi Claude nghiệm thu, (b) tự sửa 2 file nhật ký của Claude — nhắc giữ đúng ranh giới lần sau.
3. Hạ tầng (khi rảnh): postgres service vào `ci.yml`; "Require status checks" cho `main`; hardening PARSE-002.
4. Chờ sếp xác nhận quy đổi độ khó câu→nhóm.
