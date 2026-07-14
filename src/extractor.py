"""Извлечение ключевых полей из текста документа.

Поддерживаемые форматы:
    Суммы: ``1 250 000,00 руб.``, ``1250000.00 ₽``, ``1,250,000.00 RUB``
    Даты:  ``01.03.2025``, ``1 марта 2025 г.``, ``03/01/25`` (MM/DD/YY)
"""

from __future__ import annotations

import re
from pathlib import Path

# --- Константы 

CURRENCY_MARKERS = r"(?:руб(?:лей|ля)?\.?|₽|RUB|р\.)"

RU_MONTHS: dict[str, int] = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4,
    "мая": 5, "июня": 6, "июля": 7, "августа": 8,
    "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}

INN_LENGTH_LEGAL = 10
INN_LENGTH_INDIVIDUAL = 12
CENTURY_PIVOT = 2000  # двухзначный год трактуем как 20xx

AMOUNT_RE = re.compile(
    rf"(\d[\d\s\u00a0,.]*\d|\d)\s*{CURRENCY_MARKERS}",
    re.IGNORECASE,
)
DATE_DOT_RE = re.compile(r"\b(\d{2})\.(\d{2})\.(\d{4})\b")
DATE_RU_RE = re.compile(
    r"\b(\d{1,2})\s+(" + "|".join(RU_MONTHS) + r")\s+(\d{4})",
    re.IGNORECASE,
)
DATE_SLASH_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b")
INN_RE = re.compile(r"ИНН[:\s]*(\d{12}|\d{10})")
CONTRACTOR_RE = re.compile(
    r"(?:Поставщик|Контрагент|Исполнитель|Продавец|Получатель)"
    r"[:\s]*[«\"]?([^»\"\n,;]+?)[»\"]?(?:[,;\n]|ИНН|$)",
    re.IGNORECASE,
)
ORG_RE = re.compile(r"\b(ООО|АО|ПАО|ЗАО|ИП)\s*[«\"]([^»\"\n]+)[»\"]")
SUBJECT_RE = re.compile(
    r"(?:Предмет\s+(?:договора|оплаты|поставки)|Назначение\s+платежа)"
    r"[:\s]+(.+)",
    re.IGNORECASE,
)


# --- Вспомогательные функции 

def _normalize_amount(raw: str) -> float | None:
    """Привести строку суммы к float с учётом разных разделителей."""
    s = raw.replace("\u00a0", " ").strip()
    s = re.sub(r"\s+", "", s)
    if "," in s and "." in s:
        # Последний из разделителей — десятичный
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        head, _, tail = s.rpartition(",")
        if len(tail) == 2:  # десятичная запятая
            s = head.replace(",", "") + "." + tail
        else:  # запятые — разделители тысяч
            s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def _extract_amount(text: str) -> float | None:
    match = AMOUNT_RE.search(text)
    return _normalize_amount(match.group(1)) if match else None


def _extract_date(text: str) -> str | None:
    """Вернуть первую найденную дату в формате ISO (YYYY-MM-DD)."""
    if m := DATE_DOT_RE.search(text):
        day, month, year = m.groups()
        return f"{year}-{month}-{day}"
    if m := DATE_RU_RE.search(text):
        day, month_name, year = m.groups()
        month = RU_MONTHS[month_name.lower()]
        return f"{year}-{month:02d}-{int(day):02d}"
    if m := DATE_SLASH_RE.search(text):
        # Формат YYYY/MM/DD согласно примерам задания (03/01/25 = 2025-03-01)
        month, day, year = (int(g) for g in m.groups())
        if year < 100:
            year += CENTURY_PIVOT
        return f"{year}-{month:02d}-{day:02d}"
    return None


def _extract_inn(text: str) -> str | None:
    match = INN_RE.search(text)
    return match.group(1) if match else None


def _extract_contractor(text: str) -> str | None:
    # Организационная форма с кавычками — самый надёжный маркер
    if m := CONTRACTOR_RE.search(text):
        tail = text[m.start():]
        if org := ORG_RE.search(tail):
            return f"{org.group(1)} «{org.group(2).strip()}»"
        candidate = m.group(1).strip()
        if candidate:
            return candidate
    if org := ORG_RE.search(text):
        return f"{org.group(1)} «{org.group(2).strip()}»"
    return None


def _extract_subject(text: str) -> str | None:
    match = SUBJECT_RE.search(text)
    return match.group(1).strip().rstrip(".") if match else None


def extract(text: str) -> dict:
    # Извлечь ключевые поля документа.
    return {
        "amount": _extract_amount(text),
        "date": _extract_date(text),
        "inn": _extract_inn(text),
        "contractor": _extract_contractor(text),
        "subject": _extract_subject(text),
    }


def read_document(path: str | Path) -> str:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Файл не найден: {p}")
    return p.read_text(encoding="utf-8")


def extract_file(path: str | Path) -> dict:
    return extract(read_document(path))
