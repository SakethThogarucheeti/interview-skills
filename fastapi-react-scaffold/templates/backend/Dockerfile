FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
# DATABASE_URL / REDIS_URL default to localhost in app/deps.py -- override with
# --env or docker-compose networking (e.g. postgresql://postgres:postgres@postgres:5432/app)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
