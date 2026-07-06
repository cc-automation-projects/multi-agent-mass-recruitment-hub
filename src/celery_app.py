"""
Celery приложение для фоновых задач.
"""

from celery import Celery

# Импортируем модуль метрик (регистрирует сигналы Celery)
from src import celery_metrics  # noqa
from src.core.config import get_settings

_settings = get_settings()

broker_url = _settings.redis_url
result_backend = _settings.redis_url

celery_app = Celery(
    "mass_recruit_hub",
    broker=broker_url,
    backend=result_backend,
    include=[
        "src.tasks.campaign_tasks",
        "src.tasks.import_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,
    task_soft_time_limit=25 * 60,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)

if _settings.environment == "development":
    celery_app.conf.update(
        task_always_eager=True,
        task_eager_propagates=True,
    )
