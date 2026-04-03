from __future__ import annotations
from celery import Celery
from app.config import settings

celery_app = Celery(
    "bakhrushin_news",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.broker_connection_retry_on_startup = True

# Ensure tasks are registered when worker starts.
import app.workers.tasks  # noqa: F401

celery_app.conf.timezone = "UTC"
celery_app.conf.beat_schedule = {
    "collect_rss_every_15m": {
        "task": "app.workers.tasks.collect_all_sources",
        "schedule": 15 * 60,
    },
    "ai_generate_every_10m": {
        "task": "app.workers.tasks.generate_ai_for_new_items",
        "schedule": 10 * 60,
    },
    "publish_every_minute": {
        "task": "app.workers.tasks.publish_scheduled_posts",
        "schedule": 60,
    },
}
