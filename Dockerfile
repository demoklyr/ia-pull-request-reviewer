# --- Build stage: install dependencies into a virtual environment ---
FROM python:3.12-slim AS builder

WORKDIR /app

# System deps needed to build some Python packages (kept minimal on purpose).
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src ./src

# Install only production dependencies (no [dev] extras: no pytest, no ruff).
RUN pip install --no-cache-dir .

# --- Runtime stage: slim image, only what's needed to run the app ---
FROM python:3.12-slim

WORKDIR /app

# Run as a non-root user (basic container security hygiene).
RUN useradd --create-home --shell /bin/bash appuser

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "ai_code_reviewer.main:app", "--host", "0.0.0.0", "--port", "8000"]
