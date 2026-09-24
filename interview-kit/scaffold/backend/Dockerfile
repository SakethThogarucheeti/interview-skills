FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir uv && uv pip install --system --no-cache -r requirements.txt
COPY app ./app
# Build metadata: `docker build --build-arg GIT_SHA=$(git rev-parse HEAD) ...`
# (make image / make deploy / CI all pass it). Surfaces at /version.
ARG GIT_SHA=unknown
ARG BUILD_TIME=""
ENV GIT_SHA=$GIT_SHA BUILD_TIME=$BUILD_TIME
LABEL org.opencontainers.image.revision=$GIT_SHA
RUN useradd --create-home appuser
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=2)"
# All config via env (app/config.py). WEB_CONCURRENCY sets uvicorn's worker count.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
