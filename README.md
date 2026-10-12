# Sparsa Homeoclinic

![Sparsa Homeoclinic](frontend/public/sparsa-logo.png)

A role-based clinic operations platform for patient intake, case management, prescriptions, pharmacy coordination, billing and administration. Built for clinics that need lightweight, auditable workflows and a clear separation of responsibilities for Reception, Doctors, Pharmacy, PRO (billing), and Admin.

Key goals: fast setup for on-prem / small-cloud clinics, clear role-driven UI, and extensible AI + messaging integrations.

---

## Features

- Role-based dashboards (Reception, Doctor, Pharmacy, PRO, Admin)
- Patient registration, case lifecycle, and clinical notes
- Prescription authoring and pharmacy dispensing workflow
- Billing, receipts, and package-based billing computations
- Reminders and scheduled jobs (reminder scheduler)
- Messaging integrations (Twilio / WhatsApp) and object attachments
- Admin utilities: user & audit management, exports, AI settings
- Local dev-friendly: seeded demo users, setup scripts, and Docker-friendly patterns

---

## Demo / Screenshots

> Add your app screenshots to `docs/screenshots/` and update paths below. Example sizes: 1200×700px for hero / dashboard images, 800×600px for detail pages.

![Login screen](docs/screenshots/login.png)
![Reception dashboard](docs/screenshots/reception-dashboard.png)

If you’d like, I can add a small script to capture screenshots automatically from a running instance (puppeteer / playwright) and commit them to `docs/screenshots/`.

---

## Quick start (development)

Prerequisites
- Node 18+, Yarn 1.22.x (or npm)
- Python 3.11+
- MongoDB (local or Docker)

One-line bootstrap (Linux/macOS):

```bash
# runs install, creates .env defaults, installs deps
./setup_sparsa_linux.sh
```

Manual (step-by-step)

```bash
# Backend
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# ensure backend/.env contains MONGO_URL, DB_NAME, JWT_SECRET
python seed.py  # optional, server will seed at startup
uvicorn server:app --reload --host 0.0.0.0 --port 8000

# Frontend (in a separate terminal)
cd frontend
yarn install
yarn start
```

Open: http://localhost:3000

Default seeded users (development only)
- admin1 / Password@123 (ADMIN)
- jyothi / Password@123 (OWNER_DOCTOR)
- hemanth / Password@123 (DOCTOR)
- reception1 / Password@123 (RECEPTION)
- pharmacy1 / Password@123 (PHARMACY)
- pro1 / Password@123 (PRO)

---

## Architecture

High-level runtime picture:

```mermaid
flowchart LR
  Browser[Browser / Mobile UI]
  Browser -->|HTTPS| Frontend[React (CRA) Frontend]
  Frontend -->|REST / Axios| Backend[FastAPI Backend (/api)]
  Backend -->|async| Mongo[(MongoDB)]
  Backend -->|Object Storage| Storage[(Emergent / S3-like)]
  Backend -->|External APIs| Messaging[(Twilio / WhatsApp / Payment)]
  Backend -->|Background tasks| Scheduler[(Reminder scheduler / cron-like tasks)]
  Backend -.->|Auth (JWT cookies)| Browser
  note right of Backend: Roles: RECEPTION, DOCTOR, PHARMACY, PRO, ADMIN
```

Files of interest:
- Backend entrypoint: `backend/server.py`
- Shared infra / auth: `backend/core.py`
- API models: `backend/models.py`
- Routers: `backend/routers/*` (patients, cases, payments, reminders, admin, ai, etc.)
- Frontend router & role config: `frontend/src/App.js`
- Frontend auth & API client: `frontend/src/contexts/AuthContext.jsx` and `frontend/src/lib/api.js`

---

## Deployment notes

- Use a process manager (systemd) or container orchestration (Docker Compose / Kubernetes).
- For production, use environment-specific secrets (Vault / Secrets Manager) for `JWT_SECRET` and messaging/storage keys.
- Use a managed MongoDB or hardened MongoDB with backups and TLS.
- Run the backend behind a reverse proxy (NGINX) with TLS terminating.
- Recommended production command (example):

```bash
# inside container or virtualenv
gunicorn -k uvicorn.workers.UvicornWorker backend.server:app -b 0.0.0.0:8000 --workers 4
```

---

## Security & privacy

- Rotate `JWT_SECRET` carefully; token revocation strategies required for forced logout.
- Do not commit credentials to the repo. The setup scripts create `.env` files for local dev.
- Audit logs are stored in `db.audit_logs` and are created for login/logout and major actions — review the `backend/core.py` `audit()` call-sites for coverage.

---

## Contributing

- Run backend tests: `cd backend && pytest`
- Format backend code: `black . && isort .`
- Keep frontend styles consistent with Tailwind conventions and run `yarn test` locally for UI checks.

If you want me to:
- add a GitHub Actions workflow to run tests and linters on PRs, or
- add example `docker-compose.yml` for local dev (mongo + backend + frontend static),
I can prepare them and open a PR.

---

## Screenshots / assets guidance

To include screenshots in this README:
1. Create `docs/screenshots/` in the repo and add PNG/JPEG files.
2. Prefer 1200×700 px for page-level screenshots and 800×600 for smaller panels.
3. Commit images and then the markdown above will render them.

---

## License & acknowledgements

No license file is present. Add a `LICENSE` file (MIT, Apache-2.0, etc.) if you plan to publish or share this repository publicly.

Acknowledgements: built with FastAPI, React (CRA), Tailwind, Radix UI and emergent integrations.
