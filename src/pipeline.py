from __future__ import annotations

from pathlib import Path

from src.classifier import classify
from src.extractor import extract, read_document
from src.subject_checker import check_subject


def analyze_text(text: str) -> dict:
    doc_type, doc_confidence = classify(text)
    fields = extract(text)
    subject = fields.get("subject")
    subject_check = check_subject(subject) if subject else None
    return {
        "doc_type": doc_type,
        "doc_confidence": doc_confidence,
        "fields": fields,
        "subject_check": subject_check,
    }


def analyze_file(path: str | Path) -> dict:
    return analyze_text(read_document(path))
