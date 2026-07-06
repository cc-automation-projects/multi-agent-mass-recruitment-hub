"""Unit-тесты графа Agent-Interviewer."""

import pytest
from langgraph.graph import StateGraph

from src.agents.interviewer.graph import build_interviewer_graph
from src.core.models import Candidate


@pytest.fixture
def candidate() -> Candidate:
    return Candidate(
        id="cand_intv_001",
        name="Тест Интервью",
        phone="+7 999 222 33 44",
        consent_152fz=True,
        resume_text="Менеджер проектов, 5 лет.",
    )


class TestInterviewerGraph:
    def test_graph_builds(self) -> None:
        graph = build_interviewer_graph()
        assert isinstance(graph, StateGraph)

    def test_entry_point(self) -> None:
        graph = build_interviewer_graph()
        assert graph.entry_point == "prepare_questions"

    @pytest.mark.asyncio
    async def test_full_pipeline(self, candidate: Candidate) -> None:
        graph = build_interviewer_graph()
        state = {
            "candidate": candidate,
            "messages": [],
            "current_step": "start",
            "iteration_count": 0,
            "requires_human_review": False,
            "interview_result": None,
            "error": None,
        }
        result = await graph.ainvoke(state)
        assert result is not None
