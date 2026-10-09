# Sparsa Homeoclinic — PRD

## Original Problem Statement
Internal clinic management for **Sparsa Homeoclinic** (homeopathy clinic, 5 PCs on LAN).
Workflow: **Reception → Doctor → Pharmacy → PRO/Billing**.
Roles: ADMIN, OWNER_DOCTOR (Jyothi — all cases), DOCTOR (Hemanth — own only), RECEPTION, PHARMACY, PRO.

## Stack
React + FastAPI + MongoDB (original spec was Laravel + MySQL).

## What's Implemented

### v1 (33 tests pass)
JWT auth · roles · patient UIDs · case workflow · clinical notes · versioned prescriptions · pharmacy dispense · billing · bilingual EN/Telugu receipt · on-screen reminders · per-case AI assist · admin (users/audit/stats).

### v2 (53 tests pass)
File attachments (Emergent Object Storage, 10MB jpg/png/pdf) · patient timeline · 5 CSV exports · Twilio + WhatsApp Cloud API (graceful PROVIDER_NOT_CONFIGURED fallback + background scheduler) · mongodump backup/restore scripts.

### v3 (71 tests pass)
Refactored 1154-line server.py into modular routers (core.py + models.py + 10 routers + seed.py + 64-line server.py) · AI Visit Recap (5-line briefing from full patient history) · full step-by-step cron/Task Scheduler walkthrough in scripts/README.md.

### v4 (97 tests pass — current build, 2026-06-20)
- **Past Visit migration** — `POST /api/patients/{id}/past-visit` creates backdated CLOSED cases. UI form on patient timeline.
- **Google Docs paste import** — `POST /api/ai/parse-visit-notes` uses Claude Sonnet 4.5 to extract structured visit data from free-form notes; pre-fills the past-visit form.
- **Billing closure UX** — green success card after PAID, with Print Receipt / Patient Timeline / Back to Queue actions; payment form goes read-only.
- **Branding cleanup** — browser title "Sparsa Homeoclinic", removed demo-creds block from login.
- **Admin user CRUD** — `DELETE /api/admin/users/{id}` (self-delete blocked, OWNER_DOCTOR soft-deactivated).
- **Patient edit/delete** — reception/owner can edit; reception can delete cases-free patients; admin can hard-delete with cascade (clinical_notes, prescriptions, pharmacy_dispense, payments, reminders, attachments soft-deleted).
- **Admin Analytics dashboard** — 30-day cases+revenue chart, logins-by-role, top complaints, average turnaround time.
- **Pharmacy Dashboard** — KPIs (pending dispense, today's dispensed count, medicine revenue today, active reminders) + reminders side panel.
- **PRO Dashboard** — today/total revenue, outstanding, pending bills, 7-day revenue trend chart, mode breakdown, follow-ups due today.
- **Pharmacy Reminders module** — doctor's followups with `notify_pharmacy=true` appear on pharmacy dashboard + dedicated `/pharmacy/reminders` page with PENDING/COMPLETED/SENT tabs and Mark Complete action.
- **Doctor Reminders enhanced** — tabs (PENDING/SENT/COMPLETED/FAILED), search, mark complete, snooze (datetime picker), send now, delete.
- **IST everywhere** — all reminder/timeline/dashboard times shown in Asia/Kolkata. New `fmtIST` + `istLocalToUtcISO` helpers; backend day-bounds calculated in IST.
- **PRO privacy fix** — clinician-written reminder notes hidden from PRO followups feed.
- ✅ 98/98 backend tests pass with iteration_5 fixes verified.

### v5 (121 tests pass — 2026-06-20)
- **Admin Messaging Settings page** (`/admin/messaging`) — DB-backed runtime Twilio + WhatsApp credentials, no restart required. Masked display, per-field Clear via `__CLEAR__` sentinel, 30s cache refresh in scheduler. Endpoints: `GET/POST /api/admin/messaging-settings`. Provider precedence: DB → env.
- **Admin Analytics → MongoDB aggregations** — replaced 30 sequential `count_documents`+`aggregate` calls with two bucketed aggregations using `$dateAdd` + `$dateToString` (IST). Top complaints now `$split`/`$unwind`/`$group` server-side. Turnaround now a single `$dateFromString` aggregation. <0.5s on current dataset.
- **File-upload size hardening** — `/api/cases/{id}/attachments` streams in 64 KB chunks, aborts at >10 MB without buffering full payload.
- ✅ iteration_6: 23/23 backend + 8/8 frontend tests pass.

### v6 (logo branding — 2026-06-20)
- **Sparsa Homeo Care logo** wired into the sidebar, login hero card + login header, and the printable receipt. Saved at `/app/frontend/public/logo.png`. Also wired as favicon + apple-touch-icon.
- Reusable `<Logo />` component (`/app/frontend/src/components/Logo.jsx`) as single source of truth.
- Brand text harmonised to "Sparsa Homeo Care" in receipts, browser title, page meta, and WhatsApp/SMS reminder body.

### v7 (Phase A — FIR + date-only follow-ups — iteration_7 ✅ 15/15)
- **Patient model expanded**: marital_status, height_cm, weight_kg, **auto-BMI**, consulting_doctor_id, sources (multi-select), referral_name, chief_complaint, visit_type.
- New endpoint `POST /api/patients/fir` creates patient + first case atomically.
- Reception **New Patient** page rewritten as comprehensive FIR form (sectioned UI, conditional referral-name, BMI live-calc, walk-in/appointment radio).
- **Follow-up changed to date-only**: `FollowupIn.next_followup_date: date`; anchored to 09:00 IST UTC for the scheduler. UI uses a `<input type="date">`.
- Test data wiped per user's request; counters reset.

### v8 (Phases B + C + D — iteration_8 ✅ 34/34 pytest)
- **Phase B — Patient search & quick contact**:
  - `GET /api/patients?search=…` now RBAC-scoped: non-owner DOCTOR only sees patients with cases assigned to them (uses `doctor_id`, not `user.id` — fixed).
  - New `/doctor/patients` page (search + tap-to-call/SMS/WhatsApp quick-actions). Reusable `<QuickContact />` exported.
  - Pharmacy + Doctor reminder cards and PRO follow-up widget now show phone number + QuickContact buttons.
- **Phase C — PRO power features**:
  - `GET /api/pro/financial-search?q=…` — global billing search; per-patient summary + per-visit table.
  - `POST /api/cases/{id}/attachments` now accepts `kind=PAYMENT_PROOF`. PRO can upload payment proofs (UPI/PhonePe/GPay screenshots) before closing a bill. `?kind=PAYMENT_PROOF` filter on list endpoint.
  - `GET /api/pro/analytics` — comprehensive business analytics (patient demographics, source acquisition, visits by doctor + type, 30-day revenue trend, mode breakdown, consult vs medicine split, operational turnaround, outstanding).
  - New `/pro/financial-search` and `/pro/analytics` pages with bar charts.
- **Phase D — Admin & AI**:
  - Inline **Reset password** modal on Admin → Users (per-user). Backend enforces `min_length=8` on `UserCreateIn`/`UserUpdateIn`.
  - AI Visit Recap now supports `?mode=detailed` (owner doctor / admin only) → Markdown response with 6 sections: Patient Profile, Clinical Assessment, Possible Diagnostic Directions, **Mother Tincture Suggestions**, Lifestyle Recommendations, Treatment Considerations + a "decision-support only" disclaimer. `mode=brief` (default) keeps the 5-line briefing.
  - Tiny inline Markdown renderer in the timeline UI (avoids new dependency).

### v9 (Workflow re-order + Reminder fixes + AI Master Prompt + IBM Plex font — iteration_9 ✅ 17/17 backend + 8/8 frontend)
- **Workflow re-ordered**: Reception → Doctor → **PRO → Pharmacy** → Completed (was D→Pharma→PRO).
  - New status `AWAITING_PRO_REVIEW` between consultation and billing.
  - Doctor's primary action: "Complete consultation · Send to PRO". Secondary: "Send direct to Pharmacy" — requires a bypass reason (audit-logged + `pharmacy_bypassed_pro=true` on case).
  - PRO recording `PAID + medicines_taken=true` auto-forwards case to `SENT_TO_PHARMACY`. Consultation-only (`medicines_taken=false`) → `CLOSED`. Explicit "Send to Pharmacy" button also available for partial/pending payments.
  - Pharmacy dispense now closes case (was forwarded to billing).
  - Status label "CLOSED" renamed → "Completed" everywhere in UI.
- **Reminder bugs fixed**:
  - Manual reminder creation now writes `patient_phone` + `scheduled_date`.
  - Snooze writes `scheduled_date` (consistent display).
  - **Pharmacy can snooze** (was complete-only).
  - **Audience filter** for OWNER_DOCTOR & ADMIN: All / Mine / Pharmacy tabs on /doctor/reminders.
- **AI Master Prompt** (`?mode=detailed`): 11 sections — Executive Summary · Clinical Assessment · Homeopathic Analysis · Remedy Suggestions · Mother Tincture · Patient Advice · Prescription Instructions · Follow-up · Lifestyle · **Confidence (Low/Medium/High)** · **Missing Information** + ⚠️ Disclaimer. Pulls full demographics, BMI, allergies, history, prescriptions.
- **Font upgrade**: IBM Plex Sans (body) + IBM Plex Serif (headings) + IBM Plex Mono (numbers/code) — enterprise-credible, calm, used in healthcare/finance.
- Tests: `/app/backend/tests/test_iteration9.py` 17/17 pass.

## Bring-your-own-key for AI (DONE 2026-07-06)
Admin → sidebar → **AI Settings** (`/admin/ai`):
- Paste own API key for **Anthropic Claude / OpenAI GPT / Google Gemini** (stored masked in `db.settings _id:"ai"`).
- Pick active **provider + model** (dependent dropdowns, validated server-side against `ai_settings.MODELS`).
- **Test key** button per provider (`POST /api/admin/ai-settings/test`) fires a tiny prompt, returns ok/error.
- Runtime behavior (`routers/ai.py::_call_llm` → `ai_settings.resolve_ai_config`): own key used when set; if the call fails (invalid/expired key) it auto-retries once with the built-in Emergent Universal Key — AI never breaks.
- Endpoints: GET/POST `/api/admin/ai-settings`, POST `/api/admin/ai-settings/test` (ADMIN only, audited).
- Tests: `/app/backend/tests/test_ai_settings.py` 7/7 pass. Verified fallback in logs (fake key → Emergent key → valid draft).
- ⚠️ Note (2026-07-06): Emergent Universal Key budget was near-exhausted during testing (Budget exceeded 0.408/0.4) — user should top up via Profile → Universal Key → Add Balance, or add own provider keys.

## Elegant Login + Mobile Polish + Homeopathic Clinical Decision Support (DONE 2026-07-20)
- **Login page redesign**: full-bleed clinic reception image background with gradient overlay, centered glassmorphism card, larger 96px logo. `/app/frontend/src/pages/Login.jsx`.
- **Mobile / tablet responsive shell** (P2 done): Sheet-based drawer sidebar on <lg, sticky mobile top bar with hamburger + logo + role, larger touch targets (nav-links min 44px, inputs 16px font to prevent iOS zoom, buttons min 44px). `/app/frontend/src/components/AppLayout.jsx`, `/app/frontend/src/index.css`.
- **Responsive page pass**: all `p-8` pages now `p-4 sm:p-6 lg:p-8`, headings scale `text-2xl sm:text-3xl`, KPI grids collapse to 1/2 cols, wide tables wrap in `.table-scroll`, page headers stack on mobile.
- **Stacked, tab-based Case Detail** (`/app/frontend/src/pages/doctor/CaseDetail.jsx`): tabs now icon+label, horizontally scrollable strip; header block stacks vertically on tablet/mobile; prescription grid switches to stacked layout on <sm; action buttons wrap and are 40-44px tall.
- **Homeopathic Clinical Decision Support (AI Assist)** — new hero action on the AI tab:
  - Backend: `POST /api/cases/{case_id}/ai/decision_support` (added to `routers/ai.py`). Assembles a full clinical dossier (patient profile + all past visits/notes/prescriptions + current case + attachment metadata) via new `_build_clinical_dossier()` helper and calls a homeopathy-specialist system prompt (`prompts.case_decision_support()`).
  - Prompt expertise: materia medica (Boericke/Kent/Allen/Phatak/Clarke/Vermeulen), repertorization (Kent's/Boger/Synthesis), mother tinctures & Q potencies, German methodologies (Reckeweg/Schuessler biochemic/Heel), miasmatic analysis, evidence-informed homeopathy.
  - Output: 13-section Markdown advisory (Case Snapshot → Clinical Reasoning → Differentials → Homeopathic Analysis with rubrics → Suggested Remedies → Mother Tinctures → German/Biochemic → Rx draft → Patient Advice → Follow-up → Red Flags → Evidence Notes → Confidence + gaps → Disclaimer). Rendered via `react-markdown` + `remark-gfm` with themed styling.
  - RBAC preserved: only OWNER_DOCTOR + DOCTOR (with case-ownership check via `load_case_for_user`). Audited as `AI_USED action=decision_support`.
  - Tests: `/app/backend/tests/test_ai_decision_support.py` 14/14 pass (iteration_10). RBAC + regression on existing summarize/advice/instructions actions verified.
- Existing quick actions (summarize / advice / instructions) retained as secondary compact buttons under the hero card.



## How to enable WhatsApp + SMS reminders
**Option A (preferred):** Log in as ADMIN → sidebar → **Messaging** → paste keys → Save. Live immediately, no restart.
**Option B:** Add to `/app/backend/.env` and restart backend:
```

## One-tap "Apply to Rx" from AI Advisory (DONE 2026-07-20)
- **New endpoint** `POST /api/cases/{id}/ai/apply-to-rx` (`routers/ai.py`, placed BEFORE the catch-all `/ai/{action}` for route ordering): takes the Markdown advisory as body → runs a strict-JSON extraction prompt (`prompts.extract_rx_from_advisory`) → returns `{items: [...], notes_for_patient: str}`.
- **Extraction rules**: top-ranked classical remedy first, then optional mother tincture and biochemic salt if the advisory recommends them; each item has `medicine_name / potency / dosage / frequency / duration_days / instructions`. Robust JSON parsing (strips code fences, regex-extracts JSON object, coerces duration_days). Bilingual (EN/TE) instruction language.
- **Model**: `AdvisoryIn` (min_length=20, max_length=20000).
- **RBAC**: OWNER_DOCTOR + DOCTOR only (case ownership check). Audited as `AI_USED action=apply-to-rx items=N`.
- **Frontend** (`CaseDetail.jsx`): after decision-support advisory renders, a prominent **"Apply top pick to Prescription"** button appears. Click → calls apply-to-rx → hoists a `pendingRxDraft` state at CaseDetail → auto-switches to the Prescription tab → PrescriptionTab shows a teal draft banner and pre-fills the medicine rows + notes-for-patient. Doctor reviews, edits, and taps Save prescription (nothing is auto-saved).
- **Graceful empty extraction**: if the advisory has no concrete remedy (e.g. LOW confidence case with no data), returns `items=[]` and the UI shows a friendly error rather than switching tabs.
- **Dossier tuning** (side improvement): decision-support dossier now caps at the 12 most recent past visits, per-visit text truncated to ~250 chars, target response 550-800 words to reduce LLM latency.
- **Tests**: `/app/backend/tests/test_ai_apply_to_rx.py` — 15/16 pass (iteration_11). Only failure is the pre-existing edge proxy 502 on decision_support long calls (~60s edge budget); apply-to-rx itself responds in 1-4s.


WHATSAPP_PHONE_NUMBER_ID=...
WHATSAPP_ACCESS_TOKEN=...
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_FROM=+1...
```

## "Made with Emergent" badge
Per Emergent support: appears only in the preview environment. Auto-removed on deployment / paid plans.

## Backlog
### P1
- ~~BYOK admin UI for AI provider~~ (DONE 2026-07-06 — see "Bring-your-own-key" section).
- N+1 query optimization in `list_cases` (`routers/cases.py`) — batch fetch via `$in` (deployment agent warning).
- Async HTTP for messaging.py (replace `requests` with `httpx.AsyncClient`).
- Streaming CSV cursor for very large exports.
- Allow RECEPTION to create call-back reminders (if needed).

### P2
- N+1 query optimization (use `$lookup` aggregation in patient timeline + dashboards).
- Configurable reminder templates in admin UI.
- Richer top_complaints (medical term filter / TF-IDF).
- Brute-force lockout on `/api/auth/login`.
- ~~**Mobile / tablet responsive pass**~~ (DONE 2026-07-20 — drawer sidebar, responsive padding, stacked case detail, larger touch targets).

## Next Action Items
- **Current priority (2026-10-08):** User verification of the completed Patient History/Revisit enhancement. Four comprehensive history regression suites, targeted browser checks, and 46 existing-flow regression tests passed. Earlier paused tasks remain separate; see the latest verification section below for precise scope.
- Replace `/app/frontend/public/logo.png` with a higher-res / SVG version anytime — the `<Logo />` component already loads from `/logo.png`.
- Paste Twilio + WhatsApp keys via **/admin/messaging** (or backend/.env) to activate WhatsApp/SMS.
- Schedule `/app/scripts/backup.sh` on the clinic server PC (cron / Task Scheduler) — see `/app/scripts/README.md`.

## Change document implementation — code present, acceptance testing pending (2026-09-10)
- User requested extending the existing app, not rebuilding, via `update or changes.txt` (35 parts). Approved 30-day Ending Soon and Reception/Admin photo management with doctor viewing. Full plan/inspection details: `/app/memory/CHANGE_REQUEST_PLAN.md`.
- Added structured homeopathic notes (separate complaints/history/lifestyle/notes; paternal/maternal family fields and personal-history fields), partial updates preserving legacy fields, read-only history/safety display, and new note text in existing AI context. No legacy notes deleted or semantically inferred.
- Added patient-owned photo references using existing private object storage and attachment metadata. Camera/file/mobile capture controls, JPEG compression, authenticated viewing, and shared profile/case photo display. No auth credential or auth implementation changes.
- Added canonical treatment catalogue and distinct packages with month-based dates, stable contract snapshots, integer-paise balances, individually identified append-only receipts/reversals, duplicate-active guards, explicit renewals, package PRO dues/history/follow-ups, linked visit billing and report/CSV integration. Legacy visit bills remain unchanged in type; subsequent edits preserve previous snapshots. New startup indexes are additive; no patient or financial records migrated/deleted.
- User paused before full workflow testing. Package list browser smoke passed and frontend/Python compilation passed. **Do not label these changes acceptance-complete.**

## FIR registration photo addition — implemented, focused testing pending (2026-09-10)
- Exact new request: “I would like the photo adding feature on new patient registration page as well(first information report) under reception as they are the first point of contact as soon as the patient enters the clinic for the first time. Attached the page for reference. Do not make any other changes just add this feature to this page.” User confirmed optional photo, capture/retake/upload before submission and shared patient-level storage.
- Limited application edits for this follow-up to `frontend/src/pages/reception/NewPatient.jsx` and backward-compatible draft mode in `components/PatientPhotoEditor.jsx`. Added optional controls at the top of Patient Information; existing form fields/layout retained.
- FIR creation still uses the existing endpoint. Once the patient/first visit exists, upload uses the existing patient-photo endpoint. If photo upload fails, the saved patient is retained, re-registration is disabled, and Reception can retry only the photo or continue without it. Draft photo processing and submission controls prevent accidental duplicate clicks.
- Camera/file/mobile controls reuse the existing component, with normal existing-profile save mode preserved. No backend/schema changes for this follow-up.
- Verification so far: frontend build passed (`test_reports/fir-photo-build.log`); authenticated Reception FIR browser smoke passed, photo controls and original inputs visible. User paused before registration/upload/retry end-to-end tests.

## Deployment readiness health check (2026-09-10)
- User explicitly requested the Deployment Agent health check. Result: **WARN — deployable from static/build checks; no blocking code/build configuration issues reported.** No application code/configuration changes made during this check.
- Compilation, environment files, service/supervisor configuration, Mongo-only architecture and non-destructive/idempotent startup checks reported OK. External preview `/api/health` and `/login` both returned HTTP 200.
- Non-blocking findings: external login-background asset URL; admin statistics N+1 doctor count queries; permissive CORS; React hook dependency/build warnings.
- Full workflow verification remains pending for the latest features. Production environment was not tested or accessed; this check is not a deployment or a guarantee of full clinical/financial correctness.
- Existing limitations remain: AI decision-support proxy timeout; clinical-reminder permissions issue previously paused; WhatsApp/SMS providers unconfigured. Health endpoint confirms both messaging providers disabled.
- Report: `/app/test_reports/deployment_health_2026-09-10.md`.

### Priorities after the health check
- **P0:** Focused FIR tests: real photo upload, no-photo registration, camera denied/capture/retake, same photo in profile/case, failure retry without duplicate registration. Then package/payment/renewal and old-workflow regression tests before accepting the broader changes.
- **P1:** Resolve known AI timeout in a separately approved change; review permissive CORS and the paused clinical-reminder data exposure.
- **P2:** Existing N+1 optimisation, local login-background asset, messaging configuration and backup scheduling.
- Suggested safeguard: maintain a short release checklist for registration, patient identity/photo and payment allocation.

## Patient History / Revisit / Treatment Tracking — completed and verified (2026-10-08)

### Request and approval
- Source: `# MASTER PROMPT.txt`, https://customer-assets-4nw71qhi.emergentagent.net/job_simple-enterprise-ai/artifacts/03d08330588929ca_%23%20MASTER%20PROMPT.txt.
- Goal: reuse existing clinical structures to make Primary History available on revisits, show previous complaints/observations/additional notes/prescriptions chronologically, keep current notes and medicines separate, preserve all historical records/date handling/new-patient workflow, and avoid unrelated changes.
- Completed the requested read-only architecture inspection and presented an assessment before implementation. User explicitly authorised proceeding with best judgement: “No need for clarification, just proceed with your best judgment.”
- Approved defaults used: later recorded primary-history changes carry forward; Observation uses existing `diagnosis_summary`; Additional Notes uses existing `additional_info`; original baseline `notes` remains separate. These two optional inputs appear on first and repeat consultations without changing registration or workflow steps.
- Blank primary-history fields mean no replacement recorded; they do not erase the last nonblank reference. This safety rule is communicated in the UI. No undocumented deletion/versioning mechanism introduced.

### Implementation — four application files only
1. `backend/routers/patients.py`: optional `for_case_id`, `page`, `page_size` on existing `GET /api/patients/{id}/timeline`. Existing callers without `for_case_id` retain their old response/behavior. Opt-in clinical history is restricted to already-authorised clinical roles/cases and the matching patient.
2. `frontend/src/components/ClinicalNotesEditor.jsx`: displays inherited Primary History with source case/date, while current Presenting Complaint/Observation/Additional Notes stay visit-specific. Only intentionally edited fields are submitted to existing note-save API, so displaying history does not copy it into the current record. Nested edits preserve sibling fields. History retry preserves typed values.
3. New `frontend/src/components/PatientHistoryPanel.jsx`: paged read-only previous visits and all stored prescription versions/items/instructions, used in existing Notes and Prescription tabs. Dates use the existing IST formatter; first accessible/current/historical visits are distinguished. No treatment scoring, charts or clinical inference.
4. `frontend/src/pages/doctor/CaseDetail.jsx`: integrates the history view and current visit date, prevents stale case responses/Rx drafts from leaking across navigation, keeps the existing current prescription editor and write API unchanged. Added test identifiers to existing Rx controls without behavior changes.

### Data and chronology
- No new database collections, fields, indexes or migration for this enhancement. No new packages/libraries, routes replacing existing APIs, authentication changes or configuration changes.
- Existing patients → cases → clinical_notes/prescriptions relationships retained. No real historical records rewritten or deleted.
- Primary reference is a read-time projection of the latest nonblank value for each of 16 baseline leaf fields from earlier accessible visits. It is not stored as a second patient-history record. The first visit remains identifiable even after later history updates.
- Current and future visits excluded from previous-history results. Original timestamp strings returned unchanged. Timezone-aware comparison retains microsecond order; exact ties use existing case number/ID. No timestamps repaired, regenerated or reformatted in storage.
- Primary derivation is not limited to the old timeline's 200-record cap. Full previous-visit details are database-paged; all prescription versions for the selected page remain read-only.
- Hemanth's clinical history remains limited to his assigned cases; Jyothi/owner retains existing broader clinical access. This does NOT expand cross-doctor permissions or alter package financial scoping.

### Verification
- New reusable suite: `backend/tests/test_iteration15_patient_history_tracking.py` — **4 comprehensive tests passed**. Covers first/second/third visits, earlier case/note/Rx hash and timestamp immutability, baseline inheritance/updates, >200 prior visits, pagination, same-day/microsecond/different-offset ordering, ambiguous-timestamp safe error, legacy timeline compatibility and role guards.
- Existing-flow regressions — **46 tests passed, zero failures/errors/skips**: FIR/photo registration, structured notes/privacy, packages/payments/concurrency, photo access, attachments, CSV exports and dashboards. XML: `test_reports/pytest/patient_history_existing_regression.xml`.
- Targeted browser checks passed: real reception→doctor journey, independent current fields/Rx, previous Rx read-only, history failure/retry preserving typed notes, and responsive widths 320/768/1024/1440 with no page horizontal overflow.
- Frontend build passed: `test_reports/patient-history-build.log`. Python compilation and preview health passed. New features use real APIs/MongoDB; only test-time failure/delay injection was used for recovery checks.
- Test report: `test_reports/iteration_14.json`; final scope/acceptance record: `test_reports/patient_history_acceptance.md`.
- Backend history fixtures were cleaned by the test suite. The exact browser-created fixture `UIHIST480036` (`528b6d3f-9904-4d63-ab29-66cc4b36b162`) and its two cases were removed after identity verification. No existing patient records or counters were reset.

### Limitations and separate backlog
- Ambiguous legacy visit timestamps without a timezone produce a history warning rather than guessing or rewriting dates. Current case entry remains available; stored record is untouched.
- Blank values do not clear inherited baseline history. Explicit recorded replacements carry forward, and older values remain in their original visits.
- Existing doctor visibility rules still apply; unavailable cross-doctor history is not exposed.
- Testing additionally re-confirmed the PRE-EXISTING lack of login brute-force lockout and noted a missing optional auth-testing guide. Authentication was not part of the approved scope and was NOT changed. These findings do not represent a new history-feature regression.
- Existing AI decision-support timeout and unconfigured SMS/WhatsApp remain outside this enhancement. Older paused supplemental photo/mobile testing is not represented as fully completed by this feature's tests.
- Optional future enhancement, subject to approval: a read-only comparison of two selected visits; no comparison/scoring feature was added here.
