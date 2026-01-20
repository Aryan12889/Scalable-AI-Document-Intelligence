import os
from celery import Celery

# Default to memory for local dev (Windows) if Redis not set
DEFAULT_BROKER = "memory://"
REDIS_URL = os.getenv("REDIS_URL", DEFAULT_BROKER)

celery_app = Celery(
    "worker",
    broker=REDIS_URL,
    backend="rpc://",
    include=["app.workers.tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    "cleanup-expired-sessions-every-day": {
        "task": "app.workers.tasks.run_cleanup_job",
        "schedule": crontab(minute=0, hour=3), # Run at 3:00 AM UTC
    },
}
