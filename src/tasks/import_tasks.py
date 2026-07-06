"""
Задачи импорта резюме с внешних досок.
"""

import asyncio

from celery import shared_task

from src.core.audit_logger import audit_log
from src.core.database import async_session_maker
from src.services.import_resumes import ResumeImportService

_logger = audit_log()


@shared_task(bind=True, name="imports.import_hh")
def import_hh_task(self, query: str, per_page: int = 10):
    async def _run():
        async with async_session_maker() as session:
            service = ResumeImportService(session)
            count = await service.import_from_hh(query, per_page)
            return count

    try:
        count = asyncio.run(_run())
        _logger.info("hh_import_completed", query=query, count=count)
        return {"count": count}
    except Exception as e:
        _logger.error("hh_import_failed", query=query, error=str(e))
        raise self.retry(exc=e, countdown=120)


@shared_task(bind=True, name="imports.import_avito")
def import_avito_task(self, query: str, limit: int = 10):
    async def _run():
        async with async_session_maker() as session:
            service = ResumeImportService(session)
            count = await service.import_from_avito(query, limit)
            return count

    try:
        count = asyncio.run(_run())
        _logger.info("avito_import_completed", query=query, count=count)
        return {"count": count}
    except Exception as e:
        _logger.error("avito_import_failed", query=query, error=str(e))
        raise self.retry(exc=e, countdown=120)
