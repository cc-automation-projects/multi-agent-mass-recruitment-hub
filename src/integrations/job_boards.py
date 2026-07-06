"""
Реальные интеграции с hh.ru и Avito API (частично).
"""

import asyncio
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.core.audit_logger import audit_log
from src.core.config import get_settings

_logger = audit_log()
_settings = get_settings()

_client = httpx.AsyncClient(timeout=30.0, limits=httpx.Limits(max_keepalive_connections=5))


def _retry_policy():
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=1, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    )


@_retry_policy()
async def _get_hh_resumes(
    query: str,
    per_page: int = 10,
    page: int = 0,
    area: int = 113,
    order_by: str = "publication_time",
) -> list[dict[str, Any]]:
    """
    Выполняет запрос к API hh.ru/resumes для поиска резюме соискателей.
    Требуется OAuth-токен с правами на чтение резюме.
    """
    if not _settings.hh_access_token:
        _logger.error("HH_ACCESS_TOKEN not set, cannot fetch resumes")
        return []

    url = "https://api.hh.ru/resumes"
    headers = {
        "Authorization": f"Bearer {_settings.hh_access_token}",
        "User-Agent": "MassRecruitHub/1.0",
    }
    params = {
        "text": query,
        "area": area,
        "per_page": per_page,
        "page": page,
        "order_by": order_by,
        "sort_order": "desc",
    }

    try:
        resp = await _client.get(url, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("items", [])
        resumes = []
        for item in items:
            resumes.append(
                {
                    "id": item.get("id"),
                    "name": item.get("title", "Кандидат"),
                    "phone": None,
                    "resume_text": item.get("description", "")[:500],
                    "source": "hh",
                    "consent_152fz": True,
                }
            )
        return resumes
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 403:
            _logger.error("HH API access denied: token may be invalid or lacks permissions")
        elif e.response.status_code == 429:
            _logger.warning("HH API rate limit hit")
        else:
            _logger.error("HH API error", status=e.response.status_code, error=str(e))
        return []
    except Exception as e:
        _logger.error("HH API unexpected error", error=str(e))
        return []


@_retry_policy()
async def fetch_resumes_from_hh(query: str, per_page: int = 10) -> list[dict[str, Any]]:
    """
    Возвращает список резюме с hh.ru, соответствующих поисковому запросу.
    """
    _logger.info("hh_api_call", query=query, per_page=per_page)
    resumes = await _get_hh_resumes(query, per_page, page=0)
    return resumes


@_retry_policy()
async def fetch_resumes_from_avito(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """
    Получает резюме с Avito Работа (требуется API ключ).
    Пока заглушка.
    """
    _logger.warning("avito_api_not_implemented", query=query, limit=limit)
    await asyncio.sleep(0.5)
    resumes = []
    for i in range(limit):
        resumes.append(
            {
                "name": f"Авито Кандидат {i}",
                "phone": f"+7 999 111 22{i:02d}",
                "resume_text": f"Опыт работы промоутером {i} месяцев.",
                "source": "avito",
                "consent_152fz": True,
            }
        )
    return resumes
