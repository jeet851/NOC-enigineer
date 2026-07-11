from celery import Celery
from api.config import settings

celery_app = Celery(
    "noc_workers",
    broker=settings.RABBITMQ_URL,
    backend=settings.REDIS_URL,
    include=["workers.tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True
)
