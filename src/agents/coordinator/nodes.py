"""Узлы графа Agent-Coordinator с обработкой ошибок и метриками, включая handoff."""

from typing import Any

from src.core.audit_logger import audit_log
from src.core.metrics import (
    candidates_total,
    human_review_required,
    pipeline_duration_seconds,
)
from src.core.state import AgentState
from src.services.handoff_service import HandoffService
from src.services.hr_integrations import send_omnichannel_message

_logger = audit_log()
_handoff = HandoffService()


async def route_candidate(state: AgentState) -> dict[str, Any]:
    try:
        candidate = state["candidate"]
        candidates_total.labels(
            status=candidate.screening_status.value,
            source=candidate.source or "unknown",
        ).inc()
        _logger.info(
            "candidate_routed",
            candidate_id=candidate.id,
            action="screening_routed",
        )
        return state
    except Exception as e:
        _logger.error("route_candidate_failed", error=str(e))
        return {"error": f"route_candidate: {str(e)}", "requires_human_review": True}


async def screener_node(state: AgentState) -> dict[str, Any]:
    try:
        candidate = state["candidate"]
        with pipeline_duration_seconds.labels(agent_stage="screener").time():
            pass
        _logger.info(
            "screener_invoked",
            candidate_id=candidate.id,
        )
        return state
    except Exception as e:
        _logger.error("screener_node_failed", error=str(e))
        return {"error": f"screener_node: {str(e)}", "requires_human_review": True}


async def interviewer_node(state: AgentState) -> dict[str, Any]:
    try:
        candidate = state["candidate"]
        with pipeline_duration_seconds.labels(agent_stage="interviewer").time():
            pass
        _logger.info(
            "interviewer_invoked",
            candidate_id=candidate.id,
        )
        return state
    except Exception as e:
        _logger.error("interviewer_node_failed", error=str(e))
        return {"error": f"interviewer_node: {str(e)}", "requires_human_review": True}


async def analyst_node(state: AgentState) -> dict[str, Any]:
    try:
        candidate = state["candidate"]
        with pipeline_duration_seconds.labels(agent_stage="analyst").time():
            pass
        _logger.info(
            "analyst_invoked",
            candidate_id=candidate.id,
        )
        return state
    except Exception as e:
        _logger.error("analyst_node_failed", error=str(e))
        return {"error": f"analyst_node: {str(e)}", "requires_human_review": True}


async def analytics_report(state: AgentState) -> dict[str, Any]:
    try:
        candidate = state["candidate"]
        _logger.info(
            "analytics_report_generated",
            candidate_id=candidate.id,
            action="pipeline_complete",
        )
        return state
    except Exception as e:
        _logger.error("analytics_report_failed", error=str(e))
        return {"error": f"analytics_report: {str(e)}", "requires_human_review": True}


async def coordinator_human_review(state: AgentState) -> dict[str, Any]:
    try:
        candidate = state["candidate"]
        human_review_required.labels(stage="coordinator").inc()
        _logger.info(
            "coordinator_human_review",
            candidate_id=candidate.id,
            decision="pending",
        )
        return {
            "current_step": "human_review",
            "requires_human_review": True,
        }
    except Exception as e:
        _logger.error("coordinator_human_review_failed", error=str(e))
        return {"error": f"coordinator_human_review: {str(e)}", "requires_human_review": True}


async def handle_handoff(state: AgentState) -> dict[str, Any]:
    """
    Узел, вызываемый после двух неудачных звонков.
    Сохраняет состояние в Redis и отправляет сообщение в мессенджер.
    """
    try:
        candidate = state["candidate"]
        # Увеличиваем счётчик попыток
        attempts = await _handoff.increment_attempts(candidate.id)

        if attempts >= 2:
            handoff_state = {
                "candidate": candidate.dict(),
                "current_step": state.get("current_step"),
                "messages": state.get("messages", []),
                "iteration_count": state.get("iteration_count", 0),
                "requires_human_review": state.get("requires_human_review", False),
                "interview_result": state.get("interview_result"),
                "error": state.get("error"),
            }
            await _handoff.save_state(candidate.id, handoff_state)

            # Отправляем сообщение в мессенджер (сначала MAX, затем Telegram, VK)
            text = "Здравствуйте! Вы не ответили на звонок. Давайте продолжим общение в чате. Напишите 'продолжить', чтобы возобновить."
            channels = ["max", "telegram", "vk"]
            sent = False
            for channel in channels:
                # В реальности нужно получить recipient_id из профиля кандидата
                recipient_id = candidate.phone  # упрощённо
                if await send_omnichannel_message(
                    candidate.id, channel, text, extra={"recipient_id": recipient_id}
                ):
                    sent = True
                    _logger.info("handoff_message_sent", candidate_id=candidate.id, channel=channel)
                    break
            if not sent:
                _logger.warning("handoff_no_channel_available", candidate_id=candidate.id)

            # Помечаем, что handoff активирован
            return {
                "requires_human_review": True,
                "current_step": "handoff",
                "error": None,
            }
        else:
            # Можно повторить звонок позже – здесь просто возвращаемся в начало
            return {
                "current_step": "handoff_retry",
                "error": None,
            }
    except Exception as e:
        _logger.error("handle_handoff_failed", error=str(e))
        return {"error": f"handle_handoff: {str(e)}", "requires_human_review": True}
