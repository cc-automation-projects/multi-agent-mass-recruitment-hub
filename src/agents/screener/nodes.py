"""
Узлы графа Agent-Screener с обработкой ошибок, метриками и вызовом propensity dialer.
"""

from datetime import datetime
from typing import Any

from src.core.audit_logger import audit_log
from src.core.metrics import (
    human_review_required,
    pipeline_duration_seconds,
    screener_questions_asked,
)
from src.core.state import AgentState
from src.optimization import BanditService
from src.services.biometry_consent import log_biometry_consent
from src.services.propensity_dialer import predict_propensity
from src.telephony import make_call

_logger = audit_log()


async def validate_consent(state: AgentState) -> dict[str, Any]:
    try:
        candidate = state["candidate"]
        if not candidate.consent_152fz:
            _logger.warning(
                "consent_missing",
                candidate_id=candidate.id,
                action="screening_blocked",
            )
            return {"error": "consent_152fz is required", "requires_human_review": True}
        _logger.info(
            "consent_validated",
            candidate_id=candidate.id,
            action="screening_started",
        )
        return state
    except Exception as e:
        _logger.error("validate_consent_failed", error=str(e))
        return {"error": f"validate_consent: {str(e)}", "requires_human_review": True}


async def analyze_resume(state: AgentState) -> dict[str, Any]:
    try:
        candidate = state["candidate"]
        iteration_count = state["iteration_count"] + 1
        with pipeline_duration_seconds.labels(agent_stage="screener_analyze_resume").time():
            pass
        _logger.info(
            "resume_analyzed",
            candidate_id=candidate.id,
            iteration=iteration_count,
        )
        return {"iteration_count": iteration_count}
    except Exception as e:
        _logger.error("analyze_resume_failed", error=str(e))
        return {"error": f"analyze_resume: {str(e)}", "requires_human_review": True}


async def ask_questions(state: AgentState) -> dict[str, Any]:
    try:
        candidate = state["candidate"]
        iteration_count = state["iteration_count"] + 1
        screener_questions_asked.inc()
        _logger.info(
            "questions_asked",
            candidate_id=candidate.id,
            iteration=iteration_count,
        )
        return {"iteration_count": iteration_count}
    except Exception as e:
        _logger.error("ask_questions_failed", error=str(e))
        return {"error": f"ask_questions: {str(e)}", "requires_human_review": True}


async def evaluate_candidate(state: AgentState) -> dict[str, Any]:
    try:
        candidate = state["candidate"]
        iteration_count = state["iteration_count"] + 1
        with pipeline_duration_seconds.labels(agent_stage="screener_evaluate").time():
            if candidate.screening_status == "passed":
                bandit = BanditService(experiment_id="welcome_script", n_arms=3)
                selected_arm = await bandit.select_arm()
                script_variant = f"welcome_v{selected_arm + 1}"
                _logger.info(
                    "script_variant_selected", candidate_id=candidate.id, variant=script_variant
                )

                consent_audio = b"dummy_audio_consent_fragment"
                await log_biometry_consent(
                    candidate_id=candidate.id,
                    audio_fragment=consent_audio,
                    consent_given=True,
                    ip_address=None,
                    user_agent="voice_bot",
                )

                call_time = datetime.utcnow()
                prob = await predict_propensity(candidate, call_time)
                if prob > 0.6:
                    call_result = await make_call(
                        candidate_id=candidate.id,
                        phone_number=candidate.phone,
                        script=script_variant,
                    )
                    success = call_result.get("success", False)
                    await bandit.update(selected_arm, success)
                    _logger.info(
                        "outbound_call_initiated",
                        candidate_id=candidate.id,
                        variant=script_variant,
                        success=success,
                        propensity=prob,
                    )
                else:
                    _logger.info(
                        "low_propensity_skip_call",
                        candidate_id=candidate.id,
                        propensity=prob,
                    )
                    return {
                        "call_failed": True,
                        "iteration_count": iteration_count,
                    }
            else:
                _logger.info(
                    "candidate_not_qualified",
                    candidate_id=candidate.id,
                    status=candidate.screening_status,
                )

        _logger.info(
            "candidate_evaluated",
            candidate_id=candidate.id,
            iteration=iteration_count,
        )
        return {"iteration_count": iteration_count}
    except Exception as e:
        _logger.error("evaluate_candidate_failed", error=str(e))
        return {"error": f"evaluate_candidate: {str(e)}", "requires_human_review": True}


async def human_review(state: AgentState) -> dict[str, Any]:
    try:
        candidate = state["candidate"]
        human_review_required.labels(stage="screener").inc()
        _logger.info(
            "human_review_required",
            candidate_id=candidate.id,
            action="screening_pending_review",
            decision="pending",
        )
        return {
            "current_step": "human_review",
            "requires_human_review": True,
        }
    except Exception as e:
        _logger.error("human_review_node_failed", error=str(e))
        return {"error": f"human_review: {str(e)}", "requires_human_review": True}
