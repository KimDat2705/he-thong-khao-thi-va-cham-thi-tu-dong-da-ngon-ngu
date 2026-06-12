# Kiến trúc Phân hệ Ra đề — Tiếng Anh (TOEIC & B1 VSTEP)

> **Phiên bản:** 1.0 · **Cập nhật:** 11/06/2026
> **Tài liệu cha:** `docs/kien_truc_he_thong_v2.html` (kiến trúc tổng thể, mục 5)
> **Nguồn sự thật spec:** `specs/specs.json` · **Test harness:** `backend/tests/test_specs_*.py`
> **Phạm vi:** chỉ phân hệ Ra đề (exam generation), chỉ tiếng Anh. Phân hệ Thi (phòng thi/proctoring) và Chấm AI nằm ngoài phạm vi tài liệu này.

## Tóm tắt cho người đọc nhanh

| Hạng mục | Giá trị |
|---|---|
| Sản phẩm đầu ra | 100 đề TOEIC (200 câu/đề) + 100 đề B1 VSTEP (4 kỹ năng) |
| Dữ liệu đầu vào | ~15 bộ TOEIC + 30 bộ B1 dạng Word/Excel/MP3 (đối tác bàn giao) |
| Tiêu chí nghiệm thu | 100% đề qua validator tự động, trùng lặp giữa 2 đề bất kỳ ≤ 40% |
| Spec bao phủ | 16/23 spec hệ thống (4 active / 6 gap / 6 planned tại 11/06/2026) |
| Trạng thái test suite | `15 passed · 7 skipped · 7 xfailed · 0 failed` |
| Stack | FastAPI + SQLAlchemy 2 + PostgreSQL (SQLite cho test) · python-docx/openpyxl (parser) · Celery+Redis (sinh lô nền) |

Nguyên tắc kế thừa từ kiến trúc tổng thể: **blueprint-as-data** (cấu trúc chứng chỉ là dữ liệu, không phải code — thêm HSK sau này = thêm bản ghi), **bank bất biến** (đề là bản CLONE có truy vết nguồn), **Harness Engineering** (mỗi ràng buộc nghiệp vụ = 1 SPEC ID + test tự động), **cấu hình từ env** (MVP → Production chỉ đổi `.env`).

---

## 1. Pipeline tổng quan: 3 giai đoạn + cổng kiểm định

```
[Dữ liệu nguồn]──►[GĐ1 PARSER]──►[GĐ2 NGÂN HÀNG]──►[GĐ3 GENERATOR]──►[CỔNG KIỂM ĐỊNH exam_validator]
 Word/Excel/MP3    convert .doc     draft → duyệt      đọc blueprint        ĐẠT  → commit + validation_report
                   parse + gates    → approved         chọn → cân bằng      HỎNG → rollback, thử tổ hợp khác
                                    thống kê tồn kho   → clone có truy vết         (tối đa N lần rồi báo lỗi bank)
```

| Giai đoạn | Trạng thái code hiện tại | Module |
|---|---|---|
| GĐ1 — Parser/Ingestion | **Chưa có** — đặc tả ở mục 2 | `app/services/parser/` (đề xuất) |
| GĐ2 — Ngân hàng câu hỏi | Một phần — model có, thiếu API quản trị + lọc duyệt | `app/models/question*.py` · `app/api/bank.py` (đề xuất) |
| GĐ3 — Generator | Bản đầu chạy được — TOEIC hardcode, còn 6 gap (mục 5) | `app/services/toeic_generator.py` → tổng quát hóa thành `exam_generator.py` |
| Cổng kiểm định | Chưa có — logic hiện chỉ tồn tại trong test | `app/services/exam_validator.py` (đề xuất, **dùng chung với test harness**) |

---

## 2. GĐ1 — Dữ liệu nguồn & Parser Engine

### 2.1 Kiểm kê dữ liệu nguồn

| Bộ | File | Parser phải bóc tách | Lưu ý kỹ thuật |
|---|---|---|---|
| TOEIC Listening (~15 bộ) | `LT2601.docx` → `LT2629.docx` (chỉ số lẻ) + Excel đáp án + thư mục *"File nghe tong hop"* | P1, P2 câu đơn; P3, P4 nhóm 3 câu kèm audio | Link MP3 theo quy ước tên; P2 chỉ có 3 phương án A/B/C |
| TOEIC Reading (~15 bộ) | `CDR TOEIC - RT2601.doc` → `RT2615.doc` + Excel đáp án | P5 câu đơn; P6 nhóm 4 câu; P7 nhóm 2–5 câu, có ảnh | **.doc nhị phân** — phải convert sang .docx (LibreOffice headless) trước khi parse bằng python-docx |
| B1 Nghe (30 bộ, mã 2601–2630) | `LB1.XXXX.docx` + `FILE NGHE/` + `Phiếu trả lời Listening B1 - XXXX.doc` | 8 câu đơn (thông báo) + 3 nhóm hội thoại + 3 nhóm bài giảng = 35 câu | Phiếu trả lời cũng là .doc → cùng đường convert |
| B1 Đọc & Viết | `EB1 - XXXX.docx` | Reading: 4 nhóm × 10 câu; Writing: 2 đề tự luận | Câu writing nạp `type="writing"`, không có options |
| B1 Nói & phiếu chấm | `SPEAKING CARDS/` + `Phiếu chấm điểm B1 XXXX.docx` | 3 phần nói → câu `type="speaking"` | Phiếu chấm KHÔNG vào bảng questions — số hóa thành prompt chấm AI (`prompts/en/vstep_*.json`) |

### 2.2 Quy ước liên kết audio (SPEC-PARSE-002)

```
LT2601.docx  + File nghe tong hop/2601_Part1.mp3    → câu đơn Part 1 bộ 2601
               File nghe tong hop/2601_Part3_01.mp3 → nhóm hội thoại #1 Part 3 bộ 2601
LB1.2601.docx + FILE NGHE/B1_2601_Sec2_Conv1.mp3    → nhóm hội thoại #1 Listening B1 bộ 2601
```

**Quy tắc cứng:** parser KHÔNG đoán — tên file không khớp quy ước hoặc file không tồn tại → import FAIL kèm danh sách file thiếu.

> ⚠️ **Rủi ro số 1 của GĐ1:** quy ước tên MP3 thực tế có thể không đồng nhất giữa các bộ. Cần 1 buổi rà soát dữ liệu thật với đối tác **trước khi** viết `audio_linker`.

### 2.3 Thiết kế module (đề xuất)

```
app/services/parser/
├── __init__.py          # import_file(db, path) — điểm vào duy nhất, giao dịch all-or-nothing
├── converter.py         # .doc → .docx (LibreOffice headless), cache kết quả
├── docx_reader.py       # bóc câu hỏi/nhóm/đoạn văn/ảnh (python-docx)
├── xlsx_reader.py       # đọc Excel đáp án + độ khó (openpyxl)
├── audio_linker.py      # ánh xạ MP3 theo quy ước, copy vào storage, trả audio_url
├── validators.py        # validation gates — chạy TRƯỚC khi ghi DB
└── profiles/            # cấu hình nhận dạng từng định dạng nguồn
    ├── toeic_listening.py · toeic_reading.py · b1_listening.py · b1_reading_writing.py
```

Mỗi **profile** mô tả cách nhận dạng một định dạng file nguồn. Thêm định dạng mới (HSK) = thêm profile, không sửa lõi parser.

### 2.4 Validation gates & giao dịch import

| Gate | Kiểm tra | Spec |
|---|---|---|
| Toàn vẹn câu hỏi | Câu trắc nghiệm nào cũng có `reference_answer` khớp một key trong `options` | SPEC-PARSE-001 |
| Audio tồn tại | Mọi nhóm/câu Listening link tới MP3 có thật | SPEC-PARSE-002 |
| Đúng cấu trúc bộ đề | Số câu/nhóm mỗi part khớp cấu trúc chứng chỉ | (thuộc PARSE-004) |
| UTF-8 sạch | Không ký tự U+FFFD/mojibake | SPEC-COLLATE-004 |

- **All-or-nothing theo file** (SPEC-PARSE-004): một gate fail → rollback toàn bộ, sinh báo cáo lỗi JSON `{file, errors: [{location, type, message}]}` lưu vào `import_batches.error_report`.
- **Idempotent** (SPEC-PARSE-003): mỗi câu/nhóm có `content_hash` (SHA-256 nội dung chuẩn hóa); import lại → bỏ qua bản trùng.
- Mọi item vào bank ở **`status="draft"`** — bắt buộc qua duyệt trước khi sinh đề chạm tới.
- Bảng mới `import_batches` (qua Alembic): `id · source_file · content_hash · status(pending/imported/failed) · error_report JSON · imported_at`.

---

## 3. GĐ2 — Ngân hàng câu hỏi

**Mô hình:** bank = các bản ghi `Question`/`QuestionGroup` có `exam_id IS NULL`. Vòng đời: `draft` (từ parser) → `approved` (giáo viên duyệt) → `retired` (lỗi/lộ đề). **Chỉ `approved` được vào đề** (SPEC-BANK-001). Sinh đề chỉ CLONE kèm `source_question_id` — sửa/retire bank không ảnh hưởng đề đã phát hành (SPEC-BANK-002 ✓).

### 3.1 API quản trị (đề xuất — router `/api/v1/bank`, role admin/teacher)

| Endpoint | Chức năng |
|---|---|
| `POST /bank/import` (multipart: file + profile) | Nạp 1 file nguồn qua Parser; trả batch_id + báo cáo |
| `GET /bank/imports/{batch_id}` | Trạng thái + error_report của đợt nạp |
| `GET /bank/questions?part=&difficulty=&status=&topic=&exam_type=` | Duyệt/lọc ngân hàng |
| `PATCH /bank/questions/{id}` · `PATCH /bank/groups/{id}` | Sửa nội dung/độ khó/topic/trạng thái |
| `POST /bank/approve` (theo danh sách id hoặc cả batch) | Duyệt hàng loạt |
| `GET /bank/stats?exam_type=TOEIC` | Tồn kho approved theo part × độ khó × topic, đối chiếu blueprint, cảnh báo phần thiếu |

### 3.2 Năng lực ngân hàng (tính trên ~15 bộ TOEIC nguồn)

| Part | Cần/đề | Tồn kho | Trùng lặp kỳ vọng giữa 2 đề* |
|---|---|---|---|
| P1 | 6 | ~90 câu | ~0,4 câu |
| P2 | 25 | ~375 câu | ~1,7 câu |
| P3 | 13 nhóm | ~195 nhóm | ~2,6 câu |
| P4 | 10 nhóm | ~150 nhóm | ~2 câu |
| P5 | 30 | ~450 câu | ~2 câu |
| P6 | 4 nhóm | ~60 nhóm | ~1,1 câu |
| P7 | ~13 nhóm/54 câu | ~195 nhóm | ~3,5 câu |
| **Tổng** | | | **≈ 13 câu / 200 ≈ 6,6%** — dư xa ngưỡng 40% (SPEC-GEN-004) |

\* Ước lượng chọn ngẫu nhiên đều: trùng kỳ vọng ≈ n²/M mỗi part. B1 có 30 bộ nguồn nên dư dả hơn. **Lưu ý:** ô part×độ khó mỏng (vd P1-Khó chỉ ~15 câu) sẽ tái dùng nhiều — chấp nhận được vì ngưỡng đo theo cặp đề tổng thể, nhưng `/bank/stats` phải cảnh báo.

---

## 4. Blueprint-as-data: TOEIC & B1 VSTEP

Mỗi chứng chỉ là **một bản ghi** bảng `blueprints` (mới, qua Alembic). Generator đọc blueprint và thực thi — không dòng code nào nhắc "TOEIC" hay "B1".

### 4.1 Blueprint TOEIC

```json
{
  "exam_type": "TOEIC", "language": "EN", "total_questions": 200, "duration_minutes": 120,
  "difficulty_matrix": { "easy": 50, "medium": 100, "hard": 50, "tolerance_per_part": 2 },
  "parts": [
    { "part": 1, "mode": "standalone", "count": 6,  "difficulty": {"easy": 2, "medium": 3,  "hard": 1},  "media": "image+audio" },
    { "part": 2, "mode": "standalone", "count": 25, "difficulty": {"easy": 6, "medium": 13, "hard": 6},  "options": 3 },
    { "part": 3, "mode": "group", "groups": 13, "q_per_group": 3, "g_difficulty": {"easy": 3, "medium": 7, "hard": 3}, "media": "audio" },
    { "part": 4, "mode": "group", "groups": 10, "q_per_group": 3, "g_difficulty": {"easy": 2, "medium": 5, "hard": 3}, "media": "audio" },
    { "part": 5, "mode": "standalone", "count": 30, "difficulty": {"easy": 8, "medium": 15, "hard": 7} },
    { "part": 6, "mode": "group", "groups": 4, "q_per_group": 4, "g_difficulty": {"easy": 1, "medium": 2, "hard": 1} },
    { "part": 7, "mode": "group_variable", "target_questions": 54, "group_sizes": [2,3,4,5],
      "q_difficulty_target": {"easy": 9, "medium": 28, "hard": 17} }
  ],
  "constraints": { "answer_balance_range": [0.20, 0.28], "topic_max_share": 0.20, "cross_exam_overlap_max": 0.40 }
}
```

> **Quy đổi độ khó câu → nhóm (cần thống nhất với BA):** kế hoạch nghiệp vụ phân độ khó theo **câu** (vd P3: 8E/21M/10H), nhưng ràng buộc cách ly nhóm buộc chọn theo **nhóm**. Phương án nhóm gần nhất: P3 = 3/7/3 nhóm = 9/21/9 câu (lệch ±1), P4 = 2/5/3 = 6/15/9, P6 = 1/2/1 = 4/8/4 — tất cả trong **dung sai ±2 câu/phần** kế hoạch cho phép. SPEC-MATRIX-002 kiểm theo phương án nhóm này.

### 4.2 Blueprint B1 VSTEP

```json
{
  "exam_type": "VSTEP_B1", "language": "EN",
  "sections": [
    { "skill": "listening", "duration_minutes": 40, "total_questions": 35, "parts": [
        { "part": 1, "mode": "standalone", "count": 8, "desc": "Thông báo/hướng dẫn ngắn", "media": "audio" },
        { "part": 2, "mode": "group", "groups": 3, "desc": "Hội thoại ngắn", "media": "audio" },
        { "part": 3, "mode": "group", "groups": 3, "desc": "Bài thuyết trình/bài giảng", "media": "audio" }
      ],
      "note": "8 câu đơn + 6 nhóm; số câu/nhóm theo đề nguồn (4-5 câu/nhóm), validator ép TỔNG = 35" },
    { "skill": "reading", "duration_minutes": 60, "total_questions": 40, "parts": [
        { "part": 1, "mode": "group", "groups": 4, "q_per_group": 10, "desc": "Bài đọc dài 300-500 từ" }
      ] },
    { "skill": "writing", "duration_minutes": 60, "parts": [
        { "task": 1, "type": "writing", "desc": "Thư/email xã giao", "min_words": 120 },
        { "task": 2, "type": "writing", "desc": "Bài luận nghị luận theo chủ đề", "min_words": 250 }
      ] },
    { "skill": "speaking", "duration_minutes": 12, "parts": [
        { "part": 1, "type": "speaking", "desc": "Tương tác xã hội — 3-6 câu hỏi ngắn" },
        { "part": 2, "type": "speaking", "desc": "Thảo luận giải pháp — chọn 1 trong 3" },
        { "part": 3, "type": "speaking", "desc": "Phát triển chủ đề từ mindmap" }
      ] }
  ],
  "constraints": { "topic_max_share": 0.20, "cross_exam_overlap_max": 0.40 }
}
```

Khác biệt B1 so TOEIC được xử lý **qua dữ liệu blueprint, không qua if/else**: câu tự luận (`type: writing/speaking`) không cần options/đáp án; cấu trúc cây section→part; `difficulty`/`q_per_group` là trường tùy chọn.

---

## 5. GĐ3 — Thuật toán sinh đề

### 5.1 Năm bước của `generate_exam(blueprint, seed)`

```
① KIỂM TỒN KHO (fail-fast — SPEC-GEN-006)
   Đếm bank approved theo từng ô (part × độ khó) so blueprint — thiếu → raise nêu rõ part + số thiếu

② CHỌN (random.Random(seed) — SPEC-GEN-005 · BANK-001 · GEN-003 · GEN-004)
   Chỉ item approved · theo từng ô blueprint · ưu tiên item ít dùng (giảm trùng lặp lô) · topic ≤20%/part

③ CÂN BẰNG ĐÁP ÁN (SPEC-GEN-002)
   Hoán vị vị trí options + đổi reference_answer trên bản sẽ-clone (không đụng bank) → A/B/C/D mỗi loại 20–28%

④ CLONE TRONG TRANSACTION (SPEC-BANK-002 · ISOLATE-003)
   Nhóm clone nguyên khối kèm câu con · ghi source_question_id · bank bất biến

⑤ POST-CHECK: exam_validator (chạy lại toàn bộ ràng buộc trên đề vừa sinh)
   Đạt → commit + validation_report · Hỏng → rollback, thử tổ hợp khác (tối đa N=10 lần rồi báo lỗi bank)
   Validator là module DÙNG CHUNG với test harness — một thước đo duy nhất cho cả production lẫn CI
```

### 5.2 Part 7 — bài toán tổ hợp (gap lớn nhất, SPEC-GEN-001)

P7 gồm nhóm 2–5 câu phải đạt **đúng 54 câu** + độ khó 9/28/17. Greedy hiện tại dừng ở 52 câu khi bank toàn nhóm 4 câu. Thay bằng **backtracking subset-sum** (không gian nhỏ ≤20 nhóm/đề): chọn tổ hợp nhóm sao cho Σsize = 54 VÀ Σđộ khó ≈ 9/28/17 (±2); không tồn tại tổ hợp → fail-fast nêu rõ thiếu nhóm kích thước nào. Nếu dữ liệu nguồn chỉ có nhóm 4 câu ở P7 → báo đối tác bổ sung nhóm 2–3 câu hoặc BA điều chỉnh target — **quyết định nghiệp vụ, không tự "làm tròn" trong code**.

### 5.3 Hiện trạng `toeic_generator.py` vs mục tiêu

| Khía cạnh | Hiện trạng | Mục tiêu | Spec |
|---|---|---|---|
| Blueprint | Hardcode, chỉ TOEIC | Đọc bảng `blueprints`, chạy cả TOEIC + B1 | — |
| Lọc duyệt | Không lọc `status` | Chỉ `approved` | BANK-001 (gap) |
| Part 7 | Greedy → 52/54 câu (đề 198/200) | Backtracking đúng 54 + độ khó | GEN-001 (gap) |
| Ma trận toàn đề | Per-part đạt; toàn đề lệch do P7 | P7 ràng buộc độ khó → 25/50/25 | MATRIX-002 (gap) |
| Cân bằng đáp án | Chưa có | Bước ③ | GEN-002 (gap) |
| Đa dạng topic | Chưa có | Ràng buộc bước ② | GEN-003 (gap) |
| Bank thiếu | Âm thầm sinh đề thiếu câu | Fail-fast bước ① | GEN-006 (gap) |
| Seed | `random` module-level | Tham số `seed` | GEN-005 (planned) |
| Truy vết nguồn | Không lưu | `source_question_id` | GEN-004 (planned) |
| **Đã đạt** | Clone không phá bank · cách ly nhóm chuẩn · per-part difficulty đúng · sinh 1 đề <10s | | BANK-002 · ISOLATE-003 · SCALE-002 (active) |

---

## 6. API phân hệ

| Endpoint | Trạng thái | Mô tả |
|---|---|---|
| `POST /api/v1/bank/import` + API quản trị bank (mục 3.1) | đề xuất | GĐ1 + GĐ2 |
| `POST /api/v1/toeic/exams/generate` | **đã có** | Sinh 1 đề TOEIC — sẽ hợp nhất thành `POST /api/v1/exams/generate` nhận `exam_type` |
| `POST /api/v1/exams/generate-batch` | đề xuất | Sinh lô N đề chạy nền qua Celery |
| `GET /api/v1/exams/{id}/validation-report` | đề xuất | Báo cáo ràng buộc 1 đề — **hồ sơ nghiệm thu** |

```json
// POST /api/v1/exams/generate-batch
{ "exam_type": "TOEIC", "count": 100, "seed": 20260611, "title_pattern": "Đề TOEIC chuẩn hóa #{n}" }
// → 202 { "batch_id": "gen_20260611_001", "status": "running", "progress_url": "..." }

// GET /api/v1/exams/generate-batch/gen_20260611_001 (khi xong)
{ "status": "completed", "requested": 100, "generated": 100, "failed": 0, "seed": 20260611,
  "overlap_report": { "max_pairwise": 0.11, "mean_pairwise": 0.066, "threshold": 0.40, "pass": true },
  "exams": [ { "exam_id": 12, "validation": "pass", "report_url": "/api/v1/exams/12/validation-report" } ] }

// GET /api/v1/exams/12/validation-report
{ "exam_id": 12, "checks": [
    { "spec": "SPEC-GEN-001",    "name": "Blueprint số câu", "pass": true, "detail": {"p1":6,"p2":25,"p3":39,"p4":30,"p5":30,"p6":16,"p7":54,"total":200} },
    { "spec": "SPEC-MATRIX-002", "name": "Ma trận độ khó",   "pass": true, "detail": {"easy":50,"medium":99,"hard":51} },
    { "spec": "SPEC-ISOLATE-003","name": "Cách ly nhóm",     "pass": true, "detail": {"orphans":0} },
    { "spec": "SPEC-GEN-002",    "name": "Cân bằng đáp án",  "pass": true, "detail": {"A":0.24,"B":0.26,"C":0.25,"D":0.25} },
    { "spec": "SPEC-GEN-003",    "name": "Đa dạng chủ đề",   "pass": true, "detail": {"max_topic_share":0.14} },
    { "spec": "SPEC-COLLATE-004","name": "UTF-8 sạch",       "pass": true, "detail": {"replacement_chars":0} }
  ], "overall": "pass" }
```

---

## 7. Specs & Tests của phân hệ (16/23 spec hệ thống)

Quy ước trạng thái: **active** = test PASS hôm nay · **gap** = đặc tả rồi, code chưa đạt (test `xfail` — tự chuyển XPASS khi sửa xong) · **planned** = subsystem chưa tồn tại (test `skip` kèm hợp đồng trong docstring). † = ID legacy từ tài liệu v1.

| ID | Phát biểu | Trạng thái | Việc cần làm để active |
|---|---|---|---|
| SPEC-PARSE-001 † | Sau import không câu nào thiếu đáp án/options | planned | Triển khai Parser Engine + fixtures |
| SPEC-PARSE-002 | Audio Listening link MP3 tồn tại; thiếu → fail | planned | (như trên) |
| SPEC-PARSE-003 | Re-import idempotent (content-hash) | planned | (như trên) |
| SPEC-PARSE-004 | Import all-or-nothing + báo cáo lỗi JSON, item mới = draft | planned | (như trên) |
| SPEC-BANK-001 | Chỉ item approved được vào đề | **gap** | Filter `status='approved'` trong generator |
| SPEC-BANK-002 | Sinh đề không thay đổi bank | **active** | — |
| SPEC-GEN-001 | Đúng blueprint 6/25/39/30/30/16/54 = 200 | **gap** | Backtracking Part 7 |
| SPEC-MATRIX-002 † | Ma trận độ khó per-part + toàn đề 25/50/25 | **gap** (per-part ✓) | Ràng buộc độ khó nhóm P7 |
| SPEC-ISOLATE-003 † | Cách ly nhóm, không câu mồ côi | **active** | — |
| SPEC-GEN-002 | Đáp án A/B/C/D mỗi loại 20–28% | **gap** | Hoán vị options trên bản clone |
| SPEC-GEN-003 | Không topic >20% câu một part | **gap** | Ràng buộc topic khi chọn + parser nạp topic |
| SPEC-GEN-004 | Lô 100 đề: cặp bất kỳ trùng ≤40% câu nguồn | planned | Alembic `source_question_id` + ưu tiên ít dùng |
| SPEC-GEN-005 | Cùng seed + cùng bank → đề giống hệt | planned | Tham số `seed`, `random.Random(seed)` |
| SPEC-GEN-006 | Bank thiếu → raise rõ ràng | **gap** | Kiểm tồn kho fail-fast |
| SPEC-COLLATE-004 † | UTF-8 sạch toàn bộ văn bản | **active** | — |
| SPEC-SCALE-002 | Sinh 1 đề <10s | **active** | Đo lại sau khi thêm backtracking + validator |

Lệnh chạy: `cd backend && python -m pytest tests -q` — phải exit 0 (xfail/skip là trạng thái được quản lý; fail chặn merge). Truy vết 2 chiều spec ↔ test do `tests/test_specs_traceability.py` tự kiểm.

---

## 8. Kế hoạch triển khai & Definition of Done

Phân hệ nằm trong **Giai đoạn 2** kế hoạch 30 ngày (deadline 17/06/2026 — mốc thanh toán 30%). Thứ tự theo phụ thuộc kỹ thuật:

| # | Việc | Phụ thuộc | Spec chuyển trạng thái |
|---|---|---|---|
| 1 | **Alembic init** + migration: bảng `blueprints`, `import_batches`; cột `source_question_id`, `content_hash` | — | mở khóa GEN-004/005, PARSE-003 |
| 2 | Rà quy ước tên MP3 trên dữ liệu thật với đối tác | — | chốt chi tiết PARSE-002 |
| 3 | Parser TOEIC Listening (docx + xlsx + audio_linker) + fixtures test | 1, 2 | PARSE-001..004 → active |
| 4 | Converter .doc + parser TOEIC Reading; rồi profiles B1 | 3 | mở rộng coverage PARSE |
| 5 | API quản trị bank + màn duyệt + `/bank/stats` | 3 | BANK-001 → active (kèm việc 6) |
| 6 | **Vá generator**: lọc approved, fail-fast, seed, backtracking P7, cân bằng đáp án, topic; tách `exam_validator.py` | 1 | GEN-001/002/003/006 + MATRIX-002 hết xfail; GEN-005 active |
| 7 | Tổng quát hóa blueprint-as-data; thêm blueprint B1 | 6 | cùng code sinh TOEIC + B1 |
| 8 | `generate-batch` qua Celery + validation-report; chạy lô 100+100 đề thật | 5, 6, 7 | GEN-004 → active; xuất hồ sơ nghiệm thu |

**Definition of Done:**
- ✅ 16/16 spec ở mục 7 đạt **active** — suite pytest 0 failed, 0 xfailed trong nhóm spec Ra đề
- ✅ 100 đề TOEIC + 100 đề B1 sinh từ dữ liệu nguồn thật, 100% qua validator, `overlap_report` ≤ 40%
- ✅ Sinh lại lô cùng seed → kết quả giống hệt (kiểm định được)
- ✅ Hồ sơ nghiệm thu: bảng tổng hợp 200 validation-report + thống kê tồn kho bank đã duyệt
