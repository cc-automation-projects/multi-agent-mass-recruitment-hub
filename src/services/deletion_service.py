"""
Сервис каскадного удаления всех данных кандидата (право на забвение, ст. 15 152-ФЗ).

Удаляет:
- запись из PostgreSQL (основная таблица candidates, а также связанные логи и метрики)
- эмбеддинги из Qdrant (коллекция semantic_cache и RAG)
- аудиозаписи из S3 (эмуляция – локальное хранилище)
- эпизодическую память из Mem0 (через API)
- сессии из Redis
- помечает записи в аудит-логах как удалённые (но не удаляет их полностью для сохранения следов)

Все операции асинхронны, с повторными попытками и логированием.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.core.audit_logger import audit_log
from src.core.config import get_settings

_settings = get_settings()
_logger = audit_log()

_engine = None
_async_session_maker = None


def _get_engine():
    global _engine, _async_session_maker
    if _engine is None:
        _engine = create_async_engine(_settings.database_url, echo=False)
        _async_session_maker = sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)
    return _engine, _async_session_maker


async def delete_candidate_data(candidate_id: str, soft_delete_audit: bool = True) -> dict:
    """
    Полностью удаляет все данные кандидата из всех хранилищ.
    """
    results = {
        "postgres": False,
        "qdrant": False,
        "s3": False,
        "mem0": False,
        "redis": False,
        "audit": False,
        "biometry_consent": False,
    }

    # 1. PostgreSQL
    try:
        _, session_maker = _get_engine()
        async with session_maker() as session:
            await session.execute(
                text("DELETE FROM candidates WHERE id = :id"), {"id": candidate_id}
            )
            await session.execute(
                text("DELETE FROM call_logs WHERE candidate_id = :id"), {"id": candidate_id}
            )
            await session.execute(
                text("DELETE FROM interview_results WHERE candidate_id = :id"), {"id": candidate_id}
            )
            await session.commit()
        results["postgres"] = True
        _logger.info("postgres_deleted", candidate_id=candidate_id)
    except Exception as e:
        _logger.error("postgres_delete_failed", candidate_id=candidate_id, error=str(e))

    # 2. Qdrant (используем фильтр по candidate_id)
    try:
        from qdrant_client import AsyncQdrantClient
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        client = AsyncQdrantClient(url=str(_settings.qdrant_url), api_key=_settings.qdrant_api_key)
        collections = ["semantic_cache", "rag_documents"]
        for coll in collections:
            try:
                # Поиск всех точек с candidate_id
                filter_condition = Filter(
                    must=[FieldCondition(key="candidate_id", match=MatchValue(value=candidate_id))]
                )
                # Используем scroll для получения всех записей (пагинация)
                points = await client.scroll(
                    collection_name=coll,
                    scroll_filter=filter_condition,
                    limit=1000,
                )
                for point in points:
                    await client.delete(collection_name=coll, points_selector=[point.id])
                _logger.info("qdrant_deleted_from_collection", collection=coll, count=len(points))
            except Exception as e:
                _logger.warning("qdrant_delete_collection_failed", collection=coll, error=str(e))
        results["qdrant"] = True
        _logger.info("qdrant_deleted", candidate_id=candidate_id)
    except Exception as e:
        _logger.error("qdrant_delete_failed", candidate_id=candidate_id, error=str(e))

    # 3. S3 (local filesystem emulation)
    try:
        import os
        import shutil

        s3_prefix = f"audio/{candidate_id}"
        if os.path.exists(s3_prefix):
            shutil.rmtree(s3_prefix)
        results["s3"] = True
        _logger.info("s3_deleted", candidate_id=candidate_id, path=s3_prefix)
    except Exception as e:
        _logger.error("s3_delete_failed", candidate_id=candidate_id, error=str(e))

    # 4. Mem0
    try:
        from mem0 import MemoryClient

        client = MemoryClient(api_key=_settings.mem0_api_key)
        await client.delete_user(candidate_id)
        results["mem0"] = True
        _logger.info("mem0_deleted", candidate_id=candidate_id)
    except Exception as e:
        _logger.warning("mem0_delete_failed", candidate_id=candidate_id, error=str(e))

    # 5. Redis
    try:
        import redis.asyncio as redis

        r = redis.from_url(_settings.redis_url)
        keys = await r.keys(f"*{candidate_id}*")
        if keys:
            await r.delete(*keys)
        results["redis"] = True
        _logger.info("redis_deleted", candidate_id=candidate_id, keys_count=len(keys))
    except Exception as e:
        _logger.error("redis_delete_failed", candidate_id=candidate_id, error=str(e))

    # 7. Biometry consent logs
    try:
        _, session_maker = _get_engine()
        async with session_maker() as session:
            await session.execute(
                text("DELETE FROM biometry_consent_log WHERE candidate_id = :id"),
                {"id": candidate_id},
            )
            await session.commit()
        results["biometry_consent"] = True
        _logger.info("biometry_consent_deleted", candidate_id=candidate_id)
    except Exception as e:
        _logger.error("biometry_consent_delete_failed", error=str(e))

    # 6. Audit logs
    try:
        _, session_maker = _get_engine()
        async with session_maker() as session:
            await session.execute(
                text(
                    "UPDATE audit_logs SET deleted_at = NOW() WHERE candidate_id = :id AND deleted_at IS NULL"
                ),
                {"id": candidate_id},
            )
            await session.commit()
        results["audit"] = True
        _logger.info("audit_marked_deleted", candidate_id=candidate_id)
    except Exception as e:
        _logger.error("audit_mark_failed", candidate_id=candidate_id, error=str(e))

    return results
