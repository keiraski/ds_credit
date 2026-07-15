# Проверка соответствия предмета оплаты льготной сельхоз-программе.

from __future__ import annotations

import difflib
import json
import re

from src.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, llm_enabled

# Состояние LLM-режима: заполняется при вызовах, читается через llm_info()
_LLM_STATE: dict[str, str | None] = {"mode": None, "error": None}

FUZZY_THRESHOLD = 0.84          # порог схожести токенов для difflib
BASE_CONFIDENCE = 0.80          # сильное совпадение (прямой сельхоз-ключ)
WEAK_CONFIDENCE = 0.60          # только контекстные ключи -> ручная проверка
CONFIDENCE_STEP = 0.10          # прирост за каждое доп. совпадение
MAX_CONFIDENCE = 0.95
FAIL_CONFIDENCE = 0.80          # уверенность при отсутствии совпадений

ALLOWED_CATEGORIES: dict[str, list[str]] = {
    "агрохимия": ["удобрение", "удобрения", "селитра", "пестицид",
                  "гербицид", "инсектицид", "агрохимия", "фунгицид"],
    "семена и посадочный материал": ["семена", "семян", "семени", "саженец",
                                     "саженцы", "рассада", "посадочный"],
    "сельхозтехника": ["трактор", "комбайн", "сеялка", "плуг",
                       "культиватор", "опрыскиватель", "борона",
                       "сельхозтехника", "жатка"],
    "топливо и ГСМ": ["дизельное", "топливо", "гсм", "солярка"],
    "запчасти к сельхозтехнике": ["запчасти", "запасные"],
    "полевые работы": ["вспашка", "посев", "посевной", "уборка", "урожай",
                       "урожая", "поле", "полей", "мелиорация", "орошение"],
    "животноводство": ["корм", "комбикорм", "скот", "крс", "ветеринарный",
                       "поголовье", "птица"],
    "хранение и переработка урожая": ["зерно", "зернохранилище", "элеватор",
                                      "сушилка", "зерна"],
}

# Слабые (контекстные) ключи: сами по себе не доказывают целевое
# назначение — "дрон для мониторинга ПОЛЕЙ", "ПО для учёта УРОЖАЯ",
# "ремонт ЗЕРНОХРАНИЛИЩА". Совпадение только по ним даёт низкую
# уверенность и уходит на ручную проверку (см. check_subject_verdict).
WEAK_KEYWORDS: frozenset[str] = frozenset({
    "урожай", "урожая", "поле", "полей", "зерно", "зерна",
    "зернохранилище", "корм",
})

# Явные стоп-маркеры нецелевого использования
NEGATIVE_MARKERS: dict[str, str] = {
    "аренда офиса": "аренда офиса не относится к сельхоз-деятельности",
    "легковой": "легковой автомобиль не является сельхозтехникой",
    "реклам": "рекламные услуги не относятся к сельхоз-деятельности",
    "юридическ": "юридические услуги не относятся к сельхоз-деятельности",
    "ноутбук": "офисная техника не относится к сельхоз-деятельности",
}


def _tokens(text: str) -> list[str]:
    return re.findall(r"[а-яёa-z0-9-]+", text.lower())


def _match_categories(subject: str) -> tuple[list[str], bool]:
    """Вернуть (список совпавших категорий, есть ли сильное совпадение).

    Сильное совпадение — ключ не из WEAK_KEYWORDS; слабые ключи
    контекстные и сами по себе вердикт не подтверждают.
    """
    tokens = _tokens(subject)
    matched: list[str] = []
    strong_hit = False
    for category, keywords in ALLOWED_CATEGORIES.items():
        category_hit = False
        for keyword in keywords:
            direct = any(t.startswith(keyword[:6]) and
                         difflib.SequenceMatcher(None, t, keyword).ratio()
                         >= FUZZY_THRESHOLD
                         for t in tokens)
            if direct or keyword in subject.lower():
                category_hit = True
                if keyword not in WEAK_KEYWORDS:
                    strong_hit = True
                    break  # сильный ключ найден, дальше не ищем
        if category_hit:
            matched.append(category)
    return matched, strong_hit


def _check_local(subject: str) -> tuple[bool, float, str]:
    """Локальная проверка без внешних API (keyword + fuzzy matching)."""
    lowered = subject.lower()
    for marker, reason in NEGATIVE_MARKERS.items():
        if marker in lowered:
            return False, 0.91, reason

    matched, strong_hit = _match_categories(subject)
    if matched:
        base = BASE_CONFIDENCE if strong_hit else WEAK_CONFIDENCE
        confidence = min(
            MAX_CONFIDENCE,
            base + CONFIDENCE_STEP * (len(matched) - 1),
        )
        joined = "', '".join(matched)
        return True, confidence, f"предмет относится к категории '{joined}'"
    return (False, FAIL_CONFIDENCE,
            "не найдено соответствия разрешённым сельхоз-категориям")


def _check_llm(subject: str) -> tuple[bool, float, str] | None:
    """Проверка через LLM (LangChain). Возвращает None при любой ошибке;
    причина ошибки сохраняется в _LLM_STATE и видна через llm_info()."""
    try:
        from langchain_openai import ChatOpenAI

        prompt = (
            "Ты проверяешь целевое использование льготного сельхоз-кредита.\n"
            "Примеры:\n"
            'Предмет: "удобрения" -> {"matches": true, "confidence": 0.9, '
            '"reason": "агрохимия"}\n'
            'Предмет: "аренда офиса" -> {"matches": false, "confidence": 0.9,'
            ' "reason": "не сельхоз-деятельность"}\n'
            f'Предмет: "{subject}"\n'
            "Ответь только JSON с ключами matches, confidence, reason."
        )
        llm = ChatOpenAI(
            model=LLM_MODEL,
            api_key=LLM_API_KEY,
            base_url=LLM_BASE_URL,
            timeout=30,
        )
        raw = llm.invoke(prompt).content
        data = json.loads(re.sub(r"```(json)?", "", raw).strip())
        result = (bool(data["matches"]), float(data["confidence"]),
                  str(data["reason"]))
        _LLM_STATE.update(mode="cloud", error=None)
        return result
    except Exception as exc:
        _LLM_STATE.update(mode="local", error=f"{type(exc).__name__}: {exc}")
        return None


def check_subject(subject: str) -> tuple[bool, float, str]:
    # Принимает предмет оплаты, возврощает (соответствие, уверенность, объяснение).
    if not subject or not subject.strip():
        return False, 0.0, "предмет оплаты не указан"
    if llm_enabled():
        if (result := _check_llm(subject)) is not None:
            return result
    return _check_local(subject)


def llm_info() -> str:
    """Человекочитаемый статус: облачная LLM или локальный fallback."""
    if not llm_enabled():
        return "ЛОКАЛЬНЫЙ режим (keyword matching): LLM_API_KEY не задан"
    if _LLM_STATE["mode"] == "cloud":
        return f"ОБЛАЧНАЯ LLM: {LLM_MODEL}"
    if _LLM_STATE["error"]:
        return (f"FALLBACK на локальный режим: LLM недоступна "
                f"({_LLM_STATE['error']}) | конфиг: {LLM_MODEL}")
    return f"Ключ задан, LLM ещё не вызывалась | конфиг: {LLM_MODEL}"


def llm_healthcheck() -> str:
    """Пробный вызов LLM для проверки доступности; вернуть статус-строку."""
    if llm_enabled():
        _check_llm("удобрения")
    return llm_info()

# Порог ручной модерации (по ТЗ: «при низкой уверенности статус
# устанавливается как "требуется ручная проверка"»). 0.75 разделяет
# сильные совпадения (0.80+) и контекстные/слабые (0.60-0.70).
REVIEW_THRESHOLD = 0.75


def check_subject_verdict(subject: str) -> tuple[str, float, str]:
    """Вердикт с учётом порога: PASS | FAIL | MANUAL_REVIEW.

    При уверенности ниже REVIEW_THRESHOLD система не принимает
    решение сама, а помечает кейс для оператора.
    """
    ok, confidence, reason = check_subject(subject)
    if confidence < REVIEW_THRESHOLD:
        return "MANUAL_REVIEW", confidence, reason
    return ("PASS" if ok else "FAIL"), confidence, reason