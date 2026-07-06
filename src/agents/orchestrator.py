"""
Оркестратор кампании – запускает обработку списка кандидатов.
"""

import asyncio

from src.agents.screener.graph import build_screener_graph
from src.core.audit_logger import audit_log

_logger = audit_log()


async def run_campaign(candidate_ids: list[str]):
    _logger.info("campaign_started", candidate_count=len(candidate_ids))
    screener_graph = build_screener_graph()
    for candidate_id in candidate_ids:
        _logger.info("processing_candidate", candidate_id=candidate_id)
        await asyncio.sleep(0.1)
    _logger.info("campaign_completed", candidate_count=len(candidate_ids))
