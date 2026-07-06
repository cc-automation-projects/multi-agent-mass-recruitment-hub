"""Unit-тесты графа Agent-Screener."""

import pytest
from langgraph.graph import StateGraph

from src.agents.screener.graph import build_screener_graph
from src.core.models import Candidate, ScreeningStatus
from src.core.state import AgentState, should_continue


@pytest.fixture
def candidate_with_consent() -> Candidate:
    return Candidate(
        id="cand_001",
        name="Иван Иванов",
        phone="+7 999 123 45 67",
        consent_152fz=True,
        resume_text="Опыт продаж 5 лет.",
    )


@pytest.fixture
def candidate_no_consent() -> Candidate:
    return Candidate(
        id="cand_002",
        name="Пётр Петров",
        phone="+7 999 987 65 43",
        consent_152fz=False,
    )


@pytest.fixture
def initial_state(candidate_with_consent: Candidate) -> AgentState:
    return {
        "candidate": candidate_with_consent,
        "messages": [],
        "current_step": "start",
        "iteration_count": 0,
        "requires_human_review": False,
        "interview_result": None,
        "error": None,
    }


class TestGraphStructure:
    def test_graph_builds(self) -> None:
        graph = build_screener_graph()
        assert isinstance(graph, StateGraph)

    def test_entry_point_is_validate_consent(self) -> None:
        graph = build_screener_graph()
        assert graph.entry_point == "validate_consent"


class TestShouldContinue:
    def test_returns_end_when_passed(self) -> None:
        state: AgentState = {
            "candidate": Candidate(
                id="x",
                name="x",
                phone="x",
                screening_status=ScreeningStatus.PASSED,
            ),
            "messages": [],
            "current_step": "evaluate",
            "iteration_count": 0,
            "requires_human_review": False,
            "interview_result": None,
            "error": None,
        }
        assert should_continue(state) == "end"

    def test_returns_human_review_when_max_iterations(self) -> None:
        state: AgentState = {
            "candidate": Candidate(id="x", name="x", phone="x"),
            "messages": [],
            "current_step": "ask_questions",
            "iteration_count": 5,
            "requires_human_review": False,
            "interview_result": None,
            "error": None,
        }
        assert should_continue(state) == "human_review"

    def test_returns_human_review_when_flag(self) -> None:
        state: AgentState = {
            "candidate": Candidate(id="x", name="x", phone="x"),
            "messages": [],
            "current_step": "ask_questions",
            "iteration_count": 2,
            "requires_human_review": True,
            "interview_result": None,
            "error": None,
        }
        assert should_continue(state) == "human_review"
