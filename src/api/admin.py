"""
Admin endpoints for manual triggers (imports, etc.).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_admin, get_db_session
from src.core.audit_logger import audit_log
from src.core.models import User
from src.services.model_weights_service import ModelWeightsService
from src.tasks.import_tasks import import_avito_task, import_hh_task

router = APIRouter(prefix="/admin", tags=["admin"])


class WeightsUpdate(BaseModel):
    weights: dict


@router.post("/import/hh", status_code=status.HTTP_202_ACCEPTED)
async def import_from_hh(
    query: str = "курьер",
    per_page: int = 10,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_current_admin),
):
    result = import_hh_task.delay(query, per_page)
    audit_log().info("admin_import_hh", query=query, task_id=result.id)
    return {"message": f"Import started (task id: {result.id})", "task_id": result.id}


@router.post("/import/avito", status_code=status.HTTP_202_ACCEPTED)
async def import_from_avito(
    query: str = "промоутер",
    limit: int = 10,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_current_admin),
):
    result = import_avito_task.delay(query, limit)
    audit_log().info("admin_import_avito", query=query, task_id=result.id)
    return {"message": f"Import started (task id: {result.id})", "task_id": result.id}


@router.get("/model/weights")
async def get_model_weights(
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_current_admin),
):
    service = ModelWeightsService(db)
    weights = await service.get_weights()
    return weights


@router.post("/model/weights", status_code=200)
async def update_model_weights(
    payload: WeightsUpdate,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_current_admin),
    user_id: str = "admin",
):
    service = ModelWeightsService(db)
    success = await service.update_weights("propensity_dialer", payload.weights, user_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update weights")
    from src.services.propensity_dialer import reload_model

    await reload_model()
    return {"message": "Weights updated successfully", "weights": payload.weights}
