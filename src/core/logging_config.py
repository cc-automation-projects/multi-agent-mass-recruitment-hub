"""
Настройка структурированного логирования (structlog) с отправкой в Elasticsearch через Logstash.
Логи пишутся в файл JSON, а Filebeat забирает и шлёт в Logstash.
"""

import logging
import sys
from pathlib import Path

import structlog
from structlog.types import EventDict

from src.core.config import get_settings

_settings = get_settings()


def add_service_processor(_, __, event_dict: EventDict) -> EventDict:
    event_dict["service"] = "mass-recruit-hub"
    return event_dict


def setup_logging():
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    handlers = []

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(
        logging.DEBUG if _settings.environment == "development" else logging.INFO
    )
    handlers.append(console_handler)

    json_log_path = log_dir / "app.json.log"
    file_handler = logging.FileHandler(json_log_path)
    file_handler.setLevel(logging.INFO)
    handlers.append(file_handler)

    logging.basicConfig(
        level=logging.INFO,
        handlers=handlers,
    )

    timestamper = structlog.processors.TimeStamper(fmt="iso")

    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            timestamper,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            add_service_processor,
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logging.root.setLevel(logging.INFO)
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    logging.root.addHandler(console_handler)
    logging.root.addHandler(file_handler)
