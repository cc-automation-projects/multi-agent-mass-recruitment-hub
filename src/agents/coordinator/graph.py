"""
LangGraph граф Agent-Coordinator (супервизор) с обработкой ошибок и handoff.
"""

from langgraph.graph import END, StateGraph

from src.agents.coordinator.nodes import (
    analyst_node,
    analytics_report,
    coordinator_human_review,
    handle_handoff,
    interviewer_node,
    route_candidate,
    screener_node,
)
from src.core.state import AgentState


def build_coordinator_graph() -> StateGraph:
    workflow = StateGraph(AgentState)

    workflow.add_node("route_candidate", route_candidate)
    workflow.add_node("screener", screener_node)
    workflow.add_node("interviewer", interviewer_node)
    workflow.add_node("analyst", analyst_node)
    workflow.add_node("analytics_report", analytics_report)
    workflow.add_node("human_review", coordinator_human_review)
    workflow.add_node("handoff", handle_handoff)

    workflow.set_entry_point("route_candidate")

    workflow.add_conditional_edges(
        "route_candidate",
        _route_to_next,
        {
            "screener": "screener",
            "interviewer": "interviewer",
            "analyst": "analyst",
            "end": END,
            "handoff": "handoff",
        },
    )

    workflow.add_conditional_edges(
        "screener",
        _route_from_screener,
        {
            "interviewer": "interviewer",
            "human_review": "human_review",
            "end": END,
            "handoff": "handoff",
        },
    )

    workflow.add_conditional_edges(
        "interviewer",
        _route_from_interviewer,
        {
            "analyst": "analyst",
            "human_review": "human_review",
            "end": END,
            "handoff": "handoff",
        },
    )

    workflow.add_edge("analyst", "analytics_report")
    workflow.add_edge("analytics_report", END)
    workflow.add_edge("human_review", END)
    workflow.add_edge("handoff", END)

    graph = workflow.compile(interrupt_before=["human_review"])
    return graph


def _route_to_next(state: AgentState) -> str:
    if state.get("error"):
        return "end"
    return "screener"


def _route_from_screener(state: AgentState) -> str:
    if state.get("error"):
        return "human_review"
    if state["candidate"].screening_status.value == "passed":
        return "interviewer"
    if state["requires_human_review"]:
        return "human_review"
    # Если звонок не удался (можно добавить условие), направляем в handoff
    # Здесь упрощённо: при неудаче ставим флаг в state
    if state.get("call_failed"):
        return "handoff"
    return "end"


def _route_from_interviewer(state: AgentState) -> str:
    if state.get("error"):
        return "human_review"
    if state["requires_human_review"]:
        return "human_review"
    if state.get("call_failed"):
        return "handoff"
    return "analyst" if state.get("interview_result") else "end"
