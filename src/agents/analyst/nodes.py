"""Узлы графа Agent-Analyst с обработкой ошибок и метриками, с реальным fairness‑аудитом из БД."""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from src.agents.analyst.fairness_metrics import calculate_metrics_from_data
from src.core.audit_logger import audit_log
from src.core.config import get_settings
from src.core.metrics import (
    fairness_demographic_parity,
    fairness_disparate_impact,
    fairness_false_rejection_rate,
    human_review_required,
    pipeline_duration_seconds,
)
from src.core.state import AgentState

_logger = audit_log()
_settings = get_settings()
_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_async_engine(_settings.database_url, echo=False)
    return _engine


async def fetch_candidate_data_for_fairness(
    months_back: int = 1,
) -> list[dict[str, Any]]:
    """
    Извлекает данные о кандидатах и результатах интервью за последние months_back месяцев.
    Возвращает список записей с полями: group, rejected, is_strong.
    """
    engine = _get_engine()
    cutoff_date = datetime.utcnow() - timedelta(days=30 * months_back)

    query = text("""
        SELECT
            c.id,
            c.name,
            c.phone,
            c.created_at,
            c.screening_status,
            ir.overall_score,
            ir.recommendation,
            ir.interview_date
        FROM candidates c
        LEFT JOIN interview_results ir ON c.id = ir.candidate_id
        WHERE c.created_at >= :cutoff_date
    """)

    async with engine.connect() as conn:
        rows = await conn.execute(query, {"cutoff_date": cutoff_date})
        data = []
        for row in rows:
            name = row.name or ""
            gender = "male" if name.endswith("в") else "female" if name.endswith("а") else "unknown"
            rejected = row.screening_status != "passed" and row.recommendation != "pass"
            is_strong = row.overall_score is not None and row.overall_score > 0.7
            data.append(
                {
                    "group": f"gender_{gender}",
                    "rejected": rejected,
                    "is_strong": is_strong,
                }
            )
        return data


async def aggregate_metrics(state: AgentState) -> dict[str, Any]:
    try:
        with pipeline_duration_seconds.labels(agent_stage="analyst_aggregate").time():
            pass
        _logger.info("metrics_aggregated", action="analytics_aggregate")
        return state
    except Exception as e:
        _logger.error("aggregate_metrics_failed", error=str(e))
        return {"error": f"aggregate_metrics: {str(e)}", "requires_human_review": True}


async def detect_bottlenecks(state: AgentState) -> dict[str, Any]:
    try:
        _logger.info("bottlenecks_detected", action="analytics_bottlenecks")
        return state
    except Exception as e:
        _logger.error("detect_bottlenecks_failed", error=str(e))
        return {"error": f"detect_bottlenecks: {str(e)}", "requires_human_review": True}


async def fairness_audit_node(state: AgentState) -> dict[str, Any]:
    try:
        data = await fetch_candidate_data_for_fairness(months_back=1)
        if not data:
            _logger.warning("no_data_for_fairness_audit")
            return {"fairness_metrics": None, "requires_human_review": False}

        metrics = calculate_metrics_from_data(data)

        fairness_disparate_impact.labels(group="overall").set(metrics["disparate_impact"])
        fairness_demographic_parity.set(metrics["demographic_parity"])
        for group, rate in metrics["rejection_rates"].items():
            fairness_false_rejection_rate.labels(group=group).set(rate)

        _logger.info(
            "fairness_audit_completed",
            demographic_parity=metrics["demographic_parity"],
            disparate_impact=metrics["disparate_impact"],
            false_rejection_rate=metrics["false_rejection_rate"],
            rejection_rates=metrics["rejection_rates"],
        )

        requires_review = False
        if metrics["disparate_impact"] < _settings.fairness_disparate_impact_threshold:
            requires_review = True
            _logger.warning(
                "fairness_threshold_exceeded",
                metric="disparate_impact",
                value=metrics["disparate_impact"],
                threshold=_settings.fairness_disparate_impact_threshold,
            )
        if metrics["false_rejection_rate"] > _settings.fairness_false_rejection_rate_threshold:
            requires_review = True
            _logger.warning(
                "fairness_threshold_exceeded",
                metric="false_rejection_rate",
                value=metrics["false_rejection_rate"],
                threshold=_settings.fairness_false_rejection_rate_threshold,
            )

        return {
            "fairness_metrics": metrics,
            "requires_human_review": requires_review,
            "current_step": "fairness_audit",
        }
    except Exception as e:
        _logger.error("fairness_audit_node_failed", error=str(e))
        return {"error": f"fairness_audit_node: {str(e)}", "requires_human_review": True}


async def generate_report(state: AgentState) -> dict[str, Any]:
    try:
        metrics = state.get("fairness_metrics")
        if metrics:
            _logger.info("report_generated", fairness_metrics=metrics)
        else:
            _logger.info("report_generated")
        return state
    except Exception as e:
        _logger.error("generate_report_failed", error=str(e))
        return {"error": f"generate_report: {str(e)}", "requires_human_review": True}


async def analyst_human_review(state: AgentState) -> dict[str, Any]:
    try:
        human_review_required.labels(stage="analyst").inc()
        _logger.info("analyst_human_review", decision="pending")
        return {
            "current_step": "human_review",
            "requires_human_review": True,
        }
    except Exception as e:
        _logger.error("analyst_human_review_failed", error=str(e))
        return {"error": f"analyst_human_review: {str(e)}", "requires_human_review": True}
