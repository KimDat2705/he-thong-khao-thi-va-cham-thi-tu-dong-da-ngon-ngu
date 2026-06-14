# Dữ liệu Input (đối tác cung cấp) — phân hệ Ra đề

> **NGUỒN SỰ THẬT cho định dạng dữ liệu đầu vào.** Đạt cung cấp 15/06/2026, **không gửi lại** — đây là bản ghi duy nhất. Dùng để spec Parser/Blueprint đúng theo thực tế (KHÔNG đoán).
>
> ✅ **Đính chính (15/06)**: "Excel đáp án" trong docstring `test_specs_parser.py` là **ĐÚNG** — file đáp án `.xlsx` (KEY LT*/KEY RT*) nằm trong **thư mục con**, không ở gốc nên dễ tưởng không có. (Đã fetch xác nhận.)

## Thư mục gốc
- https://drive.google.com/drive/folders/17Jp859TDZCkIZw9jjLTEuV5_tp4sY7dk
- Gốc: 📁 BỘ ĐỀ TOEIC · 📁 BỘ ĐỀ B1 · 📁 Ma trận TOEIC · 📁 Ma trận B1 · 📁 CHỨC NĂNG RA ĐỀ · 📄 BÁO GIÁ….docx · 📄 kien_truc_he_thong_v2.html

## TOEIC — cấu trúc thực tế (đã fetch 15/06)

| Thư mục | Link | Nội dung thật |
|---|---|---|
| **Ma trận TOEIC** | [1RcAkl9](https://drive.google.com/drive/folders/1RcAkl9EJxuoD-RvpxuniwC_kk-mj3WBC) | **1 Google Sheet**: "Ma trận đề thi Toeic, CLO, quy trình, tiêu chí trộn đề Toeic 2026" → **blueprint THẬT + tiêu chí trộn đề** (có thể chính là nguồn của các luật GEN-001/002/003/MATRIX) |
| **Đề Đọc — câu hỏi** | [1U5R534](https://drive.google.com/drive/folders/1U5R534cnVwxQ5AwWqhlXXqfJ5Heggyb8) | 15 Word "CDR TOEIC - RT2601..RT2615": **12 file `.doc` legacy** + 2 `.docx` (RT2605, RT2611) → **cần convert .doc→.docx** |
| **Đề Đọc — đáp án** | [1NuVKX](https://drive.google.com/drive/folders/1NuVKX_zuUifbb7rvgiy7NBLna1oVPHIE) | **13 file `.xlsx`** "KEY RT.2601..2615" → **đáp án Reading (RIÊNG)** |
| **Đề Nghe — câu hỏi** | [1J9PC85](https://drive.google.com/drive/folders/1J9PC85qiWjy0-dZzZ8ZzhlINEhvxYk9e) | 15 `.docx` "LT2601..LT2629" (lẻ), 2.3–4.3 MB |
| **Đề Nghe — audio** | [1ZCMecyx](https://drive.google.com/drive/folders/1ZCMecyx2rsv9gvdw6NfSFrH0I5w7gCSh) | **15 `.mp3` ~100MB**, đặt tên theo DẢI "2601-2604.mp3 … 2629-2630.mp3" → **audio gộp nhiều đề/một file** (KHÔNG per-câu) |
| **Đề Nghe — đáp án** | [1IXEboDk](https://drive.google.com/drive/folders/1IXEboDkJTl9GAqJHghpVdfGLksGBbyuF) | **15 `.xlsx`** "Key LT2601..2629" (lẻ) → **đáp án Listening (RIÊNG)** |

## B1 (VSTEP) — chưa fetch chi tiết
- **Ma trận B1**: https://drive.google.com/drive/folders/1ZLPf-pihP3Ij50DVgZ419j_hc1ADU4b9
- **Bộ đề B1** (Đạt gửi nhiều link; mục đầu dạng markdown-link có 2 ID):
  - https://drive.google.com/drive/folders/11I30Q23oyZ5dXcp-wNZJT77vUqKl16vI
  - https://drive.google.com/drive/folders/1philfoo3XJXDfYk41rjAbTx9t5avMvy_
  - https://drive.google.com/drive/folders/1wXJbAoxdIWK9VWdnx2kZWRhVr_doCyl7
  - https://drive.google.com/drive/folders/1ViJGi5SwHake2IxKWUxv5DqFClD08blZ
  - https://drive.google.com/drive/folders/1NKM-Uw9_erFFcLFG0YuJnwZ2eKnmQMt5
  - https://drive.google.com/drive/folders/1cOfbf38hADCE7J78SyTGyy-o2LwRZWkj
  - https://drive.google.com/drive/folders/196AUX8TElWQQpxfJEFqvldUG9EjDav6n

## Hệ quả cho thiết kế (QUAN TRỌNG)

1. **Đáp án nằm file `.xlsx` RIÊNG** (KEY LT*/KEY RT*), KHÔNG inline trong đề → Parser thật phải **merge câu hỏi (.docx/.doc) + đáp án (.xlsx)** theo khoá (mã đề + số câu). Parser hiện đọc `Answer:` inline (format tự chế) → **không khớp dữ liệu thật**.
2. **Reading nhiều `.doc` legacy** → cần bước **convert .doc→.docx** trước parse (A4 là THẬT).
3. **Audio MP3 gộp theo dải (~100MB, "2601-2604.mp3")** → một file chứa nhiều đề. Quy ước A2 `{SetID}_P{Part}_{NN}.mp3` (per-câu, file riêng) **KHÔNG khớp thực tế** → mô hình audio cần thiết kế lại (mapping đề→file+đoạn/timestamp). A2 hiện chỉ đúng trên fixture giả.
4. **Ma trận = Google Sheet** ("tiêu chí trộn đề") → nhiều khả năng định nghĩa CHÍNH các luật ta đang code (độ khó/topic/cân bằng). Cần đối chiếu để xác nhận blueprint hardcode khớp thực tế + làm nền Blueprint-as-Data.

## CÁCH TRUY XUẤT NỘI DUNG (đã chạy được 15/06)
Tải về máy + parse bằng Python (cũng chính là việc parser thật sẽ làm). KHÔNG commit dữ liệu đối tác vào repo — tải vào thư mục NGOÀI repo: `D:\Dat-Antigravity\drive_input\`.
```bash
export PYTHONUTF8=1   # tránh lỗi charmap với tên file tiếng Việt
python -m pip install gdown openpyxl python-docx
# Thư mục thường: python -m gdown --folder "<folder_url>" -O "<đích>"
# Google Sheet: tải bản xuất xlsx (đủ tab):
python -m gdown "https://docs.google.com/spreadsheets/d/<SHEET_ID>/export?format=xlsx" -O matrix.xlsx
```
Bỏ qua thư mục audio (~1.5GB MP3). `.doc` legacy: python-docx KHÔNG đọc được, cần convert (LibreOffice/`docx2txt`/`antiword`).

## NỘI DUNG THẬT đã đọc (15/06) — đối chiếu spec

### Ma trận TOEIC (Sheet, 5 tab: Hướng dẫn · Tổng thể · Listening · Reading · Tiêu chí QC) — ĐÂY LÀ SPEC THẬT
- **Số câu/part = ĐÚNG KHỚP `TOEIC_BLUEPRINT`**: P1=6, P2=25, P3=39 (13 set×3), P4=30 (10 set×3), P5=30, P6=16 (4 set×4), P7=54 (đơn/đôi/ba) → 200 (L100+R100). ✓ Blueprint hardcode CHÍNH XÁC, không cần đổi số.
- **Độ khó 25/50/25 theo TỪNG KỸ NĂNG** (L100, R100 riêng), dạng KHOẢNG: mỗi kỹ năng Dễ 22–28 / TB 47–53 / Khó 22–28; toàn đề Dễ 25%±3, TB 50%±4, Khó 25%±3. → SPEC-MATRIX-002 "toàn-đề" nên reframe **per-skill** (không phải bound 200 như hiện tại).
- **Độ khó per-part**: P1 2/3/1 ✓, P2 6/13/6 ✓, P5 8/15/7 ✓ (KHỚP ta). Nhưng P3 8/21/10, P4 6/16/8, P6 3/8/5, P7 9/28/17 — tính theo **CÂU**, KHÔNG phải bội số của set → mô hình hiện gán độ khó theo NHÓM là **giản lược** (refine sau).
- **Luật trộn đề xác nhận spec ta đã làm**: giữ nguyên set 3/4/6/7 (ISOLATE-003 ✓); "không chủ điểm >20%" (GEN-003 ✓); cân bằng khóa đáp án (GEN-002 ✓); ngưỡng overlap giữa mã đề (GEN-004 ✓); chỉ item Approved (BANK-001 ✓).
- **Khái niệm MỚI** (chưa có trong specs): `Exposure_Count` (số lần dùng item/set), `Overlap_Group`, cân bằng single/double/triple passage (P7), metadata phong phú (Speaker_Count/Speech_Rate/Accent/Passage_Type/Source_Format/Topic_Domain — model đã có một phần).

### Đáp án `KEY *.xlsx` (đọc được qua openpyxl)
- Lưới đơn giản: tiêu đề "TOEIC - LISTENING - LT2601"; các cặp cột **"Câu | Đáp án"** (5 block: 1-20, 21-40, …, 81-100) → Listening **100 câu**, mỗi câu 1 đáp án A/B/C/D. Reading KEY tương tự (100 câu). **Khoá liên kết = Mã đề** (LT2601/RT2601).
- → spec A3: parse xlsx, gom các cặp Câu→Đáp án, merge với câu hỏi theo Mã đề + số câu.

### Đề `LT*.docx` (đọc được qua python-docx) — PARSER THẬT KHÁC HẲN fixture giả
- Word phức tạp: ~41 paragraph + **15 bảng (tables)** + ảnh (Part 1 photos). Mã đề nằm trong bảng ("Mã đề thi LT.2601"). Có header trường/ĐH, "Part 3:/Part 4:" + Directions, "THE END".
- **Câu hỏi/lựa chọn nằm trong TABLES + ảnh**, KHÔNG phải format thẻ `[Group]/[Question]/Key:Value` tự chế. **KHÔNG có đáp án inline** (đáp án ở KEY xlsx).
- → Parser thật phải: đọc **tables** (python-docx), trích **ảnh** Part 1 (→image_url), nhận diện Part/Directions/số câu, **merge KEY xlsx theo Mã đề**. Lớn hơn nhiều A1 giả lập (A1/A2 hiện chỉ là scaffolding trên fixture).

> Dữ liệu mẫu đã tải về `D:\Dat-Antigravity\drive_input\` (MatranTOEIC.xlsx, KEY_LT/, LT/) — ngoài repo, không commit.

### Cấu trúc chi tiết đề `LT*.docx` (15 bảng — research cho parser .docx về sau)
Câu hỏi nằm trong **tables** + ảnh, đánh số 1-100, KHÔNG đáp án (đáp án ở KEY xlsx):
- TABLE 0: header trường/ĐH/môn. **TABLE 1: "Mã đề thi LT.2601"** (khoá liên kết KEY).
- TABLE 2: directions "LISTENING TEST".
- **Part 1 (câu 1-6)**: bảng chứa số câu ("4.","5.","6.") + **ẢNH** (inline_shapes) — không có options dạng text (nhìn tranh, nghe).
- **Part 2 (câu 7-31)**: bảng "N.  Mark your answer on your answer sheet." — KHÔNG options trong đề (Q + đáp lời qua audio).
- **Part 3/4 (câu 32-100)**: bảng, mỗi ô = "N. <câu hỏi> / (A) … / (B) … / (C) … / (D) …" — câu hỏi + 4 lựa chọn ngay trong cell. Header "PART 2/Part 3:/Part 4:" xen kẽ paragraph/table.
- → **Parser `.docx` thật phải**: trích Mã đề (table); duyệt tables; nhận Part qua header; regex tách "số câu + 4 options" ở cell P3/4; trích ảnh P1; câu Part 1-2 không có options text; **merge KEY xlsx theo Mã đề + số câu** để gắn đáp án. (Reading RT*.doc: phần lớn `.doc` legacy cần convert trước.)
