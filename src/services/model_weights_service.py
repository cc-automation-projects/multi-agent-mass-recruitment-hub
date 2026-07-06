"""
Сервис для управления весами модели propensity.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.audit_logger import audit_log

_logger = audit_log()


class ModelWeightsService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_weights(self, model_name: str = "propensity_dialer") -> dict:
        result = await self.session.execute(
            f"SELECT weights FROM model_weights WHERE model_name = '{model_name}' ORDER BY id DESC LIMIT 1"
        )
        row = result.first()
        if row:
            return row[0]
        return {"experience": 0.3, "education": 0.2, "region": 0.1, "skill_match": 0.4}

    async def update_weights(self, model_name: str, weights: dict, user_id: str = "admin") -> bool:
        await self.session.execute(
            f"INSERT INTO model_weights (model_name, weights, created_by) VALUES ('{model_name}', %s, '{user_id}')",
            (weights,),
        )
        await self.session.commit()
        _logger.info(
            "model_weights_updated", model_name=model_name, weights=weights, user_id=user_id
        )
        return True
