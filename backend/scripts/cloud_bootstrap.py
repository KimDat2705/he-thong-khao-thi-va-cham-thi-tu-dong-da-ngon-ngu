"""
Cloud bootstrap: prepare the VSTEP B1 database on a fresh server.

On startup it downloads the VSTEP B1 source files and bank package from Google Drive
by file id, then runs the seeders. Idempotent: if the database already contains
the B1 exam, it does nothing.
"""
import os
import sys
import zipfile
import shutil

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(BACKEND_DIR, ".env"))

DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BACKEND_DIR, ".bootstrap_data"))
AUDIO_DIR = os.environ.get("AUDIO_DIR", os.path.join(BACKEND_DIR, "audio_data"))
os.environ.setdefault("DATABASE_URL", "sqlite:///./demo_toeic.db")  # DB name kept for SQLite path consistency


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


def _b1_bank_already_seeded() -> bool:
    try:
        from app.core.database import SessionLocal
        from app.models.question import Question
        db = SessionLocal()
        try:
            return db.query(Question).filter(
                Question.exam_id.is_(None),
                Question.exam_type == "VSTEP_B1"
            ).count() > 0
        finally:
            db.close()
    except Exception:
        return False


def _seed_b1_bank_from_archive() -> None:
    zip_id = os.environ.get("B1_BANK_ZIP_ID", "")
    if not zip_id:
        print("Bootstrap WARNING: B1_BANK_ZIP_ID environment variable not set. Skipping B1 bank bootstrap.")
        return

    zip_dest = os.path.join(DATA_DIR, "b1_bank_assets.zip")
    print(f"Bootstrap: downloading B1 bank package from Drive (ID: {zip_id}) ...")
    _download(zip_id, zip_dest)

    if not os.path.isfile(zip_dest) or os.path.getsize(zip_dest) == 0:
        raise FileNotFoundError("Downloaded B1 bank zip file is missing or empty.")

    temp_extract_dir = os.path.join(DATA_DIR, "b1_bank_temp")
    os.makedirs(temp_extract_dir, exist_ok=True)

    print("Bootstrap: extracting B1 bank assets ...")
    with zipfile.ZipFile(zip_dest, "r") as zip_ref:
        zip_ref.extractall(temp_extract_dir)

    json_src = None
    
    # Walk through extracted files and place them correctly
    for root, dirs, files in os.walk(temp_extract_dir):
        for file in files:
            full_file_path = os.path.join(root, file)
            # Find the export JSON
            if file == "b1_bank_export.json":
                json_src = full_file_path
            
            # Identify asset target directory
            relative_dir = os.path.relpath(root, temp_extract_dir)
            if "audio_gen" in relative_dir:
                target_dir = os.path.join(BACKEND_DIR, "static", "audio_gen")
                os.makedirs(target_dir, exist_ok=True)
                shutil.copy2(full_file_path, os.path.join(target_dir, file))
            elif "img" in relative_dir:
                target_dir = os.path.join(BACKEND_DIR, "static", "img")
                os.makedirs(target_dir, exist_ok=True)
                shutil.copy2(full_file_path, os.path.join(target_dir, file))

    if not json_src:
        raise FileNotFoundError("Could not find b1_bank_export.json inside the zip package.")

    # Copy json to DATA_DIR
    target_json = os.path.join(DATA_DIR, "b1_bank_export.json")
    shutil.copy2(json_src, target_json)

    print("Bootstrap: seeding VSTEP B1 bank from extracted JSON ...")
    from app.core.database import SessionLocal
    from seed_b1_bank import seed_from_json
    db = SessionLocal()
    try:
        seed_from_json(db, target_json)
    finally:
        db.close()
    
    # Clean up temp extraction dir
    shutil.rmtree(temp_extract_dir)
    print("Bootstrap: VSTEP B1 bank seeding completed successfully.")


def seed_admin_user(db) -> None:
    """Seed the admin user for testing and local management.
    Reads ADMIN_USERNAME/ADMIN_PASSWORD environment variables.
    """
    from app.models.user import User
    from app.core.security import hash_password

    admin_username = os.environ.get("ADMIN_USERNAME", "admin")
    admin_password = os.environ.get("ADMIN_PASSWORD", "adminpassword")

    existing = db.query(User).filter(User.username == admin_username).first()
    if not existing:
        admin_user = User(
            username=admin_username,
            hashed_password=hash_password(admin_password),
            full_name="Admin Demo",
            role="admin",
            is_active=True
        )
        db.add(admin_user)
        db.commit()
        print(f"Seeded admin user '{admin_username}' successfully.")
    else:
        existing.hashed_password = hash_password(admin_password)
        db.commit()
        print(f"Updated password for admin user '{admin_username}' from environment.")


def _download(file_id: str, dest: str) -> None:
    if os.path.isfile(dest) and os.path.getsize(dest) > 0:
        print(f"  cached {os.path.basename(dest)}")
        return
    import gdown
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    print(f"  downloading {os.path.basename(dest)} ...")
    gdown.download(id=file_id, output=dest, quiet=True)


def main() -> None:
    b1_seeded = _b1_already_seeded()

    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(AUDIO_DIR, exist_ok=True)

    if not b1_seeded:
        try:
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
        except Exception as e:
            print(f"Bootstrap WARNING: B1 seed failed -> {type(e).__name__}: {e}")
    else:
        print("Bootstrap: VSTEP B1 already seeded — skipping B1 download/seeding.")

    # Seed B1 Bank if not already seeded
    b1_bank_seeded = _b1_bank_already_seeded()
    if not b1_bank_seeded:
        try:
            _seed_b1_bank_from_archive()
        except Exception as e:
            print(f"Bootstrap WARNING: B1 bank seed failed -> {type(e).__name__}: {e}")
    else:
        print("Bootstrap: VSTEP B1 bank already seeded — skipping B1 bank bootstrap.")

    # Always seed admin user to make sure auth works
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        seed_admin_user(db)
    except Exception as e:
        print(f"Bootstrap WARNING: Seeding admin user failed -> {type(e).__name__}: {e}")
    finally:
        db.close()

    print("Bootstrap: done.")


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(__file__))  # allow importing sibling seed script
    main()
