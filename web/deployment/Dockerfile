FROM python:3.11-slim





ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app


RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency manifests FIRST for layer caching.
# IMPORTANT: both files are named "requirements.txt", so they MUST be copied
# under distinct names -- copying both into ./ makes one overwrite the other.
COPY requirements.txt ./requirements-root.txt
COPY web/requirements.txt ./requirements-web.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir \
    -r requirements-root.txt \
    -r requirements-web.txt
# Copy the full repository (src/, web/, templates, assets...)
COPY . .

ENV PYTHONUNBUFFERED=1
# backend.* lives under web/, src.* at repo root -> both must be importable
ENV PYTHONPATH=/app:/app/web
EXPOSE 8000

# Single worker: the job queue and payment checker are in-process background
# loops; duplicating them across workers causes double-processing.
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]