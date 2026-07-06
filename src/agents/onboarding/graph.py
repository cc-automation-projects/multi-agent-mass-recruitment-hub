"""
LangGraph граф Agent-Onboarding.

  START → collect_documents → verify_documents → schedule_welcome → send_onboarding_package → END
                                 ↓ (fail)                      ↓ (needs HR)
                              human_review              human_review (interrupt)
"""

from langgraph.graph import END, StateGraph

from src.agents.onboarding.nodes import (
    collect_documents,
    onboarding_human_review,
    schedule_welcome,
    send_onboarding_package,
    verify_documents,
)
from src.core.state import AgentState, should_continue


def build_onboarding_graph() -> StateGraph:
    workflow = StateGraph(AgentState)

    workflow.add_node("collect_documents", collect_documents)
    workflow.add_node("verify_documents", verify_documents)
    workflow.add_node("schedule_welcome", schedule_welcome)
    workflow.add_node("send_onboarding_package", send_onboarding_package)
    workflow.add_node("human_review", onboarding_human_review)

    workflow.set_entry_point("collect_documents")

    workflow.add_conditional_edges(
        "collect_documents",
        should_continue,
        {"verify_documents": "verify_documents", "human_review": "human_review", "end": END},
    )
    workflow.add_conditional_edges(
        "verify_documents",
        _route_doc_result,
        {"schedule_welcome": "schedule_welcome", "human_review": "human_review", "end": END},
    )
    workflow.add_edge("schedule_welcome", "send_onboarding_package")
    workflow.add_edge("send_onboarding_package", END)
    workflow.add_edge("human_review", END)

    graph = workflow.compile(interrupt_before=["human_review"])
    return graph


def _route_doc_result(state: AgentState) -> str:
    if state.get("error"):
        return "human_review"
    return "schedule_welcome"
