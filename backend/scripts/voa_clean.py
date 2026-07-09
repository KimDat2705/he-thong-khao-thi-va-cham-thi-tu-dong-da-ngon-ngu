"""Tiện ích làm sạch + rút gọn nội dung VOA Learning English cho seed nhà máy (SPEC-FACTORY-026 Bước B).

Vá lỗi nghiệm thu S57m: scraper gốc để lọt RÁC (dòng 'No media source currently available', bảng chú
giải 'Words in This Story' sau dấu '____', footer 'Share/See comments/Follow us/Print') vào mọi seed,
và dùng NGUYÊN bài báo (444-945 từ) làm passage R3 — quá dài so với chuẩn B1 R3 (~110-150 từ).
"""
import re

# Dòng điều hướng/footer VOA (viết thường để so) — bỏ hẳn khỏi ngữ liệu.
_JUNK_EXACT = {"share", "see comments", "follow us", "print", "no media source currently available"}
# Dòng phân cách trước bảng chú giải 'Words in This Story' — toàn dấu gạch dưới.
_SEP = re.compile(r"^[_\s]{5,}$")
# Hãng tin thương mại (để GHI CỜ nguồn — minh bạch; KHÔNG chặn: Đạt coi VOA như nguồn mở).
_WIRE = re.compile(r"Agence France-Presse|Reuters|Associated Press|\bAFP\b|\bAP\b")


def clean_paragraphs(content: str) -> list:
    """Tách nội dung thô VOA → danh sách đoạn SẠCH (bỏ media-placeholder, chú giải, footer)."""
    paras = [p.strip() for p in re.split(r"\n+", str(content or "")) if p.strip()]
    out = []
    for p in paras:
        low = p.lower()
        if p.startswith("No media source"):
            continue
        if low.startswith("words in this story"):
            break                       # tới bảng chú giải → dừng, bỏ hết phần sau
        if _SEP.match(p):
            break                       # dòng '______' phân cách glossary → dừng
        if low in _JUNK_EXACT:
            continue
        # TIÊU ĐỀ PHỤ giữa bài (vd 'Returning muscle function') = đoạn NGẮN, KHÔNG kết bằng dấu câu →
        # bỏ (vá S57m: lọt vào passage làm bẩn ngữ liệu). Body thật luôn kết bằng . ! ? " ' hoặc dài.
        if len(p.split()) <= 6 and p[-1] not in ".!?\"')”’":
            continue
        out.append(p)
    return out


def b1_excerpt(paras: list, target_words: int = 130) -> str:
    """Rút gọn về ngữ liệu B1 R3: ghép các CÂU đầu (lead = tóm tắt tự nhiên của bài) tới ~target_words.

    Cắt trọn câu (không cắt giữa câu). Lấy phần đầu bài vì lead VOA thường tự chứa đủ ý cho câu hỏi.
    """
    text = " ".join(paras)
    sents = re.split(r"(?<=[.!?])\s+", text)
    out, wc = [], 0
    for s in sents:
        s = s.strip()
        if not s:
            continue
        out.append(s)
        wc += len(s.split())
        if wc >= target_words:
            break
    return " ".join(out)


def wire_source(content: str):
    """Trả tên hãng tin thương mại được dẫn nguồn (AP/AFP/Reuters) nếu có — để GHI CỜ minh bạch."""
    hits = sorted(set(m.group(0) for m in _WIRE.finditer(str(content or ""))))
    return ", ".join(hits) if hits else None
