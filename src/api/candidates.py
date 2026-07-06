"""
API для работы с кандидатами.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user, get_db_session
from src.core.audit_logger import audit_log
from src.core.models import BiometryConsentLog, Candidate, ScreeningStatus, User

router = APIRouter(prefix="/candidates", tags=["candidates"])


@router.post("/", response_model=Candidate, status_code=status.HTTP_201_CREATED)
async def create_candidate(
    candidate: Candidate,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_current_user),
):
    if not candidate.consent_152fz:
        raise HTTPException(status_code=400, detail="consent_152fz must be true")
    candidate.screening_status = ScreeningStatus.PENDING
    db.add(candidate)
    await db.commit()
    await db.refresh(candidate)
    audit_log().info("candidate_created", candidate_id=candidate.id)
    return candidate


@router.get("/{candidate_id}", response_model=Candidate)
async def get_candidate(
    candidate_id: str,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Candidate).where(Candidate.id == candidate_id))
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    masked = await candidate.mask_pii()
    return masked


@router.get("/{candidate_id}/biometry-consent", response_model=list[BiometryConsentLog])
async def get_biometry_consent_log(
    candidate_id: str,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_current_user),
):
    """Возвращает историю согласий на биометрию для кандидата."""
    query = text("""
        SELECT id, candidate_id, consent_given, audio_hash, timestamp, ip_address, user_agent
        FROM biometry_consent_log
        WHERE candidate_id = :candidate_id
        ORDER BY timestamp DESC
    """)
    result = await db.execute(query, {"candidate_id": candidate_id})
    rows = result.fetchall()
    return [BiometryConsentLog(**dict(row._mapping)) for row in rows]
