"""Backend tests for AI decision_support endpoint & regression on existing AI actions."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://simple-enterprise-ai.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
PWD = "Password@123"
TIMEOUT = 90  # AI can be slow


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


@pytest.fixture(scope="module")
def cases_data(jyothi):
    r = jyothi.get(f"{API}/cases", timeout=30)
    assert r.status_code == 200
    data = r.json()
    # response may be dict or list
    cases = data if isinstance(data, list) else (data.get("items") or data.get("cases") or [])
    assert len(cases) > 0, "No cases available"
    return cases


@pytest.fixture(scope="module")
def jyothi_case_id(cases_data):
    # Just pick first case for owner (jyothi can access all)
    return cases_data[0]["id"]


@pytest.fixture(scope="module")
def hemanth_own_case(hemanth):
    r = hemanth.get(f"{API}/cases", timeout=30)
    assert r.status_code == 200
    data = r.json()
    cases = data if isinstance(data, list) else (data.get("items") or data.get("cases") or [])
    if not cases:
        pytest.skip("Hemanth has no assigned cases")
    return cases[0]["id"]


@pytest.fixture(scope="module")
def not_hemanth_case(jyothi, hemanth):
    # get all cases from jyothi, then pick one NOT accessible to hemanth
    r = jyothi.get(f"{API}/cases", timeout=30)
    all_cases = r.json()
    all_cases = all_cases if isinstance(all_cases, list) else (all_cases.get("items") or all_cases.get("cases") or [])
    r2 = hemanth.get(f"{API}/cases", timeout=30)
    h_cases = r2.json()
    h_cases = h_cases if isinstance(h_cases, list) else (h_cases.get("items") or h_cases.get("cases") or [])
    h_ids = {c["id"] for c in h_cases}
    for c in all_cases:
        if c["id"] not in h_ids:
            return c["id"]
    pytest.skip("No case exists that isn't hemanth's")


# ============ decision_support core test ============
class TestDecisionSupport:
    def test_owner_doctor_decision_support(self, jyothi, jyothi_case_id):
        r = jyothi.post(f"{API}/cases/{jyothi_case_id}/ai/decision_support", timeout=TIMEOUT)
        assert r.status_code == 200, f"got {r.status_code}: {r.text[:500]}"
        data = r.json()
        assert data["action"] == "decision_support"
        result = data.get("result", "")
        assert isinstance(result, str)
        assert len(result) >= 500, f"result too short: {len(result)} chars"
        # It should have some homeopathic/disclaimer indicators
        low = result.lower()
        # be lenient — check at least one indicator each
        assert any(k in low for k in ["remed", "potenc", "tincture", "homeo"]), "no homeopathic terms in result"
        assert any(k in low for k in ["disclaim", "not a substitute", "informational", "consult"]), "no disclaimer-like text"

    def test_doctor_own_case(self, hemanth, hemanth_own_case):
        r = hemanth.post(f"{API}/cases/{hemanth_own_case}/ai/decision_support", timeout=TIMEOUT)
        assert r.status_code == 200, f"got {r.status_code}: {r.text[:400]}"
        data = r.json()
        assert data["action"] == "decision_support"
        assert len(data.get("result", "")) >= 500

    def test_doctor_other_case_forbidden(self, hemanth, not_hemanth_case):
        r = hemanth.post(f"{API}/cases/{not_hemanth_case}/ai/decision_support", timeout=TIMEOUT)
        assert r.status_code in (403, 404), f"expected 403/404, got {r.status_code}: {r.text[:300]}"

    def test_invalid_action(self, jyothi, jyothi_case_id):
        r = jyothi.post(f"{API}/cases/{jyothi_case_id}/ai/foobar", timeout=30)
        assert r.status_code == 400
        assert "Invalid action" in r.text

    @pytest.mark.parametrize("username", ["pro1", "reception1", "pharmacy1", "admin1"])
    def test_non_doctor_roles_forbidden(self, username, jyothi_case_id):
        s = _login(username)
        r = s.post(f"{API}/cases/{jyothi_case_id}/ai/decision_support", timeout=30)
        assert r.status_code == 403, f"{username} expected 403, got {r.status_code}"


# ============ Regression: existing AI actions ============
class TestExistingAIActions:
    @pytest.mark.parametrize("action", ["summarize", "advice", "instructions"])
    def test_existing_actions(self, jyothi, jyothi_case_id, action):
        r = jyothi.post(f"{API}/cases/{jyothi_case_id}/ai/{action}", timeout=TIMEOUT)
        assert r.status_code == 200, f"{action}: {r.status_code} {r.text[:300]}"
        data = r.json()
        assert data["action"] == action
        assert isinstance(data.get("result"), str) and len(data["result"]) > 0


# ============ Audit log check ============
class TestAuditLog:
    def test_audit_log_recorded(self, admin, jyothi, jyothi_case_id):
        # invoke decision_support to ensure entry exists
        jyothi.post(f"{API}/cases/{jyothi_case_id}/ai/decision_support", timeout=TIMEOUT)
        r = admin.get(f"{API}/admin/audit-logs?action=AI_USED&limit=100", timeout=30)
        assert r.status_code == 200, f"audit list: {r.status_code} {r.text[:300]}"
        data = r.json()
        logs = data.get("audit_logs") or []
        # Look for AI_USED on Case with action=decision_support and matching case id
        matches = []
        for lg in logs[:200]:
            act = lg.get("action") or lg.get("action_type")
            entity = lg.get("entity_type") or lg.get("target_type") or lg.get("entity")
            entity_id = lg.get("entity_id") or lg.get("target_id")
            meta = lg.get("metadata") or lg.get("meta") or lg.get("details") or {}
            if isinstance(meta, str):
                # sometimes serialized
                meta_s = meta
            else:
                meta_s = str(meta)
            if act == "AI_USED" and (entity in ("Case", "case", None)) and entity_id == jyothi_case_id and "decision_support" in meta_s:
                matches.append(lg)
        assert matches, f"No AI_USED/decision_support audit entry for case {jyothi_case_id}"


# ============ Regression: cases endpoints ============
class TestCasesRegression:
    def test_get_cases_list(self, jyothi):
        r = jyothi.get(f"{API}/cases", timeout=30)
        assert r.status_code == 200

    def test_get_case_by_id(self, jyothi, jyothi_case_id):
        r = jyothi.get(f"{API}/cases/{jyothi_case_id}", timeout=30)
        assert r.status_code == 200
        body = r.json()
        # endpoint returns wrapped {case: {...}, clinical_notes, ...}
        case_obj = body.get("case") if isinstance(body, dict) and "case" in body else body
        assert case_obj.get("id") == jyothi_case_id
