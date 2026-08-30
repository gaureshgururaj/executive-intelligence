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
