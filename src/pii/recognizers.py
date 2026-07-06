"""
Кастомные recognizer'ы для Presidio, учитывающие российские форматы:
- Паспорт РФ (серия 4 цифры, пробел, 6 цифр)
- СНИЛС (11 цифр с дефисами или пробелами)
- Номер телефона (+7 999 123-45-67)
- Адрес (улица, дом, город)
"""

from presidio_analyzer import Pattern, PatternRecognizer


class PassportRecognizer(PatternRecognizer):
    """Распознаёт российский паспорт (серия + номер)."""

    def __init__(self):
        patterns = [Pattern("Passport (series + number)", r"\b\d{4}\s?\d{6}\b", 0.8)]
        super().__init__(supported_entity="PASSPORT", patterns=patterns, supported_language="ru")


class SnilsRecognizer(PatternRecognizer):
    """Распознаёт СНИЛС (11 цифр, возможно с дефисами/пробелами)."""

    def __init__(self):
        patterns = [Pattern("SNILS", r"\b\d{3}[-\s]?\d{3}[-\s]?\d{3}[-\s]?\d{2}\b", 0.8)]
        super().__init__(supported_entity="SNILS", patterns=patterns, supported_language="ru")


class RussianPhoneRecognizer(PatternRecognizer):
    """Распознаёт номера телефонов в формате +7 XXX XXX-XX-XX."""

    def __init__(self):
        patterns = [
            Pattern(
                "Russian phone", r"\+7[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}", 0.85
            )
        ]
        super().__init__(supported_entity="PHONE", patterns=patterns, supported_language="ru")


class RussianAddressRecognizer(PatternRecognizer):
    """Базовое распознавание адресов (улица, дом, город)."""

    def __init__(self):
        patterns = [
            Pattern(
                "Russian address (street, city)",
                r"(?:ул\.|улица|просп\.|пр\-т|переулок|пл\.|город|г\.)\s+[А-Яа-я0-9\-\s\.]+",
                0.6,
            )
        ]
        super().__init__(supported_entity="ADDRESS", patterns=patterns, supported_language="ru")


def get_russian_recognizers():
    """Возвращает список всех кастомных recognizer'ов для РФ."""
    return [
        PassportRecognizer(),
        SnilsRecognizer(),
        RussianPhoneRecognizer(),
        RussianAddressRecognizer(),
    ]
