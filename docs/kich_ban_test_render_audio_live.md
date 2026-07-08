# Kịch bản test: Render audio bộ Nghe trên LIVE (SPEC-FACTORY-024)

> Mục tiêu: bấm nút **🎧 Render audio bộ Nghe** trên web LIVE → tạo file audio thật cho một bộ Nghe →
> **đo thời lượng (kỳ vọng 16–18 phút)** + xác nhận trọn đường sidecar Supabase → nghe thử + duyệt.
> Làm bằng trình duyệt, tài khoản **admin**. Không cần câu lệnh.

---

## 0. Chuẩn bị (1 lần)

| # | Việc | Kết quả mong đợi |
|---|---|---|
| 0.1 | Đợi deploy xong sau lần push mới (Render backend build ~3–5 phút, Vercel frontend ~1–2 phút). | Deploy 2 nơi báo "success". |
| 0.2 | Mở **trang demo (link Vercel của Đạt)** trên trình duyệt. | Trang đăng nhập hiện ra. |
| 0.3 | Đăng nhập bằng tài khoản **admin** (mật khẩu admin LIVE của Đạt). | Vào được, có menu quản trị. |
| 0.4 | Vào trang **`/admin/bank`** (tab "Duyệt ngân hàng câu hỏi"). | Thấy 2 ô thống kê + panel "✨ AI Sinh Câu Hỏi" + panel "🏭 Nhà máy sinh câu" + bảng câu hỏi. |

> ⚠️ **Render đầu tiên hơi chậm**: Render free ngủ sau 15′ → lần bấm đầu backend phải "thức dậy" ~30–60s. Cứ chờ.

---

## Phần A — Sinh 1 bộ Nghe MỚI (để chắc chắn có sidecar)

> Vì sao: nút render đọc lại "bản thô" (transcript gốc) từ **Supabase Storage** (sidecar). Sidecar chỉ được
> cất cho các bộ Nghe **sinh sau bản cập nhật gần đây**. Sinh 1 bộ mới ngay bây giờ = chắc chắn có sidecar.
> (Nếu Đạt biết chắc đã có bộ Nghe mới sinh gần đây → có thể bỏ qua Phần A, sang thẳng Phần B.)

| # | Bấm gì | Kết quả mong đợi |
|---|---|---|
| A.1 | Ở panel **🏭 Nhà máy sinh câu**, ô **"Dạng câu"** → chọn **"L · Nghe (5 chọn-tranh part 7 + 10 điền-từ part 8…)"** | Dòng chú thích dưới đổi thành "✍ Tự luận — KHÔNG có cổng kiểm đáp án AI…" (Nghe do GV soát tay). |
| A.2 | **"Số đề mẫu"** = `1` · **"Biến thể/đề"** = `1` · **"Engine"** = **Gemini (thật)** | (Ô kiểm cổng đáp án bị khoá — đúng, Nghe không có cổng tự động.) |
| A.3 | Bấm **"🏭 Chạy nhà máy sinh câu"** | Nút xoay + dòng chữ "Nhà máy đang chạy nền… · ~N phút". |
| A.4 | Chờ (~1–3 phút). | Băng **xanh**: "Nhà máy đã sinh & lưu … câu/nhóm câu vào ngân hàng (dạng Nháp)…". Bộ lọc tự nhảy về **Part 7**. |

> ✅ Vừa tạo: **5 câu Part 7** (chọn-tranh) + **1 nhóm Part 8** (10 câu điền-từ) — tất cả **chưa có audio** + đã cất sidecar lên Supabase.
> ❌ Nếu báo **lỗi 500 / "internal error"**: Gemini đang lỗi tạm thời → chờ vài phút rồi bấm lại A.3.

---

## Phần B — Render audio cho bộ Nghe

| # | Bấm gì | Kết quả mong đợi |
|---|---|---|
| B.1 | Ở **"Bộ lọc tìm kiếm"** phía dưới, ô **"Part"** → chọn **"Part 8: Nghe - Điền thông tin (L2)"** | Bảng hiện các câu Part 8. Cột **Trạng thái** của bộ vừa sinh có 2 nhãn: **Draft** + **🎧 chưa audio** (cam). |
| B.2 | Bấm vào **mã số `#…`** (hoặc nội dung) của **một** câu Part 8 vừa sinh | Mở **hộp chi tiết câu hỏi**. Cuối hộp (góc trái) có checkbox **"Kèm ảnh chọn-tranh part 7 (tốn phí)"** + nút xanh ngọc **"🎧 Render audio bộ Nghe"**. |
| B.3 | **ĐỂ TRỐNG** ô "Kèm ảnh…" (lần đầu chỉ đo audio) | Checkbox không tích. |
| B.4 | Bấm **"🎧 Render audio bộ Nghe"** | Nút đổi thành "Đang render audio…" (xoay) + dòng "Đang render audio (TTS đọc trọn bài giọng C)… · ~N phút". |
| B.5 | **Chờ ~10–15 phút** (đây là bước lâu — TTS đọc trọn bài, đọc-2-lần). Có thể để yên tab. | Con số phút tăng dần. Đừng bấm lại nút. |
| B.6 | Khi xong | Băng **xanh** ở đầu trang: **"Đã render audio bộ Nghe (~`X` phút, MP3) — gắn cho nhóm part 8 + 5 câu part 7. Bộ Nghe giờ có thể duyệt."** Hộp chi tiết tự đóng. |

> 🎯 **CON SỐ CẦN ĐỌC = `X` phút** trong băng xanh. **Đạt đối chiếu: `X` nằm trong 16–18′ là ĐẠT.**
> Nếu lệch (ví dụ <16′ hoặc >18′) → báo lại, tôi tinh chỉnh lại pause/độ dài kịch bản.

---

## Phần C — Kiểm tra kết quả (nghe thử + duyệt)

| # | Bấm gì | Kết quả mong đợi |
|---|---|---|
| C.1 | Vẫn bộ lọc **Part 8**, mở lại **một** câu của bộ vừa render | Trong hộp chi tiết có mục **"File âm thanh (Listening)"** với **trình phát audio** (nút play). |
| C.2 | Bấm **play** nghe thử | Nghe được **giọng nữ (Sulafat) + giọng nam (Charon)**, đọc chậm rõ, có lời dẫn "Part One / Now listen again / Part Two…", đọc-2-lần. |
| C.3 | Đóng hộp, nhìn cột **Trạng thái** | Nhãn đã đổi thành **🎧 có audio** (xanh) cho cả bộ (Part 8 + Part 7). |
| C.4 | (Tùy chọn — duyệt thử) Tích ô chọn vài câu của bộ → bấm **"Duyệt câu đã chọn"** | Duyệt **thành công** (trước khi có audio sẽ bị chặn 400 — giờ đã mở khoá). |

> ✅ Nếu C.1–C.3 đạt + `X` ∈ 16–18′ → **render pipeline LIVE chạy đúng trọn đường** (sinh → sidecar Supabase → render → gắn audio → nghe được → duyệt được).

---

## Xử lý sự cố

| Hiện tượng | Nguyên nhân | Cách xử lý |
|---|---|---|
| Không thấy nút "🎧 Render audio bộ Nghe" trong hộp | Đang mở câu **Part 7** (nút chỉ ở **Part 8**), hoặc bộ **đã có audio** rồi | Lọc **Part 8**, mở câu **🎧 chưa audio**. |
| Băng đỏ **"…500 INTERNAL…"** khi sinh hoặc render | Gemini lỗi tạm thời (server Google) | Chờ vài phút, bấm lại. Không phải lỗi hệ thống mình. |
| Băng đỏ **"Không tải được bundle Nghe … từ Storage / thiếu sidecar"** | Bộ Nghe này sinh **trước** bản có sidecar | Làm **Phần A** (sinh bộ MỚI) rồi render bộ mới đó. |
| Băng đỏ **"Quá 20 phút chờ hiển thị…"** | Mạng chậm / render lâu hơn dự kiến | Job **vẫn chạy nền**. ĐỪNG bấm lại. Chờ ít phút, mở lại câu Part 8 — nếu đã có trình phát audio là đã xong. |
| Bị đá về trang đăng nhập | Phiên hết hạn | Đăng nhập lại admin, làm lại từ Phần B. |

## Ghi chú
- **Ảnh chọn-tranh part 7 (checkbox "tốn phí")**: để lần sau. Khi tích → sinh thêm 3 tranh A/B/C cho mỗi câu Part 7 bằng Imagen (tốn phí billing). Lần đo duration đầu **không cần**.
- Bộ Nghe sinh để test là **Nháp** — không lọt vào đề thi. Đạt có thể xoá sau ở ngân hàng nếu muốn gọn.
- Audio là **giọng máy Gemini** (đã tinh chỉnh chậm ~167 wpm chuẩn B1). GV tiếng Anh nên nghe duyệt trước khi dùng thật.
