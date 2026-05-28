from celery import Celery
from app.logging import logger
from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "agent_builder",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

logger.info(f"Celery app initialized — broker: {settings.REDIS_URL}")
