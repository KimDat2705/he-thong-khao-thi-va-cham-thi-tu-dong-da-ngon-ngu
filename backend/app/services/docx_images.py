"""
Extract embedded images from a real TOEIC Listening .docx for display.

Partner Listening files embed:
- Part 1: one photo per question (Q1-6) — the question content IS the photo.
- Part 3/4: occasional "look at the graphic" images attached to a question group.
The .docx also contains a directions/example photo and header logos that are NOT
question images and must be skipped.

We walk the document body in order, track the current part and the last-seen
question number, and associate each drawing with that question number. Part 1
photos map 1:1 to questions; Part 3/4 graphics map to the group owning that
question number.
"""
import os
import re

from docx import Document
from docx.oxml.text.paragraph import CT_P
from docx.oxml.table import CT_Tbl
from docx.text.paragraph import Paragraph
from docx.table import Table

_DRAW = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}"
_BLIP = "{http://schemas.openxmlformats.org/drawingml/2006/main}blip"
_EMBED = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"


def _drawings(element):
    return element.findall(".//" + _DRAW + "inline") + element.findall(".//" + _DRAW + "anchor")


def _rid(drawing):
    blip = drawing.find(".//" + _BLIP)
    return blip.get(_EMBED) if blip is not None else None


def _ext_for(part):
    name = str(part.partname).lower()
    for e in (".png", ".jpeg", ".jpg", ".gif", ".bmp"):
        if name.endswith(e):
            return ".jpg" if e == ".jpeg" else e
    return ".png"


def extract_question_images(docx_path: str, out_dir: str, set_id: str) -> dict:
    """
    Save question images and return mapping {question_number: relative_path}.
    relative_path is like "<set_id>/q5.png" (under out_dir), suitable for serving.
    """
    doc = Document(docx_path)
    os.makedirs(os.path.join(out_dir, set_id), exist_ok=True)

    current_part = None
    last_qnum = None
    mapping = {}

    def maybe_part(text):
        nonlocal current_part
        m = re.search(r"(?i)\bpart\s*(\d+)", text or "")
        if m:
            current_part = int(m.group(1))

    def maybe_qnum(text):
        nonlocal last_qnum
        m = re.match(r"^\s*(\d{1,3})\.", text or "")
        if m:
            last_qnum = int(m.group(1))

    def handle_drawings(element):
        nonlocal last_qnum
        if last_qnum is None:
            return  # skip example/header images that precede any question number
        for d in _drawings(element):
            rid = _rid(d)
            part = doc.part.related_parts.get(rid) if rid else None
            if part is None:
                continue
            if last_qnum in mapping:
                continue  # one image per question (first wins)
            ext = _ext_for(part)
            rel = f"{set_id}/q{last_qnum}{ext}"
            with open(os.path.join(out_dir, rel), "wb") as f:
                f.write(part.blob)
            mapping[last_qnum] = rel

    for child in doc.element.body:
        if isinstance(child, CT_P):
            p = Paragraph(child, doc)
            t = p.text.strip()
            maybe_part(t)
            maybe_qnum(t)
            handle_drawings(p._element)
        elif isinstance(child, CT_Tbl):
            tb = Table(child, doc)
            joined = " ".join(c.text for r in tb.rows for c in r.cells)
            maybe_part(joined)
            for r in tb.rows:
                for c in r.cells:
                    for para in c.paragraphs:
                        maybe_qnum(para.text.strip())
                        handle_drawings(para._element)

    return mapping
