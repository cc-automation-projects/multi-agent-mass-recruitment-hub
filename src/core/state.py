"""
Состояние графа LangGraph для массового рекрутинга.
"""

from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages

from src.core.models import Candidate, InterviewResult

MAX_ITERATIONS: int = 5


class AgentState(TypedDict):
    candidate: Annotated[Candidate, "Текущий кандидат"]
    messages: Annotated[list, add_messages]
    current_step: Annotated[str, "Текущий узел графа"]
    iteration_count: Annotated[int, "Счётчик итераций"]
    requires_human_review: Annotated[bool, "Флаг необходимости human-in-the-loop"]
    interview_result: Annotated[InterviewResult | None, "Результат собеседования"]
    error: Annotated[str | None, "Текст ошибки"]


def should_continue(state: AgentState) -> str:
    """
    Условное ребро для LangGraph.
    Возвращает:
        "human_review" – если ошибка, превышен лимит итераций или требуется review,
        "end" – терминальное состояние,
        "continue" – продолжить.
    """
    if state.get("error"):
        return "human_review"
    if state["iteration_count"] >= MAX_ITERATIONS:
        return "human_review"
    if state["requires_human_review"]:
        return "human_review"
    status = state["candidate"].screening_status
    if status in ("passed", "rejected", "needs_human_review"):
        return "end"
    return "continue"
