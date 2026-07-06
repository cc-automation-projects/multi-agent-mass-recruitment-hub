"""
Юнит-тесты механизма семантического кэширования (SemanticCache).

Проверяет:
  1. Semantic cache HIT: одинаковые промпты возвращают кэшированный ответ,
     generate_func не вызывается.
  2. Semantic cache MISS: разные промпты вызывают generate_func,
     результат сохраняется в кэш.
  3. Инвалидация кэша по запросу.
  4. Очистка просроченных записей.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from src.services.semantic_cache import EMBEDDING_DIM, SemanticCache


@pytest.fixture
def mock_qdrant():
    """Создаёт мок AsyncQdrantClient с заранее настроенными ответами."""
    client = AsyncMock()
    # get_collections → пустой список (коллекция будет создана)
    client.get_collections = AsyncMock(return_value=MagicMock(collections=[]))
    client.create_collection = AsyncMock()
    client.search = AsyncMock(return_value=[])
    client.upsert = AsyncMock()
    return client


@pytest.fixture
def cache(mock_qdrant):
    """SemanticCache с замоканным Qdrant-клиентом (bypass create())."""
    return SemanticCache(client=mock_qdrant, threshold=0.95, ttl=3600)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_hit_returns_cached_and_does_not_call_generate(cache, mock_qdrant):
    """
    HIT: одинаковые промпты → возвращается кэшированный ответ.
    generate_func НЕ вызывается.
    """
    cached_response = "Кандидат соответствует требованиям."

    # Эмулируем: Qdrant находит семантически похожий вектор (>0.95)
    mock_qdrant.search = AsyncMock(
        return_value=[
            MagicMock(
                id="cached-001",
                score=0.97,
                payload={"response": cached_response},
            )
        ]
    )

    generate_func = AsyncMock()

    result = await cache.get_or_generate(
        prompt="Оцените кандидата Иванов Иван...",
        candidate_id="cand-001",
        generate_func=generate_func,
    )

    assert result == cached_response
    generate_func.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_miss_calls_generate_and_stores_result(cache, mock_qdrant):
    """
    MISS: новый промпт → generate_func вызывается, результат сохраняется.
    """
    generated = "Кандидат не соответствует."

    # Эмулируем: Qdrant НЕ находит похожий вектор (<0.95)
    mock_qdrant.search = AsyncMock(return_value=[])

    generate_func = AsyncMock(return_value=generated)

    result = await cache.get_or_generate(
        prompt="Оцените кандидата Петров Пётр...",
        candidate_id="cand-002",
        generate_func=generate_func,
    )

    assert result == generated
    generate_func.assert_awaited_once_with("Оцените кандидата Петров Пётр...")
    mock_qdrant.upsert.assert_awaited_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_miss_then_hit_second_call_uses_cache(cache, mock_qdrant):
    """
    MISS → HIT: первый вызов промах, второй — попадание.
    Проверяет, что generate_func вызывается только один раз.
    """
    generated = "Подходит."
    prompt = "Оцените кандидата Сидоров Сидор..."

    mock_qdrant.search = AsyncMock(return_value=[])

    generate_func = AsyncMock(return_value=generated)

    result1 = await cache.get_or_generate(
        prompt=prompt,
        candidate_id="cand-001",
        generate_func=generate_func,
    )
    assert result1 == generated

    # Второй вызов — эмулируем, что Qdrant нашёл кэшированную запись
    mock_qdrant.search = AsyncMock(
        return_value=[
            MagicMock(
                id="cached-002",
                score=0.96,
                payload={"response": generated},
            )
        ]
    )

    result2 = await cache.get_or_generate(
        prompt=prompt,
        candidate_id="cand-001",
        generate_func=generate_func,
    )
    assert result2 == generated

    # generate_func должен быть вызван ровно ОДИН раз (первый вызов)
    assert generate_func.call_count == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_invalidate_cache_removes_entries(cache, mock_qdrant):
    """Инвалидация кэша удаляет записи с семантически похожим промптом."""
    mock_qdrant.search = AsyncMock(
        return_value=[
            MagicMock(id="del-001", score=0.99, payload={}),
            MagicMock(id="del-002", score=0.96, payload={}),
        ]
    )
    mock_qdrant.delete = AsyncMock()

    removed = await cache.invalidate("Удалите этот промпт")

    assert removed is True
    mock_qdrant.search.assert_awaited_once()
    assert mock_qdrant.delete.await_count == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_invalidate_cache_no_match(cache, mock_qdrant):
    """Инвалидация без совпадений возвращает False."""
    mock_qdrant.search = AsyncMock(return_value=[])

    removed = await cache.invalidate("Нет такого промпта")
    assert removed is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_clear_expired_removes_ttl_entries(cache, mock_qdrant):
    """Очистка просроченных записей удаляет их из Qdrant."""
    from datetime import datetime, timedelta

    # Используем offset-naive datetime для совместимости с semantic_cache.py,
    # который использует устаревший datetime.utcnow() (naive).
    now = datetime.utcnow()
    expired_dt = (now - timedelta(hours=2)).isoformat()
    valid_dt = (now + timedelta(hours=2)).isoformat()

    mock_qdrant.scroll = AsyncMock(
        return_value=[
            MagicMock(id="expired-01", payload={"expires_at": expired_dt}),
            MagicMock(id="expired-02", payload={"expires_at": expired_dt}),
            MagicMock(id="valid-01", payload={"expires_at": valid_dt}),
        ]
    )
    mock_qdrant.delete = AsyncMock()

    deleted = await cache.clear_expired()
    assert deleted == 2
    assert mock_qdrant.delete.await_count == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_embed_is_deterministic(cache):
    """Эмбеддинг одного и того же текста детерминирован."""
    emb1 = await cache._embed("Привет, кандидат!")
    emb2 = await cache._embed("Привет, кандидат!")
    assert emb1 == emb2
    assert len(emb1) == EMBEDDING_DIM


@pytest.mark.unit
@pytest.mark.asyncio
async def test_embed_different_texts(cache):
    """Разные тексты дают разные эмбеддинги."""
    emb1 = await cache._embed("Кандидат подходит")
    emb2 = await cache._embed("Кандидат не подходит")
    assert emb1 != emb2
