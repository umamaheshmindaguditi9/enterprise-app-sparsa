"""Backend tests for POST /api/cases/{case_id}/ai/apply-to-rx endpoint.

Coverage:
- Happy path: OWNER_DOCTOR (jyothi) with well-formed advisory → 200 + structured items.
- Body validation: missing/too-short/too-long advisory → 422.
- RBAC: PRO/RECEPTION/PHARMACY/ADMIN → 403; DOCTOR on non-owned case → 403/404.
- Empty/vague advisory → 200 with items=[] and notes_for_patient="".
- Route ordering: apply-to-rx NOT intercepted by catch-all /ai/{action}.
- Regression: /ai/summarize, /advice, /instructions, /decision_support still 200.
- Audit log: AI_USED entry with entity=Case, action=apply-to-rx recorded.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL", "https://simple-enterprise-ai.preview.emergentagent.com"
).rstrip("/")
API = f"{BASE_URL}/api"
PWD = "Password@123"
TIMEOUT = 120  # AI can be slow

WELL_FORMED_ADVISORY = """## 5. Suggested Remedies
**Natrum Muriaticum 200C** — silent grief, aversion to consolation, salt craving.
**Ignatia 30C** — recent emotional shock.

## 6. Mother Tinctures & Combinations
**Crataegus Q** — 10 drops BD for cardiac tone.

## 7. German / Biochemic Considerations
**Kali Phos 6X** — 4 pills TDS for nervous exhaustion.

## 8. Prescription Instructions (Draft)
Natrum Mur 200C, single dose weekly. Empty stomach, no coffee/mint 15 min around dose.

## 9. Patient Advice
- Regular sleep 7-8h
- Avoid emotional stress
- Drink 2L water daily
"""

VAGUE_ADVISORY = (
    "## 5. Suggested Remedies\n"
    "No concrete candidate identified from the available record.\n\n"
    "## 6. Mother Tinctures & Combinations\nNone indicated.\n\n"
    "## 7. German / Biochemic Considerations\nNot indicated for this presentation.\n\n"
    "## 8. Prescription Instructions (Draft)\nDefer prescription pending more data.\n\n"
    "## 9. Patient Advice\nInsufficient information.\n\n"
    "## 13. Confidence & Missing Data\n**Confidence: LOW** — no history available.\n"
)


def _login(username: str) -> requests.Session:
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"username": username, "password": PWD}, timeout=30)
    assert r.status_code == 200, f"login {username} failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def jyothi():
    return _login("jyothi")


@pytest.fixture(scope="module")
def hemanth():
    return _login("hemanth")


@pytest.fixture(scope="module")
def admin():
    return _login("admin1")


def _extract_cases(payload):
    return payload if isinstance(payload, list) else (payload.get("items") or payload.get("cases") or [])


@pytest.fixture(scope="module")
def jyothi_case_id(jyothi):
    r = jyothi.get(f"{API}/cases", timeout=30)
    assert r.status_code == 200
    cases = _extract_cases(r.json())
    assert cases, "No cases available for jyothi"
    return cases[0]["id"]


@pytest.fixture(scope="module")
def hemanth_case_ids(hemanth):
    r = hemanth.get(f"{API}/cases", timeout=30)
    assert r.status_code == 200
    return {c["id"] for c in _extract_cases(r.json())}


@pytest.fixture(scope="module")
def not_hemanth_case(jyothi, hemanth_case_ids):
    r = jyothi.get(f"{API}/cases", timeout=30)
    all_cases = _extract_cases(r.json())
    for c in all_cases:
        if c["id"] not in hemanth_case_ids:
            return c["id"]
    pytest.skip("No case exists that isn't hemanth's")


# ============ Happy path ============
class TestApplyToRxHappyPath:
    def test_owner_doctor_apply_to_rx(self, jyothi, jyothi_case_id):
        r = jyothi.post(
            f"{API}/cases/{jyothi_case_id}/ai/apply-to-rx",
            json={"advisory": WELL_FORMED_ADVISORY},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, f"got {r.status_code}: {r.text[:500]}"
        data = r.json()
        assert "items" in data and "notes_for_patient" in data
        assert isinstance(data["items"], list)
        assert isinstance(data["notes_for_patient"], str)
        assert len(data["items"]) >= 1, "Expected at least one extracted remedy item"
        for it in data["items"]:
            assert set(it.keys()) >= {
                "medicine_name", "potency", "dosage", "frequency",
                "duration_days", "instructions",
            }
            assert isinstance(it["medicine_name"], str) and it["medicine_name"].strip()
            assert isinstance(it["potency"], str)
            assert isinstance(it["dosage"], str)
            assert isinstance(it["frequency"], str)
            assert it["duration_days"] is None or isinstance(it["duration_days"], int)
            assert isinstance(it["instructions"], str)
        # The top pick should be Natrum Mur-ish
        top_name = data["items"][0]["medicine_name"].lower()
        assert "natrum" in top_name or "nat" in top_name, f"Unexpected top pick: {top_name}"


# ============ Body validation (422) ============
class TestApplyToRxValidation:
    def test_missing_advisory(self, jyothi, jyothi_case_id):
        r = jyothi.post(f"{API}/cases/{jyothi_case_id}/ai/apply-to-rx", json={}, timeout=30)
        assert r.status_code == 422, f"expected 422, got {r.status_code}: {r.text[:200]}"

    def test_too_short_advisory(self, jyothi, jyothi_case_id):
        r = jyothi.post(
            f"{API}/cases/{jyothi_case_id}/ai/apply-to-rx",
            json={"advisory": "too short"},  # <20 chars
            timeout=30,
        )
        assert r.status_code == 422, f"expected 422, got {r.status_code}: {r.text[:200]}"

    def test_too_long_advisory(self, jyothi, jyothi_case_id):
        big = "A" * 20001  # >20000
        r = jyothi.post(
            f"{API}/cases/{jyothi_case_id}/ai/apply-to-rx",
            json={"advisory": big},
            timeout=30,
        )
        assert r.status_code == 422, f"expected 422, got {r.status_code}: {r.text[:200]}"


# ============ RBAC ============
class TestApplyToRxRBAC:
    @pytest.mark.parametrize("username", ["pro1", "reception1", "pharmacy1", "admin1"])
    def test_non_doctor_roles_forbidden(self, username, jyothi_case_id):
        s = _login(username)
        r = s.post(
            f"{API}/cases/{jyothi_case_id}/ai/apply-to-rx",
            json={"advisory": WELL_FORMED_ADVISORY},
            timeout=30,
        )
        assert r.status_code == 403, f"{username} expected 403, got {r.status_code}: {r.text[:200]}"

    def test_doctor_cannot_access_other_doctors_case(self, hemanth, not_hemanth_case):
        r = hemanth.post(
            f"{API}/cases/{not_hemanth_case}/ai/apply-to-rx",
            json={"advisory": WELL_FORMED_ADVISORY},
            timeout=30,
        )
        assert r.status_code in (403, 404), f"expected 403/404, got {r.status_code}: {r.text[:200]}"


# ============ Empty/vague advisory → 200 with items=[] ============
class TestApplyToRxVagueAdvisory:
    def test_vague_advisory_returns_empty_items(self, jyothi, jyothi_case_id):
        r = jyothi.post(
            f"{API}/cases/{jyothi_case_id}/ai/apply-to-rx",
            json={"advisory": VAGUE_ADVISORY},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, f"got {r.status_code}: {r.text[:500]}"
        data = r.json()
        assert data["items"] == [], f"expected empty items, got {data['items']}"
        assert data["notes_for_patient"] == "", f"expected empty notes, got {data['notes_for_patient']!r}"


# ============ Route ordering ============
class TestRouteOrdering:
    def test_apply_to_rx_not_intercepted_by_catchall(self, jyothi, jyothi_case_id):
        """If route ordering is wrong, apply-to-rx would hit the catch-all /ai/{action}
        which validates action ∈ (summarize|advice|instructions|decision_support) and
        would return 400 'Invalid action'. Verify we don't get that."""
        r = jyothi.post(
            f"{API}/cases/{jyothi_case_id}/ai/apply-to-rx",
            json={"advisory": WELL_FORMED_ADVISORY},
            timeout=TIMEOUT,
        )
        assert r.status_code != 400 or "Invalid action" not in r.text, (
            f"apply-to-rx got swallowed by catch-all: {r.status_code} {r.text[:200]}"
        )

    def test_decision_support_still_works(self, jyothi, jyothi_case_id):
        r = jyothi.post(f"{API}/cases/{jyothi_case_id}/ai/decision_support", timeout=TIMEOUT)
        assert r.status_code == 200, f"got {r.status_code}: {r.text[:300]}"
        assert r.json().get("action") == "decision_support"


# ============ Regression: existing AI actions ============
class TestRegressionExistingAI:
    @pytest.mark.parametrize("action", ["summarize", "advice", "instructions"])
    def test_existing_ai_actions(self, jyothi, jyothi_case_id, action):
        r = jyothi.post(f"{API}/cases/{jyothi_case_id}/ai/{action}", timeout=TIMEOUT)
        assert r.status_code == 200, f"{action}: {r.status_code} {r.text[:300]}"
        data = r.json()
        assert data["action"] == action
        assert isinstance(data.get("result"), str) and len(data["result"]) > 0


# ============ Audit log ============
class TestApplyToRxAuditLog:
    def test_audit_log_recorded(self, admin, jyothi, jyothi_case_id):
        # Trigger apply-to-rx to ensure entry exists
        r = jyothi.post(
            f"{API}/cases/{jyothi_case_id}/ai/apply-to-rx",
            json={"advisory": WELL_FORMED_ADVISORY},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200

        r2 = admin.get(f"{API}/admin/audit-logs?action=AI_USED&limit=200", timeout=30)
        assert r2.status_code == 200, f"audit list: {r2.status_code} {r2.text[:200]}"
        data = r2.json()
        logs = data.get("audit_logs") or data.get("items") or data if isinstance(data, list) else data.get("audit_logs") or []
        if isinstance(data, list):
            logs = data
        matches = []
        for lg in logs[:300]:
            act = lg.get("action") or lg.get("action_type")
            entity = lg.get("entity_type") or lg.get("target_type") or lg.get("entity")
            entity_id = lg.get("entity_id") or lg.get("target_id")
            meta = lg.get("metadata") or lg.get("meta") or lg.get("details") or lg.get("payload") or {}
            meta_s = meta if isinstance(meta, str) else str(meta)
            if (act == "AI_USED"
                    and entity in ("Case", "case", None)
                    and entity_id == jyothi_case_id
                    and "apply-to-rx" in meta_s):
                matches.append(lg)
        assert matches, f"No AI_USED/apply-to-rx audit entry for case {jyothi_case_id}"
        # sanity: metadata mentions items count
        sample_meta = matches[0].get("metadata") or matches[0].get("meta") or matches[0].get("details") or matches[0].get("payload") or {}
        sample_s = sample_meta if isinstance(sample_meta, str) else str(sample_meta)
        assert "items" in sample_s, f"audit entry missing items count: {sample_s[:200]}"
