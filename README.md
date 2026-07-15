# Omni Ticket

Omni Ticket is Wakanow's omnichannel support platform. It provides Freshdesk- and
Freshchat-compatible support workflows under Omni branding, with a React client and
an independent FastAPI service.

## Repository Layout

- `frontend/`: React 19, TypeScript, Vite, PWA assets, and frontend container config.
- `backend/`: FastAPI, SQLAlchemy, Alembic, PostgreSQL worker, provider adapters, and tests.
- `infra/`: isolated Pulse VM deployment, rollback, static server, and Docker Compose tooling.
- `docs/`: architecture, deployment runbooks, product research, and delivery records.

The previous in-memory Python prototype has been removed. The only backend is the
service under `backend/`.

## Run Locally

Start the API:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Start the frontend in another terminal:

```bash
cd frontend
npm ci
VITE_OMNI_API_BASE_URL=http://127.0.0.1:8000/api/v1 npm run dev -- --host 127.0.0.1
```

Open `http://127.0.0.1:5173/`. API documentation is available at
`http://127.0.0.1:8000/docs`.

## Build And Check

```bash
cd frontend
npm run lint
npm run build
```

```bash
cd backend
python -m compileall app tests
pytest -q
ruff check app tests
mypy app tests
alembic upgrade head
python -m app.worker --once --market-id market-ng
```

The root GitHub Actions workflow runs both production gates on pushes and pull
requests.

## Production Containers

Build the frontend from the repository root:

```bash
docker build \
  --build-arg VITE_OMNI_API_BASE_URL=/api/v1 \
  -t omni-ticket-frontend frontend
```

Build the backend independently:

```bash
docker build -t omni-ticket-backend backend
```

The Pulse VM deployment remains isolated from the Pulse application. See
`docs/DEPLOY_RUNBOOK.md` and `infra/scripts/deploy-pulse.sh`.
Freshworks export and incremental migration are documented in
`backend/docs/FRESHWORKS_MIGRATION.md`.

## Production Principles

- PostgreSQL is the system of record; IndexedDB is limited to drafts and local preferences.
- Production attachments use S3-compatible object storage and signed access.
- Redis provides presence, rate limits, cache, and realtime fan-out; durable events remain in PostgreSQL.
- External providers return `Not configured` until credentials are saved. They never simulate delivery.
- Runtime demo seeding is disabled in staging and production.
- Secrets belong in the protected runtime environment or write-only credential store, never Git.
