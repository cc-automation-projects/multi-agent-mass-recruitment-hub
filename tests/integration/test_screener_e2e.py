"""
Интеграционные тесты графа Agent-Screener (end-to-end).

Проверяет:
  1. Полный цикл скрининга: от PENDING до терминального статуса.
  2. Итоговое состояние содержит screening_status.
  3. iteration_count не превышает MAX_ITERATIONS.
  4. Корректная обработка отсутствия consent_152fz.
  5. Маршрутизация в human_review при превышении лимита итераций.
"""

import pytest

from src.agents.screener.graph import screener_app
from src.core.models import Candidate, ScreeningStatus
from src.core.state import MAX_ITERATIONS, AgentState


def _make_candidate(
    candidate_id: str = "e2e-001",
    consent: bool = True,
    status: ScreeningStatus = ScreeningStatus.PENDING,
    resume_text: str = "Опыт работы курьером 2 года, водительские права B",
) -> Candidate:
    return Candidate(
        id=candidate_id,
        name="Тестовый Кандидат",
        phone="+7 999 111 22 33",
        consent_152fz=consent,
        screening_status=status,
        resume_text=resume_text,
    )


def _make_state(**overrides) -> AgentState:
    base: AgentState = {
        "candidate": _make_candidate(),
        "messages": [],
        "current_step": "screener",
        "iteration_count": 0,
        "requires_human_review": False,
        "interview_result": None,
        "error": None,
    }
    base.update(overrides)
    return base


@pytest.mark.integration
@pytest.mark.asyncio
async def test_screener_e2e_happy_path():
    """
    E2E Happy Path: кандидат с резюме проходит → status PASSED → coordinator.

    Проверяет:
      - screening_status установлен.
      - iteration_count в пределах лимита.
      - Граф завершается в терминальном узле.
    """
    state = _make_state()

    result = await screener_app.ainvoke(state)

    assert "candidate" in result, "Итоговое состояние должно содержать кандидата"
    assert isinstance(result["candidate"], Candidate)
    assert result["candidate"].screening_status == ScreeningStatus.PASSED
    assert result["iteration_count"] <= MAX_ITERATIONS
    assert result["current_step"] == "coordinator"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_screener_e2e_rejected_no_resume():
    """
    E2E Rejected: кандидат без резюме → handle_unexpected → rejected.

    Проверяет:
      - screening_status = REJECTED.
      - iteration_count не превышает MAX_ITERATIONS.
    """
    state = _make_state(
        candidate=_make_candidate(resume_text="", consent=True),
        iteration_count=1,
    )

    result = await screener_app.ainvoke(state)

    assert result["candidate"].screening_status == ScreeningStatus.REJECTED
    assert result["iteration_count"] <= MAX_ITERATIONS
    assert result["current_step"] == "reject_candidate"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_screener_e2e_human_review_at_limit():
    """
    E2E Human Review: iteration_count >= MAX_ITERATIONS → human_review.

    Проверяет защиту от зацикливания графа.
    """
    state = _make_state(
        candidate=_make_candidate(resume_text="", consent=True),
        iteration_count=MAX_ITERATIONS,
    )

    result = await screener_app.ainvoke(state)

    assert result["current_step"] == "human_review"
    assert result["requires_human_review"] is True
    assert result["candidate"].screening_status == ScreeningStatus.NEEDS_HUMAN_REVIEW
    assert result["iteration_count"] <= MAX_ITERATIONS


@pytest.mark.integration
@pytest.mark.asyncio
async def test_screener_e2e_consent_validation():
    """
    E2E Consent Validation: отсутствие consent_152fz → ошибка валидации.

    Проверяет, что Pydantic model_validator блокирует обработку
    кандидата без согласия (ст. 5 152-ФЗ).
    """
    with pytest.raises(ValueError, match="consent_152fz"):
        _make_candidate(
            consent=False,
            status=ScreeningStatus.SCREENING,
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_screener_e2e_all_statuses_are_terminal():
    """
    E2E: все возможные исходы завершаются в терминальных статусах.

    Проверяет, что граф не зависает в промежуточном состоянии.
    """
    terminal_statuses = {
        ScreeningStatus.PASSED,
        ScreeningStatus.REJECTED,
        ScreeningStatus.NEEDS_HUMAN_REVIEW,
    }

    test_cases = [
        _make_state(),  # happy path
        _make_state(
            candidate=_make_candidate(resume_text="", consent=True),
            iteration_count=1,
        ),
        _make_state(
            candidate=_make_candidate(resume_text="", consent=True),
            iteration_count=MAX_ITERATIONS,
        ),
        _make_state(
            candidate=_make_candidate(resume_text="отличный опыт"),
            iteration_count=MAX_ITERATIONS,
        ),
    ]

    for idx, state in enumerate(test_cases):
        result = await screener_app.ainvoke(state)
        status = result["candidate"].screening_status
        assert status in terminal_statuses, (
            f"Test case {idx}: status {status} не является терминальным"
        )
        assert result["iteration_count"] <= MAX_ITERATIONS, (
            f"Test case {idx}: iteration_count {result['iteration_count']} превысил лимит"
        )
