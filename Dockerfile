FROM python:3.11-slim

WORKDIR /app

# Зависимости отдельным слоем — кэшируется при изменении кода
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY tests/ ./tests/
COPY dataset/ ./dataset/
COPY run_demo.py .

# По умолчанию: прогнать тесты, затем демо-пайплайн
CMD ["sh", "-c", "pytest -q && python run_demo.py"]
