"""
API для управления рекрутинговыми кампаниями.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user, get_db_session
from src.core.audit_logger import audit_log
from src.core.models import Campaign, CampaignStatus, User
from src.services.campaign_service import CampaignService
from src.tasks.campaign_tasks import run_campaign_task

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.post("/", response_model=Campaign, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    name: str,
    description: str | None = None,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_current_user),
):
    service = CampaignService(db)
    campaign = await service.create_campaign(name, description)
    return campaign


@router.get("/{campaign_id}", response_model=Campaign)
async def get_campaign(
    campaign_id: str,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_current_user),
):
    service = CampaignService(db)
    campaign = await service.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


@router.post("/{campaign_id}/start", status_code=status.HTTP_202_ACCEPTED)
async def start_campaign(
    campaign_id: str,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_current_user),
):
    service = CampaignService(db)
    campaign = await service.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if campaign.status != CampaignStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Campaign already started or completed")

    success = await service.start_campaign(campaign_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to start campaign")

    run_campaign_task.delay(campaign_id)
    audit_log().info("campaign_launch_accepted", campaign_id=campaign_id)
    return {"message": "Campaign started in background", "campaign_id": campaign_id}
