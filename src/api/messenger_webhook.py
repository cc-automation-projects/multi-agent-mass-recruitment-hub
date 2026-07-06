"""
Вебхук для приёма сообщений из мессенджеров (Telegram, MAX, VK).
Поддерживает продолжение диалога после handoff.
"""

import json

import httpx
from fastapi import APIRouter, HTTPException, Request, Response

from src.core.audit_logger import audit_log
from src.services.agent_runner import resume_conversation
from src.services.audio_converter import convert_to_pcm
from src.services.handoff_service import HandoffService
from src.services.hr_integrations import send_omnichannel_message
from src.voice.pipeline import VoicePipeline

_voice_pipeline = VoicePipeline()

router = APIRouter(prefix="/webhook", tags=["messenger"])
_logger = audit_log()
_handoff = HandoffService()


@router.post("/messenger")
async def messenger_webhook(request: Request) -> Response:
    """
    Универсальный вебхук для мессенджеров.
    В реальности нужно разделить по платформам, здесь демонстрация.
    Ожидает JSON: { "platform": "telegram|max|vk", "sender_id": "...", "text": "...", "candidate_id": "..." }
    """
    try:
        body = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    platform = body.get("platform")
    sender_id = body.get("sender_id")
    text = body.get("text")
    candidate_id = body.get("candidate_id")
    audio_url = body.get("audio_url")

    if not platform or not sender_id:
        raise HTTPException(status_code=400, detail="Missing required fields")

    if audio_url and not text:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(audio_url)
                audio_bytes = resp.content
            pcm_bytes = await convert_to_pcm(audio_bytes, input_format="mp3")
            if pcm_bytes:
                text = await _voice_pipeline.transcribe_bytes(pcm_bytes)
        except Exception as e:
            _logger.error("audio_processing_failed", error=str(e))

    if not text:
        raise HTTPException(status_code=400, detail="Missing text or audio")

    _logger.info(
        "messenger_webhook_received",
        platform=platform,
        sender_id=sender_id,
        candidate_id=candidate_id,
        text_preview=text[:50],
    )

    state = await _handoff.load_state(candidate_id)
    if state:
        response_text = await resume_conversation(candidate_id, text, platform)
        if response_text is None:
            response_text = "Не удалось восстановить диалог. Пожалуйста, свяжитесь с оператором."
    else:
        _logger.warning("no_handoff_state", candidate_id=candidate_id)
        response_text = (
            "У вас нет активного диалога. Пожалуйста, начните с /start или позвоните нам."
        )

    await send_omnichannel_message(
        candidate_id=candidate_id,
        channel=platform,
        text=response_text,
        extra={"recipient_id": sender_id},
    )
    await _handoff.delete_state(candidate_id)

    return Response(status_code=200, content="OK")
