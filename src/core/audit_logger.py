"""
Аудитный логгер на основе structlog.

Соответствует требованиям 152-ФЗ (ст. 18.1, 22) — фиксация действий с ПДн
в формате JSON с обязательными полями.

Использование:
    from src.core.audit_logger import audit_log

    audit_log.info(
        "candidate_screening",
        candidate_id="cand_123",
        action="screening_started",
        decision=None,
        user_id="system"
    )
"""

import logging

import structlog
from structlog.types import EventDict

from src.core.config import get_settings

_settings = get_settings()


def add_candidate_id_processor(
    logger: logging.Logger, method_name: str, event_dict: EventDict
) -> EventDict:
    if "candidate_id" not in event_dict:
        event_dict["candidate_id"] = "unknown"
    return event_dict


def setup_structlog() -> None:
    processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        add_candidate_id_processor,
    ]

    if _settings.audit_json_logging:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    return structlog.get_logger(name)


_audit_logger: structlog.BoundLogger | None = None


def audit_log() -> structlog.BoundLogger:
    global _audit_logger
    if _audit_logger is None:
        setup_structlog()
        _audit_logger = structlog.get_logger("audit")
    return _audit_logger
