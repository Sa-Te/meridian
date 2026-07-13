FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app
COPY alembic.ini ./
COPY alembic ./alembic

# --extra-index-url (not a one-off pre-install) on the real install too:
# plain `pip install .` would otherwise resolve torch/torchaudio's default
# CUDA builds as transitive dependencies of sentence-transformers
# (ADR-0004) and pyannote.audio (ADR-0012), adding several GB of GPU
# libraries this CPU-only container never uses. Pointing the whole
# resolution at the CPU wheel index keeps every torch-family package on
# CPU builds, not just whichever one happens to be installed first.
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu .

EXPOSE 8000

# Migrations run against the compose postgres service before the app starts,
# so a fresh `docker compose up` always has a migrated schema (see ADR-0005).
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
