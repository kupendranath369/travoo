"""Iteration 27: MSG91 OTP off -> email-only registration; mobile number not required for local driver / carpool verification.
Run: cd /app/backend/tests && pytest test_iter27_otp_off.py -c /dev/null -p no:xdist -v"""
import uuid

import pytest
import requests

from test_travoo_api import API, h
import test_iter25_local_driver_redesign as b25

UIDS = b25.UIDS
db = b25.db


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    for uid in list(UIDS):
        for c, f in (("pro_drivers", "user_id"), ("driver_documents", "user_id"), ("vehicles", "owner_id"), ("files", "owner_id"),
                     ("notifications", "user_id"), ("users", "user_id")):
            db[c].delete_many({f: uid})


# OTP status
def test_otp_status_disabled():
    r = requests.get(f"{API}/auth/otp/status")
    assert r.status_code == 200
    assert r.json()["enabled"] is False


# Email register + login without phone
def test_email_register_login_no_phone():
    email = f"test_iter27_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": "Passw0rd!x", "name": "TEST Iter27", "phone": "", "language": "en", "consent": True})
    assert r.status_code == 200, r.text
    d = r.json()
    UIDS.append(d["user"]["user_id"])
    assert d["user"]["email"] == email and not d["user"].get("phone")
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": "Passw0rd!x"})
    assert r.status_code == 200, r.text
    assert r.json()["user"]["user_id"] == d["user"]["user_id"]
    me = requests.get(f"{API}/auth/me", headers=h(r.json()["token"]))
    assert me.status_code == 200


def test_register_requires_consent():
    r = requests.post(f"{API}/auth/register", json={"email": f"test_iter27_{uuid.uuid4().hex[:8]}@example.com", "password": "Passw0rd!x",
                                                    "name": "TEST NoConsent", "phone": "", "language": "en", "consent": False})
    assert r.status_code in (400, 422)


# Local driver register without phone
def test_pro_register_without_phone():
    tok, uid = b25.new_user("NoPhone27", phone=False)
    # without docs -> docs error, not phone error
    r = requests.post(f"{API}/pro/register", headers=h(tok), json=b25.reg_body())
    assert r.status_code == 400 and "mobile" not in r.json()["detail"].lower(), r.text
    b25.docs(tok)
    r = requests.post(f"{API}/pro/register", headers=h(tok), json=b25.reg_body())
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "under_review"
    me = requests.get(f"{API}/pro/me", headers=h(tok))
    assert me.status_code == 200
    assert me.json()["personal"]["phone_ok"] is False


def test_pro_register_empty_languages_422():
    tok, uid = b25.new_user("NoLang27", phone=False)
    b25.docs(tok)
    r = requests.post(f"{API}/pro/register", headers=h(tok), json=b25.reg_body(languages=[]))
    assert r.status_code == 422


# Carpool verification without phone
def test_carpool_verification_without_phone():
    tok, uid = b25.new_user("Carpool27", phone=False)
    r = requests.post(f"{API}/driver/verification", headers=h(tok), json={"vehicle_name": "TEST Swift", "licence_no": "KA0120201234567",
                                                                          "licence_expiry": "01-01-2035", "rc_no": "KA01AB1234"})
    assert r.status_code == 400 and "mobile" not in r.json()["detail"].lower(), r.text  # missing docs
    for k in db.files.distinct("kind", {}) if False else []:
        pass
    kinds = requests.get(f"{API}/driver/profile", headers=h(tok)).json()["missing"]
    for k in kinds:
        assert b25.upload(tok, k).status_code == 200
    r = requests.post(f"{API}/driver/verification", headers=h(tok), json={"vehicle_name": "TEST Swift", "licence_no": "KA0120201234567",
                                                                          "licence_expiry": "01-01-2035", "rc_no": "KA01AB1234"})
    assert r.status_code == 200, r.text
    st = requests.get(f"{API}/driver/profile", headers=h(tok)).json()["status"]
    assert st in ("under_review", "approved")


def test_carpool_expired_licence_still_validated():
    tok, uid = b25.new_user("Expired27", phone=False)
    for k in requests.get(f"{API}/driver/profile", headers=h(tok)).json()["missing"]:
        assert b25.upload(tok, k).status_code == 200
    r = requests.post(f"{API}/driver/verification", headers=h(tok), json={"vehicle_name": "TEST Swift", "licence_no": "KA0120201234567",
                                                                          "licence_expiry": "01-01-2020", "rc_no": "KA01AB1234"})
    assert r.status_code == 400 and "expired" in r.json()["detail"].lower(), r.text
