Subject: Omni Ticket progress update - 2026-06-02
To: gbolahans@wakanow.com

Omni Ticket progress update as of 2026-06-02.

Milestone status
- Epics E1-E5 remain done.
- Epic E6 remains in progress, but the local Python/FastAPI vertical slice is functionally stable and fully re-verified today.
- No new product-code defect surfaced in this run; the main remaining delivery gap is repository sync between the standalone backend workspace and the newer embedded backend copy in the frontend repo.

Epics
- E1 Research and product definition: Done.
- E2 Omni data model and app shell: Done.
- E3 Omnichannel operations workflow: Done.
- E4 Admin, analytics, knowledge, workforce, and tracker: Done.
- E5 Install-ready app, verification, and delivery: Done.
- E6 Python backend vertical slice: In progress.

Current backlog and pending items
- Decide the production hosting target.
- Deploy the packaged web, API, and worker services to managed hosting with alerting and retry observability.
- Build real provider adapters for email, WhatsApp Business, Facebook Messenger, Instagram DM, SMS, and voice.
- Add production identity integration: SSO/MFA, custom permission profiles, and approval workflows.
- Add production hardening: audit export/retention, stronger tenant isolation, object storage, antivirus scanning, signed public download policy, and attachment retention policy.
- Sync the standalone backend repository at /Users/gbolahan.salami/Documents/omni-ticket-backend from the newer embedded backend under services/omni-ticket-backend.
- Commit the workspace and open the first delivery PR once the review path is agreed.

Closed issues in the latest cycle
- 2026-05-31: worker-side supervisor notifications completed and verified.
- 2026-05-31: frontend and standalone backend were re-verified together; embedded backend was aligned with standalone service-account RBAC coverage.
- 2026-06-02: reran full verification successfully; remaining gap narrowed to standalone-backend sync.

Backend dependencies still outstanding
- Managed PostgreSQL provider.
- Production identity provider with MFA/SSO and externalized RBAC policy.
- WhatsApp Business credentials.
- Meta credentials for Facebook Messenger and Instagram DM.
- Mailbox provider credentials.
- SMS/voice provider credentials.
- Attachment object storage and malware scanning provider.

Smoke-test status
- Frontend: `npm run lint` passed, `npx tsc --noEmit` passed, `npm run build` passed.
- Backend: `python -m compileall app` passed, `ruff check app tests` passed, `mypy --cache-dir /private/tmp/omni-ticket-mypy-cache app` passed, `pytest` passed with 63 tests, `alembic upgrade head` passed, and `python -m app.worker --once --market-id market-ng` passed.
- Worker smoke completed without job failures; SLA refresh, queue recompute, and analytics rollup ran successfully.

Attachment bundle
- `docs/omni-ticket-progress-2026-06-02.zip` contains `project-tracker.md`, `BACKEND_BACKLOG.md`, and `ARCHITECTURE.md`.
