# KỊCH BẢN TEST TAY — HỆ THỐNG WEB LIVE (VSTEP B1)
### Nghiệm thu đầy đủ chức năng qua trình duyệt — từ mở link → đăng nhập → làm bài → chấm → quản trị

> **Đây là bản test cho HỆ WEB đang chạy thật trên mạng** (khác với "nhà máy sinh câu" chạy offline bằng file `.bat`).
> Bạn chỉ cần **một trình duyệt** (Chrome/Edge). Mỗi bước ghi rõ: **👉 Làm gì** → **✅ Kết quả mong muốn** (để bạn check chéo) → **☐ ô tick** để bạn tự đánh Đạt/Không.
> Làm **Phần A (Thí sinh) trước**, rồi **Phần B (Quản trị)** — vì Phần B cần có bài thí sinh vừa nộp để xem/chấm/phân tích.

---

## 🔗 ĐỊA CHỈ & TÀI KHOẢN

| Thứ | Giá trị |
|---|---|
| **Trang web (frontend)** | **https://he-thong-khao-thi-va-cham-thi-tu-do.vercel.app** |
| Máy chủ chấm (backend — chỉ dùng để "đánh thức") | https://toeic-backend-5n57.onrender.com/api/v1/exams |
| Tài khoản **Thí sinh** | Bạn **tự đăng ký** ở Bước A2 (không cần xin ai) |
| Tài khoản **Quản trị/Giáo viên** | Tên đăng nhập **`admin`** + **mật khẩu bạn đã đặt trên Render** (`ADMIN_PASSWORD`) |

> ⚠️ **Nếu quên mật khẩu admin:** vào Render → dịch vụ backend → tab **Environment** → xem/sửa biến `ADMIN_PASSWORD` → lưu (backend tự deploy lại). Không có mật khẩu thì **không làm được Phần B**.

---

## 🟡 BƯỚC B0 — ĐÁNH THỨC HỆ THỐNG (làm 1 lần, quan trọng)

Máy chủ dùng gói **miễn phí** nên **ngủ sau ~15 phút** không ai dùng. Lần bấm đầu tiên có thể phải chờ.

**👉 Làm gì:** Mở tab mới, dán link máy chủ chấm: `https://toeic-backend-5n57.onrender.com/api/v1/exams` → Enter → **chờ 30–60 giây** cho lần đầu.

**✅ Kết quả mong muốn:** Trang hiện một dòng chữ JSON có `"title":"VSTEP B1 — Đề 2601 (đề thật)"`, `"question_count":50`. → Máy chủ đã thức.

☐ Đạt ☐ Không — Ghi chú: ________________

> Nếu chờ >90 giây vẫn xoay/lỗi: tải lại trang 1 lần nữa. Vẫn lỗi → báo kỹ thuật (máy chủ có thể đang deploy).

---

# PHẦN A — VAI THÍ SINH (làm bài & xem điểm)

## A1 — Mở trang chủ
**👉 Làm gì:** Vào **https://he-thong-khao-thi-va-cham-thi-tu-do.vercel.app**

**✅ Kết quả mong muốn:**
- Tiêu đề lớn: **"Hệ thống Khảo thí và Chấm thi Đa ngôn ngữ"**
- Dòng phụ: **"Phân hệ Tạo đề & Chấm thi VSTEP B1 (AI-Powered)"**
- Có 3 nút: **"Xem đề thi →"**, **"Đăng nhập"**, **"Vào quản trị →"**

☐ Đạt ☐ Không

## A2 — Đăng ký tài khoản thí sinh
**👉 Làm gì:** Bấm **"Đăng nhập"** → ở trang đăng nhập bấm link **"Chưa có tài khoản? Đăng ký"** (hoặc vào thẳng `/register`). Nhập **Tên đăng nhập** (vd `thisinh1`) + **Mật khẩu** (vd `123456`) + Họ tên (tuỳ chọn) → bấm **"Đăng ký"**.

**✅ Kết quả mong muốn:** Nhảy về trang đăng nhập kèm dòng xanh **"Đăng ký thành công! Hãy đăng nhập tài khoản của bạn."**

☐ Đạt ☐ Không

> Thử đăng ký trùng tên → phải báo đỏ **"Tên đăng nhập đã tồn tại trên hệ thống."** (chứng tỏ có kiểm tra trùng).

## A3 — Đăng nhập (thí sinh)
**👉 Làm gì:** Nhập tài khoản vừa tạo → bấm **"Đăng nhập"**.

**✅ Kết quả mong muốn:** Tự chuyển tới trang **danh sách đề** (`/exams`), góc trên có huy hiệu **"Thí sinh"** + nút **"Đăng xuất"**.

☐ Đạt ☐ Không

> Thử sai mật khẩu → phải báo **"Tên đăng nhập hoặc mật khẩu không chính xác."**

## A4 — Xem danh sách đề & cấu trúc đề
**👉 Làm gì:** Ở trang **"Danh sách đề thi khả dụng"**, tìm thẻ đề **"VSTEP B1 — Đề 2601 (đề thật)"**. Bấm **"Xem cấu trúc"**.

**✅ Kết quả mong muốn:**
- Thẻ đề hiển thị: huy hiệu **VSTEP_B1**, **"⏱️ Thời lượng: 135 phút"**, **"📝 Số câu hỏi: 50 câu"**.
- Trang cấu trúc chia theo **Part 1…**, mỗi phần ghi loại + số câu; phần Nghe có ô **"🎧 Audio phần Nghe"**; **đáp án bị ẩn** (ghi "chế độ thí sinh — ẩn đáp án").
- Nếu bấm **"Hiện đáp án (giáo viên)"** với tư cách thí sinh → **không xem được** (chặn quyền). ✅ Đúng mong muốn (bảo mật đáp án).

☐ Đạt ☐ Không

## A5 — Vào phòng thi giám sát
**👉 Làm gì:** Quay lại `/exams`, bấm **"Làm bài →"** trên đề 2601.

**✅ Kết quả mong muốn:** Hiện màn hình **"🛡️ Phòng thi giám sát"** với lưu ý: sẽ **toàn màn hình**, **bật webcam**, **chuyển tab/thoát toàn màn hình = vi phạm**, **vi phạm 3 lần → tự nộp**, thời gian **135 phút**. Có nút **"Bắt đầu làm bài"**.

☐ Đạt ☐ Không

## A6 — Bắt đầu + kiểm giám sát (proctoring)
**👉 Làm gì:** Bấm **"Bắt đầu làm bài"**. Trình duyệt hỏi quyền **toàn màn hình** và **webcam** → bấm **Cho phép/Allow**.

**✅ Kết quả mong muốn:**
- Màn hình chuyển **toàn màn hình**; góc phải-dưới có **ô webcam nhỏ** + dòng đỏ **"● Đang giám sát"** (nếu không cho webcam thì ghi "📷 Webcam chưa bật" — vẫn thi được).
- Thanh trên cùng cố định: tiến độ **"Đã làm: 0/50 câu"**, đồng hồ **"⏱ 134:5x"** đang đếm lùi, huy hiệu vi phạm **"⚠ 0/3"** (xanh), nút **"Nộp bài"**.

☐ Đạt ☐ Không

**👉 (Tuỳ chọn) Thử vi phạm 1 lần:** Bấm phím **Esc** (thoát toàn màn hình) HOẶC Alt+Tab sang cửa sổ khác rồi quay lại.
**✅ Kết quả mong muốn:** Hiện băng đỏ **"Cảnh báo (1/3): bạn vừa rời khỏi màn hình thi…"**, huy hiệu đổi thành **"⚠ 1/3"**. (Đừng lặp 3 lần trừ khi muốn thử tự-nộp.)

☐ Đạt ☐ Không

## A7 — Làm thử đủ các dạng câu
Đề 2601 có đủ 4 kỹ năng. **Không cần làm hết 50 câu** — chỉ cần chạm mỗi dạng để kiểm hiển thị + để có dữ liệu chấm:

| Dạng | 👉 Làm gì | ✅ Kết quả mong muốn |
|---|---|---|
| **Nghe — chọn tranh** | Bấm nút **"🎧 Audio phần Nghe"** để nghe; chọn 1 tranh A/B/C | Audio phát được; ô tranh được chọn **viền xanh** |
| **Nghe — điền** | Gõ 1 từ vào ô trống | Chữ hiện trong ô |
| **Đọc — trắc nghiệm** | Chọn 1 đáp án A/B/C/D | Ô chọn **viền + nền xanh** |
| **Đọc — điền từ** | Gõ từ vào ô "Điền từ vào đây…" | Chữ hiện trong ô |
| **Viết (tự luận)** | Ở câu Viết, gõ 1 đoạn tiếng Anh ngắn (vài câu) | Có đếm **"… từ"** ở góc phải ô |
| **Nói (ghi âm)** | Bấm **"● Ghi âm"** nói vài giây → **"■ Dừng"**; *hoặc* bấm **"Tải file audio"** chọn 1 file audio bất kỳ | Sau khi xong hiện **"✓ Đã có bản ghi"** + trình phát audio |

> 💡 Để **thử chấm AI** ở bước sau, nhớ **có làm ít nhất 1 câu Viết (gõ chữ)** và **1 câu Nói (ghi/tải audio)**.

☐ Đạt ☐ Không — dạng nào lỗi: ________________

## A8 — (Tuỳ chọn) Kiểm tự lưu & làm dở
**👉 Làm gì:** Đang thi, đóng hẳn tab. Mở lại `/exams`.

**✅ Kết quả mong muốn:** Thẻ đề 2601 có huy hiệu vàng **"Đang làm dở"** và nút đổi thành **"Tiếp tục bài đang làm →"**. Bấm vào → **quay lại đúng bài**, đồng hồ **tiếp tục từ thời gian còn lại** (đếm ở máy chủ, không reset), các câu đã làm **vẫn còn** (tự lưu mỗi ~15 giây).

☐ Đạt ☐ Không

## A9 — Nộp bài & xem chấm
**👉 Làm gì:** Bấm **"Nộp bài"** → xác nhận **"Bạn có chắc chắn muốn nộp bài không?"** → Đồng ý.

**✅ Kết quả mong muốn:**
- Phần **trắc nghiệm (Nghe/Đọc) chấm ngay**.
- Phần tự luận: hiện **"Đang chấm bằng AI (Gemini)…"** (xoay vài giây → tối đa ~1–2 phút), rồi hiện:
  - Vòng tròn **tổng điểm**, huy hiệu trạng thái.
  - Mục **"Trắc nghiệm (Reading)"**: số câu đúng.
  - **"Nhận xét chi tiết từ AI (phần Viết)"**: mỗi bài có **điểm /10** + nhận xét + thẻ lỗi ngữ pháp **"❌ … → ✓ …"**.
  - **"Nhận xét chi tiết từ AI (phần Nói)"**: điểm /10 + bản ghi lời (transcription) + **"Lỗi phát âm:"**.
- Có nút **"Kết quả của tôi"**.

☐ Đạt ☐ Không

> **🔎 Cách phân biệt CHẤM THẬT vs CHẤM THỬ (mock):**
> - **THẬT (đã cắm khoá AI):** điểm **lẻ** (vd 6.5 / 7.2), nhận xét **tiếng Anh chi tiết riêng cho bài**, có liệt kê lỗi ngữ pháp cụ thể.
> - **THỬ/mock (chưa cắm khoá):** điểm **tròn cố định** (Viết 8.0, Nói 7.5), nhận xét chứa chữ **"mock"** hoặc **"Gemini API key missing"** → **báo kỹ thuật cắm `GEMINI_API_KEY` trên Render**.

## A10 — Lịch sử "Kết quả của tôi"
**👉 Làm gì:** Bấm **"Kết quả của tôi"** (hoặc vào `/my-results`).

**✅ Kết quả mong muốn:** Có thẻ bài vừa nộp: **"Bài nộp #…"**, tên đề, "Nộp lúc: …", trạng thái **"Đã chấm xong"** (xanh), cột **"Viết (AI)"** + **"Tổng điểm"**, link **"Xem chi tiết →"**.

☐ Đạt ☐ Không

## A11 — Chi tiết bài nộp
**👉 Làm gì:** Bấm **"Xem chi tiết →"** (`/submissions/…`).

**✅ Kết quả mong muốn:** Hiện đầy đủ: điểm tổng, **"Bài làm tự luận & nhận xét AI (Viết)"** (đề + bài làm của bạn + nhận xét AI + lỗi ngữ pháp), **"Bài làm & nhận xét AI (Nói)"** (trình phát audio + bản ghi lời + nhận xét). *(Ô "Duyệt/điều chỉnh điểm" chỉ hiện khi đăng nhập bằng giáo viên — xem Phần B.)*

☐ Đạt ☐ Không

**👉 Kết thúc vai thí sinh:** bấm **"Đăng xuất"**.

---

# PHẦN B — VAI GIÁO VIÊN / QUẢN TRỊ

## B1 — Đăng nhập quản trị
**👉 Làm gì:** Trang chủ → **"Vào quản trị →"** (hoặc `/login`) → đăng nhập **`admin`** + mật khẩu Render.

**✅ Kết quả mong muốn:** Vào trang **`/admin`**, có 2 tab: **"Quản trị đề thi"** và **"Duyệt ngân hàng câu hỏi"**, nút **"Đăng xuất"** đỏ góc phải.

☐ Đạt ☐ Không

## B2 — Xem tồn kho ngân hàng & sinh đề mới
**👉 Làm gì:** Ở tab **"Quản trị đề thi"**, xem bảng **"Tồn kho ngân hàng (approved vs blueprint)"**. Bấm **"Sinh đề VSTEP B1 mới"**.

**✅ Kết quả mong muốn:**
- Bảng tồn kho liệt kê Part 1…11 với cột **Approved / Cần / Đủ?** (**✓ đủ** hoặc **✗ thiếu**).
- Sau khi bấm (chờ vài giây): mục **"Đề đã sinh"** xuất hiện **1 đề mới** (vd "#2 · VSTEP_B1 · 50 câu · … phút").

☐ Đạt ☐ Không

> Nếu báo lỗi "ngân hàng chưa đủ" (409): nghĩa là có Part cột **Đủ?** = **✗ thiếu** → cần làm giàu thêm ngân hàng (Bước B4) rồi sinh lại. Đây là hành vi đúng (không sinh đề khi thiếu câu).

## B3 — Phát hành / Ẩn / Sửa đề
**👉 Làm gì:** Trên đề vừa sinh: bấm **"Phát hành"** (rồi thử **"Ẩn đề"**); bấm **"Sửa"** đổi tiêu đề/thời lượng → **"Lưu"**.

**✅ Kết quả mong muốn:** Huy hiệu đổi **"Đã phát hành"** (xanh) ↔ **"Đã ẩn"** (xám); sửa xong tiêu đề/thời lượng cập nhật ngay.

☐ Đạt ☐ Không

## B4 — Ngân hàng câu hỏi: AI sinh câu (Enrichment)
**👉 Làm gì:** Sang tab **"Duyệt ngân hàng câu hỏi"** (`/admin/bank`). Trong ô xanh **"Tự động sinh câu hỏi bằng AI (Enrichment)"**: chọn **Part** (vd *Part 1: Đọc - Câu trắc nghiệm (R1)*), **Chủ đề** (vd Sức khỏe), **Số lượng** = 3, **Độ khó** = Trung bình → bấm **"AI Sinh Câu Hỏi"**.

**✅ Kết quả mong muốn:**
- Hiện dòng **"AI đang xử lý nền… câu nháp sẽ xuất hiện khi hoàn tất"** (lô lớn có thể mất vài phút).
- Sau đó danh sách câu (lọc **Trạng thái = Draft**) có thêm **3 câu nháp mới** đúng Part đã chọn.
- Nội dung là tiếng Anh thật (nếu đã cắm khoá AI); nếu là chữ mock → báo kỹ thuật cắm khoá.

☐ Đạt ☐ Không

## B5 — Duyệt câu (Draft → Approved) & Nhân bản AI
**👉 Làm gì:**
1. Ở bảng câu hỏi, **tick** vài câu Draft → bấm **"Duyệt câu đã chọn"**.
2. **Bấm vào 1 câu trắc nghiệm** để mở chi tiết → ở cuối bấm **"🧬 Nhân bản AI (Paraphrase)"** (chọn số biến thể 1–5).

**✅ Kết quả mong muốn:**
- Câu đã duyệt đổi huy hiệu **Draft (vàng) → Approved (xanh)**; con số "Tổng đã duyệt" tăng.
- Modal chi tiết hiện đủ: nội dung, phương án (đáp án đúng **tô xanh**), giải thích; sau khi nhân bản → sinh thêm **biến thể nháp mới** (giữ điểm ngữ pháp + đáp án, viết lại khác chữ). *(Câu không phải trắc nghiệm → hiện "Chỉ nhân bản được câu trắc nghiệm có phương án." — đúng mong muốn.)*

☐ Đạt ☐ Không

## B6 — Kết quả đề thi + Phân tích + Chấm lại
**👉 Làm gì:** Về tab **"Quản trị đề thi"** → trên **đề 2601** (đề thí sinh vừa nộp ở Phần A) bấm **"Kết quả"** (`/admin/results/1`).

**✅ Kết quả mong muốn:**
- **Bảng "📊 Phân tích kết quả"**: Tổng số bài nộp, **Điểm trung bình / thấp nhất / cao nhất**, và **bảng phân tích từng câu** (tỷ lệ đúng, phân bố lựa chọn A/B/C/D, điểm AI trung bình cho câu tự luận).
- **Bảng bài nộp**: có dòng của thí sinh vừa nộp + link **"Xem"**.
- **Nút "⬇ Xuất CSV"** ở góc.

☐ Đạt ☐ Không

**👉 Chấm lại (human-in-the-loop):** Bấm **"Xem"** ở dòng bài nộp → cuộn xuống ô **"Duyệt / điều chỉnh điểm (giáo viên)"** → sửa **Điểm Viết**/**Điểm Nói** + gõ **"Nhận xét của giáo viên"** → bấm **"Lưu điểm"**.
**✅ Kết quả mong muốn:** Báo lưu thành công; điểm & nhận xét giáo viên được cập nhật (thí sinh sẽ thấy ở chi tiết bài).

☐ Đạt ☐ Không

## B7 — Xuất CSV kết quả
**👉 Làm gì:** Ở trang kết quả đề, bấm **"⬇ Xuất CSV"**.

**✅ Kết quả mong muốn:** Tải về file `.csv`; mở bằng Excel thấy các cột **Họ tên · Tài khoản · Điểm Nghe · Điểm Đọc · Điểm Viết · Tổng điểm · Trạng thái · Thời gian nộp** (tiếng Việt có dấu hiển thị đúng).

☐ Đạt ☐ Không

## B8 — (Tuỳ chọn, cần 2 cửa sổ) Giám sát thi LIVE
**👉 Làm gì:** Mở **2 cửa sổ**: cửa sổ 1 đăng nhập **thí sinh** và đang **làm bài dở** (Phần A, chưa nộp); cửa sổ 2 đăng nhập **admin** → vào **"Kết quả"** đề đó → xem ô **"Đang làm bài"** → bấm **"↻ Làm mới"**.

**✅ Kết quả mong muốn:** Ô **"Đang làm bài (1)"** hiện tên thí sinh đang thi + **"⏱ mm:ss còn lại"** (đỏ nếu ≤5 phút). Khi thí sinh nộp xong → làm mới thì tên biến khỏi danh sách "đang làm".

☐ Đạt ☐ Không

---

# PHẦN C — BẢNG TỔNG KẾT NGHIỆM THU

| # | Chức năng | Đạt / Không | Ghi chú |
|---|---|---|---|
| A2 | Đăng ký thí sinh (+ chặn trùng tên) | | |
| A3 | Đăng nhập + phân vai đúng | | |
| A4 | Xem đề + ẩn đáp án với thí sinh | | |
| A5–A6 | Phòng thi: toàn màn hình + webcam + đồng hồ + cảnh báo vi phạm | | |
| A7 | Hiển thị đủ 6 dạng câu (Nghe/Đọc/Điền/Viết/Nói) | | |
| A8 | Tự lưu + tiếp tục bài dở (đồng hồ máy chủ) | | |
| A9 | Nộp bài + chấm trắc nghiệm + **chấm AI Viết/Nói** | | |
| A10–A11 | Lịch sử điểm + chi tiết bài + nhận xét AI | | |
| B2 | Xem tồn kho + **sinh đề B1 mới từ ngân hàng** | | |
| B3 | Phát hành / ẩn / sửa đề | | |
| B4 | **AI sinh câu hỏi** (Enrichment) | | |
| B5 | Duyệt câu + **Nhân bản AI (Paraphrase)** | | |
| B6 | **Phân tích kết quả** + **chấm lại (giáo viên sửa điểm)** | | |
| B7 | Xuất CSV | | |
| B8 | Giám sát thi LIVE (tuỳ chọn) | | |

**Kết luận chung:** Đạt ☐ / Đạt-có-chỉnh ☐ / Chưa đạt ☐
**Người nghiệm thu:** __________ **Chữ ký:** __________ **Ngày:** __________

---

## ⛳ RANH GIỚI QUAN TRỌNG — hai thứ khác nhau, đừng nhầm

| | **Hệ web LIVE** (tài liệu này) | **Nhà máy sinh câu** (offline) |
|---|---|---|
| Chạy ở đâu | Trên mạng, qua **link + đăng nhập** | Trên máy, bấm đúp **`.bat`** |
| Làm gì | Thí sinh thi + chấm AI + quản trị/phân tích | **Sinh thêm ngân hàng** 8 dạng B1 + tự kiểm đáp án + render .docx |
| Ai kiểm | Bạn/giáo viên qua trình duyệt | Giáo viên mở .docx kiểm mắt |
| Hướng dẫn | **File này** | `docs/kich_ban_test_thu_cong_nha_may.md` |

> **Vì sao tách:** nhà máy sinh câu (thứ phiên gần đây cải thiện rất nhiều — 8 dạng, cổng kiểm đáp án AI) **chưa gắn lên web** (đúng chủ trương: việc của mình là mở rộng ngân hàng, pipeline ra đề là của sếp). Muốn nghiệm thu nhà máy → dùng bộ test tay riêng ở bảng trên.

---

<details>
<summary>📎 PHỤ LỤC KỸ THUẬT (không bắt buộc đọc)</summary>

- **Máy chủ ngủ:** Render gói free ngủ sau ~15' → lần đầu chờ 30–60s (Bước B0). Trước buổi demo nên "đánh thức" trước.
- **Dữ liệu tạm:** DB gói free **xoá mỗi lần deploy lại** → tài khoản đăng ký & đề sinh ra sẽ mất sau redeploy (bình thường với bản demo). Đề thật "2601" luôn được nạp lại lúc khởi động.
- **Chấm AI thật/mock:** cần biến `GEMINI_API_KEY` trên Render. Có key = chấm thật (`gemini-2.5-flash`); thiếu key = mock (điểm tròn 8.0/7.5, chữ "mock"). Xem dấu hiệu ở Bước A9.
- **Sinh câu lô lớn (Enrichment ≤50):** chạy nền trong tiến trình web (gói free không có worker riêng) → **không nên deploy lại giữa chừng** kẻo mất job đang chạy.
- **Chạy thử trên máy (không qua mạng):** backend `cd backend && uvicorn app.main:app --reload` (cổng 8000) + frontend `cd frontend && npm run dev` (cổng 3000) → mở `http://localhost:3000`. Các bước test y hệt.
- **Kiểm tự động toàn bộ logic:** `cd backend && python -m pytest tests -q` → phải **81 passed**.
</details>
