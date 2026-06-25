"""
Cloud bootstrap: prepare the TOEIC demo database on a fresh server WITHOUT
committing any partner data to the repo.

On startup it downloads the partner source files (Listening/Reading .docx, answer
.xlsx, consolidated audio .mp3) from Google Drive by file id, then runs the demo
seed (parse -> backfill -> extract images -> approve -> generate). Idempotent: if
the database already contains a generated exam, it does nothing.

Intended start command (e.g. Render, root dir = backend):
    python scripts/cloud_bootstrap.py && uvicorn app.main:app --host 0.0.0.0 --port $PORT

Required env (set in the host dashboard, shared with the uvicorn process):
    DATABASE_URL   e.g. sqlite:///./demo_toeic.db
    AUDIO_DIR      e.g. ./audio_data   (must match what the server mounts at /audio)
"""
import os
import sys

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# Google Drive file ids for the demo set (LT2601 Listening + RT2605 Reading).
FILES = {
    "LT_DOCX": ("1NTt51-mO-bNAaNi1XgySGIIT4onyTG4h", "LT2601.docx"),
    "LT_KEY": ("1zUZ-mhyku-oobVZvdl1jnZMQ5N-_8w5u", "Key_LT2601.xlsx"),
    "RT_DOCX": ("1AVtDIYt8u8yJ3DtAZqdpTboQ5V4-Log8", "RT2605.docx"),
    "RT_KEY": ("1DR3afj9H6BSQ0mi-mb-LUpVSHKl49eLh", "KEY_RT2605.xlsx"),
}
# Audio file name must satisfy find_audio_file()'s range pattern "<start> - <end>.mp3".
AUDIO_FILE = ("15HV-VVmh6YZMRn-K1DxgFtBSIkOsL2Jc", "2601 - 2604.mp3")

DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BACKEND_DIR, ".bootstrap_data"))
AUDIO_DIR = os.environ.get("AUDIO_DIR", os.path.join(BACKEND_DIR, "audio_data"))
os.environ.setdefault("DATABASE_URL", "sqlite:///./demo_toeic.db")


def _toeic_already_seeded() -> bool:
    try:
        from app.core.database import SessionLocal
        from app.models.exam import Exam
        db = SessionLocal()
        try:
            return db.query(Exam).filter(Exam.title == "TOEIC Demo Exam (seed)").count() > 0
        finally:
            db.close()
    except Exception:
        return False


def _b1_already_seeded() -> bool:
    try:
        from app.core.database import SessionLocal
        from app.models.exam import Exam
        db = SessionLocal()
        try:
            return db.query(Exam).filter(Exam.title == "VSTEP B1 — Đề 2601 (đề thật)").count() > 0
        finally:
            db.close()
    except Exception:
        return False


def _download(file_id: str, dest: str) -> None:
    if os.path.isfile(dest) and os.path.getsize(dest) > 0:
        print(f"  cached {os.path.basename(dest)}")
        return
    import gdown
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    print(f"  downloading {os.path.basename(dest)} ...")
    gdown.download(id=file_id, output=dest, quiet=True)


def main() -> None:
    toeic_seeded = _toeic_already_seeded()
    b1_seeded = _b1_already_seeded()

    if toeic_seeded and b1_seeded:
        print("Bootstrap: database already seeded — skipping.")
        return

    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(AUDIO_DIR, exist_ok=True)

    if not toeic_seeded:
        print("Bootstrap: downloading TOEIC partner data from Drive ...")
        paths = {}
        for env_key, (fid, name) in FILES.items():
            dest = os.path.join(DATA_DIR, name)
            _download(fid, dest)
            paths[env_key] = dest
        audio_dest = os.path.join(AUDIO_DIR, AUDIO_FILE[1])
        _download(AUDIO_FILE[0], audio_dest)

        # Point the seed at the downloaded files.
        os.environ["LT_DOCX"] = paths["LT_DOCX"]
        os.environ["LT_KEY"] = paths["LT_KEY"]
        os.environ["RT_DOCX"] = paths["RT_DOCX"]
        os.environ["RT_KEY"] = paths["RT_KEY"]
        os.environ["AUDIO_DIR"] = AUDIO_DIR

        print("Bootstrap: seeding TOEIC database ...")
        import seed_toeic_demo  # noqa: E402  (scripts/ on sys.path via __file__ dir)
        seed_toeic_demo.main()

        # Seed the free-text (AI-graded) demo exams too — no partner data needed.
        # These make the GRADE-003/Gemini essay-grading path demoable live (Writing +
        # a mixed VSTEP Reading+Writing exam). Requires CELERY_TASK_ALWAYS_EAGER=true
        # in the environment so grading completes without a separate Celery worker.
        print("Bootstrap: seeding free-text demo exams (Writing / VSTEP) ...")
        import seed_writing_demo  # noqa: E402
        seed_writing_demo.main()
        import seed_vstep_demo  # noqa: E402
        seed_vstep_demo.main()
    else:
        print("Bootstrap: TOEIC already seeded — skipping TOEIC download/seeding.")

    if not b1_seeded:
        print("Bootstrap: downloading VSTEP B1 folder from Drive ...")
        b1_dir = os.path.join(DATA_DIR, "B1_2601")
        os.makedirs(b1_dir, exist_ok=True)
        import gdown
        print(f"  downloading B1 folder to {b1_dir} ...")
        gdown.download_folder(id="1umWw1j24-HNeOpHTzF3c2J7g_v-C76F-", output=b1_dir, quiet=True)

        os.environ["B1_INPUT_DIR"] = b1_dir
        os.environ["AUDIO_DIR"] = AUDIO_DIR

        print("Bootstrap: seeding VSTEP B1 real exam ...")
        import seed_b1_real_exam
        seed_b1_real_exam.main()
    else:
        print("Bootstrap: VSTEP B1 already seeded — skipping B1 download/seeding.")
    print("Bootstrap: done.")


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(__file__))  # allow importing sibling seed script
    main()
