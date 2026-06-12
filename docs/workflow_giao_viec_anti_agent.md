# WORKFLOW BÀN GIAO CHO AI AGENT — Toàn bộ Phân hệ Ra đề (Setup + Track A + Track B)

> **Người giao việc:** Đạt (KimDat2705) · **Phạm vi của brief này:** TOÀN BỘ phân hệ Ra đề = Setup chung (0a/0b/0c) + Track A (Parser & Ngân hàng) + Track B (Generator & Validator).
> **Kỷ luật track vẫn giữ nguyên:** mỗi PR chỉ thuộc MỘT track (mục 2.3) — trộn 2 track trong 1 PR sẽ bị bác. Phân hệ Chấm AI (grading) NGOÀI phạm vi — không đụng.
> **Repo:** `D:\Dat-Antigravity\HeThongKhaoThiVaChamThiTuDongDaNgonNgu(AI-Powered)` · nhánh chính: `main` · milestone: **M2 — Ra đề tiếng Anh, deadline 17/06/2026**

---

## 1. Ngữ cảnh dự án (đọc trước khi làm bất kỳ việc gì)

Hệ thống khảo thí & chấm thi AI đa ngôn ngữ (EN trước, CN sau). Trọng tâm hiện tại: **phân hệ Ra đề tiếng Anh** — pipeline: file Word/Excel/MP3 thô → Parser → Ngân hàng câu hỏi → Generator → 100 đề TOEIC + 100 đề B1 VSTEP.

**Tài liệu nguồn sự thật trong repo (đọc theo thứ tự):**
1. `docs/kien_truc_phan_he_ra_de_tieng_anh.md` — kiến trúc phân hệ, thiết kế module parser, API contract, blueprint. **Mọi quyết định thiết kế lấy từ đây.**
2. `specs/specs.json` — catalog 23 spec (Harness Engineering). **Mỗi việc dưới đây gắn với spec ID cụ thể.**
3. `specs/README.md` — quy ước spec/test, vòng đời trạng thái.
4. `docs/phan_chia_cong_viec_github.md` — quy ước Git và ranh giới 2 track.
5. `D:\Dat-Antigravity\NOTE\GEMINI.md` — quy trình SDLC 7 bước của Antigravity (`/spec → /plan → /build → /test → /review → /code-simplify → /ship`). **Vị trí hiện tại của dự án: bước 1 (/spec) và 2 (/plan) đã xong** — artifact chính là các tài liệu 1–4 ở trên. Brief này thuộc đầu bước 3 (/build), thực thi theo giao thức mục 2.4.
6. Bộ file harness ở root repo — TUÂN THỦ trong suốt quá trình làm: `AGENTS.md` (luật chung: No-Hallucination, Handoff Duty), `quality-document.md` (chuẩn code — code MỚI dùng SQLAlchemy 2.0 style `select(...)`, không `db.query(...)`; mock Gemini trong test), `evaluator-rubric.md` (rubric mà PR của bạn sẽ bị chấm), `clean-state-checklist.md` (chạy trước khi kết thúc phiên), `feature_list.json` (cập nhật status/evidence/testedAt trung thực khi feature đổi trạng thái — chỉ ghi "active" khi có test pass).

**Hiện trạng code (đã kiểm chứng 11/06/2026):**
- Backend FastAPI tại `backend/`: models SQLAlchemy (users, exams, question_groups, questions, submissions, submission_details, grades), generator TOEIC bản đầu (`app/services/toeic_generator.py`), grader, Celery đã cấu hình nhưng chưa nối API.
- Test suite: `cd backend && python -m pytest tests -q` → **15 passed · 7 skipped · 7 xfailed · 0 failed**. Trạng thái này là BASELINE — mọi PR không được làm xuất hiện `failed`.
- Parser **chưa tồn tại** — 4 test `tests/test_specs_parser.py` đang skip, docstring của chúng là HỢP ĐỒNG phải thỏa.
- Alembic **chưa có** — DB đang tạo bằng `create_all()` trong `app/main.py`.

## 2. Luật làm việc (bắt buộc, không thương lượng)

### 2.1 Git & PR
- KHÔNG push trực tiếp lên `main`. Mỗi việc: nhánh `feat/<tên>` → PR → Đạt review/duyệt (mời sếp review thêm các PR nền nếu tham gia) → squash merge.
- PR nhỏ hơn ~400 dòng diff. Commit theo conventional commits: `feat(parser): ...`, `test(parser): ...`, `chore(ci): ...`.
- Mô tả PR ghi rõ spec liên quan, ví dụ: `Closes #5 — SPEC-PARSE-001 planned→active`.
- Rebase/merge `main` vào nhánh đang làm mỗi đầu buổi.

### 2.2 Harness Engineering (luật chất lượng)
- 1 ràng buộc = 1 spec trong `specs/specs.json` = test tên `test_SPEC_<DOMAIN>_<NNN>_*`.
- Khi code làm một spec đạt: **trong cùng PR** phải (a) gỡ marker `skip`/`xfail` của test tương ứng, (b) đổi `status` spec trong `specs.json` thành `active`. Meta-test `tests/test_specs_traceability.py` sẽ fail nếu khai báo lệch.
- KHÔNG sửa: code/test của phân hệ Chấm (`toeic_grader.py`, `ai_grading.py`, `workers/tasks.py`, `test_specs_grading.py`, `test_toeic_grader.py`), `system_architecture.html` (tài liệu v1 đông lạnh). `conftest.py` chỉ được sửa qua PR nền riêng được Đạt duyệt (cần cho B2/B3 — xem ghi chú trong việc đó).
- KHÔNG sửa test để "cho qua". Chỉ được cập nhật assertion khi hành vi đúng thay đổi CÓ CHỦ ĐÍCH (vd Part 7 trong B2) và phải giải thích trong mô tả PR.
- Suite phải exit 0 sau mỗi PR. `xfail`/`skip` hợp lệ; `failed` = chặn merge.

### 2.3 Ranh giới file — mỗi PR chỉ thuộc MỘT track
```
TRACK A (Parser & Ngân hàng):
  backend/app/services/parser/**            (tạo mới toàn bộ)
  backend/app/api/bank.py · app/schemas/bank.py (tạo mới)
  backend/tests/test_specs_parser.py · tests/test_bank_api.py (mới) · tests/fixtures/**
  frontend/src/app/admin/**  ·  prompts/en/**

TRACK B (Generator & Validator):
  backend/app/services/toeic_generator.py · exam_generator.py (mới) · exam_validator.py (mới)
  backend/app/api/toeic.py · app/api/exams.py (mới) · app/workers/generation_tasks.py (mới)
  backend/tests/test_specs_generation.py · test_specs_bank.py · test_toeic_generator.py
  backend/tests/test_exam_validator.py (mới)

NỀN CHUNG (chỉ sửa qua PR riêng, nêu rõ lý do, Đạt duyệt kỹ):
  backend/app/models/**       (một lần ở việc 0c — sau đó đóng băng)
  backend/tests/conftest.py   (1 PR mở rộng fixture phục vụ B2/B3)
  backend/requirements.txt    (chỉ thêm: alembic, python-docx, openpyxl)
  specs/specs.json            (chỉ đổi status/notes/tests[] của spec mình vừa làm)

CẤM TUYỆT ĐỐI (phân hệ Chấm — milestone khác):
  backend/app/services/toeic_grader.py · ai_grading.py · app/workers/tasks.py
  backend/tests/test_specs_grading.py · test_toeic_grader.py
  system_architecture.html (tài liệu v1 đông lạnh)
```
Trộn 2 track trong 1 PR → bác PR, tách lại. Cần đụng vùng cấm → DỪNG, báo Đạt.
Lưu ý: `test_specs_i18n.py`/`test_specs_scale.py` gọi generator — nếu thay đổi Track B làm 2 file này đỏ, đó là tín hiệu sai thiết kế: DỪNG và báo Đạt, không sửa 2 file đó.

### 2.4 Giao thức thực thi TỪNG issue — plan trước, code sau (BẮT BUỘC)

Mỗi issue (0a→0c, A1→A6, B1→B6) đi qua đúng 5 bước, khớp SDLC 7 bước trong `NOTE/GEMINI.md`:

1. **SPEC (đọc, không sáng tác):** đọc spec ID liên quan trong `specs/specs.json` + mục tương ứng trong `docs/kien_truc_phan_he_ra_de_tieng_anh.md`. Mục tiêu/phạm vi/giới hạn của issue lấy từ đó — KHÔNG tự thêm yêu cầu, KHÔNG mở rộng phạm vi.
2. **PLAN (viết kế hoạch ngắn → DỪNG chờ duyệt):** trước khi viết bất kỳ dòng code nào, viết implementation plan ≤ 1 trang vào mô tả issue (hoặc PR draft), gồm: *(a)* danh sách file sẽ tạo/sửa, *(b)* hàm/cấu trúc chính, *(c)* cách test + spec nào đổi trạng thái, *(d)* rủi ro/điểm chưa rõ. **DỪNG lại, chờ Đạt duyệt plan rồi mới code.** Plan bị sửa thì code theo bản đã duyệt.
3. **BUILD:** code theo đúng plan, lát nhỏ; lệch khỏi plan đã duyệt → quay lại bước 2.
4. **TEST:** `cd backend && python -m pytest tests -q` chạy 2 lần liên tiếp, exit 0, không `failed`. Spec đổi trạng thái → cập nhật `specs.json` + gỡ marker trong CÙNG commit.
5. **REVIEW:** tự rà theo PR template, mở PR, chờ review chéo. Không tự merge.

> Lý do giao thức này tồn tại: "plan ngon nghẻ xong mới code" — plan 15 phút được review rẻ hơn nhiều so với PR 400 dòng đi sai hướng phải đập lại.

---

## 3. VIỆC 0 — Setup chung (làm trước tiên, theo đúng thứ tự)

### 0a — `chore/repo-setup`: vệ sinh repo GitHub
- Bật branch protection cho `main` (require PR + 1 review + CI pass).
- Tạo labels: `parser`, `generator`, `bank`, `infra`, `spec`, `frontend`.
- Tạo milestone: `M2 — Ra đề tiếng Anh (17/06)`.
- Tạo `.github/PULL_REQUEST_TEMPLATE.md` với các mục: *Spec liên quan / Thay đổi / Cách verify / Checklist (pytest xanh, specs.json cập nhật)*.
- Tạo issues từ bảng việc trong `docs/phan_chia_cong_viec_github.md` (mẫu issue ở cuối file đó), gắn label + milestone.

### 0b — `chore/ci-pytest`: GitHub Actions
Kèm 2 việc chốt cấu hình harness còn treo: (a) cài + cấu hình linter Python `ruff` (thêm vào requirements.txt, bước CI riêng `ruff check app/`; cập nhật dòng "flake8 or similar" trong `clean-state-checklist.md` thành ruff); (b) cài `pytest-cov`, CI chạy `pytest --cov=app` — CHƯA gate theo ngưỡng 85% của quality-document.md vội (chỉ report), sẽ gate khi parser/validator hoàn thiện.
Tạo `.github/workflows/ci.yml`:
```yaml
name: CI
on:
  push: { branches: [main] }
  pull_request:
jobs:
  test:
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: backend } }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r requirements.txt
      - run: python -m pytest tests -q
```
DoD: CI chạy xanh trên PR đầu tiên (kết quả khớp baseline 15/7/7, exit 0).

### 0c — `feat/alembic-foundation`: nền migration (PR DUY NHẤT được đụng models — Đạt duyệt kỹ trước khi merge)
1. `pip install alembic` (thêm `alembic>=1.13` vào `requirements.txt`).
2. `alembic init alembic` trong `backend/`; cấu hình `env.py` đọc `DATABASE_URL` từ `app.core.config.settings`, `target_metadata` từ `app.core.database.Base`.
3. Migration 1 (baseline): autogenerate từ models hiện tại — đánh dấu trạng thái DB đang có.
4. Migration 2 (nền cho M2):
   - Bảng `blueprints`: `id · exam_type (String, index) · language (String) · structure (JSON) · is_active (Bool, default True) · created_at`.
   - Bảng `import_batches`: `id · source_file (String) · content_hash (String, index) · status (String: pending/imported/failed) · error_report (JSON, nullable) · imported_at (DateTime)`.
   - Cột mới `questions.source_question_id` (Integer, FK→questions.id, nullable, index) · `questions.content_hash` (String, nullable, index) · `question_groups.content_hash` (String, nullable, index) · `questions.import_batch_id` + `question_groups.import_batch_id` (FK→import_batches.id, nullable).
5. Tạo models tương ứng (`app/models/blueprint.py`, `app/models/import_batch.py`), import trong `main.py`.
6. Giữ `create_all()` cho dev/test (SQLite in-memory của test cần nó); ghi chú trong README backend: PostgreSQL thật dùng `alembic upgrade head`.
DoD: `alembic upgrade head` chạy được trên PostgreSQL trống; pytest vẫn 15/7/7; Đạt duyệt PR (mời sếp review nếu tham gia).

---

## 4. TRACK A — 6 việc theo thứ tự (mỗi việc = 1 nhánh = 1 PR)

### A1 — `feat/parser-core` (SPEC-PARSE-001, 003, 004)
Tạo khung `backend/app/services/parser/` đúng thiết kế mục 2.3 của `docs/kien_truc_phan_he_ra_de_tieng_anh.md`:
- `__init__.py`: hàm `import_file(db, path, profile)` — điểm vào duy nhất. Luồng: chọn profile → đọc file → validate (gates) → **all-or-nothing**: mọi gate pass mới ghi DB trong 1 transaction; fail → raise `ParserImportError` có thuộc tính `.report` dạng `{file, errors: [{location, type, message}]}` và ghi bản ghi `import_batches(status="failed", error_report=...)`.
- `validators.py`: gate "câu trắc nghiệm phải có `reference_answer` khớp một key trong `options`" (PARSE-001); gate cấu trúc bộ đề; gate UTF-8 (không U+FFFD).
- Content-hash: SHA-256 của nội dung chuẩn hóa (content + options + part) cho từng câu/nhóm; import lại file → câu/nhóm có hash đã tồn tại thì bỏ qua, đếm số skip vào báo cáo (PARSE-003).
- Mọi item ghi vào bank với `status="draft"`, `exam_id=None`, `import_batch_id` trỏ về đợt nạp.
- **Test:** gỡ `pytestmark skip` của `tests/test_specs_parser.py`, hoàn thiện 4 test theo đúng docstring hợp đồng có sẵn; tạo fixtures `tests/fixtures/parser/` (file docx mẫu chuẩn + file hỏng thiếu đáp án — tạo bằng python-docx trong script `tests/fixtures/make_fixtures.py`). Cập nhật `specs.json`: PARSE-001/003/004 → `active`.

### A2 — `feat/parser-toeic-listening` (SPEC-PARSE-002)
- `profiles/toeic_listening.py`: nhận dạng LT*.docx (P1: 6 câu đơn, P2: 25 câu đơn 3 phương án, P3: 13 nhóm × 3, P4: 10 nhóm × 3) + `xlsx_reader.py` đọc Excel đáp án/độ khó.
- `audio_linker.py`: ánh xạ MP3 theo quy ước tên (⚠️ **quy ước cụ thể chờ Đạt rà với đối tác** — viết linker nhận quy ước dạng pattern cấu hình được, đừng hardcode); file thiếu → import FAIL kèm danh sách file thiếu (PARSE-002 → active).
- Audio copy vào storage local (đường dẫn từ `.env`, ví dụ `UPLOAD_DIR`), bank lưu `audio_url` tương đối.

### A3 — `feat/parser-toeic-reading`
- `converter.py`: .doc → .docx qua LibreOffice headless (`soffice --headless --convert-to docx`); cache kết quả; LibreOffice không có → lỗi rõ ràng hướng dẫn cài.
- `profiles/toeic_reading.py`: P5 30 câu đơn; P6 4+ nhóm × 4; P7 nhóm 2–5 câu (đoạn đơn/kép/ba, có ảnh — trích ảnh nhúng ra storage, lưu `image_url`).

### A4 — `feat/parser-b1`
- `profiles/b1_listening.py` (LB1: 8 câu đơn + 3 nhóm hội thoại + 3 nhóm bài giảng = 35 câu; đáp án từ phiếu trả lời .doc → qua converter) và `profiles/b1_reading_writing.py` (EB1: 4 nhóm × 10 câu reading; 2 đề writing → `type="writing"`, không options).
- Speaking cards → câu `type="speaking"`; phiếu chấm điểm KHÔNG vào bảng questions — trích thang điểm/tiêu chí thành file `prompts/en/vstep_writing.json` + `vstep_speaking.json` (cấu trúc: `{rubric, criteria[], reference_notes}`).

### A5 — `feat/bank-admin-api` (hỗ trợ SPEC-BANK-001)
Router `backend/app/api/bank.py`, prefix `/api/v1/bank`, đăng ký vào `main.py`:
- `POST /bank/import` (multipart file + query `profile`) → gọi parser, trả `{batch_id, imported, skipped, errors}`.
- `GET /bank/imports/{batch_id}` · `GET /bank/questions` (filter part/difficulty/status/topic/exam_type, phân trang) · `PATCH /bank/questions/{id}` · `PATCH /bank/groups/{id}` · `POST /bank/approve` (body: list id hoặc batch_id).
- `GET /bank/stats?exam_type=TOEIC`: đếm approved theo part × độ khó, đối chiếu blueprint trong bảng `blueprints`, trả `warnings[]` cho ô thiếu.
- Test API bằng FastAPI TestClient trong `tests/test_bank_api.py` (file mới).
- Lưu ý: JWT chưa có trên repo — để TODO dependency `require_role("admin","teacher")` dạng stub, KHÔNG tự ý xây hệ auth (việc của milestone khác).

### A6 — `feat/bank-admin-ui` (có thể trượt sang M3, làm cuối)
Trang Next.js `frontend/src/app/admin/bank/page.tsx`: bảng câu hỏi/nhóm (lọc part/độ khó/status), nút duyệt hàng loạt, xem error_report đợt nạp, panel `/bank/stats` cảnh báo tồn kho. Dùng `NEXT_PUBLIC_API_URL` từ env, không hardcode localhost.

---

## 5. TRACK B — 6 việc Generator & Validator (mỗi việc = 1 nhánh = 1 PR)

Track B thuần thuật toán, chạy trên fixtures sẵn có — KHÔNG phụ thuộc dữ liệu đối tác. Nguồn thiết kế: `docs/kien_truc_phan_he_ra_de_tieng_anh.md` mục 5 (thuật toán 5 bước) và mục 6 (API).

### B1 — `feat/generator-hardening` (SPEC-BANK-001, GEN-006, GEN-005)
Sửa `app/services/toeic_generator.py`:
- **Lọc duyệt:** mọi query chọn câu/nhóm từ bank thêm điều kiện `status == "approved"` (BANK-001).
- **Fail-fast:** TRƯỚC khi tạo bản ghi Exam, kiểm tồn kho approved theo từng ô (part × độ khó) so blueprint; thiếu → raise `InsufficientBankError(part, difficulty, needed, available)` (exception mới định nghĩa trong cùng module), KHÔNG ghi bản ghi nào (GEN-006). ⚠️ Code hiện tại tạo Exam + commit NGAY ĐẦU hàm — phải đảo thứ tự: kiểm trước, tạo sau.
- **Seed:** thêm tham số `seed: int | None = None`; dùng `rng = random.Random(seed)` thay mọi `random.sample`/`random.shuffle` module-level (GEN-005).
- **Truy vết:** clone ghi `source_question_id` trỏ về câu gốc (cột có sẵn sau 0c).
- **Test:** gỡ xfail BANK-001 + GEN-006; gỡ skip GEN-005 và hoàn thiện. Cập nhật `specs.json` 3 spec → active. Test cũ vẫn phải xanh (fixture bank đều approved nên không ảnh hưởng).

### B2 — `feat/generator-part7-backtracking` (SPEC-GEN-001, MATRIX-002)
- Thay greedy Part 7 bằng backtracking subset-sum: chọn tổ hợp nhóm sao cho Σ câu = 54 VÀ độ khó câu ≈ 9/28/17 (±2); chọn ngẫu nhiên theo `rng` giữa các tổ hợp đạt, ưu tiên nhóm ít dùng; không tồn tại tổ hợp → raise nêu rõ thiếu nhóm kích thước nào (KHÔNG tự "làm tròn" 52).
- ⚠️ **Hai hệ quả PHẢI xử lý có chủ đích, nêu rõ trong mô tả PR:**
  1. Fixture hiện tại P7 toàn nhóm 4 câu → không tổ hợp nào đạt đúng 54 → cần **PR nền riêng trước đó** (`test: mở rộng fixture P7 nhóm 2/3/5 câu + đa dạng topic` — sửa `conftest.py`, Đạt duyệt; gộp luôn nhu cầu fixture của B3) rồi B2 mới gỡ xfail GEN-001 + MATRIX-002.
  2. Test cũ `test_toeic_generator.py` đang assert P7 = 13 nhóm × 4 câu — hành vi đúng MỚI là tổng 54 câu với nhóm kích thước trộn → cập nhật assertion theo hành vi mới trong cùng PR B2, giải thích rõ.

### B3 — `feat/generator-balance-topic` (SPEC-GEN-002, GEN-003)
- **Cân bằng đáp án:** trên danh sách câu SẼ-clone có 4 lựa chọn, hoán vị mapping options + đổi `reference_answer` tương ứng (chỉ trên bản clone — bank bất biến) đến khi mỗi đáp án A/B/C/D chiếm 20–28%; câu 3 lựa chọn (P2) giữ nguyên, không tính vào tỷ lệ.
- **Đa dạng topic:** trong bước chọn nhóm, ràng buộc ≤20% số câu một topic/part; bank không đủ đa dạng → fail-fast kèm thông điệp rõ.
- ⚠️ Phụ thuộc PR nền fixture (xem B2) — fixture hiện tại topic đơn điệu (P3 toàn "Meetings") nên chưa thể gỡ xfail GEN-003 trước đó.

### B4 — `feat/exam-validator`
- Tách `app/services/exam_validator.py`: `validate_exam(db, exam_id, blueprint) -> {checks: [...], overall: "pass"|"fail"}` — kiểm: blueprint số câu, ma trận độ khó, cách ly nhóm, cân bằng đáp án, topic, UTF-8. Format output đúng mẫu validation-report trong `docs/kien_truc_phan_he_ra_de_tieng_anh.md` mục 6.
- Generator gọi validator làm post-check trong transaction: fail → rollback + thử tổ hợp khác (tối đa 10 lần) → raise.
- Test mới `tests/test_exam_validator.py`: validator pass với đề chuẩn; fail đúng check khi bơm đề lỗi có chủ đích.

### B5 — `feat/blueprint-as-data`
- Seed 2 bản ghi bảng `blueprints` (TOEIC + VSTEP_B1 — JSON nguyên văn trong tài liệu kiến trúc mục 4) bằng data-migration hoặc script seed.
- Tổng quát hóa thành `app/services/exam_generator.py`: `generate_exam(db, exam_type, seed, ...)` đọc blueprint từ DB; xử lý mode `standalone`/`group`/`group_variable` và type `writing`/`speaking` (không options/đáp án). Giữ `generate_toeic_exam()` làm wrapper mỏng để test cũ không phải đổi.

### B6 — `feat/generate-batch` (SPEC-GEN-004)
- Router mới `app/api/exams.py`: `POST /api/v1/exams/generate-batch` đẩy Celery task trong `app/workers/generation_tasks.py` (file MỚI — không đụng `tasks.py` của grading); `GET /exams/generate-batch/{batch_id}` trả tiến độ; `GET /exams/{id}/validation-report` đọc report đã lưu.
- Overlap: tính pairwise qua `source_question_id`, trả `overlap_report` đúng format tài liệu mục 6.
- Test: bật `task_always_eager=True`; gỡ skip GEN-004 — sinh 5 đề, assert mọi cặp trùng ≤ 40%. `specs.json` → active.

---

## 6. Thứ tự làm việc đề xuất & mốc tích hợp nội bộ

Một người thực thi cả 2 track → làm tuần tự, đổi track khi bị chặn:

```
0a → 0b → 0c → B1 (quen quy trình, không chờ gì) → A1
→ [đã có quy ước MP3?] A2 → A3 → A4   |   [chưa có] PR fixture → B2 → B3 → B4, rồi quay lại A2
→ B5 → A5 → B6 → A6 (A6 có thể trượt sang M3)
```
- Nguyên tắc: việc bị chặn (chờ đối tác, chờ Đạt duyệt plan/quyết định) → chuyển track kia làm tiếp; KHÔNG chờ suông, KHÔNG tự quyết hộ.
- **Mốc tích hợp 1** (sau A2 + B4): chạy generator + validator trên bank dữ liệu THẬT đầu tiên — báo Đạt mọi lệch giả định giữa fixture và dữ liệu thật.
- **Mốc tích hợp 2** (sau A4 + A5 + B6): chạy lô 100 đề TOEIC + 100 đề B1 thật → xuất hồ sơ nghiệm thu (200 validation-report + overlap_report).
- Lệnh kiểm tra sau MỖI thay đổi: `cd backend && python -m pytest tests -q` (exit 0, không failed). Trước khi mở PR: chạy 2 lần xác nhận không flaky.

## 7. Những điều cấm kỵ (đúc kết để không phá harness)

1. KHÔNG sửa code/test phân hệ Chấm (grading) — ngoài phạm vi milestone. KHÔNG sửa test để "cho qua"; chỉ cập nhật assertion khi hành vi đúng thay đổi CÓ CHỦ ĐÍCH (vd Part 7 trong B2) và nêu rõ trong PR. `conftest.py` chỉ sửa qua PR nền riêng được Đạt duyệt.
2. KHÔNG thêm dependency mới ngoài: `alembic`, `python-docx`, `openpyxl`, `ruff`, `pytest-cov` (+ `python-multipart` đã có). Cần thêm gì khác → hỏi Đạt trước.
3. KHÔNG "làm tròn" quyết định nghiệp vụ trong code (vd dữ liệu nguồn lệch cấu trúc) — fail rõ ràng + báo lại, đó là thiết kế chủ đích (fail-fast).
4. KHÔNG đổi ID/format các spec hiện có trong `specs.json`; chỉ đổi `status`, `notes`, `tests[]` của spec mình làm.
