from celery import Celery
from app.core.config import settings

# Initialize Celery app
celery_app = Celery(
    "grading_tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.workers.tasks"]
)

# Update configuration
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Ho_Chi_Minh",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,  # Don't prefetch too many tasks since AI grading is heavy
    # Run tasks inline when no dedicated worker/broker is available (local demo,
    # Render free tier). The submit endpoint still returns "grading" first; with
    # eager mode the grade is already written by the time the candidate polls.
    task_always_eager=settings.CELERY_TASK_ALWAYS_EAGER,
    task_eager_propagates=settings.CELERY_TASK_ALWAYS_EAGER,
    # Fail fast (instead of long retries) when publishing to an unreachable broker
    # so the submit path can fall back to inline grading without hanging.
    task_publish_retry=False,
    broker_connection_retry_on_startup=False,
)
