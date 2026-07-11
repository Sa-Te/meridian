FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app
COPY alembic.ini ./
COPY alembic ./alembic

# Installed first, from the CPU-only wheel index: plain `pip install .`
# would otherwise pull in torch's default CUDA build as a transitive
# dependency of sentence-transformers (ADR-0004's local embedding model),
# adding several GB of GPU libraries this CPU-only container never uses.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir .

EXPOSE 8000

# Migrations run against the compose postgres service before the app starts,
# so a fresh `docker compose up` always has a migrated schema (see ADR-0005).
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
