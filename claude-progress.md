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
- **Cuối Session 10 (đã push)**: B2 (`977d4d0`) + harness Session 10 (`f4ef0fc`) đã push lên `origin/Dat`; xoá nhánh `feat/generator-part7`.

### Session 11 -- 2026-06-14 (Claude + Anti — hoàn thành B3: đa dạng topic thích ứng)
- **ĐÍNH CHÍNH spec GEN-003 (Claude quyết, Đạt uỷ quyền)**: ngưỡng 20% cứng **bất khả thi cho P6** (4 nhóm × 4 câu → tối thiểu 25%). Chốt **ngưỡng thích ứng**: `cap = max(0.20, nhóm_lớn_nhất_của_part / tổng_câu_part)` → P3/P4/P7 = 20%, P6 = 25% (ép 4 passage P6 khác topic). Là quy tắc nguyên lý, không phải số ma thuật.
- **Việc B3 HOÀN THÀNH** (`feat/generator-topic` → merge fast-forward vào `Dat`, commit `3c7be1f`, đã push). SPEC-GEN-003:
  - `toeic_generator.py`: `select_groups_for_part` (backtracking giữ ma trận độ khó + lọc topic theo cap) cho P3/4/6; subset-sum P7 thêm **prune theo topic** (>10 câu/topic) + `is_topic_distribution_valid`. Tái lập theo seed (local_random). Không có tổ hợp hợp lệ → `InsufficientBankError`.
  - `conftest.py`: **lặp topic CÓ KIỂM SOÁT** để test thực sự kiểm chứng (không tautology): P4 có 3 nhóm medium "Talk"; P7 có Memo=11/Report=11 câu → ép loại đúng G2+G3 (**lời giải subset-sum duy nhất**). P3/P6 distinct.
  - `test_specs_generation.py`: GEN-003 **lặp 5 seed cố định** (qua `seed=`, KHÔNG `random.seed`), assert mọi topic ≤ cap thích ứng; gỡ xfail.
- **Nghiệm thu (Claude, độc lập)**: tự verify chứng minh khả thi (Option B P7 là nghiệm DUY NHẤT — đúng); xác minh generator P7 prune topic (điểm dễ sai nhất); ranh giới đúng **4 file**; pytest **24 passed / 2 skipped / 3 xfailed** (×2; GEN-005 tái lập + MATRIX per-part xanh; MATRIX toàn-đề vẫn xfail, không flip); ruff sạch; architecture PASS.
- ⚠️ **Lưu ý bảo trì**: fixture P7 trong conftest có **lời giải subset-sum DUY NHẤT** (loại G2,G3) — rất giòn. Chứng minh nằm trong commit `3c7be1f` + task.md/walkthrough của Anti. Sửa conftest P7 tương lai phải kiểm lại tính khả thi.
- **Trạng thái spec sau B3**: **17 active / 3 gap / 3 planned** (active +1: GEN-003; gap còn GEN-002 (cân bằng đáp án), MATRIX-002 toàn-đề, GRADE-002; planned còn GEN-004, GRADE-003, SCALE-003).
- **Cuối Session 11 (đã push)**: B3 (`3c7be1f`) + harness Session 11 (`0fed6c7`) đã push lên `origin/Dat`; xoá nhánh `feat/generator-topic`.

### Session 12 -- 2026-06-14 (Claude + Anti — hoàn thành GEN-002: cân bằng đáp án)
- **Việc GEN-002 HOÀN THÀNH** (`feat/generator-answer-balance` → merge fast-forward vào `Dat`, commit `ca2ce48`, đã push). SPEC-GEN-002:
  - `toeic_generator.py`: cuối `generate_toeic_exam`, lọc câu 4 lựa chọn của ĐỀ (`exam_id==new_exam.id`, `len(options)==4` — filter trùng khít test), sắp theo id; sinh mảng letter mục tiêu A/B/C/D chia đều rồi `local_random.shuffle` (tái lập theo seed); **hoán vị options + reference_answer trên CLONE** để đáp án đúng nằm ở letter mục tiêu, giữ nguyên nội dung lựa chọn. 175 câu → mỗi đáp án ~25% (trong [20%,28%]).
  - CHỈ sửa clone → bank gốc bất biến → **BANK-002 vẫn xanh** (đã verify).
- **Nghiệm thu (Claude, độc lập)**: đọc logic hoán vị; xác nhận chỉ đụng clone (BANK-002), filter trùng test, đáp án đúng giữ nội dung; ranh giới đúng **3 file**; pytest **25 passed / 2 skipped / 2 xfailed** (×2; BANK-002 + GEN-005 + GEN-003 + COLLATE-004 vẫn xanh); ruff sạch; architecture PASS.
- **Trạng thái spec sau GEN-002**: **18 active / 2 gap / 3 planned** (active +1: GEN-002; gap còn **MATRIX-002 toàn-đề** + GRADE-002; planned còn GEN-004, GRADE-003, SCALE-003).
- 📊 **Phân hệ Ra đề EN gần hoàn chỉnh** (trên fixture): chỉ còn GEN-004 (độ trùng lô) và MATRIX-002 toàn-đề.

### Bổ sung 15/06/2026 (Claude — đối chiếu DỮ LIỆU INPUT THẬT, đính chính giả định)
- Đạt gửi toàn bộ link Drive input (không gửi lại) → ghi vào `docs/du_lieu_input_links.md` (commit `64ba66d`, pushed) + memory. Đã fetch danh sách file thật các thư mục TOEIC.
- **ĐÍNH CHÍNH**: "Excel đáp án" trong docstring là **ĐÚNG** (tôi đã sai khi nghi là giả định sai) — file `.xlsx` "KEY LT*/KEY RT*" nằm trong **thư mục con** (nên không thấy ở gốc). Đã sửa lại memory + doc.
- **Thực tế dữ liệu**: đáp án ở file `.xlsx` RIÊNG (không inline); Đề Đọc nhiều `.doc` legacy; audio MP3 **gộp ~100MB theo dải** ("2601-2604.mp3"); Ma trận TOEIC là **Google Sheet** ("tiêu chí trộn đề" — có thể là nguồn thật của luật GEN/MATRIX).
- **Hệ quả tracking**:
  - Parser hiện chỉ chạy fixture `.docx` tự chế (đáp án inline) → **KHÔNG khớp thật**. Parser thật = merge đề + Excel đáp án + convert `.doc`→`.docx` + format đề thật. A3/A4 là việc THẬT.
  - Quy ước audio A2 (`{SetID}_P{Part}_{NN}.mp3` per-câu) **không khớp** MP3 gộp thật → A2 cần thiết kế lại cho dữ liệu thật.
  - Generator (B1/B2/B3/GEN-002) + khung Parser (ImportBatch/idempotent/validation) **không bị ảnh hưởng**, dùng lại được.
  - Cần **mẫu CONTENT** (Sheet ma trận, 1 KEY.xlsx, 1 LT.docx + 1 RT.doc) để spec parser thật — công cụ chỉ đọc được tên file, không đọc nội dung.

### Session 13 -- 2026-06-15 (Claude + Anti — Blueprint-as-Data: sinh đề data-driven)
- **Việc Blueprint-as-Data HOÀN THÀNH** (commit `3db0273` trực tiếp trên `Dat` — Anti sửa uncommitted trên Dat, không có nhánh feature thật; commit thẳng = tương đương FF). Hiện thực luật kiến trúc lõi:
  - `toeic_generator.py`: tách blueprint hardcode → hằng `TOEIC_BLUEPRINT` (chép đúng từng số); thêm `generate_exam(db, structure, title, ...)` lõi data-driven, dispatch theo `part.type` (standalone/grouped/subset_sum). `generate_toeic_exam` → **wrapper mỏng** gọi `generate_exam(TOEIC_BLUEPRINT)` → 25 test cũ giữ nguyên + xanh.
  - **BEHAVIOR-PRESERVING (chốt quan trọng)**: P1-6 difficulty VẪN enforce; **P7 (subset_sum) difficulty trong blueprint chỉ là tài liệu — generate_exam BỎ QUA** (giữ count+topic) → không vỡ nghiệm-duy-nhất P7; MATRIX-002 toàn-đề vẫn xfail.
  - **SPEC-GEN-007 (mới, active)**: test seed Blueprint MINI vào DB → `generate_exam(db, bp.structure, seed=42)` đọc structure từ record → assert counts khớp MINI (2/6/10, total 18). Generator hardcode sẽ ra TOEIC 200 → fail → test chứng minh data-driven THẬT (không tautology).
- **Nghiệm thu (Claude, độc lập)**: đọc toàn bộ generator refactor; verify `TOEIC_BLUEPRINT` khớp số cũ + P7 difficulty không enforce + thứ tự part đổi (1-7) không phá test (chỉ kiểm count/constraint); ranh giới đúng **3 file** (model Blueprint chỉ DÙNG); pytest **26 passed / 2 skipped / 2 xfailed** (×2; 25 test cũ + traceability 4/4 + GEN-005 vẫn xanh); ruff sạch; architecture PASS.
- **Trạng thái spec sau B-as-D**: **24 spec — 19 active / 2 gap / 3 planned** (catalog +1: SPEC-GEN-007; gap còn MATRIX-002 toàn-đề + GRADE-002; planned còn GEN-004, GRADE-003, SCALE-003).
- 🏗️ **Nền đa ngôn ngữ đã sẵn**: thêm VSTEP/HSK = thêm Blueprint record (structure JSON) + bank, KHÔNG sửa thuật toán. Giá trị blueprint TOEIC hiện chép từ hardcode — sẽ đối chiếu/cập nhật theo **Ma trận TOEIC (Google Sheet thật)** sau (là data).

### Đọc được DỮ LIỆU THẬT (15/06, Claude) — cơ chế + findings
- Đạt cấp full link Drive + cho phép truy xuất. Cơ chế CHẠY ĐƯỢC: `PYTHONUTF8=1 python -m gdown` tải về `D:\Dat-Antigravity\drive_input\` (NGOÀI repo) + parse `openpyxl`/`python-docx`; Google Sheet → export `.xlsx`. Bỏ MP3 (~1.5GB). Chi tiết + findings + cấu trúc `.docx`: `docs/du_lieu_input_links.md` (pushed).
- **Ma trận TOEIC (Sheet) = SPEC THẬT, xác nhận việc đã làm**: số câu/part KHỚP ĐÚNG `TOEIC_BLUEPRINT`; luật trộn xác nhận ISOLATE/GEN-003(topic≤20%)/GEN-002/GEN-004/BANK-001. Refine sau: độ khó 25/50/25 **per-skill** (MATRIX-002 nên reframe) + per-part P3/4/6/7 theo CÂU; khái niệm mới Exposure_Count/Overlap_Group. Đáp án = xlsx lưới Câu/Đáp án (khoá Mã đề). Đề = Word **tables+ảnh** (đã map cấu trúc đầy đủ trong doc).

### Session 14 -- 2026-06-15 (Claude + Anti — A3: parse đáp án Excel, bước đầu Parser thật)
- **Việc A3 HOÀN THÀNH** (`feat/parser-answer-key` → merge FF vào `Dat`, commit `d2388e8`, đã push). **SPEC-PARSE-005**:
  - `parser.py`: `parse_answer_key(filepath) -> dict[int,str]` — openpyxl, QUÉT tìm header "Câu"/"Đáp án" (không hardcode dòng), ghép cặp cột, gộp 5 block, chuẩn hoá A/B/C/D. `openpyxl` vào requirements. `make_fixtures` sinh KEY xlsx mô phỏng layout thật; test assert 100 câu/keys 1-100/{A,B,C,D}.
  - PHẠM VI: chỉ parse (merge vào câu hỏi chờ parser `.docx` thật).
- **Nghiệm thu (Claude)**: ranh giới đúng **5 file** (models đóng băng); pytest **27 passed / 2 skipped / 2 xfailed** (×2; traceability 4/4); ruff sạch; architecture PASS. 🎯 **BONUS — verify trên DỮ LIỆU THẬT**: chạy `parse_answer_key` trên `Key LT2601.xlsx` thật → 100 câu, câu1=D/câu100=C khớp đúng data thật. → parser đúng cả trên file đối tác, không chỉ fixture.
- **Trạng thái spec sau A3**: **25 spec — 20 active / 2 gap / 3 planned** (catalog +1: SPEC-PARSE-005).

### Chốt phiên 15/06/2026 (clean-state checklist toàn xanh)
- **Phạm vi phiên** (Sessions 7-14 + đối chiếu dữ liệu thật): B1 · A1 · A2 · B2 · B3 · GEN-002 · Blueprint-as-Data · A3. Suite **15/7/7 → 27/2/2**.
- **Clean-state**: pytest **27 passed / 2 skipped / 2 xfailed / 0 failed**; meta-test traceability 4 passed; `ruff check app/` sạch; `check-architecture.sh` PASS; không file `*.db`; working tree sạch; `Dat` đồng bộ `origin/Dat` @ **7a072aa**.
- **Rà trạng thái (khớp, không bỏ sót)**: `specs.json` **25 spec — 20 active / 2 gap / 3 planned** (gap: MATRIX-002, GRADE-002; planned: GEN-004, GRADE-003, SCALE-003). `feature_list.json`: active = db-migration + ai-grading; in_progress = celery-worker + docx-parser + exam-generator (đã cập nhật evidence); 4 feature not_started — đúng thực tế.
- **Khác**: frontend KHÔNG đụng phiên này (npm build N/A); Celery/Redis không chạy local; dữ liệu input thật + cấu trúc đề đã ghi `docs/du_lieu_input_links.md` (data tải ngoài repo tại `D:\Dat-Antigravity\drive_input`, không commit).
- **Memory**: `du-lieu-input-drive` đã cập nhật đủ findings; `project-strategy-and-harness` + `github-repo` vẫn đúng; không có quyết định dài hạn mới cần thêm.

### Session 15 -- 2026-06-15 (Claude + Anti — PARSE-006: parser .docx table-based THẬT, bước ① lộ trình Parser thật)
- **Việc PARSE-006 HOÀN THÀNH** (Anti commit thẳng `8239a88` trên `Dat` + Claude siết test `c65eb57`; **CHƯA push**). `parser.py` thêm `parse_listening_docx(filepath) -> {set_id, items}` — **parse-only**, KHÔNG ghi DB/đáp án (tách hẳn merge ở bước ②):
  - Duyệt `doc.element.body` THEO THỨ TỰ (dispatch `CT_P`/`CT_Tbl`) giữ Part hiện hành (bẫy python-docx kinh điển — đọc `doc.paragraphs`/`doc.tables` riêng sẽ mất thứ tự); chuẩn hoá Mã đề "LT.2601"→"LT2601"; tách nhóm P3/P4 theo dòng `---` trong cell; ghép wrap option/câu qua nhiều paragraph (state-machine); P1 ghi image index, P2 options rỗng. **Giữ nguyên hàm cũ** (`parse_docx`/`import_file`) → PARSE-001..005 vẫn xanh.
  - Fixture MINI table-based (`make_fixtures.create_real_listening_docx`, sinh qua autouse `main()`): 1 cell P3 chứa **2 nhóm** ngăn bởi `---` + Q8 option A **wrap 2 paragraph**. **SPEC-PARSE-006 active**.
- **Giao thức plan-review chạy tốt**: Anti grounding file thật TRƯỚC khi viết → plan v1 → Claude bắt 1 lỗi quan trọng (fixture MINI quá đơn giản, mỗi cell 1 nhóm + options 1 dòng → KHÔNG test được dash-split + wrap) + 2 nhắc → Anti sửa plan v2 → `DUYỆT PARSE-006` → code.
- **Nghiệm thu (Claude, độc lập)**: đọc diff từng dòng; ranh giới đúng **4 file** (503+/0− → hàm cũ nguyên vẹn; models/grading/harness/conftest KHÔNG đụng); pytest **28 passed / 2 skipped / 2 xfailed** (×2 ổn định); ruff sạch; architecture PASS; traceability 4/4.
  - 🎯 **Verify FILE THẬT `LT2601.docx`** (`D:\Dat-Antigravity\drive_input\LT\`): set_id=LT2601 · P1=6 · P2=25 · P3=13 nhóm/39 câu · P4=10 nhóm/30 câu · **TOTAL=100** — khớp chính xác blueprint TOEIC Listening. Parser đúng cả ngoài fixture.
  - **Lỗ test phát hiện + Claude tự vá** (`c65eb57`): test cũ chỉ **cộng tổng** câu (`part_counts[3]==6`), không bắt được regression gộp 2 nhóm thành 1 → thêm assert P3 == **2 nhóm × 3 câu** (Option 3, đúng tiền lệ Claude tự vá lỗi nhỏ lúc review S6/S7). Logic dash-split đã verify đúng — đây là guard chống regression.
- **Ghi nhận fragility (theo dõi)**: P1 hardcode `1≤q≤3`=paragraph / `≥4`=table grounded theo layout LT2601 — các LT khác (LT2603..2629) nếu khác layout cần rà lại khi parse cả bộ.
- **Sau push (`b7b3cdc`) — sự cố CI + Claude vá** (`2ee9daa`): fixture PARSE-006 dùng `from PIL import Image` (Pillow KHÔNG có trong `requirements.txt`) → CI ubuntu fresh-install đỏ (máy Đạt có sẵn Pillow nên local xanh — **lỗ nghiệm thu của Claude**). Vá: PNG 1x1 sinh bằng stdlib (zlib+struct), không thêm dep. **Bài học** (đã ghi memory): nghiệm thu phải **grep import vs requirements**, pytest local xanh KHÔNG đủ vì local env có thể có sẵn package ngoài requirements.
- **Trạng thái spec sau PARSE-006**: **26 spec — 21 active / 2 gap / 3 planned** (catalog +1: SPEC-PARSE-006; gap vẫn MATRIX-002 + GRADE-002; planned vẫn GEN-004, GRADE-003, SCALE-003).

### Session 16 -- 2026-06-15 (Claude + Anti — PARSE-007: merge đáp án + import, BUG hash câu hỏi bắt được lúc nghiệm thu)
- **Việc PARSE-007 HOÀN THÀNH** (`feat/parser-listening-merge` → FF vào `Dat`; code `c8948fa` + vòng vá `a6fdf99`; đã push). SPEC-PARSE-007 active. `import_listening_set(db, docx_path, key_path, audio_dir=None)`:
  - Gọi `parse_listening_docx` + `parse_answer_key`; stamp `set_id` lên mọi item/question; gán `reference_answer` theo SỐ CÂU; validation all-or-nothing (thiếu/đáp-án-lạ → `ImportError`, 0 ghi); set_id docx khớp KEY (raise nếu lệch); `ImportBatch` + `save_parsed_items` (status='draft', bọc try/except + `db.rollback()`).
- **Giao thức plan-review (vòng 1)**: Anti grounding cặp file thật TRƯỚC → plan v1 → Claude bắt 2 lỗi (fixture KEY 1-block làm `parse_answer_key` raise vì cần ≥2 cột "Câu"; thiếu try/except rollback) → plan v2 → `DUYỆT` → code. Bẫy GROUP hash (nhóm Listening passage/audio=None → mọi nhóm cùng part trùng hash) đã được nêu trong brief + vá ở plan (gộp `q_contents` + `set_id`) → 23 nhóm thật không trùng.
- **🎯 Nghiệm thu Claude PHÁT HIỆN BUG trên dữ liệu THẬT (điểm quan trọng nhất phiên)**: fixture test + suite xanh, NHƯNG chạy `import_listening_set` trên cặp THẬT `LT2601.docx` + `Key LT2601.xlsx` → chỉ ghi **75/100 câu** (mất 25 câu P1/P2). Nguyên nhân: `calculate_question_hash` không phân biệt câu P1/P2 (content giống hệt "Mark your answer" + options rỗng, chỉ khác đáp án → 25 câu P2 chia 4 letter → trùng hash → nuốt 21). Fixture MINI không lộ (chỉ 2 câu P2 khác letter). **Bài học: pytest fixture xanh KHÔNG đủ — verify file thật là BẮT BUỘC.**
- **Vòng vá** (`a6fdf99`): đưa `set_id`+`number` vào `calculate_question_hash`, `set_id` vào `calculate_group_hash` (path cũ không có 2 field → default '' → tương thích ngược, PARSE-001..006 xanh); fixture KEY ép Q5=Q6="A" để LỘ bug (hash cũ mất 1 câu → test đỏ; mới → đủ). **Claude verify lại file thật: 100/100 câu + 23/23 nhóm, 0 skip, idempotent** ✓.
- **Nghiệm thu cuối (Claude, độc lập)**: pytest **29/2/2** ×2; ruff sạch; architecture PASS; traceability 4/4; ranh giới code đúng 4 file (parser/make_fixtures/test/specs — **KHÔNG đụng models**).
- ⚠️ **2 lệch quy trình của Anti phiên này** (vô hại lần này nhưng nhắc lần sau): (1) **push cả 4 commit trước khi Claude nghiệm thu** (lẽ ra chờ); (2) tự sửa `claude-progress.md` + `session-handoff.md` — **file của Claude** (lặp lỗi S7; lần này nội dung khá chính xác nên Claude chỉ chỉnh-bổ sung cho đúng lịch sử thay vì hoàn nguyên).
- **Trạng thái spec sau PARSE-007**: **27 spec — 22 active / 2 gap / 3 planned** (catalog +1: SPEC-PARSE-007; gap vẫn MATRIX-002 + GRADE-002; planned vẫn GEN-004, GRADE-003, SCALE-003).

### Session 17 -- 2026-06-15 (Claude + Anti — PARSE-008: converter .doc→.docx, bước ③; Anti tuân thủ ĐÚNG quy trình)
- **Việc PARSE-008 HOÀN THÀNH** (`feat/parser-doc-converter` → FF vào `Dat`, code `37c25cc` + Claude vá lint `cfd5431`; đã push). SPEC-PARSE-008 active. `parser.py` thêm `convert_doc_to_docx(filepath, out_dir=None) -> str`:
  - `.docx` → passthrough; `.doc` → `soffice --headless --convert-to docx` (subprocess list-args, KHÔNG shell=True); cache (đích `.docx` đã có → bỏ qua); soffice thiếu (`shutil.which` + fallback path Windows) → `FileNotFoundError` kèm hướng dẫn cài; convert fail → RuntimeError. Chỉ stdlib (os/shutil/subprocess), KHÔNG thêm dep.
  - PHẠM VI: CHỈ converter — CHƯA parse Reading (cấu trúc P5/6/7, task sau).
- **Giao thức plan-review**: Anti grounding (phát hiện máy Đạt CHƯA cài LibreOffice) → plan v1 → Claude bắt lỗi test (hàm check `os.path.exists` ở đầu → test cache/missing-tool phải tạo `dummy.doc` thật + dùng `tmp_path`) → plan v2 → `DUYỆT` → code.
- **✅ Anti tuân thủ ĐÚNG quy trình lần này** (sau nhắc S16): code+push trên NHÁNH FEATURE, CHỜ Claude nghiệm thu (KHÔNG merge Dat trước); KHÔNG đụng file nhật ký của Claude. Lời nhắc có tác dụng.
- **Nghiệm thu (Claude, độc lập)**: đọc `convert_doc_to_docx` từng dòng; ranh giới đúng **3 file** (parser/test/specs — KHÔNG đụng models); pytest **30/2/2** ×2; ruff sạch; architecture PASS; grep import xác nhận không dep mới. Bắt F401 (`import shutil` thừa trong test) → Claude tự vá `cfd5431`.
- ✅ **REAL .doc conversion ĐÃ VERIFY** (15/06, Đạt cài LibreOffice 26.2): `convert_doc_to_docx` round-trip 1 `.doc` nhị phân thật → `.docx` giữ đủ **15 tables**, python-docx đọc được (soffice headless qua fallback path `C:\Program Files\LibreOffice\program\soffice.exe`; `soffice` không cần trên PATH). CI test vẫn mock (passthrough/missing-tool/cache). File RT*.doc đối tác sẽ chạy khi làm parser Reading.
- **Trạng thái spec sau PARSE-008**: **28 spec — 23 active / 2 gap / 3 planned** (catalog +1: SPEC-PARSE-008; gap MATRIX-002 + GRADE-002; planned GEN-004, GRADE-003, SCALE-003).

### Session 18 -- 2026-06-15 (Claude + Anti — PARSE-009: parser Reading RT*.docx; 2 BUG bắt lúc nghiệm thu)
- **Việc PARSE-009 HOÀN THÀNH** (`feat/parser-reading-docx` → FF vào `Dat`, code `4668e44` + vá `0712a8a`; đã push). SPEC-PARSE-009 active. `parse_reading_docx(filepath) -> {set_id, items}` — parse-only (như PARSE-006), KHÔNG audio. Reading đánh số **1-100** (P5 1-30 câu đơn; P6 31-46 = 4 đoạn×4 chỗ trống; P7 47-100 passages đơn/đôi/ba + ảnh). Đáp án ở Key RT*.xlsx (merge là task sau).
- **Giao thức plan-review**: Anti grounding RT2605 (dry-run) → plan v1 → Claude bắt fixture đánh số 101+ trái grounding (Reading thật 1-100) → v2 → DUYỆT.
- **🎯 2 BUG bắt lúc nghiệm thu Claude (đều FIXTURE-INVISIBLE, lộ nhờ verify dữ liệu THẬT + check process)**:
  1. **Treo vô hạn**: test chạy ~24 phút không xong → Đạt hỏi. Claude check process (python ngốn 1448s CPU) → `parse_reading_docx` inner loop P6/7 KHÔNG tăng `j` ở nhánh CT_P → quay mãi. Vá: 1 `j += 1` vô điều kiện cuối loop.
  2. **Mất options 30/70 câu nhóm**: sau khi hết treo, Claude verify RT2605 thật → 100 câu NHƯNG 30 câu ≠4 options (Anti dry-run chỉ ĐẾM câu, không kiểm options). 3 mode: option-A inline cùng dòng số câu (3 opts); cả câu+4 options trong 1 paragraph (0 opts → cần `re.DOTALL` + split); paragraph trích dẫn xen giữa câu↔options (sandwich). Vá: DOTALL + `re.split` theo marker `(A-D)` (trên dòng câu + paragraph option) + append-content khi `opt_count==0`. GIỮ nhánh 4x2 table (không regress 70 câu cũ).
- **Nghiệm thu cuối (Claude, độc lập)**: đọc logic option mới; verify RT2605 thật → **100 câu, 0 câu thiếu options** (Q39/43/59/71 — các ca lỗi cũ — giờ đủ A-D); pytest **31/2/2** ×2; ruff sạch (10 F841 dọn); architecture PASS; ranh giới 4 file KHÔNG đụng models.
- ✅ **Anti tuân thủ quy trình cả 2 vòng** (code+push NHÁNH FEATURE, chờ nghiệm thu, không đụng file nhật ký Claude).
- **Bài học**: Anti dry-run/self-report hay ĐẾM (số câu) chứ không kiểm HOÀN CHỈNH (options đủ 4, có terminate). Nghiệm thu PHẢI verify dữ liệu thật bằng metric ĐÚNG (completeness), + check process (CPU) khi nghi treo.
- **Trạng thái spec sau PARSE-009**: **29 spec — 24 active / 2 gap / 3 planned** (catalog +1: SPEC-PARSE-009; gap MATRIX-002 + GRADE-002; planned GEN-004, GRADE-003, SCALE-003).

### Session 19 -- 2026-06-15 (Claude + Anti — PARSE-010: merge+import Reading; MỐC pipeline Parser thật ĐỦ Nghe+Đọc→bank)
- **Việc PARSE-010 HOÀN THÀNH** (`feat/parser-reading-merge` → FF vào `Dat`, commit `e2941f3`; đã push). SPEC-PARSE-010 active. Tổng quát hoá merge+import:
  - `import_exam_set(db, docx_path, key_path, exam_type, audio_dir=None)` — gom logic merge+validate+ImportBatch+`save_parsed_items`; dispatch parser theo `exam_type` (listening→`parse_listening_docx`, reading→`parse_reading_docx`); set_id match tổng quát `(?i)(LT|RT)\.?\s*(\d+)`. `import_listening_set` → **wrapper mỏng GIỮ nguyên chữ ký** (PARSE-007 xanh); `import_reading_set` wrapper mới.
- **Grounding completeness ĐÚNG metric** (rút kinh nghiệm S18): Anti ground RT2605+KEY RT.2605 (in-memory DB) → 100/100 câu, mọi câu draft+ABCD, 20 nhóm, 0 lỗi, idempotent. Anti tuân thủ quy trình (nhánh feature, chờ nghiệm thu, không đụng file Claude, không F841).
- **Nghiệm thu (Claude, độc lập) — verify CẢ 2 path + coexist trên dữ liệu THẬT**:
  - LISTENING qua wrapper (**regression check refactor**): LT2601 → 100 câu/23 nhóm, idempotent — **refactor KHÔNG phá Listening**.
  - READING: RT2605 → 100 câu/20 nhóm, idempotent.
  - **Coexist**: nạp cả LT2601 + RT2605 vào 1 DB → **200 câu / 43 nhóm / 0 câu thiếu đáp án** (khác set_id nên cùng tồn tại trong bank).
  - pytest **32/2/2** ×2; ruff sạch; architecture PASS; ranh giới 4 file KHÔNG đụng models.
- 🏗️ **MỐC: pipeline Parser thật ĐỦ Nghe + Đọc → bank** (trên dữ liệu đối tác THẬT: parse `.docx`/`.doc` + merge đáp án xlsx + ghi bank idempotent). Còn lại track Parser: chỉ ④ audio MP3 gộp.
- **Trạng thái spec sau PARSE-010**: **30 spec — 25 active / 2 gap / 3 planned** (catalog +1: SPEC-PARSE-010; gap MATRIX-002 + GRADE-002; planned GEN-004, GRADE-003, SCALE-003).

### Session 20 -- 2026-06-15 (Claude + Anti — PARSE-011: link audio cấp file; 🎉 TRACK PARSER HOÀN TẤT)
- **Việc PARSE-011 HOÀN THÀNH** (`feat/parser-audio-link` → FF vào `Dat`, commit `ef2ced4`; đã push). SPEC-PARSE-011 active. `find_audio_file(audio_dir, set_id) -> (selected, ambiguous_list)` + tích hợp `import_exam_set` (listening + audio_dir): map set→file MP3 gộp theo TÊN (dải/đơn, regex anchored), set `audio_url` cấp FILE trên mọi item Nghe; **NON-FATAL** (không file → None); report `audio_linked` + `audio_ambiguous`.
- **QUYẾT ĐỊNH CHỐT (Đạt+Claude): KHÔNG cắt audio** — ma trận không yêu cầu (đã quét MatranTOEIC.xlsx), đối tác không có timestamp, models đóng băng, cắt cần dep mới. Chèn cả file như đối tác đưa. Giữ PARSE-002 synthetic (per-unit fail-fast) riêng.
- **Grounding**: Anti list 15 tên MP3 thật (không tải 1.5GB) — 3 file đầu ĐÈ DẢI (2601-2604 / 2602-2605 / 2603-2606).
- **Nghiệm thu (Claude, độc lập)**: đọc `find_audio_file`; pytest **33/2/2** ×2; ruff sạch; architecture PASS; ranh giới 4 file không models; **không dep mới**. **Verify mapping trên 15 tên file THẬT**: 15/15 set có audio; ambiguity bắt đúng CHỈ LT2603 (3 file) + LT2605 (2 file); còn lại khớp đúng 1 file.
- ✅ Anti tuân thủ quy trình.
- **Trạng thái spec sau PARSE-011**: **31 spec — 26 active / 2 gap / 3 planned** (catalog +1: SPEC-PARSE-011).
- 🎉 **TRACK PARSER HOÀN TẤT**: pipeline Ra đề THẬT = parse `.docx` Nghe (006) + merge+import Nghe (007) + convert `.doc` (008) + parse Đọc (009) + merge+import chung (010) + link audio (011). Verify dữ liệu đối tác THẬT: LT2601 + RT2605 = 200 câu + audio vào bank, idempotent, coexist. `feature_list.docx-parser` → **active**.

### Chốt phiên 15/06/2026 — CUỐI (marathon Sessions 15-20: PARSE-006→011, 🎉 track Parser HOÀN TẤT)
- **Phạm vi phiên**: PARSE-006 (parse Nghe) · CI-Pillow fix (`2ee9daa`) · PARSE-007 (merge+import Nghe) · PARSE-008 (convert .doc) · PARSE-009 (parse Đọc) · PARSE-010 (merge+import chung) · PARSE-011 (link audio). Suite **27/2/2 → 33/2/2**.
- **Clean-state (toàn xanh)**: pytest **33 passed / 2 skipped / 2 xfailed / 0 failed**; traceability **4 passed**; `ruff check app/` sạch; `check-architecture.sh` PASS; KHÔNG file `*.db`; working tree sạch; `Dat` đồng bộ `origin/Dat` @ **fe238cf** (+ commit chốt sổ này).
- **Rà specs.json (khớp, không bỏ sót)**: **31 spec — 26 active / 2 gap / 3 planned** (gap: MATRIX-002, GRADE-002; planned: GEN-004, GRADE-003, SCALE-003). PARSE-006..011 đều active; traceability xanh xác nhận spec↔test khớp.
- **Rà feature_list.json**: active = db-migration + ai-grading + **docx-parser (mới active phiên này)**; in_progress = celery-worker + exam-generator; not_started = auth-api, exam-admin-api, exam-room-ui, exam-validator. Ghi đầy đủ, không thiếu.
- 🎉 **Thành tựu**: pipeline Ra đề THẬT hoàn tất — parse `.docx`/`.doc` Nghe+Đọc + merge đáp án `.xlsx` + link audio MP3 → bank; verify dữ liệu đối tác thật (LT2601 + RT2605 = 200 câu/43 nhóm/**0 thiếu đáp án** + audio, idempotent, coexist). **6 lần verify dữ liệu thật bắt 3 bug ẩn** fixture không lộ.
- **Quyết định dài hạn (đã ghi memory `audio-no-cut-file-level`)**: audio để CẢ FILE, KHÔNG cắt.
- **Khác**: frontend KHÔNG đụng (npm build N/A); Celery/Redis không chạy local; hạ tầng máy thêm LibreOffice 26.2; nhánh remote `feat/parser-audio-link` đã merge — chờ xoá (tuỳ Đạt). 3 memory nghiệm thu/brief đã ghi phiên này.

### Session 21 -- 2026-06-15 (Claude + Anti — A5: Bank-Admin API, router REST thật đầu tiên)
- **Dọn nhánh leftover**: xoá remote `feat/parser-audio-link` (đã merge từ S20) + prune. Remote còn `Dat`/`main` sạch.
- **Việc A5 HOÀN THÀNH** (`feat/bank-admin-api` → FF vào `Dat`, commit `696201e`, đã push; nhánh đã xoá local+remote). SPEC-BANK-003 active. Router REST **đầu tiên** của dự án (`app/api/` và `app/schemas/` trước đó rỗng):
  - `app/api/bank.py` prefix `/api/v1/bank`: `GET /questions` (filter part/status/topic/difficulty + phân trang, chỉ `exam_id IS NULL`), `PATCH /questions/{id}` (sửa bank item, 404 cho clone/không tồn tại), `POST /questions/approve` (bulk draft→approved + **propagate nhóm cha**), `GET /stats` (đếm part×status đối chiếu `TOEIC_BLUEPRINT`).
  - `app/services/bank_admin.py` (logic thuần, API mỏng) + `app/schemas/bank.py` (Pydantic v2). `main.py` đăng ký router.
  - **Propagate nhóm cha là ĐÚNG & CẦN**: parser ghi cả Question lẫn QuestionGroup `status="draft"`, generator lọc CẢ HAI `==approved` → không lật nhóm thì câu approved vẫn không sinh được.
- **Giao thức plan-review**: Anti grounding → plan v1 → Claude bắt **3 lỗi test** (tautology: conftest seed toàn bộ approved nên filter draft rỗng; TestClient bịt DB sai vì `:memory:` tách connection; stats ordering) → plan v2 → `DUYỆT A5` → code nhánh feature → chờ nghiệm thu.
- **Nghiệm thu (Claude, độc lập)**: đọc diff từng dòng; pytest **34/2/2** ×2; ruff sạch; architecture PASS (gồm "DB sessions managed correctly in API layers"); traceability 4/4; **không dep mới** (httpx đã có); models KHÔNG đụng.
  - **2 file ngoài plan — đều chấp nhận**: `database.py` (+1 dòng trống, vô hại); `conftest.py` đổi sang `StaticPool` — **ngoài plan NHƯNG cần thiết thật** (Claude verify thực nghiệm: bỏ StaticPool → test A5 gãy `no such table: questions` do split connection cross-thread `:memory:` dưới TestClient; an toàn cho 33 test cũ). Pattern chuẩn FastAPI test. → nhắc Anti lần sau flag khi tự thêm file ngoài plan.
  - Self-report Anti "38/38 passed" = gộp tổng (34+2+2) nói lỏng; số thực 34/2/2 đúng kỳ vọng.
- **Ghi chú thiết kế (không chặn)**: `QuestionUpdate` cho phép PATCH `status` trực tiếp → patch status=approved KHÔNG propagate nhóm; `/approve` là đường chuẩn để duyệt (nên doc/TODO sau).
- **Trạng thái spec sau A5**: **32 spec — 27 active / 2 gap / 3 planned** (catalog +1: SPEC-BANK-003; gap vẫn MATRIX-002 + GRADE-002; planned vẫn GEN-004, GRADE-003, SCALE-003). `feature_list.exam-admin-api` → **in_progress** (xong nửa bank-admin; còn Exam CRUD + auth).

### Session 22 -- 2026-06-15 (Claude — DEMO TOEIC end-to-end: Exam API + frontend + seed dữ liệu thật)
- **Bối cảnh**: sếp cần BẢN DEMO TOEIC trình trong vài giờ. Đạt chốt: dồn lực TOEIC trước (B1/Chấm/đầu mục khác giữ nguyên), cần API + giao diện "dùng được, không cần đẹp". 2 quyết định (Đạt chốt): **Claude code trực tiếp** (bỏ vòng Anti cho kịp deadline) + **nội dung đề THẬT** LT2601+RT2605 (backfill).
- **Rà soát phát hiện 2 chốt chặn**: (1) chưa có API sinh đề/xem đề (chỉ có bank.py); (2) sinh đề từ dữ liệu thật FAIL vì parser gán cứng mọi câu `difficulty="medium"`, `topic=None` → generator đòi đa dạng topic → raise. (Phân tích kỹ: **độ khó KHÔNG chặn** — generator có shortfall-fill; **topic mới là chốt chặn** — all-None = 100% một topic > cap.)
- **Backend (commit `44f638b`, SPEC-EXAM-001 active)**: `app/api/exams.py` + `app/services/exam_admin.py` + `app/schemas/exam.py` — `POST /api/v1/exams/generate` (wrap `generate_toeic_exam`), `GET /api/v1/exams`, `GET /api/v1/exams/{id}` (đề tổ chức theo part → standalone/groups → questions + options/audio/ảnh). `main.py` đăng ký router + mount `/audio` (tùy chọn qua `AUDIO_DIR`). Test `tests/test_specs_exam.py` (TestClient, sinh 200 câu, 7 part). Models KHÔNG đụng.
- **Seed (`scripts/seed_toeic_demo.py`)**: import THẬT LT2601 (`drive_input/LT`) + RT2605 (`drive_input/RT/ĐỀ ĐỌC`, đã .docx) + key `.xlsx` → **backfill độ khó/topic khớp blueprint** (distinct topic mỗi nhóm + ma trận độ khó per-part) → approve 200 câu → sinh thử 1 đề. Idempotent. DB demo SQLite (`backend/demo_toeic.db`, gitignored).
- **Frontend (Next.js 16 — đọc docs bundled trước: `params` async)**: `src/lib/api.ts` client; `/` landing, `/admin` (bảng tồn kho /stats + nút Sinh đề + list đề), `/exam/[id]` (server component await params + client `ExamView` render theo part, options, **đáp án đúng tô xanh**).
- **VERIFY end-to-end trong trình duyệt (preview)** trên dữ liệu THẬT: landing → /admin (7 part "✓ đủ", fetch backend qua CORS) → nút Sinh đề (count 1→2, đề mới hiện) → /exam/1 (Part 1 câu ảnh, Part 2 "Mark your answer", **Part 5 câu thật + 4 options + đáp án đúng**, 200 câu). Console 0 lỗi. Audio/ảnh chưa phát (MP3 ~1.5GB chưa tải; ảnh chưa trích) — non-blocking, có đường bật qua `AUDIO_DIR`.
- **Clean-state**: backend **35 passed / 2 skipped / 2 xfailed**; ruff (app/+scripts/) sạch; architecture PASS; traceability 4/4. Frontend: lint sạch cho `src/app`+`src/lib` (3 lỗi `any` còn lại CHỈ ở `src/hooks` phòng-thi — không đụng theo yêu cầu). Hướng dẫn chạy: `docs/demo_toeic_huong_dan.md`.
- **Trạng thái spec sau demo**: **33 spec — 28 active / 2 gap / 3 planned** (catalog +1: SPEC-EXAM-001). `feature_list.exam-admin-api` evidence cập nhật (thêm exam API); vẫn in_progress (còn auth + exam edit/release CRUD).
- **Bổ sung cùng phiên (commit `b61420d`) — đề "đầy đủ như thật" + bảo mật đáp án** (theo phản hồi Đạt: đề chỉ nên có câu hỏi; phải đủ ảnh + audio):
  - **Ảnh Part 1 THẬT**: `app/services/docx_images.py` trích ảnh nhúng từ `.docx` Nghe (resolve drawing→blob, bỏ ảnh ví dụ/header), map Part 1→câu (6 ảnh); seed link `image_url=/static/...`, backend mount `/static`. (Đồ hoạ P3/4/7 có trích được nhưng chưa map per-câu — Question không có cột số câu; bước sau.)
  - **Audio Nghe THẬT**: tải riêng file MP3 gộp LT2601 ("2601 - 2604.mp3" ~105MB, id `15HV-VV...` qua gdown `skip_download` lấy ID) → `drive_input/audio/`; seed link qua `find_audio_file`; exam detail trả `audio_url` cấp Part; frontend 1 player/part Nghe (audio ~45', KHÔNG cắt). Backend mount `/audio`.
  - **Ẩn đáp án (đề = câu hỏi)**: `GET /exams/{id}` mặc định KHÔNG trả `reference_answer`; `?include_answers=true` cho giáo viên (có TODO gate auth). Frontend nút toggle "Hiện đáp án (giáo viên)". test cập nhật assert ẩn/hiện.
  - **Verify trình duyệt**: 6/6 ảnh Part 1 load, audio 45:37 phát được, mặc định 0 đáp án lộ, toggle giáo viên → 200/200 câu có đáp án (P1/P2 không options hiện "Đáp án đúng: X").
- 🎉 **MỐC: TOEIC chạy được END-TO-END có giao diện** — nạp đề thật → bank → sinh đề 200 câu → xem trên web (ảnh + audio + câu hỏi thật, ẩn đáp án), dùng nội dung đối tác thật.

### Session 23 -- 2026-06-15 (Claude — merge lên main + chuẩn bị & test deploy cloud)
- **Merge `Dat` → `main`**: FF (57 commits) → `origin/main` = `origin/Dat` = **`4350868`**, đã push. Toàn bộ code (parser/generator/A5/demo/deploy) đã lên main.
- **Deploy: Đạt chọn CLOUD**. Máy KHÔNG có Docker/cloud CLI → kiến trúc **Backend → Render (Python native), Frontend → Vercel**, deploy từ GitHub. Tôn trọng luật **KHÔNG commit data đối tác**: backend tự tải data từ Drive lúc build rồi seed.
  - `backend/scripts/cloud_bootstrap.py`: tải 5 file nguồn theo Drive file-id → seed (parse+backfill+ảnh+approve+generate); idempotent. `seed_toeic_demo` nhận path qua env. `main.py` CORS theo env `ALLOWED_ORIGINS`. `requirements`: +gdown. `render.yaml`: bootstrap ở **build** (bake data → start nhanh). Guide: `docs/deploy_cloud_huong_dan.md`.
  - **ĐÃ TEST tại chỗ**: cloud_bootstrap tải nguồn + seed 200 câu + 6 ảnh + audio OK + idempotent; **frontend prod `npm run build` PASS + `npm start`** phục vụ / và /admin HTTP 200; backend 35/2/2, ruff sạch.
- ⚠️ **CHƯA deploy thật lên internet**: bước cuối cần **tài khoản Render + Vercel của Đạt** (login bằng GitHub) — Claude không có credentials. Đạt làm theo `docs/deploy_cloud_huong_dan.md` (A: Render → B: Vercel → C: nối CORS); hoặc cấp Render API key + Vercel token để Claude thử deploy bằng CLI.

## Next Steps
- ✅ **Track Parser XONG** · ✅ **A5 Bank-Admin API XONG** · ✅ **DEMO TOEIC end-to-end XONG** (Session 22) · ✅ **Merge main + deploy config sẵn sàng + test** (Session 23). **Còn lại: Đạt bấm deploy Render+Vercel theo guide.**
- **Ưu tiên TOEIC (đánh bóng demo, nếu sếp cần thêm):**
  - **Audio**: tải MP3 gộp về 1 thư mục → seed + backend với `AUDIO_DIR` → player phát được trong `/exam/[id]`.
  - **Ảnh Part 1/Part 7**: trích ảnh từ `.docx` ra file tĩnh + set `image_url` thật (hiện chỉ hiển thị chỉ số ảnh).
  - **auth-api**: bịt các endpoint đang mở (bank + exams hiện chỉ có TODO marker) trước khi đưa ra ngoài.
  - **UI duyệt bank (A6)**: nút approve draft→approved trên web (hiện duyệt qua API/seed).
- **Để sau (đã thống nhất giữ nguyên):** B1/VSTEP·HSK đa ngôn ngữ; phân hệ Chấm (GRADE-002/003, Celery); generator gaps (MATRIX-002 toàn-đề vướng P7 nghiệm-duy-nhất, GEN-004 độ trùng lô); SCALE.
- 💡 Đối chiếu `TOEIC_BLUEPRINT` ↔ Ma trận TOEIC Sheet thật → cập nhật giá trị (data).
  - ⚠️ **MATRIX-002 toàn-đề vướng**: P7 nghiệm subset-sum DUY NHẤT (B3) → độ khó P7 cố định (4E/30M/20H) → toàn đề lệch. Cần rebalance conftest P7 difficulty / nới nghiệm P7; và reframe **per-skill** theo Ma trận thật.
  - 💡 Đối chiếu **`TOEIC_BLUEPRINT` ↔ Ma trận TOEIC Sheet thật** → cập nhật giá trị (data, không sửa code).
- (Tuỳ chọn) hardening PARSE-002: bắt buộc block Listening phải có trường Audio.
- Cân nhắc thêm PostgreSQL service vào `ci.yml` để tự động test `alembic upgrade head` (hiện CI chỉ chạy pytest SQLite — không bắt được lỗi migration PG-specific).
- Khi có CI check cho `main`: bật "Require status checks" trong branch protection (nếu repo chuyển public/nâng gói).
- Chờ sếp xác nhận quy đổi độ khó câu→nhóm (±1 trong dung sai ±2). **(Quy ước MP3 KHÔNG chờ đối tác — đã chốt nội bộ ở A2.)**
