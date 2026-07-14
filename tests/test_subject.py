"""Тесты проверки предмета оплаты (локальный fallback без API)."""
from src.subject_checker import _check_local, check_subject


def test_fertilizers_pass() -> None:
    ok, confidence, reason = _check_local("Минеральные удобрения")
    assert ok is True
    assert confidence >= 0.7
    assert "агрохимия" in reason


def test_office_rent_fail() -> None:
    ok, confidence, reason = _check_local("Аренда офиса в бизнес-центре")
    assert ok is False
    assert confidence >= 0.8
    assert "офис" in reason


def test_unknown_subject_fail() -> None:
    ok, _, _ = _check_local("Абстрактные консалтинговые услуги")
    assert ok is False


def test_public_api_returns_tuple() -> None:
    result = check_subject("семена пшеницы")
    assert isinstance(result, tuple) and len(result) == 3
