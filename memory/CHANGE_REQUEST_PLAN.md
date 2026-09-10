# July 2026 clinical notes, patient photographs and package finance enhancement

## Approved scope and defaults
User source: `update or changes.txt` (35 parts). Modify, do not rebuild. Preserve existing IDs, records, workflows, authentication and role rules. User explicitly approved 30-day Ending Soon and Reception/Admin photo editing, doctors viewing. Other defaults: canonical shared treatment catalogue; zero-payment visits have a bill/visit but no financial transaction; arrears collectible after expiry; renew only when expired and settled. Existing code contained no package/renewal exceptions or treatment catalogue.

## Inspection findings (before implementation)
- MongoDB standalone, no replica set/transaction support. Existing preview collections: 57 patients, 57 cases, 24 payments (one cumulative bill per case), 8 clinical_notes, 33 reminders, 5 attachments, 8 pharmacy_dispense, 4 prescriptions, 2 doctor_profiles.
- `patients.id` / `patient_uid` and `cases.patient_id` remain source-of-truth relationships. Doctors use `doctor_profiles.id`; scope enforced through existing dependencies.
- No package, disease/treatment or transaction-ledger entities existed. Cannot infer package duration, disease or transaction history from old visit totals.
- Eight notes have diagnosis data; four allergies; two each safety/advice/additional fields. No clinical migration can safely infer new meaning.
- Existing payment endpoint overwrites cumulative visit totals; no refund/credit workflow. New package accounting must not repeat this behaviour.
- Existing object storage uses private API reads/writes, and attachment metadata in MongoDB. No storage deletion API.

## Additive changes
- Extend ClinicalNoteIn with separate homeopathic fields, nested family/personal histories. Use partial `$set` semantics. Historical fields retained; read-only historical view plus safety alert. Existing import API unchanged.
- Patient `photo_id` references a PATIENT_PHOTO metadata record in existing attachments, not a case. Replace references atomically and soft-delete prior metadata; existing private object storage reused. Images decoded/re-encoded JPEG <=800px; EXIF removed, 10MB/25MP input limits. Authenticated proxy, no public URLs.
- New `treatments`: canonical ID, normalized unique name. New `packages`: immutable contract snapshot, patient/treatment IDs, integer-paise amount, calendar month dates, lifecycle, renewal links. Index-only startup migration.
- Each package has an append-only `transactions` ledger of individually identified receipts/reversals (date, amount, method, case, reference, actor). This is an embedded MongoDB aggregate, not a replacement patient or billing system. Single-document conditional append atomically enforces overpayment/idempotency without unavailable distributed transactions. Money never uses floating-point arithmetic internally. Bounded to 5000 entries per contract.
- Existing `payments` remains visit bill records. New `kind=PACKAGE_BILL` records carry stable snapshots and package references; zero-payment visits remain visible. No legacy bill conversion. Existing-case billing modes are reserved with a conditional case update to prevent concurrent legacy/package allocation.
- Reports combine legacy bill accounting with package receipts and outstanding values using a shared projection, excluding package bills from revenue to avoid double counting. CSV includes individual package receipts/reversals.
- PRO follow-ups use existing `reminders` collection, `kind=PACKAGE_FOLLOWUP`, `audience=[PRO]`, `internal_only=true`; not automatically sent to patients. Completion via scoped package routes.

## Main files
Backend: models.py, package_models.py, package_service.py, financial_reporting.py, clinical_context.py; routers/packages.py, package_billing.py, patient_photos.py; small additive changes to cases/patients/payments/ai/reminders/attachments/dashboards/exports/admin; server router/index registration.
Frontend: ClinicalNotesEditor, PatientPhoto, PatientPhotoEditor; reusable components/packages; PRO Packages, PackageDetail; integrate CaseDetail, PatientTimeline, BillingDetail, Receipt, FinancialSearch, Dashboard, App/AppLayout.

## Migration / compatibility risks
- No delete/unset of existing clinical/financial data; no guessed package imports, no patient renumbering, no authentication changes.
- Previous notes and ordinary bills keep working. Later ordinary-bill updates retain prior snapshots in `history` in addition to existing audits.
- Unique active-slot index guards concurrent package creation; stale expired slots are released on creation, not by destructive migration. Upcoming packages reserve the same treatment slot.
- Date lifecycle and payment status calculated independently. Renewal inserts a new record, linked to previous, not copied payments. End date exclusive (e.g. 10 Jan -> 10 Jul).
- New startup indexes target only new package/treatment records and package bills; legacy billing records not reclassified.
- Existing AI latency timeout and previously paused clinical-reminder privacy issue remain outside this change. Messaging providers still unconfigured.

## Verification required
Run full new workflow suite (notes/photo/package/ledger/renewals/billing), concurrent duplicate/overpayment requests, legacy workflow regression, current storage upload/download, role boundaries, calendar/leap-month dates and responsive desktop/tablet/mobile checks. Record results and any residual risks in implementation report.