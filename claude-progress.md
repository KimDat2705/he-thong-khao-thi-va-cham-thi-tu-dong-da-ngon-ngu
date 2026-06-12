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

## Next Steps
- Anti lập plan 0c (`feat/alembic-foundation`) — việc NHẠY CẢM NHẤT chuỗi setup: PR duy nhất được đụng `backend/app/models/` (Alembic init + bảng blueprints/import_batches + cột content_hash/source_question_id). Review plan kỹ nhất từ trước tới nay; sau merge 0c thì models ĐÓNG BĂNG.
- Sau 0c: B1 (`feat/generator-hardening`) trong lúc chờ quy ước MP3 cho A2.
- Khi nào lên CI check đầu tiên cho nhánh main: quay lại branch protection bật "Require status checks" (nếu repo chuyển public/nâng gói).
- Chờ chốt với đối tác: quy ước tên file MP3 (chặn A2); chờ sếp xác nhận quy đổi độ khó câu→nhóm (±1 trong dung sai ±2).
