"""Iteration 28: Passenger / Driver app mode (account_type + mode_chosen).
Run: cd /app/backend/tests && pytest test_iter28_mode.py -c /dev/null -p no:xdist -v"""
import uuid

import pytest
import requests

from test_travoo_api import API, h
import test_iter15_lgd_local_hire as t

db = t._db()
UIDS: list = []


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    for uid in list(UIDS):
        for c, f in (("pro_drivers", "user_id"), ("driver_documents", "user_id"), ("vehicles", "owner_id"), ("files", "owner_id"),
                     ("notifications", "user_id"), ("users", "user_id")):
            db[c].delete_many({f: uid})


@pytest.fixture(scope="module")
def fresh():
    email = f"test_iter28_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": "Passw0rd!x", "name": "TEST Iter28", "phone": "", "language": "en", "consent": True})
    assert r.status_code == 200, r.text
    d = r.json()
    UIDS.append(d["user"]["user_id"])
    return d


# New email user -> mode not chosen yet
def test_new_user_mode_not_chosen(fresh):
    assert fresh["user"]["mode_chosen"] is False
    assert fresh["user"]["account_type"] == "passenger"
    me = requests.get(f"{API}/auth/me", headers=h(fresh["token"])).json()
    me = me.get("user", me)
    assert me["mode_chosen"] is False


# Switch to driver -> persisted, mode_chosen true
def test_switch_to_driver(fresh):
    r = requests.put(f"{API}/me", headers=h(fresh["token"]), json={"account_type": "driver"})
    assert r.status_code == 200, r.text
    assert r.json()["account_type"] == "driver" and r.json()["mode_chosen"] is True
    assert "password_hash" not in r.json() and "_id" not in r.json()
    me = requests.get(f"{API}/auth/me", headers=h(fresh["token"])).json()
    me = me.get("user", me)
    assert me["account_type"] == "driver" and me["mode_chosen"] is True


def test_switch_back_passenger(fresh):
    r = requests.put(f"{API}/me", headers=h(fresh["token"]), json={"account_type": "passenger"})
    assert r.status_code == 200
    assert r.json()["account_type"] == "passenger" and r.json()["mode_chosen"] is True


def test_invalid_mode_422(fresh):
    r = requests.put(f"{API}/me", headers=h(fresh["token"]), json={"account_type": "admin"})
    assert r.status_code == 422
    r = requests.put(f"{API}/me", headers=h(fresh["token"]), json={"account_type": ""})
    assert r.status_code == 422


# Other profile updates must not touch mode_chosen
def test_other_update_keeps_mode(fresh):
    r = requests.put(f"{API}/me", headers=h(fresh["token"]), json={"bio": "TEST bio"})
    assert r.status_code == 200
    assert r.json()["account_type"] == "passenger" and r.json()["mode_chosen"] is True


def test_unauth_put_me():
    r = requests.put(f"{API}/me", json={"account_type": "driver"})
    assert r.status_code == 401


# Demo accounts not prompted
@pytest.mark.parametrize("email,pw", [("passenger@travoo.in", "Passenger@2026"), ("driver@travoo.in", "Driver@2026")])
def test_demo_not_prompted(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    u = r.json()["user"]
    assert u.get("mode_chosen") is not False
