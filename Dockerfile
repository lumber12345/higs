# HiGHS Solver API — Docker image for Render (or any container host).
# Build:  docker build -t higs-solver-api .
# Run:    docker run -p 8000:8000 -e PORT=8000 higs-solver-api

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Run as a non-root user.
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Render injects $PORT; fall back to 8000 locally.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request, os; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8000') + '/health')" || exit 1
