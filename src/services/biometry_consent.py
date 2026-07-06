"""
Сервис для логирования согласия на обработку голосовой биометрии (152-ФЗ ст. 10, 15).
"""

import hashlib

from sqlalchemy import text

from src.core.audit_logger import audit_log
from src.core.database import async_session_maker

_logger = audit_log()


async def log_biometry_consent(
    candidate_id: str,
    audio_fragment: bytes,
    consent_given: bool = True,
    ip_address: str = None,
    user_agent: str = None,
) -> bool:
    """
    Сохраняет запись о согласии/отказе на биометрию.
    audio_fragment: запись голоса кандидата (первые несколько секунд или фраза "согласен").
    Вычисляет SHA256 и хранит хэш.
    """
    if not audio_fragment:
        _logger.warning(
            "No audio fragment provided for biometry consent", candidate_id=candidate_id
        )
        return False

    audio_hash = hashlib.sha256(audio_fragment).hexdigest()

    async with async_session_maker() as session:
        query = text("""
            INSERT INTO biometry_consent_log (candidate_id, consent_given, audio_hash, ip_address, user_agent)
            VALUES (:candidate_id, :consent_given, :audio_hash, :ip_address, :user_agent)
        """)
        await session.execute(
            query,
            {
                "candidate_id": candidate_id,
                "consent_given": consent_given,
                "audio_hash": audio_hash,
                "ip_address": ip_address,
                "user_agent": user_agent,
            },
        )
        await session.commit()
    _logger.info(
        "Biometry consent logged",
        candidate_id=candidate_id,
        consent=consent_given,
        hash=audio_hash[:8],
    )
    return True
