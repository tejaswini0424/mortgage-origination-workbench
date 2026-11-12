FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend ./backend
COPY alembic.ini .
COPY benchmarks ./benchmarks
CMD ["sh", "-c", "if [ -f /etc/secrets/workbench.env ]; then set -a; . /etc/secrets/workbench.env; set +a; fi; exec python -m backend.app.railway"]
