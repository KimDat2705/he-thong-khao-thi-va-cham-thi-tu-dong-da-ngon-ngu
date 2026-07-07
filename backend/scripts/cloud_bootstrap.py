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

# Đề 2601 chuẩn = 50 câu (Đọc 30 + Viết 2 + Nghe 15 + Nói 3). Gate idempotency đếm ĐỦ số câu
# thay vì chỉ "đề tồn tại": với DB BỀN (Supabase, SPEC-FACTORY-020) một lần seed chết giữa chừng
# (commit Exam xong nhưng chưa commit câu) sẽ tồn tại VĨNH VIỄN nếu chỉ check tồn tại — gate
# đếm-đủ để lần build sau seed lại (seed_b1_exam tự delete-recreate khi đề chưa có bài nộp).
B1_EXAM_EXPECTED_QUESTIONS = 50
B1_AUDIO_FILENAME = "3. NGHE (audio) — LB1-2601.mp3"


def _render_env_guard() -> None:
    """Chạy trên Render mà DATABASE_URL chưa đặt/còn trỏ SQLite → FAIL BUILD ngay, thông điệp rõ.

    Không có guard này: bootstrap seed vào SQLite bỏ đi + log 'done.' xanh giả → tưởng đã
    chuyển DB nhưng LIVE vẫn ephemeral (review đối kháng S57 C4). Render luôn đặt env RENDER=true.
    """
    if not os.environ.get("RENDER"):
        return  # máy local/dev — cho phép SQLite
    url = os.environ.get("DATABASE_URL", "")
    if not url or url.startswith("sqlite"):
        print("Bootstrap ERROR: chạy trên Render nhưng DATABASE_URL chưa đặt (hoặc còn SQLite "
              "ephemeral). Đặt chuỗi Supabase Session-Pooler ở Render dashboard → Environment "
              "rồi deploy lại. DỪNG build để không deploy bản mất-dữ-liệu.")
        sys.exit(1)


def _b1_already_seeded() -> bool:
    """Đề 2601 đã seed ĐẦY ĐỦ chưa (đề tồn tại VÀ đủ số câu — xem B1_EXAM_EXPECTED_QUESTIONS)."""
    try:
        from app.core.database import SessionLocal
        from app.models.exam import Exam
        from app.models.question import Question
        db = SessionLocal()
        try:
            exam = db.query(Exam).filter(Exam.title == "VSTEP B1 — Đề 2601 (đề thật)").first()
            if not exam:
                return False
            n = db.query(Question).filter(Question.exam_id == exam.id).count()
            if n < B1_EXAM_EXPECTED_QUESTIONS:
                print(f"Bootstrap: đề 2601 tồn tại nhưng chỉ có {n}/{B1_EXAM_EXPECTED_QUESTIONS} câu "
                      "(seed dở dang?) → sẽ seed lại.")
                return False
            return True
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


def _b1_audio_missing() -> bool:
    """Audio đề 2601 thiếu trên disk? Disk Render reset MỖI BUILD dù DB bền (Supabase) —
    nếu chỉ gate theo DB thì build sau lần seed đầu sẽ không tải audio → /audio/... 404
    (review đối kháng S57 C6)."""
    return not os.path.isfile(os.path.join(AUDIO_DIR, B1_AUDIO_FILENAME))


def _bank_assets_missing() -> bool:
    """Asset bank enrich (static/audio_gen + static/img) thiếu/rỗng trên disk? (cùng lớp C6)."""
    for sub in ("audio_gen", "img"):
        d = os.path.join(BACKEND_DIR, "static", sub)
        if not (os.path.isdir(d) and os.listdir(d)):
            return True
    return False


def _print_seed_error(e: Exception, what: str) -> None:
    """Phân loại lỗi seed: lỗi KẾT NỐI DB in chẩn đoán thẳng hướng (review S57 C10)."""
    try:
        from sqlalchemy.exc import OperationalError
        is_conn = isinstance(e, OperationalError)
    except Exception:
        is_conn = False
    if is_conn:
        print(f"Bootstrap ERROR: không kết nối được DATABASE_URL khi {what} — kiểm tra: "
              "(1) project Supabase có đang PAUSED không (free pause sau ~7 ngày idle → Restore "
              "trên dashboard); (2) chuỗi có đúng SESSION-POOLER host ...pooler.supabase.com:5432 "
              f"không; (3) mật khẩu có percent-encode ký tự đặc biệt chưa. Chi tiết: {e}")
    else:
        print(f"Bootstrap WARNING: {what} failed -> {type(e).__name__}: {e}")


def _seed_b1_bank_from_archive(seed_db: bool = True) -> None:
    """Tải zip bank → LUÔN copy asset (audio/ảnh) ra static; seed DB chỉ khi seed_db=True.

    Tách 2 việc vì disk (asset) reset mỗi build còn DB (Supabase) bền — bank đã seed vẫn
    phải bù asset cho image build mới (review S57 C6).
    """
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

    if not seed_db:
        # Chỉ bù asset cho image build mới — DB (Supabase) đã có bank, KHÔNG seed lại.
        shutil.rmtree(temp_extract_dir)
        print("Bootstrap: B1 bank assets restored to static/ (DB đã seed — bỏ qua seed JSON).")
        return

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
    """Seed/sync the admin user from ADMIN_USERNAME/ADMIN_PASSWORD env vars.

    On an EXISTING admin, the password is re-synced from env ONLY when ADMIN_PASSWORD
    is explicitly set — so a redeploy never silently reverts a password (e.g. one
    rotated via the app) to a weak hardcoded default. If ADMIN_PASSWORD is unset, a
    brand-new admin is created with a dev-only default AND a loud warning; set
    ADMIN_PASSWORD in the host env (Render dashboard) for any deployed instance.
    """
    from app.models.user import User
    from app.core.security import hash_password

    admin_username = os.environ.get("ADMIN_USERNAME", "admin")
    env_password = os.environ.get("ADMIN_PASSWORD")  # None if unset — do NOT default here

    existing = db.query(User).filter(User.username == admin_username).first()
    if not existing:
        if not env_password:
            print("Bootstrap WARNING: ADMIN_PASSWORD not set — seeding admin with a WEAK dev-only "
                  "default. Set ADMIN_PASSWORD in the host env for any deployed instance.")
        admin_user = User(
            username=admin_username,
            hashed_password=hash_password(env_password or "adminpassword"),
            full_name="Admin Demo",
            role="admin",
            is_active=True,
        )
        db.add(admin_user)
        db.commit()
        print(f"Seeded admin user '{admin_username}' successfully.")
    elif env_password:
        existing.hashed_password = hash_password(env_password)
        db.commit()
        print(f"Synced password for admin user '{admin_username}' from ADMIN_PASSWORD env.")
    else:
        print(f"Admin user '{admin_username}' exists; ADMIN_PASSWORD not set — leaving password unchanged.")


def _download(file_id: str, dest: str) -> None:
    if os.path.isfile(dest) and os.path.getsize(dest) > 0:
        print(f"  cached {os.path.basename(dest)}")
        return
    import gdown
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    print(f"  downloading {os.path.basename(dest)} ...")
    gdown.download(id=file_id, output=dest, quiet=True)


def main() -> None:
    _render_env_guard()   # Render + thiếu DATABASE_URL → FAIL BUILD ngay (không seed vào SQLite bỏ đi)

    b1_seeded = _b1_already_seeded()
    audio_missing = _b1_audio_missing()

    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(AUDIO_DIR, exist_ok=True)

    # DB bền (Supabase) nhưng disk reset mỗi build → tải folder đề khi CẦN SEED *hoặc* CẦN BÙ AUDIO.
    if not b1_seeded or audio_missing:
        try:
            print("Bootstrap: downloading VSTEP B1 folder from Drive ...")
            b1_dir = os.path.join(DATA_DIR, "B1_2601")
            os.makedirs(b1_dir, exist_ok=True)
            import gdown
            print(f"  downloading B1 folder to {b1_dir} ...")
            gdown.download_folder(id="1umWw1j24-HNeOpHTzF3c2J7g_v-C76F-", output=b1_dir, quiet=True)

            os.environ["B1_INPUT_DIR"] = b1_dir
            os.environ["AUDIO_DIR"] = AUDIO_DIR

            if not b1_seeded:
                print("Bootstrap: seeding VSTEP B1 real exam ...")
                import seed_b1_real_exam
                seed_b1_real_exam.main()          # seed cũng tự copy audio vào AUDIO_DIR
            else:
                # DB đủ 50 câu — chỉ bù file audio cho image build mới (audio_url='/audio/<file>').
                src_audio = os.path.join(b1_dir, B1_AUDIO_FILENAME)
                if os.path.isfile(src_audio):
                    shutil.copy2(src_audio, os.path.join(AUDIO_DIR, B1_AUDIO_FILENAME))
                    print(f"Bootstrap: restored exam audio asset -> {os.path.join(AUDIO_DIR, B1_AUDIO_FILENAME)}")
                else:
                    raise FileNotFoundError(f"Audio '{B1_AUDIO_FILENAME}' not found in downloaded B1 folder.")
        except Exception as e:
            _print_seed_error(e, "seed/bù asset đề 2601")
            if not b1_seeded:
                # Lần seed ĐẦU thất bại → build ĐỎ (deploy không có đề là vô nghĩa + gate
                # đếm-đủ-câu sẽ seed lại ở build sau). Data đã đủ mà chỉ bù asset lỗi → không chặn.
                sys.exit(1)
    else:
        print("Bootstrap: VSTEP B1 already seeded (đủ câu) + audio asset OK — skipping.")

    # Bank: DB đã seed vẫn phải bù asset (static/audio_gen + static/img) cho image build mới.
    b1_bank_seeded = _b1_bank_already_seeded()
    if not b1_bank_seeded or _bank_assets_missing():
        try:
            _seed_b1_bank_from_archive(seed_db=not b1_bank_seeded)
        except Exception as e:
            _print_seed_error(e, "seed/bù asset bank B1")
    else:
        print("Bootstrap: VSTEP B1 bank already seeded + assets OK — skipping.")

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
