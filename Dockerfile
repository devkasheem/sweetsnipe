FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app




# (removed legacy single-file requirements install)



RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Dependency manifests under distinct names (both are named requirements.txt)
COPY requirements.txt ./requirements-root.txt
COPY web/requirements.txt ./requirements-web.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir \
    -r requirements-root.txt \
    -r requirements-web.txt

# Copy the full repository (src/, web/, templates, assets...)
COPY . .







# backend.* lives under web/, src.* at repo root
ENV PYTHONPATH=/app:/app/web
EXPOSE 8000

CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]