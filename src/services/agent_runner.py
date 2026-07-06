"""
Запуск LangGraph агента из сохранённого состояния (handoff).
"""

from src.agents.analyst.graph import build_analyst_graph
from src.agents.coordinator.graph import build_coordinator_graph
from src.agents.interviewer.graph import build_interviewer_graph
from src.agents.onboarding.graph import build_onboarding_graph
from src.agents.screener.graph import build_screener_graph
from src.core.audit_logger import audit_log
from src.core.state import AgentState
from src.services.handoff_service import HandoffService

_logger = audit_log()
_handoff = HandoffService()


def _get_graph_for_step(step: str):
    """Возвращает скомпилированный граф LangGraph по названию шага."""
    if step == "screener":
        return build_screener_graph()
    elif step == "interviewer":
        return build_interviewer_graph()
    elif step == "coordinator":
        return build_coordinator_graph()
    elif step == "analyst":
        return build_analyst_graph()
    elif step == "onboarding":
        return build_onboarding_graph()
    else:
        return build_coordinator_graph()


async def resume_conversation(candidate_id: str, user_message: str, channel: str) -> str | None:
    """
    Восстанавливает диалог из сохранённого состояния, передаёт сообщение пользователя
    и возвращает ответ агента.
    """
    state = await _handoff.load_state(candidate_id)
    if not state:
        _logger.warning("No handoff state for candidate", candidate_id=candidate_id)
        return None

    agent_state: AgentState = {
        "candidate": state["candidate"],
        "messages": state.get("messages", []),
        "current_step": state.get("current_step", "coordinator"),
        "iteration_count": state.get("iteration_count", 0),
        "requires_human_review": state.get("requires_human_review", False),
        "interview_result": state.get("interview_result"),
        "error": state.get("error"),
    }

    agent_state["messages"].append({"role": "user", "content": user_message})

    graph = _get_graph_for_step(agent_state["current_step"])
    if graph is None:
        _logger.error("Unknown graph step", step=agent_state["current_step"])
        return None

    try:
        final_state = None
        async for event in graph.astream(agent_state, stream_mode="values"):
            final_state = event

        if final_state is None:
            return None

        messages = final_state.get("messages", [])
        assistant_messages = [m for m in messages if m.get("role") == "assistant"]
        if assistant_messages:
            response = assistant_messages[-1].get("content")
        else:
            response = "Сообщение получено. Ожидайте."

        if final_state.get("current_step") not in ("end", "finished"):
            await _handoff.save_state(candidate_id, final_state)

        return response
    except Exception as e:
        _logger.error("Failed to resume conversation", candidate_id=candidate_id, error=str(e))
        return "Извините, произошла ошибка при обработке сообщения. Пожалуйста, попробуйте позже."
