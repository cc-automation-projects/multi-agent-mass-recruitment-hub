"""Unit-тесты графа Agent-Coordinator."""

import pytest
from langgraph.graph import StateGraph

from src.agents.coordinator.graph import build_coordinator_graph
from src.core.models import Candidate


@pytest.fixture
def candidate() -> Candidate:
    return Candidate(
        id="cand_coord_001",
        name="Тест Координатор",
        phone="+7 999 111 22 33",
        consent_152fz=True,
        resume_text="Full-stack разработчик, 3 года опыта.",
    )


class TestCoordinatorGraph:
    def test_graph_builds(self) -> None:
        graph = build_coordinator_graph()
        assert isinstance(graph, StateGraph)

    def test_entry_point(self) -> None:
        graph = build_coordinator_graph()
        assert graph.entry_point == "route_candidate"

    @pytest.mark.asyncio
    async def test_full_pipeline(self, candidate: Candidate) -> None:
        graph = build_coordinator_graph()
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
