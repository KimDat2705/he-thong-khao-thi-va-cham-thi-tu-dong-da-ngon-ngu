# Quy trình GitHub & Phân chia công việc — Phân hệ Ra đề (2 người)

> **Cập nhật:** 11/06/2026 · **Milestone:** M2 — Ra đề tiếng Anh (deadline 17/06/2026)
> **Nguyên tắc:** 1 issue = 1 branch = 1 PR nhỏ · CI pytest là cổng merge · 2 track tách vùng file để gần như không bao giờ conflict.

## 1. Vị trí hiện tại theo quy trình chuẩn

| Bước SDLC | Trạng thái |
|---|---|
| ① Yêu cầu nghiệp vụ | ✅ `ke_hoach_trien_khai_toeic_b1.md` (BA) |
| ② Kiến trúc hệ thống | ✅ `docs/kien_truc_he_thong_v2.html` |
| ③ Kiến trúc + đặc tả chức năng phân hệ (API contract, spec kiểm chứng được) | ✅ `docs/kien_truc_phan_he_ra_de_tieng_anh.*` + `specs/specs.json` |
| ④ **Thiết lập nền tảng cộng tác (GitHub flow + CI)** | ⬅️ **BẮT ĐẦU TỪ ĐÂY** |
| ⑤ Implementation theo vertical slice | Sau ④, theo 2 track dưới |
| ⑥ Thiết kế giao diện | KHÔNG phải bước kế tiếp — phân hệ Ra đề chỉ cần màn quản trị bank, làm sau khi API có contract (issue A5/A6) |

## 2. Quy ước làm việc chung (GitHub Flow)

- **Nhánh:** `main` được bảo vệ (không push trực tiếp). Mỗi việc: `feat/<tên>`, `fix/<tên>`, `docs/<tên>`.
- **PR:** nhỏ (<~400 dòng diff), mô tả ghi rõ spec liên quan (vd "Closes #12 — SPEC-GEN-006 gap→active"). Người còn lại review rồi mới merge (squash merge).
- **CI bắt buộc:** GitHub Actions chạy `cd backend && python -m pytest tests -q` — exit ≠ 0 thì không merge được. `xfail`/`skip` hợp lệ; `failed` chặn.
- **Commit message:** conventional commits — `feat:`, `fix:`, `test:`, `docs:`, `chore:`. Ví dụ: `feat(generator): fail-fast khi bank thiếu (SPEC-GEN-006)`.
- **Đồng bộ:** rebase/merge `main` vào nhánh của mình mỗi sáng; PR để quá 2 ngày phải chia nhỏ.
- **Ranh giới file:** mỗi track chỉ sửa vùng file của mình (mục 4). Cần sửa file vùng chung (`models/`, `conftest.py`, `requirements.txt`, `specs/specs.json` phần của người kia) → mở PR riêng, cả 2 duyệt.
- **Cập nhật spec:** PR nào làm 1 spec đổi trạng thái thì sửa `specs/specs.json` (status) + gỡ marker xfail/skip **trong cùng PR** — meta-test traceability sẽ bắt nếu quên.

## 3. Việc làm CHUNG trước tiên (1 buổi, pair cùng nhau)

| # | Issue | Nội dung | Sản phẩm |
|---|---|---|---|
| 0a | `chore: thiết lập repo` | Bảo vệ nhánh main, labels (`parser`, `generator`, `bank`, `infra`, `spec`), milestone "M2 — Ra đề (17/06)", PR template | Cấu hình GitHub |
| 0b | `chore: CI pytest` | `.github/workflows/ci.yml` — Python 3.11, cài requirements, chạy pytest | CI xanh trên main |
| 0c | `feat: alembic init + migration nền` | Khởi tạo Alembic; migration: bảng `blueprints`, `import_batches`; cột `questions.source_question_id`, `questions.content_hash` | **PR chung cuối cùng đụng models** — sau PR này 2 track độc lập hoàn toàn |

## 4. Hai track song song (gần như không đụng file nhau)

### Track A — Parser & Ngân hàng câu hỏi
**Vùng file:** `backend/app/services/parser/**`, `backend/app/api/bank.py`, `backend/tests/test_specs_parser.py`, `backend/tests/fixtures/**`, `frontend/src/app/admin/**`
**Phù hợp với:** người giữ liên hệ đối tác/dữ liệu nguồn (cần rà file thật).

| # | Branch | Nội dung | Spec | Ước lượng |
|---|---|---|---|---|
| A1 | `feat/parser-core` | Khung `import_file()` all-or-nothing, `import_batches`, content_hash, validation gates, error report JSON | PARSE-001/003/004 skip→active | 1,5 ngày |
| A2 | `feat/parser-toeic-listening` | Profile LT*.docx + xlsx_reader + audio_linker (sau buổi rà MP3 với đối tác) | PARSE-002 → active | 1,5 ngày |
| A3 | `feat/parser-toeic-reading` | converter.py (.doc→.docx LibreOffice headless) + profile RT | mở rộng coverage | 1 ngày |
| A4 | `feat/parser-b1` | Profiles LB1/EB1 + speaking cards; phiếu chấm → `prompts/en/` | mở rộng coverage | 1,5 ngày |
| A5 | `feat/bank-admin-api` | Router `/api/v1/bank`: list/filter, patch, approve bulk, `/bank/stats` đối chiếu blueprint | hỗ trợ BANK-001 | 1 ngày |
| A6 | `feat/bank-admin-ui` | Trang Next.js `/admin/bank`: bảng duyệt draft→approved, xem error report đợt nạp | — | 1–2 ngày (có thể trượt sang M3) |

### Track B — Generator, Validator & Sinh lô
**Vùng file:** `backend/app/services/exam_generator.py` (mới), `exam_validator.py` (mới), `backend/app/api/toeic.py`/`exams.py`, `backend/tests/test_specs_generation.py`, `test_specs_bank.py`
**Phù hợp với:** người làm thuần thuật toán theo spec đã chốt (không phụ thuộc dữ liệu đối tác — chạy trên fixtures có sẵn).

| # | Branch | Nội dung | Spec | Ước lượng |
|---|---|---|---|---|
| B1 | `feat/generator-hardening` | Lọc `status='approved'` + kiểm tồn kho fail-fast + tham số `seed` (`random.Random`) | BANK-001, GEN-006 gap→active; GEN-005 → active | 1 ngày |
| B2 | `feat/generator-part7-backtracking` | Subset-sum chọn nhóm P7 đạt đúng 54 câu + độ khó 9/28/17 | GEN-001, MATRIX-002 → active | 1,5 ngày |
| B3 | `feat/generator-balance-topic` | Hoán vị options cân bằng đáp án 20–28%; ràng buộc topic ≤20%/part | GEN-002, GEN-003 → active | 1 ngày |
| B4 | `feat/exam-validator` | Tách `exam_validator.py` dùng chung; refactor test gọi validator; post-check + rollback trong generate | củng cố toàn bộ GEN | 1 ngày |
| B5 | `feat/blueprint-as-data` | Bảng `blueprints` thành nguồn cấu hình; tổng quát hóa generator; seed 2 bản ghi TOEIC + B1 | — | 1,5 ngày |
| B6 | `feat/generate-batch` | `POST /exams/generate-batch` (Celery) + `GET validation-report` + overlap_report | GEN-004 → active | 1,5 ngày |

### Điểm hẹn tích hợp (2 track gặp nhau)

| Mốc | Điều kiện | Việc chung |
|---|---|---|
| Hẹn 1 (~ngày 4) | A2 + B4 xong | Chạy generator trên dữ liệu THẬT đầu tiên (bank TOEIC Listening đã import) — phát hiện lệch giả định fixture vs dữ liệu thật |
| Hẹn 2 (cuối M2) | A4 + B6 xong | Chạy lô 100 đề TOEIC + 100 đề B1 thật → xuất hồ sơ nghiệm thu (200 validation-report + overlap_report) |

## 5. Definition of Done của milestone M2

- [ ] 16/16 spec phân hệ Ra đề ở trạng thái `active` (suite: 0 failed, 0 xfailed trong nhóm này)
- [ ] CI xanh trên `main`; mọi thay đổi đều qua PR có review
- [ ] 100 đề TOEIC + 100 đề B1 sinh từ dữ liệu nguồn thật, 100% qua validator, overlap ≤ 40%
- [ ] Sinh lại cùng seed → kết quả giống hệt
- [ ] Hồ sơ nghiệm thu xuất được từ API

## 6. Mẫu issue (dán vào GitHub Issues)

```markdown
### feat(generator): fail-fast khi bank thiếu — SPEC-GEN-006

**Spec:** SPEC-GEN-006 (specs/specs.json) — hiện trạng `gap`, test `test_SPEC_GEN_006_insufficient_bank_raises` đang xfail.

**Việc:**
- [ ] Bước kiểm tồn kho đầu generate: đếm bank approved theo (part × độ khó) so blueprint
- [ ] Thiếu → raise `InsufficientBankError` nêu part + số thiếu; không ghi bản ghi nào
- [ ] Gỡ marker xfail; đổi status spec thành `active` trong specs.json

**DoD:** pytest 0 failed; test GEN-006 chuyển passed; meta-test traceability vẫn xanh.
```
