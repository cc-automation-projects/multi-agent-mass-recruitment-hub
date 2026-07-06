"""
Semantic Cache для LLM-инференса (MVR-cache / SemShareKV).

Кэширует KV-кэш семантически похожих промптов, снижая стоимость
инференса в 5–10 раз для массовых однотипных обзвонов.

Архитектура:
  1. Промпт → эмбеддинг (sentence-transformers/multilingual-e5-large).
  2. Поиск в Qdrant по косинусной близости (> threshold).
  3. Если найден → возвращаем кэшированный ответ.
  4. Если нет → вызываем LLM (generate_func), сохраняем результат.

Для поддержки cascade deletion (право на забвение) при сохранении
точки в payload добавляется candidate_id.
"""

import asyncio
import hashlib
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from uuid import uuid4

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from src.core.config import get_settings

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 1024
CACHE_COLLECTION = "semantic_cache"

_embedding_model = None


def _get_embedding_model():
    global _embedding_model
    if _embedding_model is not None:
        return _embedding_model
    try:
        from sentence_transformers import SentenceTransformer

        _embedding_model = SentenceTransformer("intfloat/multilingual-e5-large")
        logger.info("Loaded sentence-transformers model: intfloat/multilingual-e5-large")
    except ImportError:
        logger.warning(
            "sentence-transformers not installed. Using fallback deterministic embedding."
        )
        _embedding_model = None
    return _embedding_model


class CacheEntry:
    """Запись в семантическом кэше с привязкой к кандидату."""

    def __init__(
        self,
        prompt: str,
        response: str,
        embedding: list[float],
        candidate_id: str,
        ttl_seconds: int = 3600,
    ):
        self.id: str = uuid4().hex
        self.prompt: str = prompt
        self.response: str = response
        self.embedding: list[float] = embedding
        self.candidate_id: str = candidate_id
        self.created_at: datetime = datetime.utcnow()
        self.expires_at: datetime = self.created_at + timedelta(seconds=ttl_seconds)
        self.hit_count: int = 0

    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at

    def to_point(self) -> PointStruct:
        return PointStruct(
            id=self.id,
            vector=self.embedding,
            payload={
                "prompt": self.prompt,
                "response": self.response,
                "candidate_id": self.candidate_id,
                "created_at": self.created_at.isoformat(),
                "expires_at": self.expires_at.isoformat(),
                "hit_count": self.hit_count,
            },
        )


class SemanticCache:
    """
    Семантический кэш для LLM-запросов на базе Qdrant.
    """

    def __init__(self, client: AsyncQdrantClient, threshold: float, ttl: int):
        self._client = client
        self._threshold = threshold
        self._ttl = ttl
        self._collection_ready: bool = False

    @classmethod
    async def create(
        cls,
        threshold: float | None = None,
        ttl: int | None = None,
    ) -> "SemanticCache":
        settings = get_settings()
        threshold = threshold or settings.semantic_cache_similarity_threshold
        ttl = ttl or settings.semantic_cache_ttl

        client = AsyncQdrantClient(
            url=str(settings.qdrant_url),
            api_key=settings.qdrant_api_key,
        )

        cache = cls(client=client, threshold=threshold, ttl=ttl)
        await cache._ensure_collection()
        logger.info(
            "SemanticCache initialised",
            extra={"threshold": threshold, "ttl": ttl, "qdrant_url": str(settings.qdrant_url)},
        )
        return cache

    async def _ensure_collection(self) -> None:
        collections = await self._client.get_collections()
        existing = {c.name for c in collections.collections}
        if CACHE_COLLECTION not in existing:
            await self._client.create_collection(
                collection_name=CACHE_COLLECTION,
                vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
            )
            logger.info("Created Qdrant collection", extra={"collection": CACHE_COLLECTION})
        self._collection_ready = True

    async def get_or_generate(
        self,
        prompt: str,
        candidate_id: str,
        generate_func: Callable[[str], Awaitable[str]],
    ) -> str:
        """Проверяет кэш, при промахе вызывает generate_func и сохраняет результат с candidate_id."""
        embedding = await self._embed(prompt)
        cached = await self._search(embedding)

        if cached is not None:
            logger.info(
                "Semantic cache HIT",
                extra={
                    "prompt_prefix": prompt[:60],
                    "similarity": cached["score"],
                    "threshold": self._threshold,
                },
            )
            await self._increment_hit(cached["id"])
            return cached["response"]

        logger.info("Semantic cache MISS", extra={"prompt_prefix": prompt[:60]})
        try:
            response = await generate_func(prompt)
        except Exception:
            logger.exception("LLM generate_func failed")
            raise

        await self._store(prompt, response, embedding, candidate_id)
        return response

    async def invalidate(self, prompt: str) -> bool:
        embedding = await self._embed(prompt)
        hits = await self._client.search(
            collection_name=CACHE_COLLECTION,
            query_vector=embedding,
            limit=10,
            score_threshold=self._threshold,
        )
        for hit in hits:
            await self._client.delete(collection_name=CACHE_COLLECTION, points_selector=[hit.id])
        logger.info("Cache invalidated", extra={"removed": len(hits)})
        return len(hits) > 0

    async def invalidate_by_candidate(self, candidate_id: str) -> int:
        """Удаляет все кэш-записи, связанные с указанным кандидатом (для cascade deletion)."""
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        filter_condition = Filter(
            must=[FieldCondition(key="candidate_id", match=MatchValue(value=candidate_id))]
        )
        points = await self._client.scroll(
            collection_name=CACHE_COLLECTION,
            scroll_filter=filter_condition,
            limit=100,
        )
        deleted = 0
        for point in points:
            await self._client.delete(collection_name=CACHE_COLLECTION, points_selector=[point.id])
            deleted += 1
        if deleted:
            logger.info(
                "Cache invalidated by candidate", candidate_id=candidate_id, removed=deleted
            )
        return deleted

    async def clear_expired(self) -> int:
        points = await self._client.scroll(collection_name=CACHE_COLLECTION, limit=1000)
        deleted = 0
        for point in points:
            expires_at = point.payload.get("expires_at")
            if expires_at and datetime.fromisoformat(expires_at) < datetime.utcnow():
                await self._client.delete(
                    collection_name=CACHE_COLLECTION, points_selector=[point.id]
                )
                deleted += 1
        if deleted:
            logger.info("Expired cache entries cleaned", extra={"count": deleted})
        return deleted

    async def _embed(self, text: str) -> list[float]:
        model = _get_embedding_model()
        if model is not None:
            loop = asyncio.get_running_loop()
            embedding = await loop.run_in_executor(
                None, lambda: model.encode(text, convert_to_numpy=True)
            )
            return embedding.tolist()
        else:
            seed = int(hashlib.md5(text.encode()).hexdigest(), 16) % (10**8)
            rng = __import__("random").Random(seed)
            return [rng.gauss(0, 1) for _ in range(EMBEDDING_DIM)]

    async def _search(self, embedding: list[float]) -> dict | None:
        hits = await self._client.search(
            collection_name=CACHE_COLLECTION,
            query_vector=embedding,
            limit=1,
            score_threshold=self._threshold,
        )
        if not hits:
            return None
        hit = hits[0]
        return {"id": hit.id, "response": hit.payload["response"], "score": hit.score}

    async def _store(
        self, prompt: str, response: str, embedding: list[float], candidate_id: str
    ) -> None:
        entry = CacheEntry(prompt, response, embedding, candidate_id, self._ttl)
        await self._client.upsert(collection_name=CACHE_COLLECTION, points=[entry.to_point()])

    async def _increment_hit(self, point_id: str) -> None:
        try:
            points = await self._client.retrieve(collection_name=CACHE_COLLECTION, ids=[point_id])
            if points:
                current_hits = points[0].payload.get("hit_count", 0)
                await self._client.set_payload(
                    collection_name=CACHE_COLLECTION,
                    payload={"hit_count": current_hits + 1},
                    points=[point_id],
                )
        except Exception:
            logger.warning("Failed to increment hit counter", extra={"point_id": point_id})
