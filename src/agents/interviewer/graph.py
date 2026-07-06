"""
LangGraph граф Agent-Interviewer с опциональным анализом видео.
"""

from langgraph.graph import END, StateGraph

from src.agents.interviewer.nodes import (
    analyze_prosody_node,
    analyze_results,
    analyze_video_node,
    conduct_interview,
    human_review_interview,
    prepare_questions,
)
from src.core.state import AgentState, should_continue


def build_interviewer_graph(include_video: bool = False) -> StateGraph:
    workflow = StateGraph(AgentState)

    workflow.add_node("prepare_questions", prepare_questions)
    workflow.add_node("conduct_interview", conduct_interview)
    workflow.add_node("analyze_prosody", analyze_prosody_node)
    workflow.add_node("analyze_results", analyze_results)
    workflow.add_node("human_review_interview", human_review_interview)

    if include_video:
        workflow.add_node("analyze_video", analyze_video_node)
        workflow.add_edge("conduct_interview", "analyze_prosody")
        workflow.add_edge("analyze_prosody", "analyze_video")
        workflow.add_edge("analyze_video", "analyze_results")
    else:
        workflow.add_edge("conduct_interview", "analyze_prosody")
        workflow.add_edge("analyze_prosody", "analyze_results")

    workflow.set_entry_point("prepare_questions")
    workflow.add_edge("prepare_questions", "conduct_interview")

    workflow.add_conditional_edges(
        "analyze_results",
        should_continue,
        {
            "end": END,
            "human_review": "human_review_interview",
            "continue": END,
        },
    )
    workflow.add_edge("human_review_interview", END)

    graph = workflow.compile(interrupt_before=["human_review_interview"])
    return graph
