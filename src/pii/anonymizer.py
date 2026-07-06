"""
Анонимизация ПДн с использованием Microsoft Presidio (асинхронная обёртка).
"""

import asyncio

from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

from src.core.audit_logger import audit_log
from src.core.config import get_settings

_settings = get_settings()
_logger = audit_log()

_analyzer = None
_anonymizer = None


def _get_engines():
    global _analyzer, _anonymizer
    if _analyzer is None:
        _analyzer = AnalyzerEngine()
        try:
            from src.pii.recognizers import get_russian_recognizers

            for recognizer in get_russian_recognizers():
                _analyzer.registry.add_recognizer(recognizer)
        except ImportError:
            _logger.warning("Russian recognizers not loaded")
    if _anonymizer is None:
        _anonymizer = AnonymizerEngine()
    return _analyzer, _anonymizer


async def anonymize_pii(text: str) -> str:
    if not text:
        return text

    loop = asyncio.get_running_loop()
    analyzer, anonymizer = await loop.run_in_executor(None, _get_engines)

    results = await loop.run_in_executor(None, analyzer.analyze, text, "ru")
    anonymized = await loop.run_in_executor(None, anonymizer.anonymize, text, results)

    _logger.info("pii_anonymized", original_length=len(text), masked_length=len(anonymized.text))
    return anonymized.text
