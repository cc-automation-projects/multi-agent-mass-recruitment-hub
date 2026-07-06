"""
Сервис для управления рекрутинговыми кампаниями.
"""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.audit_logger import audit_log
from src.core.models import Campaign, CampaignStatus

_logger = audit_log()


class CampaignService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_campaign(self, name: str, description: str | None = None) -> Campaign:
        campaign = Campaign(
            id=str(uuid.uuid4()),
            name=name,
            description=description,
            status=CampaignStatus.DRAFT,
        )
        self.session.add(campaign)
        await self.session.commit()
        _logger.info("campaign_created", campaign_id=campaign.id, name=name)
        return campaign

    async def get_campaign(self, campaign_id: str) -> Campaign | None:
        result = await self.session.execute(select(Campaign).where(Campaign.id == campaign_id))
        return result.scalar_one_or_none()

    async def add_candidates(self, campaign_id: str, candidate_ids: list[str]) -> bool:
        campaign = await self.get_campaign(campaign_id)
        if not campaign:
            return False
        campaign.candidate_ids = list(set(campaign.candidate_ids + candidate_ids))
        campaign.updated_at = datetime.utcnow()
        await self.session.commit()
        _logger.info(
            "candidates_added_to_campaign", campaign_id=campaign_id, count=len(candidate_ids)
        )
        return True

    async def start_campaign(self, campaign_id: str) -> bool:
        campaign = await self.get_campaign(campaign_id)
        if not campaign:
            return False
        if campaign.status != CampaignStatus.DRAFT:
            _logger.warning("campaign_already_started", campaign_id=campaign_id)
            return False
        campaign.status = CampaignStatus.RUNNING
        campaign.started_at = datetime.utcnow()
        await self.session.commit()
        _logger.info("campaign_started", campaign_id=campaign_id)
        return True

    async def complete_campaign(self, campaign_id: str) -> bool:
        campaign = await self.get_campaign(campaign_id)
        if not campaign:
            return False
        campaign.status = CampaignStatus.COMPLETED
        campaign.completed_at = datetime.utcnow()
        await self.session.commit()
        _logger.info("campaign_completed", campaign_id=campaign_id)
        return True
