"""Классификация типа документа по содержимому.

Подход: взвешенный keyword-скоринг. Для каждого класса задан словарь
маркеров с весами; итоговый скор нормализуется в распределение.
Если разрыв между top-1 и top-2 меньше порога ``GAP_THRESHOLD`` —
возвращается ``unknown`` (лучше отдать кейс на ручную проверку,
чем дать ненадёжный ответ).
"""

from __future__ import annotations

import re

# Порог разрыва подобран на dataset/: у однозначных документов гап
# top1-top2 составляет 0.59-1.00, у шумного OCR-файла с маркерами двух
# типов — 0.14. Порог 0.15 отделяет второй случай (unknown -> ручная
# проверка). Меньший порог (0.10) пропустит ненадёжный ответ "spec",
# больший (0.30+) начнёт отбраковывать корректные документы по мере
# роста датасета, увеличивая долю ручных проверок без выигрыша в точности.
GAP_THRESHOLD = 0.15

DOC_KEYWORDS: dict[str, dict[str, float]] = {
    "contract": {
        "договор": 3.0, "стороны": 2.0, "обязуется": 2.0,
        "предмет договора": 3.0, "заключили": 2.0,
        "ответственность сторон": 2.0, "реквизиты сторон": 1.5,
    },
    "spec": {
        "спецификация": 4.0, "номенклатура": 3.0, "наименование товара": 2.0,
        "ед. изм": 2.0, "количество": 1.5, "приложение к договору": 2.0,
    },
    "invoice": {
        "счёт на оплату": 4.0, "счет на оплату": 4.0, "плательщик": 2.0,
        "к оплате": 2.0, "итого": 1.5, "назначение платежа": 2.0,
        "счёт №": 2.5, "счет №": 2.5,
    },
    "act": {
        "акт": 3.0, "выполненных работ": 3.0, "оказанных услуг": 3.0,
        "сдал": 2.0, "принял": 2.0,
        "универсальный передаточный документ": 4.0, "упд": 3.0,
    },
}


def _scores(text: str) -> dict[str, float]:
    lowered = text.lower()
    result: dict[str, float] = {}
    for doc_type, keywords in DOC_KEYWORDS.items():
        score = 0.0
        for keyword, weight in keywords.items():
            hits = len(re.findall(re.escape(keyword), lowered))
            score += weight * min(hits, 3)  # ограничиваем вклад повторов
        result[doc_type] = score
    return result


def classify(text: str) -> tuple[str, float]:
    """Определить тип документа.

    Args:
        text: Текст документа.

    Returns:
        Кортеж ``(тип, уверенность)``, где тип — один из
        ``contract | spec | invoice | act | unknown``,
        уверенность — доля скора победителя в сумме всех скоров (0..1).
    """
    scores = _scores(text)
    total = sum(scores.values())
    if total == 0:
        return "unknown", 0.0

    probs = {k: v / total for k, v in scores.items()}
    ranked = sorted(probs.items(), key=lambda kv: kv[1], reverse=True)
    (top_type, top_prob), (_, second_prob) = ranked[0], ranked[1]

    if top_prob - second_prob < GAP_THRESHOLD:
        return "unknown", top_prob
    return top_type, top_prob
