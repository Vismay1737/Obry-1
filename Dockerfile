# ─── Base Image ──────────────────────────────────────────────────────────────
FROM python:3.10-slim

# ─── Labels ───────────────────────────────────────────────────────────────────
LABEL maintainer="OpenEnv CyberSOC"
LABEL version="1.0.0"
LABEL description="Cybersecurity SOC defense simulation — OpenEnv compatible"

# ─── Environment Variables ────────────────────────────────────────────────────
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=7860 \
    MODEL_NAME="gpt-4o-mini"

# ─── Working Directory ────────────────────────────────────────────────────────
WORKDIR /app

# ─── System Dependencies ──────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ─── Python Dependencies ──────────────────────────────────────────────────────
COPY pyproject.toml .
COPY uv.lock .
COPY README.md .
COPY env/ ./env/
COPY server/ ./server/
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

# ─── Application Code ─────────────────────────────────────────────────────────
COPY inference.py .
COPY openenv.yaml .

# ─── Port ─────────────────────────────────────────────────────────────────────
EXPOSE 7860

# ─── Healthcheck ──────────────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:7860/health || exit 1

# ─── Start Server ─────────────────────────────────────────────────────────────
CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
