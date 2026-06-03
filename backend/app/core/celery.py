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
)
