# KỊCH BẢN TEST THỦ CÔNG — NHÀ MÁY SINH NGÂN HÀNG ĐỀ B1

> Dành cho Đạt tự chạy tay để nghiệm thu chức năng nội bộ **trước khi** merge với code sếp.
> Mỗi bước = 1 lệnh copy-paste + "kết quả mong muốn". Chạy trong thư mục `backend/`.
> Dữ liệu mẫu (tổng hợp, KHÔNG dùng đề sếp): `backend/tests/fixtures/factory_sample/`.

## Ký hiệu
- **[OFFLINE]** — chạy được KHÔNG cần internet/key (chế độ MOCK, tất định). Chứng minh **cấu trúc/luồng** chạy đúng.
- **[THẬT]** — cần `GEMINI_API_KEY` (đặt trong `backend/.env`). Chứng minh **chất lượng nội dung** Gemini sinh thật + audio + cổng kiểm đáp án.
- Nên làm **[OFFLINE] trước** (nhanh, chắc chắn), rồi **[THẬT]** nếu có key.

## Bảng tổng quan (làm lần lượt)
| # | Bước | Loại | Chứng minh |
|---|---|---|---|
| 0 | Chuẩn bị môi trường | — | venv + cài đặt |
| 1 | Chạy test tự động | OFFLINE | Toàn bộ logic (81 test) đúng, tất định |
| 2 | Sinh thử đủ 8 dạng (mock) | OFFLINE | Orchestrator + parser + QC + render chạy trọn |
| 3 | Mở file .docx | OFFLINE | Bản đề + đáp án + ô GV ký đúng |
| 4 | Sinh thử THẬT (Gemini) | THẬT | Chất lượng câu sinh thật |
| 5 | Cổng kiểm đáp án AI | THẬT | Bắt đáp án sai/ảo giác, gắn cờ NGHI cho GV |
| 6 | Đo recall/FP cổng | THẬT | Số đo khách quan cổng kiểm đáp án |
| 7 | Render audio bài Nghe | THẬT (tốn quota) | Ghép audio ~16-18' + MP3 |

---

## Bước 0 — Chuẩn bị (1 lần)
```bash
cd backend
python -m venv venv                 # nếu chưa có
source venv/Scripts/activate        # Windows Git Bash
pip install -r requirements.txt
# (tùy chọn, chỉ cho audio MP3) pip install -r requirements-audio.txt
```
**[THẬT]** để bật chế độ Gemini: tạo file `backend/.env` chứa 1 dòng `GEMINI_API_KEY=<khóa của bạn>`.
> **Kết quả mong muốn:** cài đặt xong không lỗi. (Không có key vẫn chạy được các bước [OFFLINE].)

---

## Bước 1 — Chạy bộ test tự động [OFFLINE] · *mỏ neo tin cậy*
```bash
python -m pytest tests -q
```
> **Kết quả mong muốn:** dòng cuối `81 passed` (0 failed). Đây chứng minh **toàn bộ**: sinh 8 dạng, QC, cổng kiểm đáp án, chống méo-JSON, orchestrator, roundtrip, render — đều đúng tất định, không cần key.
> Muốn chạy riêng phần nhà máy: `python -m pytest tests/test_specs_factory.py -q` → `19 passed`.

---

## Bước 2 — Sinh thử ĐỦ 8 DẠNG (mock) [OFFLINE]
```bash
python scripts/make_bank_expansion.py \
  --bank-raw tests/fixtures/factory_sample/bank_raw.json \
  --pool-speak tests/fixtures/factory_sample/pool_speak.json \
  --pool-lis tests/fixtures/factory_sample/pool_lis.json \
  --per-seed 1 --n-target 1 --out out_test_mock
```
> **Kết quả mong muốn (in ra màn hình):**
> - Dòng đầu: `Chế độ sinh: MOCK`
> - `Sinh 8 dạng. Tổng item merge-ready: ... · all_ok=True`
> - 8 dòng, mỗi dạng: `[reading_s1] 5 item · QC 5 · merge-ready 5 · {...} · đủ-pool=True` … (các dạng: `reading_s1, reading_s2_notice, reading_s3_comprehension, reading_s4_cloze, writing_w1_rewrite, writing_w2_letter, speaking, listening`).
> - Trong thư mục `out_test_mock/`: **8 file `*_bundle.json` + 8 file `*.docx`**.
> ✅ **Đạt (PASS)** nếu: đủ 8 dạng, không dạng nào lỗi, mỗi dạng `item ≥ 1` và `QC ≥ 1`.
> ⚠️ *Lưu ý:* mock sinh nội dung "giả" (chỗ giữ) — chỉ để kiểm **luồng**, KHÔNG phải chất lượng. Chất lượng xem Bước 4.

---

## Bước 3 — Mở file .docx (GV soát) [OFFLINE]
Mở bằng Word: `out_test_mock/reading_s1.docx` (và thử `reading_s4_cloze.docx`, `listening.docx`).
> **Kết quả mong muốn:** mỗi .docx có: dòng tiêu đề (độ khó/nguồn seed/QC), **phần ĐỀ**, ngắt trang, **phần ĐÁP ÁN**, và dòng **"GV duyệt / Chữ ký / Ngày"** cuối. Bài cloze (R4) có hộp từ; bài Nghe có ghi chú ảnh `[ẢNH ...]` (ảnh giao riêng).
> ✅ **PASS** nếu mở được, thấy đủ phần đề + đáp án + ô ký.

---

## Bước 4 — Sinh thử THẬT bằng Gemini [THẬT]
*(giống Bước 2 nhưng có `.env` chứa key → tự chuyển REAL)*
```bash
python scripts/make_bank_expansion.py \
  --bank-raw tests/fixtures/factory_sample/bank_raw.json \
  --pool-speak tests/fixtures/factory_sample/pool_speak.json \
  --per-seed 2 --out out_test_real
```
Rồi mở `out_test_real/reading_s1_bundle.json` (hoặc `.docx`) đọc câu sinh ra.
> **Kết quả mong muốn:**
> - Dòng đầu: `Chế độ sinh: REAL Gemini (gemini-3.5-flash)`.
> - Câu sinh ra là tiếng Anh **thật, đúng ngữ pháp, KHÁC câu gốc** (cùng điểm ngữ pháp/chủ đề), đúng 4 phương án (R1) / hộp từ (R4) …
> - `count_qc_ok` gần bằng `count`.
> ✅ **PASS** nếu câu đọc được, hợp lý B1, khác nguyên văn seed. ⚠️ **Chất lượng cuối do GV tiếng Anh chấm** — công cụ KHÔNG tự duyệt.

---

## Bước 5 — Cổng kiểm đáp án AI [THẬT]
```bash
python scripts/make_bank_expansion.py \
  --bank-raw tests/fixtures/factory_sample/bank_raw.json \
  --verify --per-seed 1 --out out_test_verify
```
> **Kết quả mong muốn:**
> - Dòng tổng có thêm: `item NGHI đáp án (GV soát): <số>`.
> - Mỗi dạng đọc in thêm `NGHI đáp án <n>` + tạo file `out_test_verify/reading_s*_verify_report.md`.
> - Mở `reading_s1_verify_report.md`: bảng liệt kê item **NGHI** (nếu có) kèm lý do ("checker chọn X, ta gắn Y" …). Nếu 0 NGHI → ghi "Không có item NGHI".
> ✅ **PASS** nếu chạy xong, có báo cáo. ⚠️ *Item NGHI = "cần GV soát", KHÔNG phải "hỏng".* (Nếu chạy không có key sẽ in `⚠ Bỏ qua kiểm đáp án … MOCK`.)

---

## Bước 6 — Đo recall / false-positive của cổng [THẬT]
```bash
python scripts/eval_answer_gate.py
```
> **Kết quả mong muốn:** in `recall (bắt đáp án SAI) = .../... = ~100%` và `flag-khi-đáp-án-ĐÚNG = ... = thấp (0-20%)`.
> ✅ **PASS** nếu **recall cao (bắt hết/gần hết đáp án cài sai)** và FP thấp. (Đây là bằng chứng khách quan cổng hoạt động; đã đo curated 100%/10% + đề sếp thật 100%.)

---

## Bước 7 — Render audio bài Nghe [THẬT · tốn quota, có thể bỏ]
```bash
python scripts/make_lis_variants.py \
  --pool tests/fixtures/factory_sample/pool_lis.json \
  --limit 1 --per-seed 1 --audio --out out_test_audio
```
> **Kết quả mong muốn:** in `🔊 LB1.90-...: <đường dẫn>.mp3 (khoảng 16'-18'...)`. Trong `out_test_audio/audio/` có file `.mp3` (hoặc `.wav` nếu chưa cài lameenc). Mở nghe: có lời dẫn + hội thoại + đoạn nói + khoảng lặng.
> ✅ **PASS** nếu ra file audio nghe được, độ dài ~16-18 phút. ⚠️ **Giọng máy** — GV tiếng Anh phải nghe duyệt. Ảnh chọn-tranh (`--images`) cần bật **billing** ảnh (bỏ qua nếu chưa bật).

---

## Ghi chú quan trọng (đọc trước khi kết luận PASS/FAIL)
1. **Máy chỉ kiểm được CẤU TRÚC** (đủ phương án, đáp án ∈ hộp từ, đủ câu, không trùng…). **Đúng/sai NGỮ NGHĨA + chất lượng tiếng Anh = GV tiếng Anh chấm.** Công cụ KHÔNG bao giờ tự duyệt — luôn có ô GV ký.
2. **Cờ NGHI (SUSPECT) / cảnh báo roundtrip = "người cần xem", KHÔNG phải "hỏng".** Cổng chỉ gắn cờ, không tự xoá.
3. **Mock vs Thật:** mock chứng minh *luồng chạy*; thật chứng minh *chất lượng*. Nên làm cả hai.
4. **Chưa có dữ liệu sếp:** đây là dữ liệu mẫu tổng hợp. Khi sếp gửi bank thật, thay đường dẫn `--bank-raw`/`--pool-*` là chạy y hệt.
5. Muốn soi kỹ 1 dạng: có CLI riêng — `make_r1_variants.py --bank <file>`, `make_r4_variants.py`, `make_lis_variants.py`, `make_speak_variants.py` … (đều có `--verify` cho R1-R4).
