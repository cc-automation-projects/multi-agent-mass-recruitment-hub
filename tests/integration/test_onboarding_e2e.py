"""
Интеграционные тесты графа Agent-Onboarding.

Проверяют:
  - Сбор и верификацию документов.
  - Отправку приветственного пакета.
  - Переход в human_review при ошибке.
"""

from unittest.mock import AsyncMock, patch

import pytest

from src.agents.onboarding.graph import build_onboarding_graph
from src.core.models import Candidate, ScreeningStatus
from src.core.state import AgentState


@pytest.fixture
def candidate() -> Candidate:
    return Candidate(
        id="onb-e2e-001",
        name="Новый Сотрудник",
        phone="+7 999 777 88 99",
        consent_152fz=True,
        screening_status=ScreeningStatus.PASSED,
    )


@pytest.fixture
def initial_state(candidate) -> AgentState:
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
async def test_onboarding_happy_path(initial_state):
    graph = build_onboarding_graph()

    with (
        patch(
            "src.agents.onboarding.nodes.collect_documents", new_callable=AsyncMock
        ) as mock_collect,
        patch(
            "src.agents.onboarding.nodes.verify_documents", new_callable=AsyncMock
        ) as mock_verify,
        patch(
            "src.agents.onboarding.nodes.schedule_welcome", new_callable=AsyncMock
        ) as mock_schedule,
        patch(
            "src.agents.onboarding.nodes.send_onboarding_package", new_callable=AsyncMock
        ) as mock_send,
    ):
        mock_collect.return_value = initial_state
        mock_verify.return_value = initial_state
        mock_schedule.return_value = initial_state
        mock_send.return_value = initial_state

        result = await graph.ainvoke(initial_state)

    assert "error" not in result
    assert result["current_step"] != "human_review"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_onboarding_verification_failure(initial_state):
    graph = build_onboarding_graph()

    with patch(
        "src.agents.onboarding.nodes.verify_documents", new_callable=AsyncMock
    ) as mock_verify:
        mock_verify.return_value = {"error": "Invalid passport", "requires_human_review": True}

        result = await graph.ainvoke(initial_state)

    assert result.get("requires_human_review") is True
    assert "human_review" in result.get("current_step", "")
