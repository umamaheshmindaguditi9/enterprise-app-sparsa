# Code-review resolution — 2026-10-11

## Findings and changes

| Reported finding | Verified result and resolution |
| --- | --- |
| `core.py` ↔ `package_service.py` cycle | The old reverse dependency was a deferred import in `core.enrich_case`. Moved case presentation into `case_views.py`; the cases router imports it directly. Shared core no longer imports package services. Both import orders passed with required environment loaded. |
| Secret in `tests/test_iteration6.py` | The flagged value was a synthetic provider-test token. Token, preview account passwords, and test URL now come from test-runner environment. Setup/acceptance script passwords also use environment. No real account or provider key was created/changed. |
| Secret in frontend `api.js:22` | False positive: public `ROLE_LABELS`, not an API key. Left legitimate role labels unchanged; no credential moved into a browser environment variable. |
| 51 missing hook dependencies | Standard exhaustive-deps check identified **8 actual warnings**, not 51. Fixed all 8 with stable callbacks and complete dependencies. PastVisitForm and ClinicalNotesEditor did not have the claimed dependency omissions. No suppressions or module constants unnecessarily added to dependency arrays. |
| 10 undefined Python variables | Ruff F821/F822/F823 found **0** before and after refactor. No speculative variable changes. |
| 52 incorrect `is` comparisons | Ruff E711/E712/F632 found **0**. Valid identity checks (`is None`, etc.) are preserved; blanket replacement would be incorrect. |
| Complex backend functions | Extracted pure AI context formatters, package lifecycle/payment/renewal status helpers and clinical normalization helpers. No AI provider/model/authentication changes. |
| Complex frontend components | Split photo conversion/camera/state, clinical-note merging/save state and field rendering, package loading/payment fields/validation. Existing UI, request shapes and permissions retained. |
| Three index-key locations | Static ledger headings use their titles; legacy read-only prescription rows/markdown lines use content identity plus duplicate occurrence rather than list position. No persisted record IDs were changed. |
| JSX computations | Memoized legacy note entries, historical FIR display entries and active package options. Package option labels are a single text value, avoiding the preview nested-span warning on these options. |
| Service type hints | Added parameter/return annotations throughout `package_service`, `fir_parsing`, `historical_package_service`, `clinical_context`; targeted ANN001/ANN201/ANN202 checks pass. |

## Verification
- Frontend production build compiled successfully: `code-review-build.log`.
- Frontend hooks/undefined-name lint: **0 findings**, `code_review_eslint_iteration17.json` (strict config is `frontend/eslint.config.js`).
- Python undefined-name/literal-comparison checks: **0 findings**; Python compilation and both service/router import orders passed.
- **40 selected regression tests passed**: `pytest/iteration17_regression40_nonblock_auth.xml`.
- **11 helper characterization tests passed**: `pytest/iteration18_characterization.xml`.
- Persisted browser acceptance script passed: `iteration18_acceptance.log`, `iteration_18.json`. Verified a real saved historical payment before deliberately aborting its browser response, exact-body retry without duplicate case/payment, then failed-photo/successful-photo retry without another visit save. Backdated IST timestamp and package terms retained; responsive widths 320/768/1024/1440 passed.
- New test fixtures and import reservations were removed with targeted IDs; cleanup evidence: `iteration18_cleanup.log`. No existing clinical records were rewritten.

## Precise scope / limitations
- There are **no mocked application APIs**. Network failure injection and fixed clocks in unit tests are test-only. The persisted failure mechanism is an authenticated context API POST followed by aborting the first intercepted browser response; it is not an application XHR patch or production failpoint.
- One **pre-existing auth lockout test still fails**: an older test expects HTTP 429 after repeated incorrect passwords; current behavior is HTTP 401 with no lockout. Authentication changes were outside this code-review request and have not been silently implemented.
- Live AI generation was not re-run; its prompt-formatting helpers were characterized. Previously documented AI proxy timeout and unconfigured SMS/WhatsApp remain separate.
- Dedicated browser tests for every camera/device condition and notes/photo read-only combination were not added. Those branches were inspected; the real photo upload, preview, recovery path and affected backend contracts were exercised.
- Optional next improvement: run the lint, helper and payment-recovery suites automatically before releases. Test-only browser dependencies were installed in an isolated disposable environment, not production dependency manifests.