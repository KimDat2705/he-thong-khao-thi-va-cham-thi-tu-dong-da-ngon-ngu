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

## Cần lấy thêm (CONTENT — fetch chỉ thấy tên file, không thấy nội dung)
- Nội dung **Ma trận TOEIC** (Sheet) — để chốt blueprint thật + tiêu chí.
- Cấu trúc 1 file **KEY *.xlsx** (cột nào: số câu? đáp án? part?) — để spec A3.
- Cấu trúc bên trong 1 **LT*.docx** + 1 **RT*.doc** — để spec parser thật (câu/nhóm/đoạn văn nằm thế nào).
