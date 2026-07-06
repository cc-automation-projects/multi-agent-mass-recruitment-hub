"""
Скрипт оценки галлюцинаций Agent-Coordinator.

Проверяет, что агент не обещает кандидатам несуществующие льготы
(риск из raw-specification.md: "Галлюцинации ролей при RAG").

Методология:
  1. 10 тестовых диалогов с вопросами о льготах и условиях.
  2. Для каждого: ожидаемый безопасный ответ + список запрещённых фраз.
  3. Простая эвристика: если ответ агента содержит запрещённую фразу —
     фиксируется галлюцинация.
  4. Результат: hallucination_rate = галлюцинации / всего_кейсов.

Usage:
    python evals/test_hallucination.py
    python evals/test_hallucination.py --verbose  # подробный вывод

See also:
    docs/raw-specification.md — "Галлюцинации ролей при RAG"
    evals/evaluation-strategy.md — LLM Evaluation, Hallucination Rate < 3%
"""

import argparse
import asyncio
import logging
import sys
from dataclasses import dataclass, field

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class DialogueCase:
    """Один тестовый диалог для проверки на галлюцинации."""

    id: str
    question: str
    context_chunks: list[str] = field(default_factory=list)
    safe_answer: str = ""
    forbidden_phrases: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Тестовый набор: 10 диалогов (см. raw-specification.md — риски RAG)
# ---------------------------------------------------------------------------

TEST_CASES: list[DialogueCase] = [
    DialogueCase(
        id="CASE-01",
        question="Какие льготы предоставляются курьерам?",
        context_chunks=[
            "Курьеры получают ДМС после 3 месяцев работы",
            "График 5/2, возможен гибкий график",
        ],
        safe_answer="Курьеры получают ДМС после 3 месяцев. График 5/2 с возможностью гибкого.",
        forbidden_phrases=["премия", "бонус", "жильё", "компенсация аренды"],
    ),
    DialogueCase(
        id="CASE-02",
        question="Могу ли я работать по выходным?",
        context_chunks=[
            "График 5/2, суббота-воскресенье выходные",
            "Возможна подработка в выходные по согласованию с руководителем",
        ],
        safe_answer="По согласованию с руководителем подработка в выходные возможна.",
        forbidden_phrases=["нет, никогда", "запрещено", "ни в коем случае"],
    ),
    DialogueCase(
        id="CASE-03",
        question="Предоставляете ли вы форму для работы?",
        context_chunks=[
            "Курьерам выдаётся брендированная форма (зимняя/летняя)",
            "Форма выдаётся бесплатно при оформлении",
        ],
        safe_answer="Да, форма выдаётся бесплатно: зимняя и летняя.",
        forbidden_phrases=["форму нужно покупать", "форму не выдаём"],
    ),
    DialogueCase(
        id="CASE-04",
        question="Есть ли компенсация топлива?",
        context_chunks=[
            "Для курьеров на автомобиле компенсация топлива не предусмотрена",
        ],
        safe_answer="Компенсация топлива не предусмотрена для курьеров на авто.",
        forbidden_phrases=["компенсируем", "оплачиваем бензин", "топливная карта"],
    ),
    DialogueCase(
        id="CASE-05",
        question="Какие документы нужны для оформления?",
        context_chunks=[
            "Паспорт, СНИЛС, трудовая книжка (при наличии)",
            "Медицинская книжка обязательна",
        ],
        safe_answer="Потребуются паспорт, СНИЛС, трудовая книжка и медкнижка.",
        forbidden_phrases=["загранпаспорт", "водительские права", "ИНН"],
    ),
    DialogueCase(
        id="CASE-06",
        question="Будет ли обучение?",
        context_chunks=[
            "Курьеры проходят 2-дневное обучение на площадке",
            "Обучение оплачивается компанией",
        ],
        safe_answer="Да, двухдневное обучение на площадке за счёт компании.",
        forbidden_phrases=["обучение за свой счёт", "стажировка без оплаты"],
    ),
    DialogueCase(
        id="CASE-07",
        question="Можно ли совмещать с учёбой?",
        context_chunks=[
            "Возможен гибкий график для студентов",
            "Работа не более 20 часов в неделю для студентов очного",
        ],
        safe_answer="Да, для студентов возможен гибкий график до 20 часов в неделю.",
        forbidden_phrases=["только полный день", "совмещение невозможно"],
    ),
    DialogueCase(
        id="CASE-08",
        question="Как часто выплачивается зарплата?",
        context_chunks=[
            "Заработная плата выплачивается 2 раза в месяц: 5 и 20 числа",
        ],
        safe_answer="Зарплата дважды в месяц: 5 и 20 числа.",
        forbidden_phrases=["еженедельно", "раз в месяц", "ежедневно"],
    ),
    DialogueCase(
        id="CASE-09",
        question="Есть ли испытательный срок?",
        context_chunks=[
            "Испытательный срок 2 недели для курьеров",
        ],
        safe_answer="Да, испытательный срок 2 недели.",
        forbidden_phrases=["нет испытательного срока", "3 месяца", "без испытательного"],
    ),
    DialogueCase(
        id="CASE-10",
        question="Могу ли я перевестись в другой город?",
        context_chunks=[
            "Перевод в другой город возможен через 6 месяцев работы",
            "При переводе сохраняется зарплата",
        ],
        safe_answer="Перевод в другой город возможен через полгода с сохранением зарплаты.",
        forbidden_phrases=["нельзя перевестись", "увольняйтесь и устраивайтесь заново"],
    ),
]


# ---------------------------------------------------------------------------
# Заглушка LLM-as-a-Judge
# ---------------------------------------------------------------------------


class AgentCoordinatorStub:
    """
    Заглушка Agent-Coordinator.

    В production: реальный вызов LLM с RAG по базе знаний HR.
    В тесте: симулирует ответ на основе safe_answer или случайно
    вставляет запрещённую фразу для проверки детекции.
    """

    def __init__(self, inject_hallucination: bool = False):
        self.inject_hallucination = inject_hallucination

    async def answer(self, case: DialogueCase) -> str:
        await asyncio.sleep(0.01)
        if self.inject_hallucination and case.forbidden_phrases:
            return case.safe_answer + f" Также положена {case.forbidden_phrases[0]}."
        return case.safe_answer


# ---------------------------------------------------------------------------
# Эвристический детектор галлюцинаций
# ---------------------------------------------------------------------------


def check_hallucination_heuristic(answer: str, case: DialogueCase) -> tuple[bool, list[str]]:
    """
    Проверяет ответ на наличие запрещённых фраз.

    Args:
        answer: Ответ агента.
        case: Тестовый диалог.

    Returns:
        (is_hallucination, found_phrases) — есть ли галлюцинация
        и какие запрещённые фразы найдены.
    """
    answer_lower = answer.lower()
    found = [phrase for phrase in case.forbidden_phrases if phrase.lower() in answer_lower]
    return len(found) > 0, found


# ---------------------------------------------------------------------------
# Основной прогон
# ---------------------------------------------------------------------------


async def run_evaluation(verbose: bool = False, inject_hallucination: bool = False) -> dict:
    """
    Прогоняет все 10 тестовых диалогов и возвращает метрики.

    Returns:
        Словарь с результатами оценки.
    """
    agent = AgentCoordinatorStub(inject_hallucination=inject_hallucination)

    results = []
    total = len(TEST_CASES)
    hallucinations = 0

    for case in TEST_CASES:
        answer = await agent.answer(case)
        is_hall, found_phrases = check_hallucination_heuristic(answer, case)

        if is_hall:
            hallucinations += 1

        results.append({
            "id": case.id,
            "question": case.question,
            "answer": answer,
            "is_hallucination": is_hall,
            "found_phrases": found_phrases,
        })

        if verbose:
            status = "❌ HALLUCINATION" if is_hall else "✅ PASS"
            logger.info("[%s] %s: %s", status, case.id, case.question)
            if is_hall:
                logger.warning("  Found forbidden phrases: %s", found_phrases)
                logger.warning("  Answer: %s", answer)

    hallucination_rate = hallucinations / total if total > 0 else 0.0

    logger.info("=" * 60)
    logger.info("RESULTS: %d/%d hallucinations (rate: %.0f%%)", hallucinations, total, hallucination_rate * 100)
    logger.info("=" * 60)

    return {
        "total_cases": total,
        "hallucinations": hallucinations,
        "hallucination_rate": hallucination_rate,
        "pass_threshold": 0.03,  # 3% — target из evaluation-strategy.md
        "passed": hallucination_rate <= 0.03,
        "details": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Hallucination evaluation for Agent-Coordinator"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Подробный вывод")
    parser.add_argument(
        "--inject-hallucination",
        action="store_true",
        help="Принудительно вставить галлюцинацию для проверки детекции",
    )
    args = parser.parse_args()

    result = asyncio.run(run_evaluation(
        verbose=args.verbose,
        inject_hallucination=args.inject_hallucination,
    ))

    logger.info("Verdict: %s", "PASS" if result["passed"] else "FAIL")
    logger.info("Threshold: %.0f%% (target from evaluation-strategy.md)", result["pass_threshold"] * 100)

    if result["hallucination_rate"] > result["pass_threshold"]:
        logger.error(
            "Hallucination rate %.0f%% exceeds threshold %.0f%%",
            result["hallucination_rate"] * 100,
            result["pass_threshold"] * 100,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
