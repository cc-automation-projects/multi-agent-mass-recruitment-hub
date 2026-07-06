"""
Клиент для запуска RPA-сценариев (интеграция с 1С через n8n / UiPath).
"""

import uuid

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.core.audit_logger import audit_log
from src.core.config import get_settings

_settings = get_settings()
_logger = audit_log()


def _retry_policy():
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=1, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    )


@_retry_policy()
async def trigger_1c_onboarding(candidate: dict) -> str | None:
    """
    Запускает процесс онбординга в 1С:ЗУП через RPA-слой.
    Возвращает task_id (идентификатор задачи в 1С) или None.
    """
    if not _settings.rpa_webhook_url:
        _logger.warning("RPA_WEBHOOK_URL not set, skipping 1C onboarding")
        return None

    transaction_id = str(uuid.uuid4())

    payload = {
        "transaction_id": transaction_id,
        "action": "create_employee",
        "candidate": {
            "id": candidate.get("id"),
            "name": candidate.get("name"),
            "phone": candidate.get("phone"),
            "email": candidate.get("email"),
            "position": candidate.get("position", "Курьер"),
            "start_date": candidate.get("start_date"),
        },
        "callback_url": _settings.rpa_callback_url,
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(_settings.rpa_webhook_url, json=payload)
        resp.raise_for_status()
        result = resp.json()
        task_id = result.get("task_id") or transaction_id
        _logger.info("1C onboarding triggered", task_id=task_id, candidate_id=candidate.get("id"))
        return task_id
