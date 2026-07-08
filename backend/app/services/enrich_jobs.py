"""Async question-enrichment jobs (SPEC-BANK-006).

The synchronous ``/enrich`` endpoint caps generation at 5 questions to stay under
the HTTP timeout. This module runs enrichment as a background job so the API can
accept larger batches (up to ``MAX_ASYNC_COUNT``): the POST returns a ``job_id``
immediately and the client polls ``GET /bank/tasks/{job_id}`` for progress.

Execution model — chosen so it behaves on every deployment target:
  * A real Celery worker (broker reachable, not eager) -> ``enrich_bank_task.delay``.
  * No worker (Render free tier: no Redis; also when ``CELERY_TASK_ALWAYS_EAGER``
    is on) -> a daemon thread runs the job in-process so a 50-question batch does
    not block the POST past the HTTP timeout.
  * Tests set ``RUN_JOBS_INLINE=True`` to execute synchronously and deterministically.

Job status lives in an in-memory dict. On Render free the API runs as a single
uvicorn process, so the POST (which starts the job) and the polling GET share the
same store. NOTE (MVP limitation — see the mvp-scaling-decision note): the store is
per-process and cleared on restart; a multi-process / multi-host deployment would
need a shared store (Redis result backend or a dedicated DB table). Deferred with
the rest of the scaling work.
"""
import logging
import threading
import uuid
from typing import Optional

from app.core.celery import celery_app
from app.core.database import SessionLocal

logger = logging.getLogger(__name__)

# Valid VSTEP B1 parts accepted by the enrichment generators
# (Reading 1-4, Writing 5-6, Listening 7-8, Speaking 9-11).
VALID_PARTS = {"1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11"}

# Upper bound for a single async batch (SPEC-BANK-006 AC: up to 50 câu/lần).
MAX_ASYNC_COUNT = 50

# Cap on retained job records to bound memory in the long-running web process.
_MAX_JOBS = 500

# Test seam: when True, dispatch runs the job inline (same thread) for determinism.
RUN_JOBS_INLINE = False

# job_id -> {job_id, status, part, requested, generated_count, error}
# status in: pending | running | completed | error
_JOBS: dict = {}
_LOCK = threading.Lock()


def create_job(part: str, count: int) -> str:
    """Register a new pending job and return its id."""
    job_id = uuid.uuid4().hex
    with _LOCK:
        # Bound memory: drop the oldest records once the store grows large. Dicts
        # keep insertion order, so the first keys are the oldest jobs (MVP
        # in-memory store; see module docstring).
        while len(_JOBS) >= _MAX_JOBS:
            _JOBS.pop(next(iter(_JOBS)))
        _JOBS[job_id] = {
            "job_id": job_id,
            "status": "pending",
            "part": part,
            "requested": count,
            "generated_count": 0,
            "error": None,
        }
    return job_id


def get_job(job_id: str) -> Optional[dict]:
    """Return a copy of the job record, or None if unknown."""
    with _LOCK:
        job = _JOBS.get(job_id)
        return dict(job) if job else None


def _set(job_id: str, **fields) -> None:
    with _LOCK:
        if job_id in _JOBS:
            _JOBS[job_id].update(fields)


def run_generator(
    generator,
    db,
    part: str,
    count: int,
    topic: Optional[str],
    difficulty: Optional[str],
) -> int:
    """Dispatch to the part-specific B1 generator and return the saved count.

    ``part`` must already be validated against ``VALID_PARTS`` by the caller.
    Shared by both the synchronous ``/enrich`` endpoint and the async job runner.
    """
    if part == "1":
        return generator.generate_r1_questions(db, count, topic, req_difficulty=difficulty)
    elif part == "2":
        return generator.generate_r2_questions(db, count, topic, req_difficulty=difficulty)
    elif part == "3":
        return generator.generate_r3_groups(db, count, topic, req_difficulty=difficulty)
    elif part == "4":
        return generator.generate_r4_groups(db, count, topic, req_difficulty=difficulty)
    elif part == "5":
        return generator.generate_writing_questions(db, count, 5, topic, req_difficulty=difficulty)
    elif part == "6":
        return generator.generate_writing_questions(db, count, 6, topic, req_difficulty=difficulty)
    elif part == "7":
        return generator.generate_l1_questions(db, count, topic, req_difficulty=difficulty)
    elif part == "8":
        return generator.generate_l2_groups(db, count, topic, req_difficulty=difficulty)
    elif part == "9":
        return generator.generate_speaking_questions(db, count, 9, topic, req_difficulty=difficulty)
    elif part == "10":
        return generator.generate_speaking_questions(db, count, 10, topic, req_difficulty=difficulty)
    elif part == "11":
        return generator.generate_speaking_questions(db, count, 11, topic, req_difficulty=difficulty)
    raise ValueError(f"Unsupported part: {part}")


def run_enrich_job(
    job_id: str,
    part: str,
    count: int,
    topic: Optional[str] = None,
    difficulty: Optional[str] = None,
) -> None:
    """Execute one enrichment job and record its outcome in the job store.

    Opens its own DB session (this runs outside any request), so it is safe from a
    Celery worker or a background thread. Tests point ``SessionLocal`` at the test
    engine to observe the drafts it writes.
    """
    from app.services.b1_question_gen import B1QuestionGenerator

    _set(job_id, status="running")
    db = SessionLocal()
    try:
        generator = B1QuestionGenerator()
        generated = run_generator(generator, db, part, count, topic, difficulty)
        _set(job_id, status="completed", generated_count=generated)
        logger.info(f"Enrich job {job_id} completed: {generated} item(s) for part {part}.")
    except Exception as exc:  # surface any generator failure to the client
        db.rollback()
        _set(job_id, status="error", error=str(exc))
        logger.error(f"Enrich job {job_id} failed: {exc}")
    finally:
        db.close()


def dispatch_enrich_job(
    job_id: str,
    part: str,
    count: int,
    topic: Optional[str],
    difficulty: Optional[str],
) -> None:
    """Start a job on the best available executor (see module docstring)."""
    if RUN_JOBS_INLINE:
        run_enrich_job(job_id, part, count, topic, difficulty)
        return

    # Prefer a real Celery worker only when one can actually consume the task
    # (broker reachable and not in eager mode). Otherwise fall through to a thread.
    if not celery_app.conf.task_always_eager:
        try:
            from app.workers.tasks import enrich_bank_task

            enrich_bank_task.delay(job_id, part, count, topic, difficulty)
            return
        except Exception as exc:  # broker unreachable (Render free: no Redis)
            logger.warning(f"Celery broker unavailable ({exc}); running enrich job in a thread.")

    threading.Thread(
        target=run_enrich_job,
        args=(job_id, part, count, topic, difficulty),
        daemon=True,
    ).start()


# ----------------------------------------------------------------------------
# NHÀ MÁY SINH CÂU (boss_factory) → ngân hàng. Tái dùng nguyên job store ở trên.
# Khác /enrich thường: sinh biến thể BÁM SEED thật + qua CỔNG KIỂM ĐÁP ÁN AI (R1–R4) trước khi lưu.
# Không có Celery task riêng → luôn chạy trong daemon thread (Render free không có worker).
# ----------------------------------------------------------------------------

def run_factory_job(
    job_id: str,
    skill: str,
    limit: int = 3,
    per_seed: int = 1,
    engine: str = "gemini",
    verify: bool = True,
) -> None:
    """Chạy một lượt nhà máy → lưu ngân hàng, ghi kết quả vào job store.

    engine='mock' → generator=None (không gọi Gemini, chỉ test luồng); ngược lại B1QuestionGenerator.
    Mở DB session riêng (chạy ngoài request). Test trỏ SessionLocal vào engine test để soi câu đã lưu.
    """
    from app.services import factory_service
    from app.services.b1_question_gen import B1QuestionGenerator

    _set(job_id, status="running")
    db = SessionLocal()
    try:
        generator = None if engine == "mock" else B1QuestionGenerator()
        result = factory_service.run_factory_to_bank(
            db, skill, limit=limit, per_seed=per_seed, verify=verify, generator=generator
        )
        _set(
            job_id,
            status="completed",
            generated_count=result["saved_questions"] + result["saved_groups"],
            skill=skill,
            saved_questions=result["saved_questions"],
            saved_groups=result["saved_groups"],
            qc_ok=result["qc_ok"],
            answer_suspect=result["answer_suspect"],
        )
        logger.info(f"Factory job {job_id} completed: {result}")
    except Exception as exc:  # surface any failure to the client
        db.rollback()
        _set(job_id, status="error", error=str(exc))
        logger.error(f"Factory job {job_id} failed: {exc}")
    finally:
        db.close()


def dispatch_factory_job(
    job_id: str,
    skill: str,
    limit: int,
    per_seed: int,
    engine: str,
    verify: bool,
) -> None:
    """Khởi chạy factory job trên daemon thread (hoặc inline khi RUN_JOBS_INLINE cho test)."""
    if RUN_JOBS_INLINE:
        run_factory_job(job_id, skill, limit, per_seed, engine, verify)
        return
    threading.Thread(
        target=run_factory_job,
        args=(job_id, skill, limit, per_seed, engine, verify),
        daemon=True,
    ).start()


# ----------------------------------------------------------------------------
# RENDER AUDIO (+ảnh) cho bộ Nghe đã có trong ngân hàng (SPEC-FACTORY-024). Op DÀI (nhiều call TTS +
# retry, vài→10+ phút) → BẮT BUỘC chạy nền, KHÔNG inline request. Tái dùng job store ở trên.
# ----------------------------------------------------------------------------

def run_render_lis_job(job_id: str, group_id: int, with_images: bool = False) -> None:
    """Render audio (+ảnh opt-in) cho bộ Nghe của nhóm part 8 `group_id` → gắn URL, ghi kết quả job store.

    Mở DB session riêng (chạy ngoài request). Cần B1QuestionGenerator có client (GEMINI_API_KEY) cho TTS.
    """
    from app.services import listening_render
    from app.services.b1_question_gen import B1QuestionGenerator

    _set(job_id, status="running")
    db = SessionLocal()
    try:
        generator = B1QuestionGenerator()
        result = listening_render.render_listening_media(db, group_id, generator, with_images=with_images)
        _set(job_id, status="completed", generated_count=1, **result)
        logger.info(f"Render Nghe job {job_id} completed: {result}")
    except Exception as exc:  # surface any failure to the client
        db.rollback()
        _set(job_id, status="error", error=str(exc))
        logger.error(f"Render Nghe job {job_id} failed: {exc}")
    finally:
        db.close()


def dispatch_render_lis_job(job_id: str, group_id: int, with_images: bool) -> None:
    """Khởi chạy render job trên daemon thread (hoặc inline khi RUN_JOBS_INLINE cho test)."""
    if RUN_JOBS_INLINE:
        run_render_lis_job(job_id, group_id, with_images)
        return
    threading.Thread(
        target=run_render_lis_job,
        args=(job_id, group_id, with_images),
        daemon=True,
    ).start()
