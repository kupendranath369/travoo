"""Iteration 31 (Travoo light UI redesign): register phone validation, mode switch, pro settings outstation, core regression."""
import uuid

import pytest
import requests

from test_travoo_api import API, h
import test_iter15_lgd_local_hire as t

db = t._db()
CREATED = []


def reg(phone=None, **extra):
    email = f"test_iter31_{uuid.uuid4().hex[:8]}@example.com"
    body = {"email": email, "password": "Passw0rd!x", "name": "TEST_Iter31", "consent": True, **extra}
    if phone is not None:
        body["phone"] = phone
    r = requests.post(f"{API}/auth/register", json=body, timeout=20)
    if r.status_code == 200:
        CREATED.append(r.json()["user"]["user_id"])
    return r


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    for uid in CREATED:
        for c, f in (("pro_drivers", "user_id"), ("notifications", "user_id"), ("user_sessions", "user_id"), ("users", "user_id")):
            db[c].delete_many({f: uid})


# Register: mobile number optional + validated
@pytest.mark.parametrize("phone", ["12345", "5876543210", "98765432101", "abcdefghij"])
def test_register_invalid_phone_400(phone):
    r = reg(phone)
    assert r.status_code == 400, r.text
    assert "mobile" in r.json()["detail"].lower()


def test_register_empty_phone_ok():
    r = reg("")
    assert r.status_code == 200, r.text
    assert r.json()["user"].get("phone", "") in ("", None)


def test_register_no_phone_field_ok():
    assert reg().status_code == 200


def test_register_valid_phone_persisted():
    r = reg("9876543210")
    assert r.status_code == 200, r.text
    tok = r.json()["token"]
    me = requests.get(f"{API}/auth/me", headers=h(tok)).json()
    me = me.get("user", me)
    assert "3210" in (me.get("phone") or "")


def test_register_missing_consent_400():
    assert reg("9876543210", consent=False).status_code == 400


# Mode switch passenger <-> driver
def test_mode_switch_roundtrip():
    tok = reg().json()["token"]
    for m in ("driver", "passenger"):
        r = requests.put(f"{API}/me", headers=h(tok), json={"account_type": m})
        assert r.status_code == 200, r.text
        me = requests.get(f"{API}/auth/me", headers=h(tok)).json()
        assert me.get("user", me)["account_type"] == m


# Pro settings require a pro profile
def test_pro_settings_without_profile():
    tok = reg().json()["token"]
    r = requests.put(f"{API}/pro/settings", headers=h(tok), json={"acceptOutstationTrips": True})
    assert r.status_code in (400, 403, 404), r.text
