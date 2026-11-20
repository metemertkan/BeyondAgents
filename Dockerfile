FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MEM0_TELEMETRY=False

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install uv && uv pip install --system -r pyproject.toml

COPY penny ./penny
COPY portal ./portal
COPY recall ./recall
COPY month_end ./month_end
COPY gate ./gate
COPY scripts ./scripts
COPY web ./web

EXPOSE 8092

HEALTHCHECK --interval=10s --timeout=5s --retries=6 \
    CMD curl -fsSL http://localhost:8092/api/health || exit 1

CMD ["python", "-m", "web"]
