"""
Service for persistent bandit state using Redis.
"""

import json

from redis.asyncio import Redis

from src.core.audit_logger import audit_log
from src.core.config import get_settings
from src.optimization.bandit import ThompsonSampling

_logger = audit_log()
_settings = get_settings()


class BanditService:
    """
    Manages Thompson Sampling bandit for script variants.
    State is stored in Redis.
    """

    def __init__(self, experiment_id: str, n_arms: int, redis_client: Redis | None = None):
        self.experiment_id = experiment_id
        self.n_arms = n_arms
        self._redis = redis_client or Redis.from_url(_settings.redis_url, decode_responses=True)
        self._key = f"bandit:{experiment_id}"

    async def _load_state(self) -> dict | None:
        data = await self._redis.get(self._key)
        if data:
            return json.loads(data)
        return None

    async def _save_state(self, state: dict) -> None:
        await self._redis.setex(self._key, 86400 * 30, json.dumps(state))

    async def select_arm(self) -> int:
        state = await self._load_state()
        if state is None:
            bandit = ThompsonSampling(self.n_arms)
        else:
            bandit = ThompsonSampling(self.n_arms)
            bandit.alpha = state["alpha"]
            bandit.beta = state["beta"]
        arm = bandit.select_arm()
        return arm

    async def update(self, arm: int, success: bool):
        state = await self._load_state()
        if state is None:
            bandit = ThompsonSampling(self.n_arms)
        else:
            bandit = ThompsonSampling(self.n_arms)
            bandit.alpha = state["alpha"]
            bandit.beta = state["beta"]
        bandit.update(arm, 1 if success else 0)
        await self._save_state({"alpha": bandit.alpha, "beta": bandit.beta})
        _logger.info("bandit_updated", experiment=self.experiment_id, arm=arm, success=success)
