"""
Helpers for extracting embedded image assets from .docx files.

Used by the VSTEP B1 real-exam seeder (scripts/seed_b1_real_exam.py) to persist
question images pulled from partner Word files.
"""


def _ext_for(part):
    name = str(part.partname).lower()
    for e in (".png", ".jpeg", ".jpg", ".gif", ".bmp"):
        if name.endswith(e):
            return ".jpg" if e == ".jpeg" else e
    return ".png"
