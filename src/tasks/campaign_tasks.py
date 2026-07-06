"""
Задачи, связанные с рекрутинговыми кампаниями.
"""

import asyncio

from celery import shared_task

from src.agents.orchestrator import run_campaign
from src.core.audit_logger import audit_log
from src.core.database import async_session_maker
from src.services.campaign_service import CampaignService

_logger = audit_log()


@shared_task(bind=True, max_retries=3, name="campaigns.run_campaign")
def run_campaign_task(self, campaign_id: str):
    """
    Запускает кампанию (обзвон кандидатов) в фоне.
    """

    async def _run():
        async with async_session_maker() as session:
            service = CampaignService(session)
            campaign = await service.get_campaign(campaign_id)
            if not campaign:
                raise ValueError(f"Campaign {campaign_id} not found")
            if campaign.status != "running":
                _logger.warning("campaign_not_running", campaign_id=campaign_id)
                return
            candidate_ids = campaign.candidate_ids
            await run_campaign(candidate_ids)
            await service.complete_campaign(campaign_id)

    try:
        asyncio.run(_run())
        _logger.info("campaign_task_completed", campaign_id=campaign_id)
    except Exception as e:
        _logger.error("campaign_task_failed", campaign_id=campaign_id, error=str(e))
        raise self.retry(exc=e, countdown=60)
