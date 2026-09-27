# egy-finance-radar backend: FastAPI served by uvicorn.
# Stays internal to the Docker network; the frontend proxies /api/* to it.
FROM python:3.13-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# deps first for layer caching
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# app code + seed data (snapshot.json / orders.json). data/ is mounted as a
# volume in compose so writes (refresh, new orders) persist across restarts.
COPY app ./app
COPY data ./data
COPY migrations ./migrations

EXPOSE 8000

# Apply pending DB migrations, seed (idempotent), then serve. Running these in
# the entrypoint (not a FastAPI startup event) keeps request handling unaffected;
# compose's depends_on: db service_healthy guarantees Postgres is up first. The
# seed is idempotent, so a fresh volume comes up populated and restarts are no-ops.
# config paths (SNAPSHOT_PATH="data/snapshot.json") are relative to WORKDIR.
CMD ["sh", "-c", "python -m app.db.migrate && python -m app.db.seed && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
