# Модуль интеллектуальной обработки документов

Тестовое задание DS: извлечение полей, классификация типа документа и проверка
целевого использования льготного сельхоз-кредита.

## 1. Как запустить (3 команды)

```bash
pip install -r requirements.txt
pytest
python run_demo.py
```

`run_demo.py` перед таблицами печатает строку `Режим LLM: ...` — облачная LLM,
локальный режим или fallback с причиной ошибки (нет ключа, нет библиотеки,
ошибка API). Далее выводятся две таблицы: извлечённые поля + тип документа по
всем файлам `dataset/` и вердикты по `subjects_test.txt`.

### Анализ произвольных файлов

Передайте один или несколько путей — для каждого выводится отчёт (тип документа,
поля, вердикт по предмету оплаты):

```bash
python run_demo.py dataset/03_invoice.txt
python run_demo.py file1.txt file2.txt          # несколько сразу
```

Без аргументов `run_demo.py` работает как раньше — демо на `dataset/`.

### Запуск в Docker

Основной способ — через compose (он автоматически читает `.env` с ключами LLM):

```bash
docker compose build                                 # /сборка/пересборка после изменений кода/датасета
docker compose run --rm ds-pipeline                  # тесты + демо-пайплайн
docker compose run --rm ds-pipeline python run_demo.py                                    # только демо
docker compose run --rm ds-pipeline python run_demo.py dataset/test_06_contract_storage.txt   # один файл
```

Без compose `.env` не подхватывается сам — для LLM-режима нужно добавить `--env-file`:

```bash
docker build -t ds_credit .
docker run --rm --env-file .env ds_credit python run_demo.py
docker run --rm ds_credit python run_demo.py         # локальный режим, без ключей
```

Настройка LLM-режима: нужно скопировать `.env.example` в `.env`

```bash
cp .env.example .env
nano .env
```

и заполните `LLM_API_KEY`, `LLM_MODEL`, `LLM_BASE_URL`. Без `.env` работает
локальный fallback (keyword matching). Важно: после изменения кода или датасета
образ нужно пересобрать (`docker compose build`), иначе контейнер запустит
старую копию.

## 2. Технологии и почему

- **Python 3.11+, stdlib (re, difflib)** — все три задачи решаются детерминированными
  правилами, без ML-зависимостей: воспроизводимо, быстро, работает офлайн.
- **pytest** — тесты из ТЗ + дополнительные кейсы форматов.
- **LangChain** — LLM-режим `check_subject`. Конфигурация через `.env`: `LLM_API_KEY`,
  `LLM_MODEL`, `LLM_BASE_URL` — подходит любой OpenAI-совместимый провайдер (OpenAI,
  Anthropic через compatibility-эндпоинт, свой шлюз). Протестировано с Anthropic API (`claude-sonnet-5`, `https://api.anthropic.com/v1`). Промпт калиброван занижать уверенность на неоднозначных предметах оплаты, чтобы такие кейсы уходили на ручную проверку. Ключ не задан или запрос упал → автоматический fallback на keyword matching.

## 3. Архитектура

```
src/
  extractor.py        # regex-извлечение полей
  classifier.py       # keyword-скоринг + порог гапа
  subject_checker.py  # проверка целевого назначения + вердикт с порогом
  pipeline.py         # весь пайплайн одним вызовом
tests/                # pytest-тесты
dataset/              # 12 документов (6 базовых + 6 test_*), OCR-файл,
                      # subjects_test.txt, README с ожиданиями
run_demo.py           # демо на dataset/ + анализ переданных файлов
```

Пайплайн: текст → `classify` (тип) → `extract` (поля) → `check_subject_verdict`
(целевое назначение предмета оплаты) → сводный отчёт. `pipeline.analyze_text/analyze_file`
связывает три модуля в один вызов; если `extract` не нашёл предмет оплаты, проверка
предмета пропускается (`subject_check = None`), а не падает.

Логика функций:
- `extract` — набор регулярных выражений на каждое поле; суммы нормализуются с учётом
  разделителей тысяч (пробел/запятая/nbsp) и десятичного знака (`,`/`.`); даты трёх
  форматов приводятся к ISO (01.03.2025 / 1 марта 2025 г. / 03/01/25 переводятся в
  формат YYYY-MM-DD).
- `classify` — взвешенные ключевые маркеры по 4 классам, скор нормализуется в
  распределение; если гап между top-1 и top-2 < 0.15 — `unknown` (обоснование порога
  в комментарии `src/classifier.py`).
- `check_subject` — стоп-маркеры нецелевого использования → словарь разрешённых
  категорий (keyword + fuzzy через difflib) → объяснение из совпавшей категории.
  Ключевые слова разделены на сильные и слабые (контекстные): прямые сельхоз-ключи
  («трактор», «семена», «вспашка») дают уверенность 0.80–0.95, контекстные («полей»,
  «урожая», «зерно») сами по себе целевое назначение не доказывают и дают 0.60.
- `check_subject_verdict` — трёхуровневый вердикт `PASS | FAIL | MANUAL_REVIEW`:
  при уверенности ниже `REVIEW_THRESHOLD = 0.75` система не принимает решение
  самостоятельно, а помечает кейс на ручную проверку (по ТЗ: «при низкой уверенности
  статус устанавливается как "требуется ручная проверка"»). Порог применяется и к
  локальному режиму, и к уверенности облачной LLM.

## 4. Компромиссы

- Правила вместо ML: на 12 документах обучать нечего; правила прозрачны и объяснимы,
  но потребуют пополнения словарей на реальном потоке.
- Разметка сильных/слабых ключей сделана вручную по тестовой выборке; на проде её
  нужно валидировать на размеченных данных.
- Калибровка уверенности LLM держится на инструкциях в промпте — для прода нужна
  проверка на размеченной выборке и, возможно, отдельная модель калибровки.
- Латиница в кириллице после OCR (`pyб`, `дoговор`) не нормализуется — из-за этого
  сумма в OCR-файле пропущена.
- `03/01/25` принят как MM/DD/YY; в проде формат нужно фиксировать по источнику.


## 5. Как проверить

Локально:

```bash
pytest -v            # тесты, включая обязательные asserts из ТЗ
python run_demo.py   # таблицы: извлечение/классификация и subjects_test
```

В Docker (образ собирается один раз командами из раздела 1):

```bash
docker run --rm ds_credit pytest -v            # тесты
docker run --rm ds_credit python run_demo.py   # демо-пайплайн
```

Анализ своих файлов в контейнере — примонтируйте папку с ними и передайте пути:

```bash
docker run --rm -v "$PWD/dataset:/app/dataset" ds_credit \
  python run_demo.py dataset/03_invoice.txt
```

## 6. Примеры вызовов

### Из консоли (интерактивный Python)

Запустите интерпретатор в корне проекта:

```bash
python
```

и выполните:

```python
from src.extractor import extract
from src.classifier import classify
from src.subject_checker import check_subject, check_subject_verdict, llm_healthcheck

extract("Сумма: 1 250 000,00 руб. от 1 марта 2025 г. ИНН 7701234567")
# {'amount': 1250000.0, 'date': '2025-03-01', 'inn': '7701234567', ...}

classify("Счёт на оплату №12 от 01.03.2025")
# ('invoice', 0.79)

check_subject("минеральные удобрения")
# (True, 0.80, "предмет относится к категории 'агрохимия'")

check_subject_verdict("дрон для мониторинга полей")
# ('MANUAL_REVIEW', 0.60, "предмет относится к категории 'полевые работы'")

check_subject(None)  # пустой/отсутствующий предмет не роняет проверку
# (False, 0.0, "предмет оплаты не указан")

llm_healthcheck()    # статус: облачная LLM или локальный режим и почему
# 'ОБЛАЧНАЯ LLM: claude-sonnet-5' / 'ЛОКАЛЬНЫЙ режим: LLM_API_KEY не задан'
```

Одной командой без входа в интерпретатор:

```bash
python -c "from src.subject_checker import check_subject_verdict; print(check_subject_verdict('ремонт зернохранилища'))"
```

### Из-под контейнера

Тот же интерактивный Python внутри контейнера (с ключами из `.env`):

```bash
docker compose run --rm ds-pipeline python
```

далее команды идентичны консольным примерам выше. Разовый вызов:

```bash
docker compose run --rm ds-pipeline python -c "from src.subject_checker import llm_healthcheck; print(llm_healthcheck())"
```

### Работа с файлами напрямую

```python
from src.extractor import extract_file
from src.pipeline import analyze_file

extract_file("dataset/03_invoice.txt")   # прочитать файл и вернуть только поля

analyze_file("dataset/03_invoice.txt")   # весь пайплайн одним вызовом
# {'doc_type': 'invoice', 'doc_confidence': 0.79,
#  'fields': {'amount': 1250000.0, 'date': '2025-03-01', ...},
#  'subject_check': (True, 0.80, "предмет относится к категории 'агрохимия'")}
```

Вывод `run_demo.py` — в RESULTS.md.