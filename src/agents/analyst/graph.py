"""
LangGraph граф Agent-Analyst (аналитика + fairness-аудит).

  START → aggregate_metrics → detect_bottlenecks → fairness_audit → generate_report → END
                                                       ↓ (needs review)
                                                    human_review (interrupt)
"""

from langgraph.graph import END, StateGraph

from src.agents.analyst.nodes import (
    aggregate_metrics,
    analyst_human_review,
    detect_bottlenecks,
    fairness_audit_node,
    generate_report,
)
from src.core.state import AgentState


def build_analyst_graph() -> StateGraph:
    workflow = StateGraph(AgentState)

    workflow.add_node("aggregate_metrics", aggregate_metrics)
    workflow.add_node("detect_bottlenecks", detect_bottlenecks)
    workflow.add_node("fairness_audit", fairness_audit_node)
    workflow.add_node("generate_report", generate_report)
    workflow.add_node("human_review", analyst_human_review)

    workflow.set_entry_point("aggregate_metrics")

    workflow.add_edge("aggregate_metrics", "detect_bottlenecks")
    workflow.add_edge("detect_bottlenecks", "fairness_audit")

    workflow.add_conditional_edges(
        "fairness_audit",
        _route_after_audit,
        {
            "generate_report": "generate_report",
            "human_review": "human_review",
        },
    )
    workflow.add_edge("generate_report", END)
    workflow.add_edge("human_review", END)

    graph = workflow.compile(interrupt_before=["human_review"])
    return graph


def _route_after_audit(state: AgentState) -> str:
    if state.get("requires_human_review"):
        return "human_review"
    return "generate_report"
