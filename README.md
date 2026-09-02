# AI Executive Intelligence Platform

Phase 1 skeleton for the first vertical slice:

RSS → Trend Agent → Quality Gate → Persistence → API → Dashboard

Copy `.env.example` to `.env` at the repository root before starting Postgres or the API. Do not commit `.env`.

Requires Python 3.12+, Node.js 20.9+, and Docker.

## Install backend dependencies

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Install frontend dependencies

```bash
cd frontend
npm install
```

## Start PostgreSQL

From the repository root:

```bash
docker compose up -d
```

## Run FastAPI

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API is at http://localhost:8000. Health check: http://localhost:8000/health

## Run Next.js

```bash
cd frontend
npm run dev
```

The app is at http://localhost:3000. It calls `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`) for the health indicator. Override by creating `frontend/.env.local` if needed.

## Scheduled enabled-source ingestion

The scheduler decides **when** ingestion runs. The application decides **what**
to ingest. `EnabledSourceIngestionRunner` still owns one transaction per source.

Do not overlap scheduled executions yet. There is no in-process lock.

Prerequisite: at least one enabled source in Postgres. Seed the default OpenAI
News feed once:

```bash
cd backend
source .venv/bin/activate
PYTHONPATH=. python scripts/seed_sources.py
```

Manual run (same command a scheduler should invoke):

```bash
cd backend
source .venv/bin/activate
PYTHONPATH=. python scripts/run_enabled_sources.py
```

`INGEST_MAX_ARTICLES` (default `3`) is the RSS candidate slice **per source**
before skip-before-LLM and analysis. Unchanged persisted articles are skipped
before the LLM, so repeat runs are cheap.

The interval lives outside the app. Example hourly cron (adjust the repo and
venv paths; keep secrets in `.env` or the host's secret store, not in crontab
text):

```cron
0 * * * * cd /path/to/executive-intelligence/backend && PYTHONPATH=. /path/to/executive-intelligence/backend/.venv/bin/python scripts/run_enabled_sources.py >> /tmp/ingest-enabled-sources.log 2>&1
```

A hosted scheduler can invoke the same command. Exit codes:

- `0` — the run finished, including zero enabled sources and item-level
  failures that were still committed for that source
- `1` — at least one source-level failure (`SourceRunResult.error`)
- non-zero — setup, discovery, config, or database initialization raised

## Run backend tests

```bash
cd backend
source .venv/bin/activate
pytest
```

## Run linting

Backend:

```bash
cd backend
source .venv/bin/activate
ruff check app tests
black --check app tests
```

Frontend:

```bash
cd frontend
npx tsc --noEmit
```
