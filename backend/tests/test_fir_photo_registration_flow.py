"""FIR photo registration flow tests (patient creation + patient photo storage + RBAC)."""

import os
import uuid
from io import BytesIO

import pytest
import requests
from PIL import Image


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    raise RuntimeError("REACT_APP_BACKEND_URL is required for preview testing")
API = f"{BASE_URL.rstrip('/')}/api"


def _login(username: str, password: str = "Password@123") -> requests.Session:
    session = requests.Session()
    response = session.post(
        f"{API}/auth/login",
        json={"username": username, "password": password},
        timeout=30,
    )
    assert response.status_code == 200, f"login failed for {username}: {response.status_code} {response.text}"
    return session


def _jpeg_file(size=(1200, 900), color=(80, 140, 200)):
    image = Image.new("RGB", size, color)
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=95)
    buffer.seek(0)
    return ("test-photo.jpg", buffer.getvalue(), "image/jpeg")


@pytest.fixture(scope="session")
def sessions():
    return {
        "reception": _login("reception1"),
        "admin": _login("admin1"),
        "doctor": _login("hemanth"),
        "owner": _login("jyothi"),
    }


def _create_fir(session: requests.Session, doctor_id: str):
    suffix = uuid.uuid4().hex[:8]
    payload = {
        "first_name": f"TEST_FIR_PHOTO_{suffix}",
        "last_name": "Patient",
        "gender": "FEMALE",
        "age": 29,
        "marital_status": "SINGLE",
        "phone": f"9000{suffix[:6]}",
        "address": "FIR photo automation",
        "consulting_doctor_id": doctor_id,
        "sources": ["ONLINE_SEARCH"],
        "chief_complaint": "Seasonal migraine",
        "visit_type": "WALK_IN",
        "preferred_language": "EN",
    }
    response = session.post(f"{API}/patients/fir", json=payload, timeout=30)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["patient"]["id"]
    assert data["case"]["id"]
    return data


# FIR creation and patient photo integration checks
class TestFIRPhotoRegistrationFlow:
    def test_fir_without_photo_creates_patient_and_case(self, sessions):
        created = _create_fir(sessions["reception"], "doctor-hemanth")
        patient_id = created["patient"]["id"]
        case_id = created["case"]["id"]

        patient_get = sessions["reception"].get(f"{API}/patients/{patient_id}", timeout=30)
        assert patient_get.status_code == 200

        timeline = sessions["reception"].get(f"{API}/patients/{patient_id}/timeline", timeout=30)
        assert timeline.status_code == 200
        assert sum(1 for e in timeline.json()["timeline"] if e["case"]["id"] == case_id) == 1

        no_photo = sessions["reception"].get(f"{API}/patients/{patient_id}/photo", timeout=30)
        assert no_photo.status_code == 404

    def test_put_photo_after_fir_returns_compressed_private_jpeg(self, sessions):
        created = _create_fir(sessions["reception"], "doctor-hemanth")
        patient_id = created["patient"]["id"]

        put_response = sessions["reception"].put(
            f"{API}/patients/{patient_id}/photo",
            files={"file": _jpeg_file(size=(2200, 1600))},
            timeout=45,
        )
        assert put_response.status_code == 200, put_response.text
        body = put_response.json()
        assert body["patient_id"] == patient_id

        photo_get = sessions["reception"].get(f"{API}/patients/{patient_id}/photo", timeout=30)
        assert photo_get.status_code == 200
        assert photo_get.headers["content-type"].startswith("image/jpeg")
        assert "no-store" in (photo_get.headers.get("cache-control") or "")

        loaded = Image.open(BytesIO(photo_get.content))
        assert max(loaded.size) <= 800

    def test_doctor_assigned_case_can_view_photo(self, sessions):
        created = _create_fir(sessions["reception"], "doctor-hemanth")
        patient_id = created["patient"]["id"]
        save_photo = sessions["reception"].put(
            f"{API}/patients/{patient_id}/photo",
            files={"file": _jpeg_file()},
            timeout=45,
        )
        assert save_photo.status_code == 200

        doctor_get = sessions["doctor"].get(f"{API}/patients/{patient_id}/photo", timeout=30)
        assert doctor_get.status_code == 200

    def test_doctor_cannot_view_non_assigned_patient_photo(self, sessions):
        created = _create_fir(sessions["reception"], "doctor-jyothi")
        patient_id = created["patient"]["id"]
        save_photo = sessions["reception"].put(
            f"{API}/patients/{patient_id}/photo",
            files={"file": _jpeg_file()},
            timeout=45,
        )
        assert save_photo.status_code == 200

        doctor_get = sessions["doctor"].get(f"{API}/patients/{patient_id}/photo", timeout=30)
        assert doctor_get.status_code == 403

    def test_only_reception_admin_can_put_photo(self, sessions):
        created = _create_fir(sessions["reception"], "doctor-hemanth")
        patient_id = created["patient"]["id"]

        owner_put = sessions["owner"].put(
            f"{API}/patients/{patient_id}/photo",
            files={"file": _jpeg_file()},
            timeout=45,
        )
        assert owner_put.status_code == 403

        doctor_put = sessions["doctor"].put(
            f"{API}/patients/{patient_id}/photo",
            files={"file": _jpeg_file()},
            timeout=45,
        )
        assert doctor_put.status_code == 403

        admin_put = sessions["admin"].put(
            f"{API}/patients/{patient_id}/photo",
            files={"file": _jpeg_file()},
            timeout=45,
        )
        assert admin_put.status_code == 200

    def test_invalid_file_type_returns_422(self, sessions):
        created = _create_fir(sessions["reception"], "doctor-hemanth")
        patient_id = created["patient"]["id"]
        invalid = sessions["reception"].put(
            f"{API}/patients/{patient_id}/photo",
            files={"file": ("bad.txt", b"not an image", "text/plain")},
            timeout=30,
        )
        assert invalid.status_code == 422

    def test_oversize_file_returns_413(self, sessions):
        created = _create_fir(sessions["reception"], "doctor-hemanth")
        patient_id = created["patient"]["id"]
        too_large = sessions["reception"].put(
            f"{API}/patients/{patient_id}/photo",
            files={"file": ("huge.bin", b"A" * (10 * 1024 * 1024 + 1), "application/octet-stream")},
            timeout=60,
        )
        assert too_large.status_code == 413
