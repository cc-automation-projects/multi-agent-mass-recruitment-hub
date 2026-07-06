"""
API endpoints for candidate data deletion (right to be forgotten).
"""

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.deps import get_current_user
from src.core.audit_logger import audit_log
from src.core.models import User
from src.services.deletion_service import delete_candidate_data

router = APIRouter(prefix="/candidates", tags=["deletion"])


@router.post("/{candidate_id}/delete", status_code=status.HTTP_202_ACCEPTED)
async def delete_candidate(candidate_id: str, _: User = Depends(get_current_user)):
    """
    Запрос на удаление всех данных кандидата (право на забвение, 152-ФЗ ст. 15).
    """
    audit_log().info(
        "deletion_request_received",
        candidate_id=candidate_id,
        action="right_to_be_forgotten",
    )

    result = await delete_candidate_data(candidate_id)

    if not any(result.values()):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No data found for candidate {candidate_id} or deletion failed",
        )

    return {"message": f"Deletion of candidate {candidate_id} accepted", "details": result}
