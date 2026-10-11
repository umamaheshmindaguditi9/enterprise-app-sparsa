# Sparsa Homeoclinic — Test Credentials

Seeded on backend startup. Login via POST /api/auth/login with `{username, password}`.

| Username    | Password       | Role          | Display Name        | Dashboard         |
|-------------|----------------|---------------|---------------------|-------------------|
| admin1      | Password@123   | ADMIN         | System Admin        | /admin            |
| jyothi      | Password@123   | OWNER_DOCTOR  | Dr. Jyothi Vani     | /doctor           |
| hemanth     | Password@123   | DOCTOR        | Dr. Hemanth         | /doctor           |
| reception1  | Password@123   | RECEPTION     | Reception Desk      | /reception        |
| pharmacy1   | Password@123   | PHARMACY      | Pharmacy Counter    | /pharmacy         |
| pro1        | Password@123   | PRO           | Billing Desk        | /pro              |

## Auth endpoints
- POST `/api/auth/login` — body: `{ "username": "...", "password": "..." }` → sets httpOnly access_token + refresh_token cookies, returns user object
- GET  `/api/auth/me` — returns current user
- POST `/api/auth/logout` — clears cookies

## Notes
- Roles enforced server-side. OWNER_DOCTOR (Jyothi) can see all cases including Hemanth's.
- DOCTOR (Hemanth) can only see his own assigned cases.
- ADMIN has full read access to all data and exclusive access to user management + audit logs + stats.

## Environment for preview test runners
- `REACT_APP_BACKEND_URL`: use the value in `frontend/.env`.
- `TEST_CLINIC_PASSWORD`: supply the existing preview account password documented above; account credentials are unchanged.
- `TEST_TWILIO_AUTH_TOKEN`: required only for iteration-6 provider/security tests; supply a disposable, randomly generated synthetic test string, NOT a live provider credential. It must never be used to send messages.
- The historical-package setup/acceptance scripts also require `TEST_CLINIC_PASSWORD`; all existing account credentials remain unchanged.
- The test runner passes these values; do not commit them into source. Provider-settings tests must restore their original settings on exit.
