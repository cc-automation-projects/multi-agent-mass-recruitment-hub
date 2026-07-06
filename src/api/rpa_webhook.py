"""
Вебхук для получения статуса выполнения RPA-задачи из 1С.
"""

from fastapi import APIRouter, Response
from pydantic import BaseModel

from src.core.audit_logger import audit_log

router = APIRouter(prefix="/webhook", tags=["rpa"])
_logger = audit_log()


class RPAStatusUpdate(BaseModel):
    transaction_id: str
    task_id: str
    status: str
    error: str | None = None


@router.post("/1c/callback")
async def rpa_callback(update: RPAStatusUpdate) -> Response:
    """
    Принимает обновления статуса от RPA-оркестратора (n8n).
    """
    _logger.info(
        "RPA callback received",
        transaction_id=update.transaction_id,
        task_id=update.task_id,
        status=update.status,
        error=update.error,
    )
    return Response(status_code=200)
