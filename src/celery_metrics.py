"""
Метрики Celery для Prometheus с использованием сигналов.
"""

import time
from typing import Any

from celery import signals
from celery.app.trace import Task

from src.core.metrics import celery_task_duration_seconds, celery_tasks_total

_start_times: dict[str, float] = {}


@signals.task_prerun.connect
def on_task_prerun(
    sender: Task, task_id: str, task: str, args: tuple, kwargs: dict, **kw: Any
) -> None:
    _start_times[task_id] = time.perf_counter()


@signals.task_postrun.connect
def on_task_postrun(
    sender: Task,
    task_id: str,
    task: str,
    args: tuple,
    kwargs: dict,
    retval: Any,
    state: str,
    **kw: Any,
) -> None:
    start = _start_times.pop(task_id, None)
    if start is not None:
        duration = time.perf_counter() - start
        queue = getattr(sender.request, "delivery_info", {}).get("routing_key", "default")
        celery_task_duration_seconds.labels(task_name=task, queue=queue).observe(duration)
    celery_tasks_total.labels(task_name=task, status="success").inc()


@signals.task_failure.connect
def on_task_failure(
    sender: Task, task_id: str, task: str, args: tuple, kwargs: dict, einfo: Exception, **kw: Any
) -> None:
    celery_tasks_total.labels(task_name=task, status="failure").inc()
    _start_times.pop(task_id, None)


@signals.task_retry.connect
def on_task_retry(
    sender: Task, task_id: str, task: str, args: tuple, kwargs: dict, einfo: Exception, **kw: Any
) -> None:
    celery_tasks_total.labels(task_name=task, status="retry").inc()
