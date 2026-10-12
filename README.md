<!-- Premium README for Sparsa Homeoclinic -->

# Sparsa Homeoclinic

[![Status](https://img.shields.io/badge/status-active-brightgreen.svg)](#)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](#)
[![React](https://img.shields.io/badge/react-19.0-blue.svg)](#)
[![MongoDB](https://img.shields.io/badge/mongodb-%E2%89%A5--4.0-green.svg)](#)

A role-driven clinic operations platform for patient intake, case lifecycle management, prescriptions, pharmacy coordination, billing and administration — optimized for small clinics that want an auditable, lightweight on‑prem or cloud deployment.

This repository contains a FastAPI backend (Python) and a React frontend (Create React App + CRACO + Tailwind) wired together for a smooth developer experience and fast iteration.

---

## Highlights

- Clean role separation: Reception, Doctor, Pharmacy, PRO (billing), Admin
- Full case lifecycle: intake → consult → dispense → billing → receipts
- Extensible AI workflows and messaging integrations (Twilio / WhatsApp)
- Local-friendly dev experience: seed data, setup scripts, and Docker-ready patterns

---

## Demo / Screenshots

(Place production-ready screenshots under `docs/screenshots/`. I recommend committing the following files:)

- `docs/screenshots/hero-dashboard.png` — clinic dashboard (1200×700)
- `docs/screenshots/login.png` — login page (800×500)
- `docs/screenshots/case-detail.png` — case detail / prescription (1200×700)

Example markdown (already present in README):

```md
![Login screen](docs/screenshots/login.png)
![Reception dashboard](docs/screenshots/reception-dashboard.png)
```

I can add a small Playwright script to capture these images from a running instance and commit them for you.

---

## Quick links

- Backend: `backend/` (FastAPI)
- Frontend: `frontend/` (React + Tailwind)
- Setup scripts: `setup_project.sh`, `setup_sparsa_linux.sh`
- Seed data: `backend/seed.py`
- API entrypoint: `backend/server.py`

---

## Getting started (short)

Prerequisites
- Python 3.11+
- Node.js 18+ and Yarn 1.22.x (or npm)
- MongoDB (local or Docker)

Bootstrap (recommended):

```bash
# recommended quick bootstrap (Linux/macOS)
./setup_sparsa_linux.sh
```

Manual (backend + frontend):

```bash
# Backend
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# ensure backend/.env (MONGO_URL, DB_NAME, JWT_SECRET)
uvicorn server:app --reload --host 0.0.0.0 --port 8000

# Frontend (separate shell)
cd frontend
yarn install
yarn start
```

Open: http://localhost:3000 — the app redirects to `/login` for unauthenticated users.

Default dev users (auto-seeded) — change before production:

- admin1 / Password@123 (ADMIN)
- jyothi / Password@123 (OWNER_DOCTOR)
- hemanth / Password@123 (DOCTOR)
- reception1 / Password@123 (RECEPTION)
- pharmacy1 / Password@123 (PHARMACY)
- pro1 / Password@123 (PRO)

---

## Architecture (concise)

```mermaid
flowchart LR
  Browser[Browser / Mobile UI]
  Browser -->|HTTPS| Frontend[React (CRA) Frontend]
  Frontend -->|REST / Axios| Backend[FastAPI Backend (/api)]
  Backend -->|async| Mongo[(MongoDB)]
  Backend -->|Object Storage| Storage[(Emergent / S3-like)]
  Backend -->|External APIs| Messaging[(Twilio / WhatsApp / Payment)]
  Backend -->|Background tasks| Scheduler[(Reminder scheduler)]
  Backend -.->|Auth (JWT cookies)| Browser
  note right of Backend: Roles: RECEPTION, DOCTOR, PHARMACY, PRO, ADMIN
```

Key runtime pieces:
- `backend/server.py` — app startup, middleware, router registration
- `backend/core.py` — DB connection, JWT handling, auth helpers, audit
- `backend/routers/*` — domain API routes (patients, cases, packages, payments, reminders, admin, ai)
- `frontend/src/App.js` — route map and role guards
- `frontend/src/contexts/AuthContext.jsx` — login / refresh / logout
- `frontend/src/lib/api.js` — axios client and formatting helpers

---

## Deployment recommendations

- Containerize the backend and frontend for production. Example `docker-compose.yml` should include MongoDB (or use managed DB), backend, and optionally a static frontend service.
- Use a secret manager for `JWT_SECRET`, messaging keys, and storage credentials.
- Serve frontend static files from a CDN or object storage (S3) behind HTTPS.
- Use a production ASGI server (Gunicorn + Uvicorn workers) behind NGINX.

Example production command inside a container or virtualenv:

```bash
gunicorn -k uvicorn.workers.UvicornWorker backend.server:app -b 0.0.0.0:8000 --workers 4
```

---

## Security notes

- Do NOT use seeded passwords in production. Rotate credentials and use role-appropriate accounts.
- `JWT_SECRET` must be a strong random value; rotate with care (implement revocation if needed).
- Audit logs are written via `backend/core.py` `audit()` — review for required retention and access controls.

---

## Testing & CI

- Backend tests: `cd backend && pytest`
- Frontend tests: `cd frontend && yarn test`

I can add a GitHub Actions CI workflow that runs `pytest`, `black --check`, and `yarn test` on each PR; let me know and I will open a PR for the workflow.

---

## Contributing

1. Fork the repo and open a branch for your change.
2. Run tests and linters locally before opening a PR.
3. Keep commits focused and add a helpful PR description.

Formatting (backend): `black . && isort .`

---

## Roadmap & ideas

- Official Docker Compose example for local full-stack dev
- Playwright-based visual regression & automated screenshot capture
- GitHub Actions CI + automated code scanning
- Optional SSO / SAML provider support for clinics with centralized auth

---

## License

No LICENSE file is present. Add a `LICENSE` (MIT / Apache-2.0 / GPL) if you want to publish or open-source this repository.

---

## Need help?

If you want, I can:
- add screenshots automatically (Playwright) and commit them to `docs/screenshots/`
- create a `docker-compose.yml` and a `Makefile` for dev
- add a GitHub Actions CI workflow that runs tests & linters

Happy to continue — tell me which of the above you want next and I will implement it.