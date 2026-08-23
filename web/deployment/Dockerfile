FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# App root is /app/web so main.py's RELATIVE paths
# ("frontend/assets", "frontend/templates") resolve correctly.
WORKDIR /app/web

# Build context is the REPO ROOT on Railway -> use web/ prefixes
COPY web/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY web/backend ./backend
COPY web/frontend ./frontend

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/web
EXPOSE 8000

CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2"]
