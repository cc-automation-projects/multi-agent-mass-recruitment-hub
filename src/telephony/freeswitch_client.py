"""
FreeSWITCH клиент с использованием ESL (Event Socket).
"""

from src.core.audit_logger import audit_log
from src.core.config import get_settings
from src.telephony.esl_client import ESLClient

_settings = get_settings()
_logger = audit_log()

_esl_client: ESLClient | None = None


async def _get_esl_client() -> ESLClient | None:
    global _esl_client
    if _esl_client is None:
        _esl_client = ESLClient(
            host=_settings.freeswitch_host,
            port=_settings.freeswitch_port,
            password=_settings.freeswitch_password,
            timeout=10.0,
        )
        if not await _esl_client.connect():
            _esl_client = None
            _logger.error("ESL client failed to connect")
            return None
    return _esl_client


async def make_call(
    candidate_id: str,
    phone_number: str,
    script: str = "default",
    max_attempts: int = 2,
) -> dict:
    client = await _get_esl_client()
    if client is None:
        _logger.error("ESL client not available", candidate_id=candidate_id)
        return {"success": False, "error": "ESL client not connected"}

    gateway = _settings.freeswitch_gateway.rstrip("/")
    destination = f"{gateway}/{phone_number}"
    playback = f"playback://{script}.wav"

    result = await client.originate(destination, extension=playback)

    if result.get("success"):
        _logger.info(
            "call_initiated",
            candidate_id=candidate_id,
            phone_number=phone_number,
            call_id=result.get("call_id"),
        )
    else:
        _logger.error(
            "call_failed",
            candidate_id=candidate_id,
            phone_number=phone_number,
            error=result.get("error"),
        )
    return result


async def check_call_status(call_id: str) -> dict:
    client = await _get_esl_client()
    if client is None:
        return {"status": "unknown", "error": "ESL client not available"}

    response = await client.api(f"show call {call_id}")
    if "no such call" in response.lower():
        return {"status": "completed", "call_id": call_id}
    elif "ringing" in response.lower():
        return {"status": "ringing", "call_id": call_id}
    elif "answered" in response.lower():
        return {"status": "answered", "call_id": call_id}
    else:
        return {"status": "unknown", "call_id": call_id, "raw": response}
