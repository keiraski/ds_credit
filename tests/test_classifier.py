"""Тесты классификатора типов документов."""
from src.classifier import classify


def test_invoice_from_spec() -> None:
    doc_type, confidence = classify("Счёт на оплату №12 от 01.03.2025 ...")
    assert doc_type == "invoice"
    assert confidence > 0.5


def test_contract() -> None:
    text = ("Договор поставки. Стороны заключили договор. "
            "Предмет договора: поставка. Ответственность сторон.")
    assert classify(text)[0] == "contract"


def test_spec() -> None:
    text = "Спецификация №1. Номенклатура: наименование товара, ед. изм, количество."
    assert classify(text)[0] == "spec"


def test_act_upd() -> None:
    text = "Универсальный передаточный документ. Акт выполненных работ. Сдал. Принял."
    assert classify(text)[0] == "act"


def test_unknown_on_empty() -> None:
    doc_type, confidence = classify("случайный текст про погоду")
    assert doc_type == "unknown"
    assert confidence == 0.0


def test_unknown_on_ambiguous() -> None:
    # Маркеры двух классов с сопоставимыми скорами -> unknown
    doc_type, _ = classify("договор спецификация договор спецификация")
    assert doc_type == "unknown"
