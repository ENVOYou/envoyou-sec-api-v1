# ====== Base image for both stages ======
FROM python:3.11-slim as base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# ====== Builder stage ======
FROM base as builder

WORKDIR /app
COPY requirements.txt .

# Gunakan cache untuk dependency
RUN pip install --upgrade pip \
 && pip install --prefix=/install -r requirements.txt

# ====== Production stage ======
FROM base as production

ENV PATH="/opt/venv/bin:$PATH"
RUN python -m venv /opt/venv

# Copy hasil install dari builder ke virtualenv
COPY --from=builder /install /opt/venv

WORKDIR /app
COPY . .

# Non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser \
 && mkdir -p storage/reports \
 && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
