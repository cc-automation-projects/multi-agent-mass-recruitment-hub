"""
Интеграционные тесты графа Agent-Analyst.

Проверяют:
  - Сбор метрик.
  - Fairness-аудит (с синтетическими данными).
  - Генерацию отчёта.
  - Переход в human_review при превышении порогов.
"""

from unittest.mock import patch

import pytest

from src.agents.analyst.graph import build_analyst_graph
from src.core.models import Candidate, ScreeningStatus
from src.core.state import AgentState


@pytest.fixture
def candidate() -> Candidate:
    return Candidate(
        id="analyst-e2e-001",
        name="Аналитик Тест",
        phone="+7 999 000 11 22",
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
async def test_analyst_happy_path(initial_state):
    graph = build_analyst_graph()

    with patch("src.agents.analyst.nodes._generate_synthetic_data") as mock_data:
        mock_data.return_value = [
            {"group": "gender_male", "rejected": False, "is_strong": True},
            {"group": "gender_female", "rejected": False, "is_strong": True},
        ] * 50

        result = await graph.ainvoke(initial_state)

    assert "fairness_metrics" in result
    assert result["fairness_metrics"]["disparate_impact"] == 1.0
    assert result.get("requires_human_review") is False
    assert "current_step" == "generate_report" or "generate_report" in result.get(
        "current_step", ""
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_analyst_fairness_violation(initial_state):
    graph = build_analyst_graph()

    with patch("src.agents.analyst.nodes._generate_synthetic_data") as mock_data:
        mock_data.return_value = [
            {"group": "gender_male", "rejected": False, "is_strong": True}
        ] * 90 + [{"group": "gender_female", "rejected": True, "is_strong": True}] * 40

        result = await graph.ainvoke(initial_state)

    assert result.get("requires_human_review") is True
    assert "human_review" in result.get("current_step", "")
