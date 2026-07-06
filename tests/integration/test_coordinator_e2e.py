"""
Интеграционные тесты графа Agent-Coordinator (супервизор).

Проверяют маршрутизацию между агентами:
  - screener → interviewer → analyst → analytics_report
  - переход в human_review при ошибке.
"""

from unittest.mock import AsyncMock, patch

import pytest

from src.agents.coordinator.graph import build_coordinator_graph
from src.core.models import Candidate, ScreeningStatus
from src.core.state import AgentState


@pytest.fixture
def candidate_passed() -> Candidate:
    return Candidate(
        id="coord-e2e-001",
        name="Успешный Кандидат",
        phone="+7 999 111 22 33",
        consent_152fz=True,
        resume_text="Опыт работы",
        screening_status=ScreeningStatus.PASSED,
    )


@pytest.fixture
def candidate_needs_review() -> Candidate:
    return Candidate(
        id="coord-e2e-002",
        name="Проблемный Кандидат",
        phone="+7 999 444 55 66",
        consent_152fz=True,
        resume_text="",
        screening_status=ScreeningStatus.NEEDS_HUMAN_REVIEW,
    )


@pytest.fixture
def initial_state_passed(candidate_passed) -> AgentState:
    return {
        "candidate": candidate_passed,
        "messages": [],
        "current_step": "start",
        "iteration_count": 0,
        "requires_human_review": False,
        "interview_result": None,
        "error": None,
    }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_coordinator_full_pipeline(initial_state_passed):
    graph = build_coordinator_graph()

    with (
        patch(
            "src.agents.coordinator.nodes.screener_node", new_callable=AsyncMock
        ) as mock_screener,
        patch(
            "src.agents.coordinator.nodes.interviewer_node", new_callable=AsyncMock
        ) as mock_interviewer,
        patch("src.agents.coordinator.nodes.analyst_node", new_callable=AsyncMock) as mock_analyst,
    ):
        mock_screener.return_value = initial_state_passed
        mock_interviewer.return_value = initial_state_passed
        mock_analyst.return_value = initial_state_passed

        result = await graph.ainvoke(initial_state_passed)

    assert "current_step" in result
    assert "error" not in result


@pytest.mark.integration
@pytest.mark.asyncio
async def test_coordinator_human_review_on_error(initial_state_passed):
    graph = build_coordinator_graph()

    with patch(
        "src.agents.coordinator.nodes.screener_node", new_callable=AsyncMock
    ) as mock_screener:
        mock_screener.side_effect = Exception("Screener failed")

        result = await graph.ainvoke(initial_state_passed)

    assert result["requires_human_review"] is True
    assert "human_review" in result["current_step"] or result["current_step"] == "human_review"
