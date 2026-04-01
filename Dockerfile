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
    API_BASE_URL="https://api.openai.com/v1" \
    MODEL_NAME="gpt-4o-mini" \
    HF_TOKEN=""

# ─── Working Directory ────────────────────────────────────────────────────────
WORKDIR /app

# ─── System Dependencies ──────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ─── Python Dependencies ──────────────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir \
    pydantic>=2.0.0 \
    openai>=1.0.0 \
    fastapi>=0.104.0 \
    "uvicorn[standard]>=0.24.0" \
    python-multipart>=0.0.6 \
    httpx>=0.25.0

# ─── Application Code ─────────────────────────────────────────────────────────
COPY env/ ./env/
COPY app.py .
COPY inference.py .
COPY openenv.yaml .
COPY README.md .

# ─── Port ─────────────────────────────────────────────────────────────────────
EXPOSE 7860

# ─── Healthcheck ──────────────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:7860/health || exit 1

# ─── Start Server ─────────────────────────────────────────────────────────────
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
