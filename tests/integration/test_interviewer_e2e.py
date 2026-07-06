"""
Интеграционные тесты графа Agent-Interviewer (end-to-end).

Проверяют:
  1. Полный проход: подготовка → интервью → анализ просодии → результат.
  2. Обработку отсутствия аудио.
  3. Переход в human_review при ошибке или низкой оценке.
"""

from unittest.mock import AsyncMock, patch

import pytest

from src.agents.interviewer.graph import build_interviewer_graph
from src.core.models import Candidate, ProsodyAnalysis, ScreeningStatus
from src.core.state import AgentState


@pytest.fixture
def candidate() -> Candidate:
    return Candidate(
        id="intv-e2e-001",
        name="Тест Кандидат",
        phone="+7 999 111 22 33",
        consent_152fz=True,
        resume_text="Опыт работы 3 года",
        screening_status=ScreeningStatus.PENDING,
    )


@pytest.fixture
def initial_state(candidate: Candidate) -> AgentState:
    return {
        "candidate": candidate,
        "messages": [],
        "current_step": "start",
        "iteration_count": 0,
        "requires_human_review": False,
        "interview_result": None,
        "error": None,
    }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_interviewer_full_pipeline(initial_state):
    graph = build_interviewer_graph()

    with (
        patch("src.agents.interviewer.nodes.os.makedirs"),
        patch("src.agents.interviewer.nodes.open", create=True),
        patch(
            "src.agents.interviewer.prosody.analyze_audio", new_callable=AsyncMock
        ) as mock_prosody,
    ):
        mock_prosody.return_value = ProsodyAnalysis(
            tone="neutral",
            speech_rate=4.0,
            avg_pause_seconds=0.5,
            interruptions=0,
            confidence=0.85,
        )

        result = await graph.ainvoke(initial_state)

    assert "interview_result" in result
    assert result["interview_result"] is not None
    assert result["interview_result"].overall_score > 0
    assert result["interview_result"].prosody is not None
    assert result["interview_result"].prosody.confidence == 0.85
    assert result["current_step"] == "analyze_results"
    assert "error" not in result


@pytest.mark.integration
@pytest.mark.asyncio
async def test_interviewer_no_audio(initial_state):
    graph = build_interviewer_graph()

    with patch("src.agents.interviewer.nodes.os.path.exists", return_value=False):
        result = await graph.ainvoke(initial_state)

    assert "interview_result" in result
    assert result["interview_result"].prosody is None
    assert result["current_step"] == "analyze_results"
    assert "error" not in result


@pytest.mark.integration
@pytest.mark.asyncio
async def test_interviewer_prosody_failure(initial_state):
    graph = build_interviewer_graph()

    with patch(
        "src.agents.interviewer.prosody.analyze_audio",
        side_effect=Exception("Audio processing failed"),
    ):
        result = await graph.ainvoke(initial_state)

    assert result.get("error") is not None
    assert result["requires_human_review"] is True
    assert (
        "human_review_interview" in result["current_step"]
        or result["current_step"] == "human_review_interview"
    )
