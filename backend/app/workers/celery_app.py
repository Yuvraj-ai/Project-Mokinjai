from celery import Celery

celery_app = Celery("agent_builder")

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    task_time_limit=600,
    task_soft_time_limit=540,
)

def configure_celery():
    from app.config import get_settings
    settings = get_settings()
    celery_app.conf.update(
        broker_url=settings.REDIS_URL,
        result_backend=settings.REDIS_URL,
    )

configure_celery()
celery_app.autodiscover_tasks(["app.workers"])
