"""Iter18 health/regression pass after env fixes: auth, locations, trip search/detail, bookings, chat, notifications, admin (TEST admin)."""
import os
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import pytest
import requests
from pymongo import MongoClient

BASE_URL = ""
with open("/app/frontend/.env") as f:
    for line in f:
        if line.startswith("EXPO_PUBLIC_BACKEND_URL"):
            BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")
API = f"{BASE_URL}/api"
IST = timezone(timedelta(hours=5, minutes=30))
STATE = {"bookings": []}


def env_backend(key):
    with open("/app/backend/.env") as f:
        for line in f:
            if line.startswith(key + "="):
                return line.split("=", 1)[1].strip().strip('"')


def h(t):
    return {"Authorization": f"Bearer {t}"}


def login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module")
def passenger():
    return login("passenger@travoo.in", "Passenger@2026")


@pytest.fixture(scope="module")
def driver():
    return login("driver@travoo.in", "Driver@2026")


@pytest.fixture(scope="module")
def mdb():
    c = MongoClient(env_backend("MONGO_URL"))
    yield c[env_backend("DB_NAME")]
    c.close()


@pytest.fixture(scope="module")
def test_admin(mdb):
    """Temporary TEST_ admin (so the real bootstrap admin password is never changed)."""
    uid = "user_test_" + uuid.uuid4().hex[:10]
    email = f"test_admin_{uuid.uuid4().hex[:6]}@example.com"
    pw = "TestAdmin123"
    mdb.users.insert_one({"user_id": uid, "email": email, "name": "TEST_Admin", "role": "admin", "phone": "",
                          "language": "en", "password_hash": bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode(),
                          "must_change_password": True, "created_at": datetime.now(timezone.utc)})
    yield {"uid": uid, "email": email, "pw": pw}
    mdb.users.delete_one({"user_id": uid})
    mdb.admin_sessions.delete_many({"user_id": uid})


# --- health / auth
def test_health():
    r = requests.get(f"{API}/settings", timeout=20)
    assert r.status_code == 200


def test_passenger_login(passenger):
    assert passenger["user"]["email"] == "passenger@travoo.in"
    assert "_id" not in passenger["user"] and "password_hash" not in passenger["user"]
    r = requests.get(f"{API}/auth/me", headers=h(passenger["token"]), timeout=20)
    assert r.status_code == 200 and r.json()["email"] == "passenger@travoo.in"


def test_driver_login(driver):
    assert driver["user"]["email"] == "driver@travoo.in"


def test_bad_login():
    r = requests.post(f"{API}/auth/login", json={"email": "passenger@travoo.in", "password": "wrong-pass1"}, timeout=20)
    assert r.status_code == 401


def test_admin_blocked_on_app_login():
    r = requests.post(f"{API}/auth/login", json={"email": "admin@travoo.in", "password": "VOuKjR_Jtv72uS2x"}, timeout=20)
    assert r.status_code in (401, 403)


# --- locations / trips
def test_location_search():
    for q in ("Bengaluru", "Chennai"):
        r = requests.get(f"{API}/locations/search", params={"q": q}, timeout=20)
        assert r.status_code == 200
        rows = r.json()
        assert rows and rows[0]["name"] == q
        STATE[q] = rows[0]


def test_trip_search_blr_chennai():
    a, b = STATE["Bengaluru"], STATE["Chennai"]
    r = requests.get(f"{API}/trips/search", params={"from_lat": a["lat"], "from_lng": a["lng"], "to_lat": b["lat"], "to_lng": b["lng"]}, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    items = d if isinstance(d, list) else (d.get("items") or d.get("trips") or d.get("results") or [])
    print("search response keys:", list(d.keys()) if isinstance(d, dict) else "list", "count", len(items))
    assert len(items) > 0, "No demo trips Bengaluru->Chennai"
    STATE["trips"] = items


def test_trip_detail(passenger):
    t = STATE["trips"][0]
    tid = t.get("trip_id") or t.get("trip", {}).get("trip_id")
    r = requests.get(f"{API}/trips/{tid}", headers=h(passenger["token"]), timeout=20)
    assert r.status_code == 200, r.text
    assert r.json()["trip_id"] == tid


# --- bookings / chat
def test_create_booking_and_list(passenger):
    me = passenger["user"]["user_id"]
    tid = None
    for t in STATE["trips"]:
        cand = t.get("trip_id")
        d = requests.get(f"{API}/trips/{cand}", headers=h(passenger["token"]), timeout=20).json()
        if d.get("driver_id") != me and d.get("seats_available", 0) >= 1:
            r = requests.post(f"{API}/bookings", headers=h(passenger["token"]), json={"trip_id": cand, "seats": 1, "passenger_names": ["TEST_Rider"]}, timeout=20)
            if r.status_code == 200:
                tid = cand
                STATE["bookings"].append(r.json()["booking_id"])
                STATE["bid"] = r.json()["booking_id"]
                assert r.json()["status"] in ("pending", "confirmed")
                break
            print("booking attempt", cand, r.status_code, r.text[:150])
    assert tid, "Could not create any booking"
    r = requests.get(f"{API}/bookings/mine", headers=h(passenger["token"]), timeout=20)
    assert r.status_code == 200
    d = r.json()
    rows = d if isinstance(d, list) else (d.get("items") or d.get("as_passenger") or [])
    blob = str(d)
    assert STATE["bid"] in blob


def test_chat(passenger):
    bid = STATE["bid"]
    r = requests.post(f"{API}/bookings/{bid}/messages", headers=h(passenger["token"]), json={"text": "TEST_hello"}, timeout=20)
    assert r.status_code == 200, r.text
    r = requests.get(f"{API}/bookings/{bid}/messages", headers=h(passenger["token"]), timeout=20)
    assert r.status_code == 200 and "TEST_hello" in str(r.json())
    r = requests.get(f"{API}/conversations", headers=h(passenger["token"]), timeout=20)
    assert r.status_code == 200


def test_cancel_booking(passenger):
    bid = STATE["bid"]
    r = requests.post(f"{API}/bookings/{bid}/cancel", headers=h(passenger["token"]), json={"reason": "TEST cleanup"}, timeout=20)
    assert r.status_code == 200, r.text
    r = requests.get(f"{API}/bookings/{bid}", headers=h(passenger["token"]), timeout=20)
    assert r.json()["status"].startswith("cancel")


def test_notifications(passenger, driver):
    for u in (passenger, driver):
        r = requests.get(f"{API}/notifications", headers=h(u["token"]), timeout=20)
        assert r.status_code == 200 and "items" in r.json()


def test_driver_endpoints(driver):
    for p in ("/earnings", "/trips/mine", "/driver/profile", "/bookings/mine"):
        r = requests.get(f"{API}{p}", headers=h(driver["token"]), timeout=20)
        assert r.status_code == 200, f"{p}: {r.status_code} {r.text[:200]}"


# --- admin portal
def test_admin_real_login_must_change():
    r = requests.post(f"{API}/admin/auth/login", json={"email": "admin@travoo.in", "password": "VOuKjR_Jtv72uS2x"}, timeout=20)
    assert r.status_code == 200, r.text
    d = r.json()
    print("real admin must_change_password:", d["admin"]["must_change_password"])
    tok = d["token"]
    if d["admin"]["must_change_password"]:
        assert requests.get(f"{API}/admin/stats", headers=h(tok), timeout=20).status_code == 403
    requests.post(f"{API}/admin/auth/logout", headers=h(tok), timeout=20)


def test_admin_forced_change_then_stats(test_admin):
    r = requests.post(f"{API}/admin/auth/login", json={"email": test_admin["email"], "password": test_admin["pw"]}, timeout=20)
    assert r.status_code == 200, r.text
    tok = r.json()["token"]
    assert r.json()["admin"]["must_change_password"] is True
    assert requests.get(f"{API}/admin/stats", headers=h(tok), timeout=20).status_code == 403
    r = requests.post(f"{API}/admin/auth/change-password", headers=h(tok), json={"current_password": test_admin["pw"], "new_password": "TestAdmin456New"}, timeout=20)
    assert r.status_code == 200, r.text
    assert r.json()["must_change_password"] is False
    r = requests.get(f"{API}/admin/stats", headers=h(tok), timeout=20)
    assert r.status_code == 200, r.text
    for p in ("/admin/users", "/admin/drivers", "/admin/passengers", "/admin/rides", "/admin/bookings", "/admin/trips",
              "/admin/notifications", "/admin/activity", "/admin/tickets", "/admin/reviews", "/admin/settings", "/admin/featured",
              "/admin/licence-verifications", "/admin/hire-bookings", "/admin/pro-drivers", "/admin/locations/missing", "/admin/vehicles"):
        rr = requests.get(f"{API}{p}", headers=h(tok), timeout=30)
        assert rr.status_code == 200, f"{p}: {rr.status_code} {rr.text[:200]}"
