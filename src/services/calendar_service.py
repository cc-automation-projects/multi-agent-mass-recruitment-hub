"""
Интеграция с календарями (Google, Яндекс).
"""

import asyncio
from datetime import datetime, timedelta

import httpx
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from src.core.audit_logger import audit_log
from src.core.config import get_settings

_settings = get_settings()
_logger = audit_log()


async def get_google_calendar_service():
    """Возвращает авторизованный сервис Google Calendar."""
    creds = None
    token_path = _settings.google_calendar_token_path
    if token_path and token_path.exists():
        creds = Credentials.from_authorized_user_file(token_path, _settings.google_calendar_scopes)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            await asyncio.get_running_loop().run_in_executor(None, creds.refresh, Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                _settings.google_calendar_credentials_path, _settings.google_calendar_scopes
            )
            creds = await asyncio.get_running_loop().run_in_executor(
                None, flow.run_local_server, port=0
            )
        if token_path:
            await asyncio.get_running_loop().run_in_executor(
                None, lambda: creds.to_json(), token_path
            )
    return build("calendar", "v3", credentials=creds)


async def get_google_free_busy(
    calendar_id: str, time_min: datetime, time_max: datetime
) -> list[datetime]:
    """Возвращает список свободных слотов (начало часа) на интервале."""
    service = await get_google_calendar_service()
    body = {
        "timeMin": time_min.isoformat() + "Z",
        "timeMax": time_max.isoformat() + "Z",
        "items": [{"id": calendar_id}],
    }
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, lambda: service.freebusy().query(body=body).execute())
    busy = result["calendars"][calendar_id].get("busy", [])
    current = time_min.replace(minute=0, second=0, microsecond=0)
    free_slots = []
    while current < time_max:
        occupied = False
        for b in busy:
            start = datetime.fromisoformat(b["start"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(b["end"].replace("Z", "+00:00"))
            if start <= current < end:
                occupied = True
                break
        if not occupied:
            free_slots.append(current)
        current += timedelta(hours=1)
    return free_slots


async def get_yandex_access_token() -> str:
    """Получает или обновляет access token для Яндекс.Календаря."""
    return _settings.yandex_calendar_access_token


async def get_yandex_free_busy(
    calendar_id: str, time_min: datetime, time_max: datetime
) -> list[datetime]:
    """Возвращает список свободных слотов (начало часа) через Яндекс.Календарь API."""
    token = await get_yandex_access_token()
    headers = {"Authorization": f"OAuth {token}"}
    url = f"https://calendar.yandex.ru/api/v1/calendars/{calendar_id}/events"
    params = {
        "from": time_min.isoformat(),
        "to": time_max.isoformat(),
        "page_size": 100,
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers, params=params)
        resp.raise_for_status()
        events = resp.json().get("events", [])
    busy_intervals = []
    for e in events:
        start = datetime.fromisoformat(e["start"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(e["end"].replace("Z", "+00:00"))
        busy_intervals.append((start, end))
    current = time_min.replace(minute=0, second=0, microsecond=0)
    free_slots = []
    while current < time_max:
        occupied = False
        for b_start, b_end in busy_intervals:
            if b_start <= current < b_end:
                occupied = True
                break
        if not occupied:
            free_slots.append(current)
        current += timedelta(hours=1)
    return free_slots


async def check_calendar_availability(
    hr_id: str,
    duration_min: int = 30,
    calendar_type: str = "google",
    calendar_id: str | None = None,
) -> list[datetime]:
    """
    Проверяет доступность HR в календаре.
    Поддерживает 'google' и 'yandex'.
    """
    if duration_min < 15 or duration_min > 120:
        raise ValueError("duration_min must be between 15 and 120")

    now = datetime.utcnow()
    time_min = now
    time_max = now + timedelta(days=3)

    if calendar_type == "google":
        if not calendar_id:
            calendar_id = _settings.google_calendar_default_id
        free_slots = await get_google_free_busy(calendar_id, time_min, time_max)
    elif calendar_type == "yandex":
        if not calendar_id:
            calendar_id = _settings.yandex_calendar_default_id
        free_slots = await get_yandex_free_busy(calendar_id, time_min, time_max)
    else:
        raise ValueError(f"Unsupported calendar type: {calendar_type}")

    return free_slots
