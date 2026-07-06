"""Узлы графа Agent-Onboarding с обработкой ошибок."""

from typing import Any

from src.core.audit_logger import audit_log
from src.core.state import AgentState
from src.services.rpa_client import trigger_1c_onboarding

_logger = audit_log()


async def collect_documents(state: AgentState) -> dict[str, Any]:
    try:
        candidate = state["candidate"]
        _logger.info(
            "documents_collected",
            candidate_id=candidate.id,
            action="onboarding_doc_collection",
        )
        return state
    except Exception as e:
        _logger.error("collect_documents_failed", error=str(e))
        return {"error": f"collect_documents: {str(e)}", "requires_human_review": True}


async def verify_documents(state: AgentState) -> dict[str, Any]:
    try:
        candidate = state["candidate"]
        _logger.info(
            "documents_verified",
            candidate_id=candidate.id,
            decision="pending",
        )
        return state
    except Exception as e:
        _logger.error("verify_documents_failed", error=str(e))
        return {"error": f"verify_documents: {str(e)}", "requires_human_review": True}


async def schedule_welcome(state: AgentState) -> dict[str, Any]:
    try:
        candidate = state["candidate"]
        _logger.info(
            "welcome_scheduled",
            candidate_id=candidate.id,
            action="onboarding_welcome",
        )
        return state
    except Exception as e:
        _logger.error("schedule_welcome_failed", error=str(e))
        return {"error": f"schedule_welcome: {str(e)}", "requires_human_review": True}


async def send_onboarding_package(state: AgentState) -> dict[str, Any]:
    try:
        candidate = state["candidate"]
        candidate_dict = candidate.dict() if hasattr(candidate, "dict") else candidate
        task_id = await trigger_1c_onboarding(candidate_dict)
        if task_id:
            _logger.info("onboarding_task_created", candidate_id=candidate.id, task_id=task_id)
            state["notes"] = f"Onboarding task created: {task_id}"
        else:
            _logger.warning("onboarding_skipped_no_rpa", candidate_id=candidate.id)
        return state
    except Exception as e:
        _logger.error("send_onboarding_package_failed", error=str(e))
        return {"error": f"send_onboarding_package: {str(e)}", "requires_human_review": True}


async def onboarding_human_review(state: AgentState) -> dict[str, Any]:
    try:
        candidate = state["candidate"]
        _logger.info(
            "onboarding_human_review",
            candidate_id=candidate.id,
            decision="pending",
        )
        return {
            "current_step": "human_review",
            "requires_human_review": True,
        }
    except Exception as e:
        _logger.error("onboarding_human_review_failed", error=str(e))
        return {"error": f"onboarding_human_review: {str(e)}", "requires_human_review": True}
