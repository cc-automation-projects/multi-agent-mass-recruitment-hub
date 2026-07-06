"""
LangGraph граф Agent-Screener.
"""

from langgraph.graph import END, StateGraph

from src.agents.screener.nodes import (
    analyze_resume,
    ask_questions,
    evaluate_candidate,
    human_review,
    validate_consent,
)
from src.core.state import AgentState, should_continue


def build_screener_graph() -> StateGraph:
    workflow = StateGraph(AgentState)

    workflow.add_node("validate_consent", validate_consent)
    workflow.add_node("analyze_resume", analyze_resume)
    workflow.add_node("ask_questions", ask_questions)
    workflow.add_node("evaluate", evaluate_candidate)
    workflow.add_node("human_review", human_review)

    workflow.set_entry_point("validate_consent")
    workflow.add_conditional_edges(
        "validate_consent",
        _route_no_consent,
        {"analyze_resume": "analyze_resume", "end": END},
    )
    workflow.add_conditional_edges(
        "analyze_resume",
        _route_no_resume,
        {"ask_questions": "ask_questions", "evaluate": "evaluate"},
    )
    workflow.add_conditional_edges(
        "ask_questions",
        should_continue,
        {"evaluate": "evaluate", "human_review": "human_review", "end": END},
    )
    workflow.add_conditional_edges(
        "evaluate",
        should_continue,
        {"end": END, "human_review": "human_review", "continue": END},
    )
    workflow.add_edge("human_review", END)

    graph = workflow.compile(interrupt_before=["human_review"])
    return graph


def _route_no_consent(state: AgentState) -> str:
    if state.get("error") or not state["candidate"].consent_152fz:
        return "end"
    return "analyze_resume"


def _route_no_resume(state: AgentState) -> str:
    if state.get("error"):
        return "evaluate"
    if state["candidate"].resume_text:
        return "evaluate"
    return "ask_questions"
