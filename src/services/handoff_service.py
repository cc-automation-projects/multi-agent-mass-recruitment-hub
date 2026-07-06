"""
Сервис для омниканального handoff: сохранение состояния диалога в Redis
при переключении с телефонного звонка на мессенджер.
"""

import json

from redis.asyncio import Redis

from src.core.audit_logger import audit_log
from src.core.config import get_settings
from src.core.models import Candidate

_settings = get_settings()
_logger = audit_log()


class HandoffService:
    """Управляет сохранением и восстановлением состояния handoff."""

    def __init__(self, redis_client: Redis | None = None):
        self._redis = redis_client or Redis.from_url(_settings.redis_url, decode_responses=True)
        self._prefix = "handoff:"
        self._attempts_prefix = "handoff_attempts:"

    async def save_state(self, candidate_id: str, state: dict, ttl_seconds: int = 3600) -> None:
        """Сохраняет состояние графа для кандидата после неудачного звонка."""
        if "candidate" in state and isinstance(state["candidate"], Candidate):
            state["candidate"] = state["candidate"].dict()
        key = f"{self._prefix}{candidate_id}"
        await self._redis.setex(key, ttl_seconds, json.dumps(state))
        _logger.info(
            "handoff_state_saved",
            candidate_id=candidate_id,
            ttl=ttl_seconds,
        )

    async def load_state(self, candidate_id: str) -> dict | None:
        """Загружает сохранённое состояние."""
        key = f"{self._prefix}{candidate_id}"
        data = await self._redis.get(key)
        if data:
            loaded = json.loads(data)
            if "candidate" in loaded and isinstance(loaded["candidate"], dict):
                loaded["candidate"] = Candidate(**loaded["candidate"])
            return loaded
        return None

    async def delete_state(self, candidate_id: str) -> None:
        """Удаляет сохранённое состояние (после успешного продолжения диалога)."""
        key = f"{self._prefix}{candidate_id}"
        await self._redis.delete(key)
        _logger.info("handoff_state_deleted", candidate_id=candidate_id)

    async def increment_attempts(self, candidate_id: str) -> int:
        """Увеличивает счётчик неудачных звонков для кандидата."""
        key = f"{self._attempts_prefix}{candidate_id}"
        attempts = await self._redis.incr(key)
        await self._redis.expire(key, 86400)  # 24 часа
        _logger.info("handoff_attempts_incremented", candidate_id=candidate_id, attempts=attempts)
        return attempts

    async def reset_attempts(self, candidate_id: str) -> None:
        """Сбрасывает счётчик неудачных звонков (при успешном звонке)."""
        key = f"{self._attempts_prefix}{candidate_id}"
        await self._redis.delete(key)
        _logger.info("handoff_attempts_reset", candidate_id=candidate_id)

    async def get_attempts(self, candidate_id: str) -> int:
        """Возвращает текущее количество неудачных звонков."""
        key = f"{self._attempts_prefix}{candidate_id}"
        val = await self._redis.get(key)
        return int(val) if val else 0
