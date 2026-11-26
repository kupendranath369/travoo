# Phase-1 smoke/regression: health, auth, trips search/detail/publish, bookings, hire, admin
import os
import uuid
from datetime import datetime, timedelta

import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

DRIVER = ("driver@travoo.in", "Driver@2026")
PASSENGER = ("passenger@travoo.in", "Passenger@2026")
ADMIN = ("admin@travoo.in", "VOuKjR_Jtv72uS2x")

BLR = {"loc_id": "in_bengaluru_karnataka", "name": "Bengaluru", "lat": 12.9716, "lng": 77.5946, "state": "Karnataka"}
CHN = {"loc_id": "in_chennai_tamil_nadu", "name": "Chennai", "lat": 13.0827, "lng": 80.2707, "state": "Tamil Nadu"}

STATE = {}


_TOK = {}


def login(email, pw):
    if email in _TOK:
        return _TOK[email]
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=30)
    assert r.status_code == 200, r.text
    _TOK[email] = r.json()["token"]
    return _TOK[email]


def H(t):
    return {"Authorization": f"Bearer {t}"}


# Health
def test_health():
    r = requests.get(f"{API}/health", timeout=20)
    assert r.status_code == 200 and r.json().get("status") == "ok"


# Auth
class TestAuth:
    def test_register_requires_consent(self):
        r = requests.post(f"{API}/auth/register", json={"email": f"test_{uuid.uuid4().hex[:6]}@example.com",
                                                        "password": "Passw0rd!x", "name": "TEST_NoConsent", "consent": False}, timeout=30)
        assert r.status_code == 400

    def test_register_login_me(self):
        email = f"test_iter35_{uuid.uuid4().hex[:8]}@example.com"
        r = requests.post(f"{API}/auth/register", json={"email": email, "password": "Passw0rd!x", "name": "TEST_Iter35", "consent": True}, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["token"] and d["user"]["email"] == email and "_id" not in d["user"] and "password_hash" not in d["user"]
        STATE["new_uid"], STATE["new_email"] = d["user"]["user_id"], email
        tok = login(email, "Passw0rd!x")
        me = requests.get(f"{API}/auth/me", headers=H(tok), timeout=30)
        assert me.status_code == 200 and me.json()["email"] == email
        STATE["new_token"] = tok

    def test_duplicate_register(self):
        r = requests.post(f"{API}/auth/register", json={"email": STATE["new_email"], "password": "Passw0rd!x", "name": "TEST_Iter35", "consent": True}, timeout=30)
        assert r.status_code == 409

    def test_login_wrong_pw(self):
        r = requests.post(f"{API}/auth/login", json={"email": PASSENGER[0], "password": "wrong-pass"}, timeout=30)
        assert r.status_code == 401

    def test_login_seeded(self):
        for e, p in (DRIVER, PASSENGER):
            assert login(e, p)

    def test_me_unauth(self):
        assert requests.get(f"{API}/auth/me", timeout=20).status_code == 401


# Trips
class TestTrips:
    def test_search_blr_chn(self):
        r = requests.get(f"{API}/trips/search", params={"from_lat": 12.9716, "from_lng": 77.5946, "to_lat": 13.0827, "to_lng": 80.2707}, timeout=60)
        assert r.status_code == 200, r.text
        rows = r.json()
        rows = rows if isinstance(rows, list) else rows.get("trips", rows.get("results", []))
        assert len(rows) >= 1
        STATE["trip_ids"] = [t["trip_id"] for t in rows]
        assert all("_id" not in t for t in rows)

    def test_trip_detail(self):
        tid = STATE["trip_ids"][0]
        assert requests.get(f"{API}/trips/{tid}", timeout=30).status_code == 401  # auth required
        r = requests.get(f"{API}/trips/{tid}", headers=H(login(*PASSENGER)), timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["trip_id"] == tid and r.json()["driver"]["name"]

    def test_trip_404(self):
        assert requests.get(f"{API}/trips/trip_doesnotexist", headers=H(login(*PASSENGER)), timeout=20).status_code == 404

    def test_publish_trip_as_driver(self):
        tok = login(*DRIVER)
        prof = requests.get(f"{API}/driver/profile", headers=H(tok), timeout=30)
        assert prof.status_code == 200, prof.text
        vehicles = prof.json().get("vehicles") or []
        assert vehicles, prof.json()
        vid = vehicles[0]["vehicle_id"]
        date = (datetime.utcnow() + timedelta(days=12)).strftime("%Y-%m-%d")
        body = {"origin": BLR, "destination": CHN, "pickup_point": "TEST_Majestic", "drop_point": "TEST_Koyambedu",
                "date": date, "time": "06:15", "seats": 2, "price": 500, "vehicle_id": vid, "instant_booking": True, "notes": "TEST_iter35"}
        r = requests.post(f"{API}/trips", json=body, headers=H(tok), timeout=90)
        assert r.status_code == 200, r.text
        t = r.json()
        assert t["seats_available"] == 2 and t["price"] == 500
        STATE["my_trip"], STATE["driver_token"] = t["trip_id"], tok
        g = requests.get(f"{API}/trips/{t['trip_id']}", headers=H(tok), timeout=30)
        assert g.status_code == 200

    def test_publish_forbidden_for_non_driver(self):
        r = requests.post(f"{API}/trips", json={}, headers=H(STATE["new_token"]), timeout=30)
        assert r.status_code in (403, 422)


# Bookings
class TestBookings:
    def test_book_and_cancel(self):
        tid, tok = STATE["my_trip"], STATE["new_token"]
        r = requests.post(f"{API}/bookings", json={"trip_id": tid, "seats": 1}, headers=H(tok), timeout=30)
        assert r.status_code == 200, r.text
        b = r.json()
        assert b["status"] == "confirmed" and b["fare_total"] == 500
        t = requests.get(f"{API}/trips/{tid}", headers=H(tok), timeout=30).json()
        assert t["seats_available"] == 1
        dup = requests.post(f"{API}/bookings", json={"trip_id": tid, "seats": 1}, headers=H(tok), timeout=30)
        assert dup.status_code == 409
        mine = requests.get(f"{API}/bookings/mine", headers=H(tok), timeout=30)
        assert mine.status_code == 200 and any(x["booking_id"] == b["booking_id"] for x in mine.json())
        c = requests.post(f"{API}/bookings/{b['booking_id']}/cancel", json={"reason": "TEST"}, headers=H(tok), timeout=30)
        assert c.status_code == 200, c.text
        g = requests.get(f"{API}/bookings/{b['booking_id']}", headers=H(tok), timeout=30)
        assert g.status_code == 200 and g.json().get("status", g.json().get("booking", {}).get("status")) in ("cancelled", "cancelled_by_passenger")
        t = requests.get(f"{API}/trips/{tid}", headers=H(tok), timeout=30).json()
        assert t["seats_available"] == 2

    def test_cannot_book_own_trip(self):
        r = requests.post(f"{API}/bookings", json={"trip_id": STATE["my_trip"], "seats": 1}, headers=H(STATE["driver_token"]), timeout=30)
        assert r.status_code == 400

    def test_passenger_book_seeded_and_cancel(self):
        tok = login(*PASSENGER)
        r = requests.post(f"{API}/bookings", json={"trip_id": STATE["my_trip"], "seats": 1}, headers=H(tok), timeout=30)
        assert r.status_code == 200, r.text
        bid = r.json()["booking_id"]
        c = requests.post(f"{API}/bookings/{bid}/cancel", json={"reason": "TEST"}, headers=H(tok), timeout=30)
        assert c.status_code == 200


# Hire
class TestHire:
    def test_hire_drivers(self):
        date = (datetime.utcnow() + timedelta(days=3)).strftime("%Y-%m-%d")
        r = requests.get(f"{API}/hire/drivers", params={"lat": 12.9716, "lng": 77.5946, "date": date}, headers=H(STATE["new_token"]), timeout=30)
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), list)

    def test_hire_misc_endpoints(self):
        tok = H(STATE["new_token"])
        date = (datetime.utcnow() + timedelta(days=3)).strftime("%Y-%m-%d")
        for path, params in [("/hire/bookings", None), ("/hire/requests", None), ("/hire/favourites", None), ("/pro/me", None),
                             ("/lgd/status", None), ("/lgd/states", None), ("/lgd/subdistricts/search", {"q": "Bangalore"}),
                             ("/hire/identify-taluk", {"loc_id": "in_bengaluru_karnataka"})]:
            r = requests.get(f"{API}{path}", params=params, headers=tok, timeout=60)
            assert r.status_code < 500, f"{path} -> {r.status_code} {r.text[:200]}"
            STATE.setdefault("hire_codes", {})[path] = r.status_code
        sd = requests.get(f"{API}/lgd/subdistricts/search", params={"q": "Bangalore"}, timeout=30).json()
        if sd:
            code = sd[0]["code"]
            r = requests.get(f"{API}/hire/local-drivers", params={"subdistrict_code": code, "date": date, "time": "10:00"}, headers=tok, timeout=60)
            assert r.status_code == 200, r.text
            assert "local" in r.json()


# Admin
class TestAdmin:
    def test_admin_login_and_stats(self):
        r = requests.post(f"{API}/admin/auth/login", json={"email": ADMIN[0], "password": ADMIN[1]}, timeout=30)
        assert r.status_code == 200, r.text
        tok = r.json()["token"]
        s = requests.get(f"{API}/admin/stats", headers=H(tok), timeout=30)
        assert s.status_code in (200, 403), s.text
        STATE["admin_stats_code"] = s.status_code
        if s.status_code == 403:
            pytest.fail(f"admin/stats blocked: {s.text}")
        assert isinstance(s.json(), dict)

    def test_admin_via_app_login_blocked(self):
        r = requests.post(f"{API}/auth/login", json={"email": ADMIN[0], "password": ADMIN[1]}, timeout=30)
        assert r.status_code == 403


# Cleanup: cancel published TEST trip
def test_zz_cleanup():
    if STATE.get("my_trip"):
        r = requests.post(f"{API}/trips/{STATE['my_trip']}/cancel", json={"reason": "TEST cleanup"}, headers=H(STATE["driver_token"]), timeout=30)
        assert r.status_code == 200, r.text
    print("STATE", {k: v for k, v in STATE.items() if "token" not in k})
