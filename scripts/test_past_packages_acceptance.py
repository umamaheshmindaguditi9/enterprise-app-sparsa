"""Iteration 16 acceptance browser test for Add Past Visit -> Packages & dues.

Focus:
- Real backend commit + browser response-loss on first save (CDP response-stage fault)
- Retry same save path (idempotent replay, no duplicate records)
- Photo upload failure then successful retry without re-saving visit payment
- Package/date/payment UI checks + responsive overflow checks
"""

from __future__ import annotations

import asyncio
import base64
import json
from pathlib import Path

from playwright.async_api import async_playwright


SETUP_JSON = Path("/app/test_reports/iteration16_ui_setup.json")
BASE_URL = "https://sparsa-clinic.preview.emergentagent.com"


def _tiny_png() -> bytes:
    # 1x1 PNG
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+X2JYAAAAASUVORK5CYII="
    )


async def run() -> int:
    if not SETUP_JSON.exists():
        print("FAIL: setup fixture missing. Run setup_iteration16_ui_fixture.py first.")
        return 1

    setup = json.loads(SETUP_JSON.read_text(encoding="utf-8"))
    patient_id = setup["patient_id"]
    package_id = setup["package_id"]
    marker = setup["marker"]

    complaint_marker = f"{marker} CDP SAVE"
    clinical_values = {
        "past-clinical-chief-complaint": f"Chief {complaint_marker}",
        "past-clinical-presenting-complaint": "Presenting complaint",
        "past-clinical-past-history": "Past history",
        "past-clinical-family-history-father": "Father history",
        "past-clinical-family-history-mother": "Mother history",
        "past-clinical-family-history-paternal-grandfather": "PGF history",
        "past-clinical-family-history-paternal-grandmother": "PGM history",
        "past-clinical-family-history-maternal-grandfather": "MGF history",
        "past-clinical-family-history-maternal-grandmother": "MGM history",
        "past-clinical-personal-history-appetite": "Good",
        "past-clinical-personal-history-thirst": "Moderate",
        "past-clinical-personal-history-bowels": "Regular",
        "past-clinical-personal-history-urine": "Normal",
        "past-clinical-personal-history-sleep": "Disturbed",
        "past-clinical-personal-history-thermal": "Hot",
        "past-clinical-life-style": "Sedentary",
        "past-clinical-notes": "Clinical notes summary",
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 1024})
        page = await context.new_page()

        page.on("console", lambda msg: print(f"CONSOLE[{msg.type}]: {msg.text}"))

        post_payloads: list[str] = []
        post_response_bodies: list[dict] = []
        request_urls: list[str] = []
        counters = {"past_visit_posts": 0, "photo_upload_posts": 0}

        async def _capture_response(resp):
            try:
                req = resp.request
                if req.method != "POST":
                    return
                if "/api/patients/" in resp.url and "/past-visit" in resp.url and resp.status == 200:
                    post_response_bodies.append(await resp.json())
            except Exception:
                return

        page.on("response", lambda resp: asyncio.create_task(_capture_response(resp)))

        def _capture_request(req):
            if req.method != "POST":
                return
            if "/api/patients/" in req.url and "/past-visit" in req.url:
                counters["past_visit_posts"] += 1
                post_payloads.append(req.post_data or "")
                request_urls.append(req.url)
            if "/api/cases/" in req.url and "/attachments" in req.url:
                counters["photo_upload_posts"] += 1

        page.on("request", _capture_request)

        # First attachment upload should fail; retry should succeed.
        photo_fail_once = {"done": False}

        async def attachment_route(route):
            req = route.request
            if req.method == "POST" and "/api/cases/" in req.url and "/attachments" in req.url and not photo_fail_once["done"]:
                photo_fail_once["done"] = True
                await route.abort(error_code="failed")
                return
            await route.continue_()

        await page.route("**/api/cases/*/attachments", attachment_route)

        print("STEP: login as admin")
        await page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded")
        await page.fill('[data-testid="login-username-input"]', "admin1")
        await page.fill('[data-testid="login-password-input"]', "Password@123")
        await page.click('[data-testid="login-submit-button"]', force=True)
        await page.wait_for_timeout(700)

        print("STEP: open past-visit form")
        await page.goto(f"{BASE_URL}/reception/patients/{patient_id}/past-visit", wait_until="domcontentloaded")
        await page.wait_for_selector('[data-testid="past-visit-form"]', timeout=15000)

        print("STEP: baseline checks")
        baseline_pkg = await page.evaluate(
            """async (pid) => {
                const r = await fetch(`/api/packages/${pid}`, { credentials: 'include' });
                const d = await r.json();
                return { status: r.status, package: d.package };
            }""",
            package_id,
        )
        if baseline_pkg.get("status") != 200:
            raise RuntimeError(f"Failed baseline package fetch: {baseline_pkg}")
        baseline_transactions = len(baseline_pkg["package"].get("transactions", []))

        # CDP response-stage fault injection for first successful past-visit POST.
        print("STEP: enable CDP response-loss for first 200 past-visit response")
        cdp = await context.new_cdp_session(page)
        await cdp.send(
            "Fetch.enable",
            {
                "patterns": [
                    {
                        "urlPattern": "*/api/patients/*/past-visit",
                        "requestStage": "Response",
                    }
                ]
            },
        )
        cdp_state = {"dropped": False, "status": None, "response_body": None}

        async def on_paused(params):
            rid = params["requestId"]
            status = params.get("responseStatusCode")
            if cdp_state["dropped"]:
                await cdp.send("Fetch.continueResponse", {"requestId": rid})
                return
            if status == 200 and "/api/patients/" in params.get("request", {}).get("url", "") and "/past-visit" in params.get("request", {}).get("url", ""):
                cdp_state["status"] = status
                try:
                    body = await cdp.send("Fetch.getResponseBody", {"requestId": rid})
                    raw = body.get("body", "")
                    if body.get("base64Encoded"):
                        raw = base64.b64decode(raw).decode("utf-8", "ignore")
                    cdp_state["response_body"] = json.loads(raw) if raw else None
                except Exception:
                    cdp_state["response_body"] = None
                cdp_state["dropped"] = True
                await cdp.send("Fetch.failRequest", {"requestId": rid, "errorReason": "Failed"})
                await cdp.send("Fetch.disable")
                return
            await cdp.send("Fetch.continueResponse", {"requestId": rid})

        cdp.on("Fetch.requestPaused", lambda p: asyncio.create_task(on_paused(p)))

        print("STEP: fill FIR + all 17 clinical fields + package payment")
        await page.fill('[data-testid="chief-complaint-input"]', complaint_marker)
        await page.fill('[data-testid="past-medicine-0"]', "Belladonna")
        await page.fill('[data-testid="past-potency-0"]', "30C")
        await page.fill('[data-testid="past-dosage-0"]', "4 pills")
        await page.fill('[data-testid="past-frequency-0"]', "TID")
        await page.fill('[data-testid="past-days-0"]', "5")

        for test_id, value in clinical_values.items():
            await page.fill(f'[data-testid="{test_id}"]', value)

        await page.set_input_files('[data-testid="photo-file-input"]', {
            "name": "tiny.png",
            "mimeType": "image/png",
            "buffer": _tiny_png(),
        })
        await page.wait_for_selector('[data-testid="fir-photo-ready"]', timeout=5000)

        await page.click('[data-testid="past-billing-package"]', force=True)
        await page.wait_for_selector('[data-testid="past-package-fields"]', timeout=10000)
        await page.select_option('[data-testid="past-package-select"]', value=package_id)
        await page.fill('[data-testid="past-package-payment-amount"]', "123")
        await page.fill('[data-testid="past-package-payment-reference"]', f"{marker}-CDP-REF")
        await page.fill('[data-testid="past-package-payment-date"]', "2024-09-10")
        await page.select_option('[data-testid="past-package-payment-mode"]', value="CASH")
        await page.check('[data-testid="past-package-medicines-taken"]', force=True)

        # Responsive overflow checks with package selected
        print("STEP: responsive overflow checks")
        for width in (320, 768, 1024, 1440):
            await page.set_viewport_size({"width": width, "height": 1024})
            await page.wait_for_timeout(150)
            dims = await page.evaluate(
                """() => ({
                    bodyScroll: document.body.scrollWidth,
                    bodyClient: document.body.clientWidth,
                    rootScroll: document.documentElement.scrollWidth,
                    rootClient: document.documentElement.clientWidth
                })"""
            )
            if dims["bodyScroll"] > dims["bodyClient"] + 2 or dims["rootScroll"] > dims["rootClient"] + 2:
                raise RuntimeError(f"Horizontal overflow detected at width {width}: {dims}")

        await page.set_viewport_size({"width": 1440, "height": 1024})

        print("STEP: first save with response drop")
        await page.click('[data-testid="save-past-visit-btn"]', force=True)
        await page.wait_for_selector('[data-testid="past-package-save-pending"]', timeout=15000)

        if cdp_state["status"] != 200 or not cdp_state["dropped"]:
            raise RuntimeError(f"CDP response-drop did not capture real 200 response: {cdp_state}")

        # committed before retry
        print("STEP: verify committed record exists before retry")
        timeline_before_retry = await page.evaluate(
            """async (pid, marker) => {
                const r = await fetch(`/api/patients/${pid}/timeline`, { credentials: 'include' });
                const d = await r.json();
                const rows = (d.timeline || []).filter(x => (x.case?.complaint_text || '') === marker);
                return { status: r.status, matches: rows.map(x => x.case?.id) };
            }""",
            patient_id,
            complaint_marker,
        )
        if timeline_before_retry.get("status") != 200 or len(timeline_before_retry.get("matches", [])) != 1:
            raise RuntimeError(f"Expected exactly one committed case before retry, got: {timeline_before_retry}")

        if not await page.locator('[data-testid="visit-date"]').is_disabled():
            raise RuntimeError("Fields expected disabled while pending package save")

        print("STEP: retry same save")
        await page.click('[data-testid="save-past-visit-btn"]', force=True)
        await page.wait_for_selector('[data-testid="past-photo-warning"]', timeout=20000)

        if counters["past_visit_posts"] != 2:
            raise RuntimeError(f"Expected exactly 2 past-visit POSTs, got {counters['past_visit_posts']}")
        if len(post_payloads) != 2 or post_payloads[0] != post_payloads[1]:
            raise RuntimeError("Retry request body mismatch; expected exact same payload and idempotency key")

        first_case = (cdp_state.get("response_body") or {}).get("case", {}).get("id")
        if not first_case:
            raise RuntimeError("Could not extract first committed case id from dropped 200 response")

        timeline_after_retry = await page.evaluate(
            """async (pid, marker) => {
                const r = await fetch(`/api/patients/${pid}/timeline`, { credentials: 'include' });
                const d = await r.json();
                const rows = (d.timeline || []).filter(x => (x.case?.complaint_text || '') === marker);
                return { status: r.status, matches: rows.map(x => x.case?.id) };
            }""",
            patient_id,
            complaint_marker,
        )
        if timeline_after_retry.get("status") != 200:
            raise RuntimeError(f"Timeline fetch failed after retry: {timeline_after_retry}")
        unique_case_ids = sorted(set(timeline_after_retry.get("matches", [])))
        if unique_case_ids != [first_case]:
            raise RuntimeError(f"Retry should return same case only. expected={first_case}, got={unique_case_ids}")

        if not await page.locator('[data-testid="save-past-visit-btn"]').is_disabled():
            raise RuntimeError("Save button should stay disabled after case save")

        print("STEP: photo retry without re-submitting payment")
        await page.click('[data-testid="past-retry-photo"]', force=True)
        await page.wait_for_timeout(1800)
        if await page.locator('[data-testid="past-photo-warning"]').count() != 0:
            raise RuntimeError("Photo warning still present after retry")

        if counters["past_visit_posts"] != 2:
            raise RuntimeError("Past-visit save was re-submitted during photo retry")
        if counters["photo_upload_posts"] < 2:
            raise RuntimeError(f"Expected two photo upload attempts (fail+success), got {counters['photo_upload_posts']}")

        print("STEP: final backend assertions")
        details = await page.evaluate(
            """async (caseId, packageId) => {
                const caseResp = await fetch(`/api/cases/${caseId}`, { credentials: 'include' });
                const caseData = await caseResp.json();
                const attResp = await fetch(`/api/cases/${caseId}/attachments`, { credentials: 'include' });
                const attData = await attResp.json();
                const pkgResp = await fetch(`/api/packages/${packageId}`, { credentials: 'include' });
                const pkgData = await pkgResp.json();
                return {
                    case_status: caseResp.status,
                    att_status: attResp.status,
                    pkg_status: pkgResp.status,
                    caseData,
                    attData,
                    pkgData,
                };
            }""",
            first_case,
            package_id,
        )
        if details["case_status"] != 200:
            raise RuntimeError(f"Case details fetch failed: {details['case_status']}")
        if details["att_status"] != 200:
            raise RuntimeError(f"Attachment list fetch failed: {details['att_status']}")
        if details["pkg_status"] != 200:
            raise RuntimeError(f"Package details fetch failed: {details['pkg_status']}")

        case_data = details["caseData"]
        payment = case_data.get("payment") or {}
        notes = case_data.get("clinical_notes") or {}
        rx = case_data.get("prescriptions") or []
        atts = details["attData"].get("attachments") or []
        pkg = details["pkgData"].get("package") or {}

        if case_data.get("case", {}).get("id") != first_case:
            raise RuntimeError("Unexpected case id in final details")
        if payment.get("kind") != "PACKAGE_BILL":
            raise RuntimeError(f"Expected PACKAGE_BILL payment, got: {payment}")
        if len(rx) != 1:
            raise RuntimeError(f"Expected one prescription version, got {len(rx)}")
        if notes.get("case_id") != first_case:
            raise RuntimeError("Clinical notes not linked to expected case")
        if len(atts) != 1:
            raise RuntimeError(f"Expected exactly one attachment, got {len(atts)}")

        case_txs = [t for t in pkg.get("transactions", []) if t.get("case_id") == first_case and float(t.get("amount", 0)) > 0]
        if len(case_txs) != 1:
            raise RuntimeError(f"Expected one positive ledger transaction for case, got {len(case_txs)}")

        # package terms unchanged except financials
        after_pkg = pkg
        for key in ("start_date", "end_date", "patient_id", "name", "duration_value"):
            if after_pkg.get(key) != baseline_pkg["package"].get(key):
                raise RuntimeError(f"Package term changed unexpectedly for {key}")
        if len(after_pkg.get("transactions", [])) != baseline_transactions + 1:
            raise RuntimeError("Unexpected number of package transactions after save")

        # option/span warning triage
        option_children = await page.evaluate(
            """() => Array.from(document.querySelectorAll('option'))
                .filter(o => o.children && o.children.length > 0)
                .map(o => ({text: o.textContent, childCount: o.children.length}))"""
        )
        if option_children:
            print(f"WARN: option elements with children found: {option_children}")
        else:
            print("PASS: no option elements with nested children in app DOM")

        # Get error messages using specific selectors
        error_text = await page.evaluate("""() => {
        const errorElements = Array.from(document.querySelectorAll('.error, [class*=\"error\"], [id*=\"error\"]'));
        return errorElements.map(el => el.textContent).join(', ');
        }""")
        if error_text:
            print(f"Found error message: {error_text}")
        else:
            print("No error messages found on the page")

        print("PASS: Iteration16 acceptance browser flow complete")
        await context.close()
        await browser.close()
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
