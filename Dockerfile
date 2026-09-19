# ==============================================================================
# LLM Cost Guard - Production Dockerfile
# Multi-stage lightweight build with non-root execution
# ==============================================================================

FROM python:3.11-slim as builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Pre-cache tiktoken encoding files into builder
ENV TIKTOKEN_CACHE_DIR=/build/.cache/tiktoken
RUN mkdir -p /build/.cache/tiktoken && \
    python -c "import tiktoken; tiktoken.get_encoding('cl100k_base'); tiktoken.get_encoding('o200k_base')"

# ==============================================================================
# Final Runtime Stage
# ==============================================================================
FROM python:3.11-slim as runner

WORKDIR /app

# Create unprivileged system user
RUN groupadd -g 1001 appgroup && \
    useradd -u 1001 -g appgroup -s /bin/bash -m appuser

# Copy installed wheels and binaries from builder
COPY --from=builder /root/.local /home/appuser/.local
COPY --from=builder /build/.cache /app/.cache

# Copy application source and configs
COPY app/ /app/app/
COPY config/ /app/config/
COPY alembic/ /app/alembic/
COPY alembic.ini /app/alembic.ini
COPY examples/ /app/examples/

# Set ownership and permissions
RUN chown -R appuser:appgroup /app

USER appuser

ENV PATH="/home/appuser/.local/bin:$PATH"
ENV PYTHONPATH="/app"
ENV TIKTOKEN_CACHE_DIR="/app/.cache/tiktoken"
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
