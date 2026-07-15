"""Прогон пайплайна на файлах из dataset/ с выводом сводных таблиц.

Запуск:
    python run_demo.py                 # демо на dataset/
    python run_demo.py file1 file2 ... # анализ произвольных файлов
"""

from __future__ import annotations

import sys
from pathlib import Path

from src.classifier import classify
from src.extractor import extract
from src.pipeline import analyze_file
from src.subject_checker import check_subject, check_subject_verdict


DATASET_DIR = Path(__file__).parent / "dataset"
SUBJECTS_FILE = DATASET_DIR / "subjects_test.txt"


def run_extraction_and_classification() -> None:
    """Таблица: файл -> тип документа + извлечённые поля."""
    header = (f"{'Файл':<24}{'Тип':<10}{'Conf':<7}{'Amount':<12}"
              f"{'Date':<12}{'INN':<14}Contractor")
    print(header)
    print("-" * len(header))
    for path in sorted(p for p in DATASET_DIR.glob("*.txt")
                   if p.name != "subjects_test.txt"):
        text = path.read_text(encoding="utf-8")
        doc_type, confidence = classify(text)
        fields = extract(text)
        print(f"{path.name:<24}{doc_type:<10}{confidence:<7.2f}"
              f"{str(fields['amount']):<12}{str(fields['date']):<12}"
              f"{str(fields['inn']):<14}{fields['contractor']}")


def run_subject_checks() -> None:
    """Таблица: предмет оплаты -> вердикт / уверенность / объяснение."""
    print(f"\n{'Предмет оплаты':<46}{'Ожид.':<7}{'Верд.':<7}{'Conf':<7}Объяснение")
    print("-" * 110)
    for line in SUBJECTS_FILE.read_text(encoding="utf-8").splitlines():
        if "|" not in line:
            continue
        subject, expected = (part.strip() for part in line.rsplit("|", 1))
        ok, confidence, reason = check_subject(subject)
        #verdict = "PASS" if ok else "FAIL"
        verdict, confidence, reason = check_subject_verdict(subject)
        print(f"{subject:<46}{expected:<7}{verdict:<7}{confidence:<7.2f}{reason}")


def analyze_paths(paths: list[str]) -> None:
    """Разобрать переданные файлы и вывести отчёт по каждому."""
    for raw in paths:
        path = Path(raw)
        if not path.exists():
            print(f"\n[!] Файл не найден: {path}")
            continue
        result = analyze_file(path)
        fields = result["fields"]
        print(f"\n=== {path.name} ===")
        print(f"Тип документа : {result['doc_type']} "
              f"(conf {result['doc_confidence']:.2f})")
        print(f"Сумма         : {fields['amount']}")
        print(f"Дата          : {fields['date']}")
        print(f"ИНН           : {fields['inn']}")
        print(f"Контрагент    : {fields['contractor']}")
        print(f"Предмет оплаты: {fields['subject']}")
        if result["subject_check"] is not None:
            ok, confidence, reason = result["subject_check"]
            #verdict = "PASS" if ok else "FAIL"
            verdict, confidence, reason = check_subject_verdict(fields["subject"])

            print(f"Целевое исп-е : {verdict} (conf {confidence:.2f}) — {reason}")
        else:
            print("Целевое исп-е : предмет оплаты в документе не найден")


if __name__ == "__main__":
    from src.subject_checker import llm_healthcheck
    print(f"Режим LLM: {llm_healthcheck()}\n")
    if len(sys.argv) > 1:
        analyze_paths(sys.argv[1:])
    else:
        run_extraction_and_classification()
        run_subject_checks()
