FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY data/runbooks/ ./data/runbooks/

# Pre-build SQLite DB & Qdrant Hybrid Index into image layers
RUN python -m app.ingestion

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
