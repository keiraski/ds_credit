"""Тесты извлечения полей (включая обязательные asserts из ТЗ)."""
from src.extractor import extract


def test_amount_ru_spaces() -> None:
    assert extract("Сумма: 1 250 000,00 руб.")["amount"] == 1_250_000.0


def test_amount_dot_ruble_sign() -> None:
    assert extract("Итого 1250000.00 ₽")["amount"] == 1_250_000.0


def test_amount_us_format() -> None:
    assert extract("К оплате 1,250,000.00 RUB")["amount"] == 1_250_000.0


def test_inn() -> None:
    assert extract("ИНН 7701234567")["inn"] == "7701234567"


def test_no_digits() -> None:
    assert extract("без цифр")["amount"] is None


def test_date_dot() -> None:
    assert extract("от 01.03.2025")["date"] == "2025-03-01"


def test_date_russian() -> None:
    assert extract("1 марта 2025 г.")["date"] == "2025-03-01"


def test_date_slash_mm_dd_yy() -> None:
    assert extract("03/01/25")["date"] == "2025-03-01"


def test_contractor() -> None:
    text = "Поставщик: ООО «АгроСнаб», ИНН 7701234567"
    assert extract(text)["contractor"] == "ООО «АгроСнаб»"


def test_subject() -> None:
    text = "Предмет договора: поставка удобрений."
    assert extract(text)["subject"] == "поставка удобрений"


def test_missing_fields_are_none() -> None:
    result = extract("пустой текст")
    assert all(v is None for v in result.values())
