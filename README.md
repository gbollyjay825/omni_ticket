# Omni Ticket

Omni Ticket is a high-fidelity, Freshdesk/Freshworks-inspired omnichannel operations support platform for a generic support desk.

The repository contains the React PWA at the root and an independent Python backend in `services/omni-ticket-backend`. Together they cover an Omni Command center, unified work queue, native channel chats, Customer 360, AI-assisted queue automation, knowledge, rules, handoffs, analytics, workforce, market-based administration, PostgreSQL-ready persistence, and connector boundaries for Email, WhatsApp, Facebook Messenger, Instagram DM, SMS, voice, portal, and partner APIs.

## Repository Layout

- `src/`: Vite, React, and TypeScript PWA.
- `public/`: PWA manifest, app icons, and service worker shell assets.
- `docs/`: product research, UI plan, architecture, and tracker artifacts.
- `backend/`: early local demo bridge kept for compatibility with the original prototype.
- `services/omni-ticket-backend/`: production-shaped FastAPI backend with tests, migrations, worker, Docker, and deployment docs.

## Run Locally

```bash
npm install
npm run dev -- --host 127.0.0.1
```

Open `http://127.0.0.1:5173/`.

## Build And Check

```bash
npm run lint
npm run build
npm run preview
```

Backend checks:

```bash
cd services/omni-ticket-backend
python -m compileall app tests
pytest -q
ruff check app tests
mypy app tests
alembic upgrade head
python -m app.worker --once --market-id market-ng
```

The root GitHub Actions workflow runs the same production gate on push and pull request: frontend lint/build, backend compile, lint, typecheck, tests, Alembic migration sanity, and a one-cycle worker smoke test.

## Production Container

Build the PWA as a static Nginx container. The API URL is baked into the Vite build:

```bash
docker build \
  --build-arg VITE_OMNI_API_BASE_URL=https://api.your-omni-ticket-domain.example/api/v1 \
  -t omni-ticket-frontend .
```

Run locally against the Python backend:

```bash
docker run --rm -p 8080:80 \
  omni-ticket-frontend
```

## Key Files

- `src/domain.ts`: domain model.
- `src/seed.ts`: realistic omnichannel seed data.
- `src/store.ts`: IndexedDB-backed local-first state and workflow actions.
- `src/OmniApp.tsx`: PWA shell and screens.
- `Dockerfile` and `nginx.conf`: production static SPA container.
- `backend/app.py`: local Python HTTP API server with docs and an OpenAPI-style schema.
- `backend/store.py`: in-memory backend state and mutation helpers.
- `docs/`: research, UI plan, architecture, and project tracker.

## PWA Notes

The service worker registers only in production builds. Offline sends are simulated by placing reply/note/handoff events in the local outbox.

## Backend Notes

Run the lightweight prototype bridge with:

```bash
python3 -m backend.app
```

Then open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) for the route list and [http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json) for the schema.

Run the production-shaped Python backend with:

```bash
cd services/omni-ticket-backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
