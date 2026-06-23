# Phase 11 image -- slim Python base, layer-cached deps, uvicorn-served FastAPI.
# Secrets (GEMINI_API_KEYS / GROQ_API_KEYS) are NEVER baked in; they are injected
# at runtime by the host (Render / Railway / Cloud Run / `docker run -e ...`).
FROM python:3.11-slim

# Faster, quieter, no .pyc clutter; unbuffered stdout for live deploy logs.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    LLM_CACHE_DIR=/data/llm_cache \
    PORT=8000

# OS dependencies kept minimal -- only what python wheels need at runtime.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements.txt FIRST so the deps layer is cached across code edits.
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# Then the project code. (.dockerignore excludes secrets, venv, caches.)
COPY . .

# Writable directory for SQLite + the LLM cache when the deploy host gives us a
# read-only image. Mount a volume here in production to persist the cache.
RUN mkdir -p /data/llm_cache

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -fsS http://localhost:${PORT}/healthz || exit 1

# Single worker is fine for the demo: the pipeline holds a sqlite connection +
# the in-memory circuit-breaker set per process. Scale by running more replicas.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
