# Sparsa Homeoclinic

Sparsa Homeoclinic is a role-based clinic and hospital operations application for patient intake, case management, doctor workflows, pharmacy coordination, billing, and administration. The project is split into a Python FastAPI backend backed by MongoDB and a React frontend with role-based dashboards.

## What this project includes

- Patient registration and case creation flows
- Doctor-facing case timelines, notes, prescriptions, and follow-ups
- Pharmacy workflow tracking and reminder management
- PRO / billing screens, financial search, and receipt generation
- Admin screens for users, audits, exports, messaging, and AI settings
- JWT-based authentication with role-aware access control
- MongoDB-backed persistence and audit logging

## Tech stack

### Backend
- Python 3.11+
- FastAPI
- Motor / PyMongo
- JWT authentication with bcrypt password hashing
- Pydantic models for validation

### Frontend
- React 19
- Create React App with CRACO
- Tailwind CSS
- React Router
- Radix UI and custom component patterns

### Data and integrations
- MongoDB
- Twilio / WhatsApp messaging support
- Emergent object storage / attachments support

## Repository structure

```text
.
├── backend/                    # FastAPI backend application
│   ├── routers/                # Auth, patients, cases, pharmacy, billing, admin, AI, exports
│   ├── __pycache__/            # Generated Python cache files
│   ├── ai_settings.py          # AI settings helpers
│   ├── clinical_context.py     # Clinical context shaping helpers
│   ├── core.py                 # Shared DB, JWT, roles, auth, audit helpers
│   ├── financial_reporting.py  # Revenue / financial reporting helpers
│   ├── fir_parsing.py          # FIR parsing utilities
│   ├── messaging.py            # Messaging and provider integration logic
│   ├── models.py               # Pydantic request / response models
│   ├── package_models.py       # Package and billing models
│   ├── package_service.py      # Package logic and billing calculations
│   ├── patient_access.py       # Access / finance visibility logic
│   ├── prompts.py              # Prompt templates and AI instructions
│   ├── requirements.txt        # Backend Python dependencies
│   ├── seed.py                 # Seed users and initial clinic data
│   ├── server.py               # FastAPI app startup and router registration
│   ├── storage.py              # Storage integration helpers
│   └── tests/                  # Backend tests
├── frontend/                   # React frontend application
│   ├── public/                 # Static frontend assets
│   ├── src/                    # App source code
│   ├── README.md               # CRA default starter README (not the project README)
│   ├── package.json            # Frontend dependencies and scripts
│   ├── craco.config.js         # CRACO config
│   ├── tailwind.config.js      # Tailwind config
│   └── yarn.lock               # Frontend lockfile
├── memory/                     # Product docs, plans, and test credentials
│   ├── PRD.md
│   ├── CHANGE_REQUEST_PLAN.md
│   └── test_credentials.md
├── scripts/                    # Operational scripts
│   ├── README.md               # Backup / restore guide
│   ├── backup.sh
│   ├── restore.sh
│   └── ...
├── .gitignore
├── .gitconfig
├── README.md                   # This file
├── design_guidelines.json       # Design / product guidance document
├── setup_project.sh            # Full bootstrap script for Linux/macOS-like environments
├── setup_sparsa_linux.sh       # Alternative setup script for Linux
├── setup-guide-expert.sh        # Guided setup script
├── test_result.md              # Test summary report
├── tests/                      # Project-level tests / validation
├── yarn.lock                   # Root lockfile
└── .emergent/                  # Emergent-generated workspace metadata
```

## How the app fits together

The backend exposes a FastAPI API under `/api` and mounts domain-specific routers such as auth, patients, cases, pharmacy, payments, reminders, exports, admin, and AI. The frontend is role-aware and routes users to different dashboards based on their role via `frontend/src/App.js`.

A typical flow is:

1. A user signs in from the React UI.
2. The browser calls the backend through the API client.
3. The backend validates the JWT and loads the user from MongoDB.
4. MongoDB stores patients, cases, billing records, reminders, and audit logs.
5. Role-specific pages render different workflows for reception, doctors, pharmacy, billing, and admin.

## Default roles and seeded users

The project seeds a small set of default users in `backend/seed.py`.

- `admin1` / `Password@123`
- `jyothi` / `Password@123`
- `hemanth` / `Password@123`
- `reception1` / `Password@123`
- `pharmacy1` / `Password@123`
- `pro1` / `Password@123`

These are intentionally simple local-development credentials and should be changed before production use.

## Prerequisites

- MongoDB running locally or in Docker
- Python 3.11+
- Node.js 18+ and Yarn 1.22.x
- Optional: messaging and storage credentials if you plan to enable those integrations

## Quick local setup

### Option 1: use the provided Linux setup script

```bash
./setup_sparsa_linux.sh
```

This script installs required system packages, creates local `.env` files, creates a Python virtual environment, installs backend dependencies, and installs frontend dependencies.

### Option 2: manual setup

#### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

#### Frontend

```bash
cd frontend
yarn install
```

## Environment variables

The backend expects these variables at runtime.

```bash
MONGO_URL="mongodb://localhost:27017"
DB_NAME="sparsa_homeoclinic"
JWT_SECRET="replace-with-a-strong-random-secret"
```

Optional but commonly used in production or advanced setups:

```bash
CORS_ALLOWED_ORIGINS="http://localhost:3000"
```

The setup scripts create local `.env` files under `backend/` and `frontend/`. Review them before running the app, especially if you need to change the database name, port, or CORS origin.

## Run the application

Start MongoDB if it is not already running.

### Start the backend

```bash
cd backend
source .venv/bin/activate
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

### Start the frontend

```bash
cd frontend
yarn start
```

Then open:

```text
http://localhost:3000
```

The app redirects unauthenticated users to `/login`.

## Key backend entry points

- `backend/server.py` — FastAPI app start-up, CORS config, middleware, router registration
- `backend/core.py` — DB connection, JWT generation, authentication helpers, role constants
- `backend/models.py` — Pydantic models for patients, cases, billing, reminders, AI settings
- `backend/routers/` — domain endpoints for patients, cases, pharmacy, billing, AI, admin, and exports
- `backend/seed.py` — initial users and role setup

## Key frontend entry points

- `frontend/src/App.js` — main route configuration and role-based protection
- `frontend/src/contexts/AuthContext.jsx` — authentication state and login/logout logic
- `frontend/src/lib/api.js` — API client and formatting helpers
- `frontend/src/pages/` — role-based dashboard and workflow pages

## Operational notes

- The backend starts up default indexing and seeded data automatically.
- The app includes a reminder scheduler and messaging refresh tasks during startup.
- The project includes backup/restore scripts in `scripts/` and documentation in `scripts/README.md`.

## Testing and validation

The repository includes backend test files and test reports.

To run backend tests:

```bash
cd backend
pytest
```

To build the frontend:

```bash
cd frontend
yarn build
```

## Production guidance

This repository is structured for development and internal deployment, not as a turnkey SaaS deployment. Before production use:

- rotate the default seeded passwords
- use a real `JWT_SECRET`
- configure secure MongoDB access and backups
- configure CORS explicitly
- enable real messaging/storage credentials if those features are needed
- review admin and role permissions before exposing the app publicly

## License

No explicit license file is present in this repository, so the repository should be treated as unlicensed unless a specific project policy states otherwise.

## Summary

Sparsa Homeoclinic is a full-stack clinic management system focused on operational workflows rather than a generic starter app. It is designed around real medical-clinic role boundaries: reception, doctors, pharmacy, PRO/billing, and admin.
