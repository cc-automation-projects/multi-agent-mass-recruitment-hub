"""
Функции для расчёта метрик fairness-аудита.

- Demographic Parity: разница в вероятности отказа между группами.
- Disparate Impact: отношение минимальной вероятности отказа к максимальной.
- False Rejection Rate: доля ошибочно отклонённых сильных кандидатов (требует ground truth).
"""

from typing import Any


def demographic_parity(rejection_rates: dict[str, float]) -> float:
    """
    Рассчитывает максимальную разницу в rejection rate между группами.
    """
    rates = list(rejection_rates.values())
    if len(rates) < 2:
        return 0.0
    return max(rates) - min(rates)


def disparate_impact(rejection_rates: dict[str, float]) -> float:
    """
    Рассчитывает Disparate Impact = min(rejection_rate) / max(rejection_rate).
    Значение < 0.8 считается проблемным (дискриминация).
    """
    rates = list(rejection_rates.values())
    if not rates:
        return 1.0
    min_rate = min(rates)
    max_rate = max(rates)
    if max_rate == 0:
        return 1.0
    return min_rate / max_rate


def false_rejection_rate(rejected_count: int, false_rejections: int) -> float:
    """
    Доля ошибочно отклонённых кандидатов среди всех отклонённых.
    """
    if rejected_count == 0:
        return 0.0
    return false_rejections / rejected_count


def calculate_metrics_from_data(data: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Принимает список записей кандидатов с полями: group, rejected, is_strong.
    """
    groups = {}
    for item in data:
        group = item["group"]
        if group not in groups:
            groups[group] = {"total": 0, "rejected": 0, "false_rejections": 0}
        groups[group]["total"] += 1
        if item["rejected"]:
            groups[group]["rejected"] += 1
        if item["is_strong"] and item["rejected"]:
            groups[group]["false_rejections"] += 1

    rejection_rates = {}
    false_rejection_rates = {}
    for group, stats in groups.items():
        total = stats["total"]
        rejected = stats["rejected"]
        false_rej = stats["false_rejections"]
        rejection_rates[group] = rejected / total if total > 0 else 0.0
        false_rejection_rates[group] = false_rej / rejected if rejected > 0 else 0.0

    overall_dp = demographic_parity(rejection_rates)
    overall_di = disparate_impact(rejection_rates)
    overall_frr = false_rejection_rate(
        sum(s["rejected"] for s in groups.values()),
        sum(s["false_rejections"] for s in groups.values()),
    )

    return {
        "rejection_rates": rejection_rates,
        "false_rejection_rates": false_rejection_rates,
        "demographic_parity": overall_dp,
        "disparate_impact": overall_di,
        "false_rejection_rate": overall_frr,
    }
