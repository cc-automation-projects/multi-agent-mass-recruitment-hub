"""
Интеграции с внешними HR-системами, мессенджерами и календарями.

Поддерживает:
- Telegram Bot API (реальные вызовы)
- VK API (реальные вызовы)
- MAX API (заглушка, требует реального endpoint)
- Календари: Google Calendar, Яндекс.Календарь (заглушки, т.к. требуют OAuth2)
"""

from datetime import datetime

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.core.audit_logger import audit_log
from src.core.config import get_settings
from src.pii.anonymizer import anonymize_pii
from src.services.calendar_service import check_calendar_availability as real_check_calendar

_settings = get_settings()
_logger = audit_log()

_http_client = httpx.AsyncClient(timeout=30.0)


def retry_on_network():
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=1, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    )


async def check_calendar_availability(hr_id: str, duration_min: int = 30) -> list[datetime]:
    """
    Реальная проверка календаря через Google или Яндекс.
    Использует настройки из config.
    """
    calendar_type = _settings.calendar_provider
    return await real_check_calendar(hr_id, duration_min, calendar_type=calendar_type)


async def send_telegram_message(chat_id: str, text: str) -> bool:
    if not _settings.telegram_bot_token:
        _logger.warning("telegram_token_not_set", error="missing token")
        return False

    url = f"https://api.telegram.org/bot{_settings.telegram_bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}

    try:
        resp = await _http_client.post(url, json=payload)
        resp.raise_for_status()
        _logger.info("telegram_message_sent", chat_id=chat_id, text_length=len(text))
        return True
    except Exception as e:
        _logger.error("telegram_send_failed", chat_id=chat_id, error=str(e))
        return False


async def send_vk_message(user_id: str, text: str) -> bool:
    if not _settings.vk_api_token:
        _logger.warning("vk_token_not_set")
        return False

    url = "https://api.vk.com/method/messages.send"
    params = {
        "user_id": user_id,
        "message": text,
        "access_token": _settings.vk_api_token,
        "v": "5.131",
        "random_id": int(datetime.utcnow().timestamp()),
    }

    try:
        resp = await _http_client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        if data.get("error"):
            _logger.error("vk_api_error", error=data["error"])
            return False
        _logger.info("vk_message_sent", user_id=user_id, text_length=len(text))
        return True
    except Exception as e:
        _logger.error("vk_send_failed", user_id=user_id, error=str(e))
        return False


async def send_max_message(user_id: str, text: str) -> bool:
    if not _settings.max_api_key:
        _logger.warning("max_api_key_not_set")
        return False

    url = _settings.max_api_endpoint or "https://api.max.ru/v1/messages"
    headers = {
        "Authorization": f"Bearer {_settings.max_api_key}",
        "Content-Type": "application/json",
    }
    payload = {"to": user_id, "text": text}

    try:
        resp = await _http_client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        _logger.info("max_message_sent", user_id=user_id, text_length=len(text))
        return True
    except Exception as e:
        _logger.error("max_send_failed", user_id=user_id, error=str(e))
        return False


async def send_email_notification(email: str, subject: str, body: str) -> bool:
    _logger.info(
        "email_stub",
        email=email,
        subject=subject,
        body_preview=body[:50],
        note="Real email integration not implemented yet",
    )
    return True


async def send_omnichannel_message(
    candidate_id: str,
    channel: str,
    text: str,
    extra: dict | None = None,
) -> bool:
    valid_channels = {"telegram", "vk", "max", "email"}
    if channel not in valid_channels:
        raise ValueError(f"Unsupported channel: {channel}")

    if extra is None:
        extra = {}
    recipient_id = extra.get("recipient_id")
    if not recipient_id and channel != "email":
        _logger.error("missing_recipient", channel=channel, candidate_id=candidate_id)
        return False

    if channel == "telegram":
        return await send_telegram_message(recipient_id, text)
    elif channel == "vk":
        return await send_vk_message(recipient_id, text)
    elif channel == "max":
        return await send_max_message(recipient_id, text)
    elif channel == "email":
        email = extra.get("email", recipient_id)
        subject = extra.get("subject", "Уведомление от MassRecruitHub")
        return await send_email_notification(email, subject, text)
    return False


async def anonymize_pdn(text: str) -> str:
    """
    Анонимизирует ПДн через Presidio (вызов из src.pii.anonymizer).
    """
    return await anonymize_pii(text)
