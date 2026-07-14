# Модуль интеллектуальной обработки документов

Тестовое задание DS: извлечение полей, классификация типа документа и проверка
целевого использования льготного сельхоз-кредита.

## 1. Как запустить (3 команды)

```bash
pip install -r requirements.txt
pytest
python run_demo.py
```

`run_demo.py` прогоняет пайплайн на файлах из `dataset/` и печатает две таблицы:
извлечённые поля + тип документа и вердикты по `subjects_test.txt`.

### Анализ произвольных файлов

Передайте один или несколько путей — для каждого выводится отчёт (тип документа,
поля, вердикт по предмету оплаты):

```bash
python run_demo.py dataset/03_invoice.txt
python run_demo.py file1.txt file2.txt          # несколько сразу
```

Несуществующие файлы обрабатываются мягко (`[!] Файл не найден`), без падения.
Без аргументов `run_demo.py` работает как раньше — демо на `dataset/`.

### Запуск в Docker

```bash
docker compose up --build
```

или без compose:

```bash
docker build -t test_ds_credit .
docker run --rm test_ds_credit
```

Для LLM-режима `check_subject` скопируйте `.env.example` в `.env` 
```bash
cp .env.example .env
nano .env
```
и заполните `LLM_API_KEY`,
`LLM_MODEL`, `LLM_BASE_URL` — compose подхватит файл автоматически. Без `.env`
работает локальный fallback. Контейнер прогоняет тесты (pytest) и затем демо-пайплайн. Разовые команды внутри контейнера:

```bash
docker run --rm test_ds_credit pytest -v
docker run --rm test_ds_credit python run_demo.py
```

## 2. Технологии и почему

- **Python 3.11+, stdlib (re, difflib)** — все три задачи решаются детерминированными
  правилами, без ML-зависимостей: воспроизводимо, быстро, работает офлайн.
- **pytest** — тесты из ТЗ + дополнительные кейсы форматов.
- **LangChain** — LLM-режим `check_subject`. Конфигурация через `.env`: `LLM_API_KEY`, `LLM_MODEL`, `LLM_BASE_URL` — подходит любой
  OpenAI-совместимый провайдер (OpenAI, Anthropic через compatibility-эндпоинт, свой
  шлюз). Ключ не задан или запрос упал → автоматический fallback на keyword matching.

## 3. Архитектура

```
src/
  extractor.py        # regex-извлечение полей
  classifier.py       # keyword-скоринг + порог гапа
  subject_checker.py  # проверка целевого назначения
  pipeline.py         # весь пайплайн одним вызовом
tests/                # pytest-тесты
dataset/              # 6 документов, OCR-файл, subjects_test.txt, README с ожиданиями
run_demo.py           # демо на dataset/ + анализ переданных файлов
```

Пайплайн: текст → `classify` (тип) → `extract` (поля) → `check_subject` (целевое
назначение предмета оплаты) → сводный отчёт. `pipeline.analyze_text/analyze_file`
связывает три модуля в один вызов; если `extract` не нашёл предмет оплаты, проверка
предмета пропускается (`subject_check = None`), а не падает.

Логика функций:
- `extract` — набор регулярных выражений на каждое поле; суммы нормализуются с учётом
  разделителей тысяч (пробел/запятая/nbsp) и десятичного знака (`,`/`.`); даты трёх
  форматов приводятся к ISO (01.03.2025 / 1 марта 2025 г. / 03/01/25 переводятся в формат YYYY-MM-DD).
- `classify` — взвешенные ключевые маркеры по 4 классам, скор нормализуется в
  распределение; если гап между top-1 и top-2 < 0.15 — `unknown` (обоснование порога
  в комментарии `src/classifier.py`).
- `check_subject` — стоп-маркеры нецелевого использования → словарь разрешённых
  категорий (keyword + fuzzy через difflib) → объяснение из совпавшей категории.
  Уверенность растёт с числом совпавших категорий (0.70 → 0.95).

## 4. Компромиссы

- Правила вместо ML: на 6 документах обучать нечего; правила прозрачны и объяснимы,
  но потребуют пополнения словарей на реальном потоке.
- Латиница в кириллице после OCR (`pyб`, `дoговор`) не нормализуется — из-за этого
  сумма в OCR-файле пропущена (честно показано в таблице результатов).
- `03/01/25` принят как MM/DD/YY; в проде формат нужно фиксировать по источнику.
- Уверенность — эвристика (доля скора / число совпадений), не калиброванная вероятность.

## 5. Как проверить

Локально:

```bash
pytest -v            # 21 тест, включая обязательные asserts из ТЗ
python run_demo.py   # таблицы: извлечение/классификация и subjects_test (15/15 ожидаемых)
```

В Docker (образ собирается один раз командами из раздела 1):

```bash
docker run --rm test_ds_credit pytest -v            # тесты
docker run --rm test_ds_credit python run_demo.py   # демо-пайплайн
```

Анализ своих файлов в контейнере — примонтируйте папку с ними и передайте пути:

```bash
docker run --rm -v "$PWD/dataset:/app/dataset" test_ds_credit \
  python run_demo.py dataset/03_invoice.txt
```

## 6. Примеры вызовов

```python
from src.extractor import extract
from src.classifier import classify
from src.subject_checker import check_subject

extract("Сумма: 1 250 000,00 руб. от 1 марта 2025 г. ИНН 7701234567")
# {'amount': 1250000.0, 'date': '2025-03-01', 'inn': '7701234567', ...}

classify("Счёт на оплату №12 от 01.03.2025")
# ('invoice', 0.79)

check_subject("минеральные удобрения")
# (True, 0.70, "предмет относится к категории 'агрохимия'")

check_subject(None)  # пустой/отсутствующий предмет не роняет проверку
# (False, 0.0, "предмет оплаты не указан")
```

Работа с файлами напрямую:

```python
from src.extractor import extract_file
from src.pipeline import analyze_file

extract_file("dataset/03_invoice.txt")   # прочитать файл и вернуть только поля

analyze_file("dataset/03_invoice.txt")   # весь пайплайн одним вызовом
# {'doc_type': 'invoice', 'doc_confidence': 0.79,
#  'fields': {'amount': 1250000.0, 'date': '2025-03-01', ...},
#  'subject_check': (True, 0.70, "предмет относится к категории 'агрохимия'")}
```

Вывод `run_demo.py` — в RESULTS.md.
