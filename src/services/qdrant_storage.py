"""
Qdrant vector storage wrapper.

Абстрагирует Qdrant Client для использования в semantic_cache и RAG-пайплайне.
Хранится в РФ-контуре (Qdrant — российская разработка).
"""

from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, UpdateResult, VectorParams

from src.core.config import get_settings

_settings = get_settings()


class QdrantStorage:
    """Упрощённая обёртка над Qdrant."""

    def __init__(
        self,
        collection: str = "default",
        url: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self._collection = collection
        self._client = QdrantClient(
            url=url or str(_settings.qdrant_url),
            api_key=api_key or _settings.qdrant_api_key,
        )

    async def ensure_collection(self, vector_size: int = 384) -> None:
        collections = await self._client.get_collections()
        names = [c.name for c in collections.collections]
        if self._collection not in names:
            await self._client.create_collection(
                collection_name=self._collection,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )

    async def search(self, vector: list[float], limit: int = 1) -> list[Any]:
        return await self._client.search(
            collection_name=self._collection,
            query_vector=vector,
            limit=limit,
        )

    async def upsert(self, vector: list[float], payload: dict[str, Any]) -> UpdateResult:
        return await self._client.upsert(
            collection_name=self._collection,
            points=[PointStruct(id=hash(str(payload)), vector=vector, payload=payload)],
        )

    async def delete(self, vector: list[float]) -> None:
        await self._client.delete(
            collection_name=self._collection,
            points_selector=[hash(str(vector))],
        )
