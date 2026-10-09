# Patient History / Revisit Acceptance — 2026-10-08

## Scope and approval
Implemented the uploaded MASTER PROMPT after the required read-only assessment and explicit user instruction to proceed with best judgement. Scope is clinical history reuse and visit separation, not a system rebuild, permission expansion, database migration, AI/provider change or authentication enhancement.

## Delivered
- Primary History reference on revisits, using existing notes and source case/date labels. Later nonblank recorded updates carry forward without changing previous visits.
- Independent current Presenting Complaint, Observation (`diagnosis_summary`) and Additional Notes (`additional_info`). Original primary `notes` stays separate.
- Read-only previous visits and all stored prescription versions/items, including potency, dosage, frequency, duration and instructions, within existing Doctor Case tabs.
- Latest-previous-first order; first accessible visit marked; current and historical visits differentiated. Same-day, microsecond and offset-aware chronological comparisons do not alter stored timestamps.
- Paged previous-visit data and a baseline that can reach beyond 200 prior visits. Existing default timeline response is unchanged.
- Dirty-only note saves; inherited reference values are not automatically copied to current records. History-retry failures do not erase typed current notes. Case navigation guards prevent stale case/Rx state.

## Files changed
Application files: `backend/routers/patients.py`; `frontend/src/components/ClinicalNotesEditor.jsx`; new `frontend/src/components/PatientHistoryPanel.jsx`; `frontend/src/pages/doctor/CaseDetail.jsx`.

Tests: `backend/tests/test_iteration15_patient_history_tracking.py` plus reports. No model/schema/dependency/configuration/auth/permission write logic changed.

## Verification results
| Check | Result |
|---|---|
| New history regression suite | 4 comprehensive tests passed; 0 failed/error/skipped |
| Existing-flow regression suite | 46 tests passed; 0 failed/error/skipped |
| First → return → third visit | Passed; current records independent |
| Earlier case/note/Rx hashes and timestamps | Unchanged after subsequent-visit saves |
| Baseline from more than 200 visits | Passed |
| Pagination and role isolation | Passed |
| Same-day/microsecond/timezone ordering | Passed; original timestamps preserved |
| Browser history/Rx/dirty-only save/retry | Passed targeted checks |
| Responsive widths | 320/768/1024/1440 passed; no page horizontal overflow |
| Build / Python compilation / preview health | Passed |

Evidence: `iteration_14.json`, `pytest/iteration15_patient_history.xml`, `pytest/patient_history_existing_regression.xml`, `patient-history-existing-regression.log`, `patient-history-build.log`. The test agent's aggregate report also includes an unrelated auth-lockout check; the requested history scope passed. No successful application API is mocked. Fault/delay injection was used only in browser recovery tests.

## Data safety and cleanup
No real clinical records were migrated, merged, rewritten or deleted. Tests used labelled synthetic records. The backend history suite cleaned its own patients; the exact browser history fixture UIHIST480036 and its two cases were removed after identity verification. ID counters were not reset, so numbering gaps caused by test creation/deletion are expected.

## Known limitations
- A blank baseline field means no replacement recorded, not deletion of earlier clinical history.
- Existing clinical permissions restrict which visits can contribute reference data. No additional cross-doctor access granted.
- If a legacy current visit has an ambiguous/no-timezone timestamp, the history request returns a warning instead of inventing a date. Current note/Rx entry remains available.
- Pre-existing login lockout gap, optional missing auth-testing guide, long AI advice timeout and unconfigured messaging remain separate backlog. They were not silently addressed under this narrowly approved change.

## Next action
Clinic user verification of a returning-patient consultation. Optional future change, only after approval: read-only side-by-side comparison of two visits.