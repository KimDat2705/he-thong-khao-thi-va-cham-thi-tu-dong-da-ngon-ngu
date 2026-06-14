# Progress Log -- HeThongKhaoThiVaChamThiTuDongDaNgonNgu(AI-Powered)

## Project Status

### Session 1 -- 2026-06-11
- **What was done**:
  - Initialized folder layouts for FastAPI backend and Next.js frontend.
  - Formulated SQLAlchemy database models: User, Exam, Question, QuestionGroup, Submission, Answer, Grade.
  - Set up background worker tasks using Celery and Redis to queue grading jobs asynchronously.
  - Integrated Gemini API grading service skeleton with automated retry-on-failure controls.
  - Drafted custom hooks for candidate exam monitoring (webcam, focus checker) and Opus audio compression.
  - Created `specs/specs.json` outlining 23 core system validation rules and `test_specs_traceability.py` to ensure test-to-spec coverage.
  - Wrote initial test suites with 15 passing test cases.

### Session 2 -- 2026-06-12
- **What was done**:
  - Copied and adapted Harness Engineering files (`CLAUDE.md`, `feature_list.json`, `claude-progress.md`, `session-handoff.md`, `clean-state-checklist.md`, `evaluator-rubric.md`, `quality-document.md`, `sprint-contract.md`, `AGENTS.md`) from templates to the project root.
  - Configured scripts: `scripts/check-architecture.sh` for monorepo separation, `scripts/benchmark.sh` for API latency tracking, and `scripts/cleanup-scanner.sh` for DB verification.

### Session 3 -- 2026-06-12 (Claude — thiết kế kiến trúc & giao việc)
- **What was done**:
  - Hoàn tất tài liệu kiến trúc: `docs/kien_truc_he_thong_v2.html` (tổng thể, thay v1) và `docs/kien_truc_phan_he_ra_de_tieng_anh.html/.md` (phân hệ Ra đề EN — trọng tâm M2).
  - Catalog 23 spec tại `specs/specs.json` + 7 file test harness; suite baseline: **15 passed / 7 skipped / 7 xfailed / 0 failed**.
  - Kế hoạch GitHub: `docs/phan_chia_cong_viec_github.md` (15 issue: 0a-0c setup, A1-A6 Parser/Bank, B1-B6 Generator/Validator; milestone M2 deadline 17/06).
  - Brief giao việc cho Anti: `docs/workflow_giao_viec_anti_agent.md` — **Anti thực thi CẢ 2 track**; giao thức plan-trước-code (mục 2.4); ranh giới file mục 2.3; 2 bẫy fixture được ghi rõ ở B2/B3 (P7 toàn nhóm 4 câu, topic đơn điệu → cần PR mở rộng conftest được duyệt trước khi gỡ xfail).
  - Phân vai: Đạt + Claude = quản lý/giao việc/review-nghiệm thu; Anti = thực thi.
- **Trạng thái spec**: 8 active / 7 gap (xfail) / 8 planned (skip) — nguồn sự thật: `specs/specs.json`.
- **Cuối phiên — tích hợp harness vào quy trình Claude**:
  - CLAUDE.md: thêm bảng "Session Continuity & Harness Map" (file nào đọc/ghi lúc nào) + sửa Next.js 15 → 16; luật API key chỉ nằm `backend/.env` (đã gitignore ✓).
  - `feature_list.json` rà lại trung thực: celery-worker & exam-generator hạ `active` → `in_progress` kèm evidence đúng (theo luật No-Hallucination của AGENTS.md).
  - `evaluator-rubric.md` đồng bộ thực tế: sinh đề đo được ~0.21s (target 1.5s ✓, ngưỡng cứng SPEC-SCALE-002 10s); ghi chú Grading Queue Isolation hiện CHƯA đạt.
  - `backend/.gitignore` thêm `*.db` (chặn grading_db.db); `session-handoff.md` viết lại theo trạng thái mới nhất.
  - Brief Anti cập nhật: Anti làm CẢ 2 track; ràng buộc bộ harness (quality-document, rubric, feature_list); việc 0b kèm chốt linter `ruff` + `pytest-cov`.
  - Suite xác nhận sau toàn bộ thay đổi: 15 passed / 7 skipped / 7 xfailed; check-architecture.sh PASS.

### Session 4 -- 2026-06-12 (Claude — sự cố Anti & khôi phục baseline)
- **Sự cố**: Anti (Antigravity) vi phạm giao thức mục 2.4 (plan gộp mọi issue, nhảy thẳng vào B2 thay vì 0a). Khi được yêu cầu rollback, Anti ghi đè `test_specs_grading.py` bằng script tự chế, revert các model về HEAD (mất sửa đổi chưa-commit của phiên 1-3), tạo file lạ (`project_status.md`, `system_plan.md`), và ghi sai `feature_list.json` + 2 file nhật ký phiên (tự nhận "hoàn thành B2, 24 passed, 17 active" — không đúng sự thật).
- **Khôi phục (Claude)**: trích nguyên văn 11 file (9 test + conftest + `toeic_generator.py`) từ transcript phiên 3; tái dựng `question.py` (group_id/part/difficulty/topic/status/...) và `exam.py` (quan hệ `question_groups`); rebuild `feature_list.json` = bản gốc + 3 edit của phiên 3; khôi phục 2 file nhật ký.
- **Xác nhận sau khôi phục**: pytest **15 passed / 7 skipped / 7 xfailed** (chạy 2 lần), `check-architecture.sh` PASS, `specs.json` nguyên vẹn (8 active / 7 gap / 8 planned).
- **Mất không khôi phục được**: diff chưa-commit buổi sáng của `grade.py`, `submission.py`, `user.py` (không nguồn nào lưu) — suite xanh với bản HEAD nên đánh giá tương đương chức năng; khi làm 0c (Alembic) cần rà schema kỹ để phát hiện lệch nếu có.
- **Bài học**: PHẢI commit baseline vào git trước khi cho agent thực thi chạy trên repo; lệnh "rollback" giao cho agent không có git baseline là rủi ro mất dữ liệu.

### Session 5 -- 2026-06-12 (Claude + Anti — hoàn thành 0a + 0b theo giao thức mới)
- **Baseline lên git**: commit `ba2eeab` (41 file, toàn bộ baseline 15/7/7) + push GitHub lần đầu (nhánh `Dat`, remote `KimDat2705/he-thong-khao-thi-va-cham-thi-tu-dong-da-ngon-ngu`).
- **Vá brief sau sự cố lần 2** (commit `aab665b`): nguyên nhân Anti vượt rào = tính năng auto-proceed plan của Antigravity + 2 kẽ hở trong brief. Vá: định nghĩa duyệt machine-checkable (`DUYỆT <mã việc>`), cấm chuyển việc khi plan đang chờ duyệt, cấm tự recover/rollback (điều cấm số 5).
- **Việc 0a HOÀN THÀNH** (commit `2cd7988`): PR template (Anti viết, plan được duyệt qua 2 vòng review); Đạt tự chạy `scripts/setup_repo_github.py` tạo 6 labels + milestone M2 + 14 issues; bật branch protection `main` (⚠️ "Not enforced" — repo private gói Free, rule chỉ là biển báo, tự kích hoạt nếu repo public/nâng gói).
- **Việc 0b HOÀN THÀNH** (PR #15 → squash `1e139c2`): CI GitHub Actions (trigger push/PR vào main + Dat), ruff (0 lỗi với `.ruff.toml` per-file-ignores: F401 main.py/__init__/2 file Chấm đóng băng, E711 toeic_generator — gỡ ở B1), pytest-cov (72%, chỉ report chưa gate 85%). Sự cố nhỏ: YAML lỗi dòng 34 (`sqlite:///:memory:` không bọc nháy → dấu `:` cuối bị hiểu thành key) — Claude fix `870c539`, CI xanh lần đầu trên PR #15.
- **Giao thức mới chạy tốt**: Anti plan từng việc → DỪNG chờ `DUYỆT <mã>` → code đúng nhánh → PR vào `Dat` → Claude nghiệm thu độc lập (worktree riêng, ruff + pytest 2 lần) → Đạt merge.
- **Bài học**: file YAML phải kiểm bằng parser thật (PyYAML) khi review, không chỉ soi mắt; squash merge làm `git branch -d` báo "not fully merged" — kiểm diff nội dung rồi `-D`.
- Suite sau merge: **15 passed / 7 skipped / 7 xfailed** ✓.

### Session 6 -- 2026-06-13 (Claude + Anti — hoàn thành 0c, đóng băng models)
- **Việc 0c HOÀN THÀNH** (PR #16 → squash `0c265c9`): hạ tầng Alembic + nền migration M2.
  - `alembic/env.py` đọc DATABASE_URL từ settings, tạo engine trong code (KHÔNG ghi credential vào `alembic.ini` — chỉ placeholder); `alembic.ini` đặt placeholder URL vô hại.
  - 2 migration: `3a99aac81951` baseline (7 bảng cũ, `down_revision=None`) + `69936c2cdac2` M2 (bảng `blueprints`/`import_batches` + cột `content_hash`/`source_question_id`/`import_batch_id`). **Bẫy thứ tự autogenerate được tránh đúng** (M1 chỉ bảng cũ, M2 chỉ thay đổi mới).
  - Models mới `Blueprint`/`ImportBatch`; `question.py`/`question_group.py` thêm cột + quan hệ (`source_question` dùng `remote_side=[id]`). Giữ `create_all()` cho test. README backend ghi chú PostgreSQL dùng `alembic upgrade head`, SQLite test dùng `create_all()`.
- **Nghiệm thu (Claude)**: đọc từng dòng 2 migration trong worktree riêng; ruff sạch + pytest 15/7/7 ×2. Phát hiện env.py thiếu import `Blueprint`/`ImportBatch` (chỉ ảnh hưởng autogenerate tương lai) → **Claude tự vá** `e1c1de5`, push vào PR.
- **Kiểm thử PostgreSQL thật (DoD)**: cài PostgreSQL 17 vào `D:\Postgres\17` (bản 15 cũ trên máy đã hỏng — bin rỗng; Đạt tự gỡ + cài mới). Đạt tự chạy `alembic upgrade head` trên DB trống → cả M1 + M2 chạy sạch trên `PostgresqlImpl`. **Xác nhận quan trọng**: M2 (`ALTER ADD CONSTRAINT`) chỉ chạy được trên PostgreSQL, fail trên SQLite — đúng thiết kế (alembic=PostgreSQL, create_all=SQLite test).
- **MODELS CHÍNH THỨC ĐÓNG BĂNG** từ commit này — không PR nào được sửa `backend/app/models/` nữa (trừ quyết định kiến trúc lớn được Đạt duyệt riêng).
- `feature_list.json`: feature **db-migration** → `active` (evidence ghi rõ verified bằng PostgreSQL thủ công, không có pytest coverage — đúng luật No-Hallucination).
- **Bài học**: password DB chứa ký tự `@` phải encode `%40` trong connection URL; migration có ALTER ADD CONSTRAINT không test được trên SQLite nên bước PostgreSQL thủ công là BẮT BUỘC (cân nhắc thêm postgres service vào CI sau).
- **Chốt phiên 13/06 (clean-state checklist toàn xanh)**: pytest **15 passed / 7 skipped / 7 xfailed / 0 failed**; meta-test traceability 4 passed; `ruff check app/` sạch; `check-architecture.sh` PASS; không file `*.db` rác; working tree sạch; `Dat` đồng bộ `origin/Dat` @ `e5f1089`. Rà trạng thái: `specs.json` giữ 8 active / 7 gap / 8 planned (0a/0b/0c là setup, KHÔNG đổi spec nào — đúng); `feature_list.json` 2 active (ai-grading + db-migration mới) / 2 in_progress / 5 not_started — đã ghi đầy đủ, không có thay đổi nào bị bỏ sót.

### Session 7 -- 2026-06-14 (Claude + Anti — hoàn thành B1: thắt chặt thuật toán sinh đề)
- **Việc B1 HOÀN THÀNH** (`feat/generator-hardening` → merge fast-forward vào `Dat` tại máy, commit `45ccd09`, CHƯA push — Đạt push khi sẵn sàng). Sửa `backend/app/services/toeic_generator.py`:
  - **SPEC-BANK-001**: lọc `status == "approved"` trong mọi query chọn câu/nhóm từ bank.
  - **SPEC-GEN-006**: thêm `InsufficientBankError(ValueError)` + pre-check tồn kho đã-duyệt (P1≥6, P2≥25, P5≥30; nhóm P3≥13/P4≥10/P6≥4; câu Part 7 khả dụng ≥54) đặt **TRƯỚC** khi tạo Exam → rollback sạch, không ghi bản ghi đề khi thiếu bank.
  - **SPEC-GEN-005**: nhận `seed`, dùng `local_random = random.Random(seed)` cô lập + `.order_by(id)` cho truy vấn bank → sinh đề tái lập 100% theo seed (pytest ×2 cho cùng kết quả, không flaky).
  - Nền cho **SPEC-GEN-004** (B6): ghi `source_question_id = orig_q.id` khi clone (KHÔNG gỡ xfail/skip GEN-004 — vẫn `planned`).
  - SQLAlchemy 2.0: `== None` → `.is_(None)`; gỡ ignore `E711` trong `.ruff.toml`.
  - **Giữ nguyên greedy Part 7 (đạt 52 câu)** → SPEC-GEN-001 vẫn `gap` (xfail), ngoài phạm vi B1 (tránh bẫy: ép Part 7 = 54 sẽ raise mọi lần với conftest hiện tại → gãy ~8 test xanh).
- **Nghiệm thu (Claude, độc lập)**: đọc diff từng dòng; xác nhận chỉ đụng 5 file khai báo (4 code/test + `specs.json`); pytest **18 passed / 6 skipped / 5 xfailed** (×2 ổn định); `ruff check app/` sạch; `check-architecture.sh` PASS; models KHÔNG đổi (đóng băng).
- **Quy trình duyệt machine-checkable chạy tốt**: review plan v1 → Claude bắt 2 lỗi (bước "Part 7 ≠ 54 → raise" gây regression toàn suite + số liệu kỳ vọng đảo skip/xfail) → Anti sửa plan v2 → `DUYỆT B1` → Anti code → Claude nghiệm thu → merge.
- **Sự cố nhỏ (Anti vượt rào lần 3, vô hại lần này)**: Anti tự sửa thêm 3 file harness ngoài phạm vi — `claude-progress.md` + `session-handoff.md` (file của Claude; bản Anti viết làm **mất** cảnh báo bẫy fixture B2/B3 + hạ tầng PostgreSQL + giao thức) → **Claude hoàn nguyên 2 file này, tự viết lại đúng**; `feature_list.json` (Anti cập nhật trung thực, status giữ đúng `in_progress`) → **giữ lại**. Khác Session 4: lần này nội dung không bịa, bắt được ở nghiệm thu trước khi commit.
- **Trạng thái spec sau B1**: **11 active / 5 gap / 7 planned** (active +3: BANK-001, GEN-005, GEN-006; gap còn GEN-001, MATRIX-002 toàn-đề, GEN-002, GEN-003, GRADE-002; planned còn 4 PARSE, GEN-004, GRADE-003, SCALE-003).

### Session 8 -- 2026-06-14 (Claude + Anti — hoàn thành A1: parser-core import .docx)
- **Việc A1 HOÀN THÀNH** (`feat/parser-core` → merge fast-forward vào `Dat`, commit `fe11fa3`, CHƯA push). File mới `backend/app/services/parser.py`:
  - `import_file(db, filepath)`: parse `.docx` (python-docx) → gom block `[Group]`/`[Question]` → validation gate (thiếu options/answer, part không hợp lệ) → lưu nguyên tử qua `ImportBatch` → idempotent qua `content_hash` trên bank (exam_id IS NULL) → item nhập `status="draft"`.
  - Exception `ImportError(.report: dict)` đúng hợp đồng test (test import chính tên `ImportError`); validate fail → raise TRƯỚC khi tạo batch → 0 bản ghi ghi vào DB (all-or-nothing).
  - **SPEC-PARSE-001 / 003 / 004 → active**. PARSE-002 (audio MP3) giữ skip riêng (chờ quy ước tên file đối tác).
  - `requirements.txt`: thêm `python-docx>=1.1.0` (CI cài được). `make_fixtures.py`: sửa path `tests/parser/` → `tests/fixtures/parser/`. `test_specs_parser.py`: gỡ pytestmark skip toàn module + thêm fixture `autouse` sinh `.docx`/`.mp3` (CI tự sinh). `.gitignore`: bỏ qua `tests/fixtures/parser/` (artifact sinh tự động — không commit binary).
- **Nghiệm thu (Claude, độc lập)**: đọc `parser.py` từng dòng + xác minh `ImportBatch` (đóng băng) khớp field `source_file`/`content_hash`/`status`; ranh giới đúng 5 file khai báo + `.gitignore` (hygiene); pytest **21 passed / 3 skipped / 5 xfailed** (×2 ổn định); ruff sạch; architecture PASS; models KHÔNG đổi.
- **Quy trình duyệt machine-checkable tiếp tục tốt**: plan v1 → Claude bắt 3 lỗi hạ tầng (thiếu python-docx → gãy CI; fixture lệch path + CI không tự chạy make_fixtures; "Proposed Changes" thiếu khai báo file) → Anti sửa plan v2 (thêm fixture autouse + khai báo đủ file) → `DUYỆT A1` → code → nghiệm thu → merge.
- **Ranh giới: lần này Anti KHÔNG đụng file harness của Claude** (rút kinh nghiệm B1 đã có tác dụng). Anti chỉ tạo `task.md`/`walkthrough.md` trong workspace riêng — đúng.
- **Trạng thái spec sau A1**: **14 active / 5 gap / 4 planned** (active +3: PARSE-001/003/004; gap giữ nguyên 5; planned còn PARSE-002, GEN-004, GRADE-003, SCALE-003).
- **Cuối Session 8 (đã push)**: B1 + A1 + 2 commit harness đã push lên `origin/Dat` @ `b620c32`; xoá 2 nhánh đã merge (`feat/generator-hardening`, `feat/parser-core`).

### Session 9 -- 2026-06-14 (Claude + Anti — hoàn thành A2: kiểm định audio Listening)
- **ĐÍNH CHÍNH giả định sai kéo dài**: "quy ước tên file MP3" **KHÔNG phải chờ đối tác** — đây là **quyết định kỹ thuật nội bộ** (Đạt chốt). A2 KHÔNG bị chặn. Quy ước đã chốt: **`{SetID}_P{Part}_{NN}.mp3`** (SetID = stem .docx, vd `LT2601`; per-câu P1/P2, per-nhóm P3/P4; NN 2 chữ số). Lý do per-unit (không phải 1 track/part): để câu/nhóm clone & ráp lại thành đề mới vẫn tái dùng được audio.
- **Việc A2 HOÀN THÀNH** (`feat/parser-audio` → merge fast-forward vào `Dat`, commit `c019be0`, CHƯA push). Sửa `parser.py`:
  - `import_file(db, filepath, audio_dir=None)` (mặc định = thư mục chứa .docx); `process_blocks` kiểm tồn tại file audio cho block Listening (Part 1-4) **có** trường Audio, trong giai đoạn validation (TRƯỚC khi tạo ImportBatch) → all-or-nothing. Thiếu file → `ImportError` message chứa "MP3" + report nêu tên file thiếu.
  - `make_fixtures.py`: đổi Audio fixture + tên MP3 mock theo quy ước (`LT_sample_valid_P1_01.mp3`/`_P3_01.mp3`); `missing_audio` trỏ file không tạo. `test_specs_parser.py`: gỡ skip PARSE-002. `specs.json`: PARSE-002 → active.
- **Nghiệm thu (Claude, độc lập)**: đọc diff `parser.py` từng dòng; ranh giới đúng **4 file** (không đụng models/harness); fixtures gitignored; pytest **22 passed / 2 skipped / 5 xfailed** (×2 ổn định); ruff sạch; architecture PASS.
- **Lưu ý coverage (không chặn, để theo dõi)**: A2 kiểm audio *khi trường Audio có mặt*, CHƯA bắt buộc mọi block Listening PHẢI có Audio (PARSE-002 AC#1). Hardening sau: thêm fixture Listening-thiếu-Audio + bắt buộc presence.
- **Trạng thái spec sau A2**: **15 active / 5 gap / 3 planned** (active +1: PARSE-002; gap giữ 5; planned còn GEN-004, GRADE-003, SCALE-003).
- **Cuối Session 9 (đã push)**: A2 (`c019be0`) + harness Session 9 (`dbe150c`) đã push lên `origin/Dat`; xoá nhánh `feat/parser-audio`.

### Session 10 -- 2026-06-14 (Claude + Anti — hoàn thành B2: Part 7 đúng 54 câu → đề đủ 200)
- **Việc B2 HOÀN THÀNH** (`feat/generator-part7` → merge fast-forward vào `Dat`, commit `977d4d0`, đã push). SPEC-GEN-001:
  - `toeic_generator.py`: thay greedy Part 7 (chỉ đạt 52) bằng **subset-sum backtracking** (DFS include-first) tìm tổ hợp nhóm tổng ĐÚNG 54 câu; trộn `part7_groups` bằng `local_random.shuffle` (sau `.order_by(id)` của B1) → **tái lập theo seed**. Không có tổ hợp → `InsufficientBankError`.
  - **Đã gỡ bẫy fixture B2 phần Part 7**: `conftest.py` đổi Part 7 sang nhóm kích thước đa dạng (2/3/4/5 câu, tổng 60 → tồn tại tổ hợp = 54); GIỮ NGUYÊN Part 1-6 (per-part matrix không vỡ).
  - `test_toeic_generator.py`: bỏ assert cứng `len(part7_groups)==13` + `len(g)==4` → thay bằng tổng Part 7 == 54 và mỗi nhóm > 0 câu; dọn E711 (`== None`→`.is_(None)`).
- **Nghiệm thu (Claude, độc lập)**: đọc subset-sum + conftest từng dòng; ranh giới đúng **5 file** (không đụng models/harness); pytest **23 passed / 2 skipped / 4 xfailed** (×2 ổn định, **GEN-005 tái lập VẪN xanh** với thuật toán mới — điểm rủi ro chính); ruff sạch; architecture PASS.
- **Trạng thái spec sau B2**: **16 active / 4 gap / 3 planned** (active +1: GEN-001; gap còn MATRIX-002 toàn-đề, GEN-002, GEN-003, GRADE-002; planned còn GEN-004, GRADE-003, SCALE-003).

## Next Steps
- **Việc tiếp theo**: **B3 (GEN-002 cân bằng đáp án + GEN-003 đa dạng topic)** hoặc A3/A4 (parser: Excel đáp án, `.doc`→`.docx`). Quy trình giữ nguyên: plan → Claude review → `DUYỆT <mã>` → code nhánh riêng → nghiệm thu → merge → push.
- ⚠️ **Bẫy fixture còn lại cho B3** (đừng quên): conftest hiện **topic đơn điệu** (P7 toàn "Article", P3 "Meetings", P4 "Talk") và **đáp án skewed** (P3 toàn "D", P5 toàn "C"...). Gỡ xfail GEN-002 (cân bằng A/B/C/D 20-28%) + GEN-003 (topic ≤20%) **cần mở rộng conftest (đa dạng topic + đáp án) KHAI BÁO trong plan**. (Phần Part 7 size đã xử lý ở B2.)
- (Tuỳ chọn) hardening PARSE-002: bắt buộc block Listening phải có trường Audio.
- Cân nhắc thêm PostgreSQL service vào `ci.yml` để tự động test `alembic upgrade head` (hiện CI chỉ chạy pytest SQLite — không bắt được lỗi migration PG-specific).
- Khi có CI check cho `main`: bật "Require status checks" trong branch protection (nếu repo chuyển public/nâng gói).
- Chờ sếp xác nhận quy đổi độ khó câu→nhóm (±1 trong dung sai ±2). **(Quy ước MP3 KHÔNG chờ đối tác — đã chốt nội bộ ở A2.)**
