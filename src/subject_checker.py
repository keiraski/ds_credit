# Проверка соответствия предмета оплаты льготной сельхоз-программе.

from __future__ import annotations

import difflib
import json
import re

from src.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, llm_enabled

FUZZY_THRESHOLD = 0.84          # порог схожести токенов для difflib
BASE_CONFIDENCE = 0.70          # уверенность при одном совпадении
CONFIDENCE_STEP = 0.10          # прирост за каждое доп. совпадение
MAX_CONFIDENCE = 0.95
FAIL_CONFIDENCE = 0.80          # уверенность при отсутствии совпадений

ALLOWED_CATEGORIES: dict[str, list[str]] = {
    "агрохимия": ["удобрение", "удобрения", "селитра", "пестицид",
                  "гербицид", "инсектицид", "агрохимия", "фунгицид"],
    "семена и посадочный материал": ["семена", "саженец",
                                     "саженцы", "рассада", "посадочный"],
    "сельхозтехника": ["трактор", "комбайн", "сеялка", "плуг",
                       "культиватор", "опрыскиватель", "борона",
                       "сельхозтехника", "жатка"],
    "топливо и ГСМ": ["дизельное", "топливо", "гсм", "солярка"],
    "запчасти к сельхозтехнике": ["запчасти", "запасные"],
    "полевые работы": ["вспашка", "посев", "посевной", "уборка", "урожай", "поле",
                       "полей", "мелиорация", "орошение"],
    "животноводство": ["корм", "комбикорм", "скот", "крс", "ветеринарный",
                       "поголовье", "птица"],
    "хранение и переработка урожая": ["зерно", "зернохранилище", "элеватор",
                                      "сушилка", "зерна"],
}

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


def _match_categories(subject: str) -> list[str]:
    """Вернуть список категорий, с которыми совпал предмет оплаты."""
    tokens = _tokens(subject)
    matched: list[str] = []
    for category, keywords in ALLOWED_CATEGORIES.items():
        for keyword in keywords:
            direct = any(t.startswith(keyword[:6]) and
                         difflib.SequenceMatcher(None, t, keyword).ratio()
                         >= FUZZY_THRESHOLD
                         for t in tokens)
            if direct or keyword in subject.lower():
                matched.append(category)
                break
    return matched


def _check_local(subject: str) -> tuple[bool, float, str]:
    """Локальная проверка без внешних API (keyword + fuzzy matching)."""
    lowered = subject.lower()
    for marker, reason in NEGATIVE_MARKERS.items():
        if marker in lowered:
            return False, 0.91, reason

    matched = _match_categories(subject)
    if matched:
        confidence = min(
            MAX_CONFIDENCE,
            BASE_CONFIDENCE + CONFIDENCE_STEP * (len(matched) - 1),
        )
        joined = "', '".join(matched)
        return True, confidence, f"предмет относится к категории '{joined}'"
    return (False, FAIL_CONFIDENCE,
            "не найдено соответствия разрешённым сельхоз-категориям")


def _check_llm(subject: str) -> tuple[bool, float, str] | None:
    """Проверка через LLM (LangChain). Возвращает None при любой ошибке."""
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
            temperature=0,
            timeout=30,
        )
        raw = llm.invoke(prompt).content
        data = json.loads(re.sub(r"```(json)?", "", raw).strip())
        return bool(data["matches"]), float(data["confidence"]), str(data["reason"])
    except Exception:
        return None


def check_subject(subject: str) -> tuple[bool, float, str]:
    # Принимает предмет оплаты, возврощает (соответствие, уверенность, объяснение).
    if not subject or not subject.strip():
        return False, 0.0, "предмет оплаты не указан"
    if llm_enabled():
        if (result := _check_llm(subject)) is not None:
            return result
    return _check_local(subject)
