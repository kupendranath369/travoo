"""TRAVOO backend regression tests (auth, locations, driver verification, trips, bookings, earnings, reviews, chat, tickets, admin)."""
import os
import uuid
import threading
from datetime import datetime, timedelta, timezone

import pytest
import requests

BASE_URL = (os.environ.get("EXPO_BACKEND_URL") or os.environ.get("EXPO_PUBLIC_BACKEND_URL") or "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("EXPO_PUBLIC_BACKEND_URL"):
                BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")
API = f"{BASE_URL}/api"
IST = timezone(timedelta(hours=5, minutes=30))
STATE = {}


def h(tok):
    return {"Authorization": f"Bearer {tok}"}


def login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["token"]


def register(prefix="u"):
    email = f"test_{prefix}_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": "Passw0rd!x", "name": f"TEST_{prefix}",
                                                     "consent": True}, timeout=20)
    assert r.status_code == 200, r.text
    d = r.json()
    return d["token"], d["user"], email


def loc(q):
    r = requests.get(f"{API}/locations/search", params={"q": q}, timeout=20)
    row = r.json()[0]
    return {k: row.get(k) for k in ("loc_id", "name", "type", "district", "state", "pin", "lat", "lng")}


def future(days=3):
    return (datetime.now(IST) + timedelta(days=days)).strftime("%Y-%m-%d")


@pytest.fixture(scope="module")
def admin():
    return login("admin@travoo.in", "TravooAdmin@2026")


@pytest.fixture(scope="module")
def driver(admin):
    """Fresh TEST driver: register -> verify -> admin approve -> vehicle."""
    tok, user, _ = register("drv")
    r = requests.post(f"{API}/driver/verification", headers=h(tok), json={
        "legal_name": "TEST Driver", "phone": "9876543210", "licence_no": "KA0120201234567",
        "licence_expiry": "01-01-2030", "rc_no": "KA01AB9999"})
    assert r.status_code == 200
    STATE["drv_submit_status"] = r.json()["status"]
    # trip creation before approval must 403 (status under_review)
    STATE["drv_uid"] = user["user_id"]
    STATE["drv_tok"] = tok
    return tok


# ---- auth
class TestAuth:
    def test_register_requires_consent(self):
        r = requests.post(f"{API}/auth/register", json={"email": f"test_nc_{uuid.uuid4().hex[:6]}@example.com",
                                                         "password": "Passw0rd!x", "name": "TEST nc", "consent": False})
        assert r.status_code == 400

    def test_register_dup_and_login_me(self):
        tok, user, email = register("auth")
        assert user["email"] == email and "password_hash" not in user
        r = requests.post(f"{API}/auth/register", json={"email": email, "password": "Passw0rd!x", "name": "TEST d", "consent": True})
        assert r.status_code == 409
        tok2 = login(email, "Passw0rd!x")
        me = requests.get(f"{API}/auth/me", headers=h(tok2)).json()
        assert me["user_id"] == user["user_id"]
        assert requests.post(f"{API}/auth/login", json={"email": email, "password": "wrongpass"}).status_code == 401

    def test_register_mixed_case_email_login(self):
        email = f"TEST_Mixed_{uuid.uuid4().hex[:6]}@Example.com"
        r = requests.post(f"{API}/auth/register", json={"email": email, "password": "Passw0rd!x", "name": "TEST mc", "consent": True})
        assert r.status_code == 200
        r2 = requests.post(f"{API}/auth/login", json={"email": email, "password": "Passw0rd!x"})
        assert r2.status_code == 200, f"mixed-case login failed: {r2.status_code}"

    def test_update_me_upi_validation(self):
        tok, _, _ = register("upi")
        assert requests.put(f"{API}/me", headers=h(tok), json={"upi_id": "bad-upi"}).status_code == 400
        r = requests.put(f"{API}/me", headers=h(tok), json={"upi_id": "test.user@okaxis", "language": "hi"})
        assert r.status_code == 200 and r.json()["upi_id"] == "test.user@okaxis" and r.json()["language"] == "hi"


# ---- locations
class TestLocations:
    @pytest.mark.parametrize("q", ["Bengaluru", "Bangalore", "ಬೆಂಗಳೂರು", "बेंगलुरु"])
    def test_bengaluru_aliases(self, q):
        rows = requests.get(f"{API}/locations/search", params={"q": q}).json()
        assert rows and any("Bengaluru" in r["name"] for r in rows[:3]), [r["name"] for r in rows[:3]]

    def test_pin_prefix(self):
        rows = requests.get(f"{API}/locations/search", params={"q": "5600"}).json()
        assert rows and all((r.get("pin") or "").startswith("5600") for r in rows)

    def test_osm_village(self):
        r = requests.get(f"{API}/locations/osm", params={"q": "Hampi"}, timeout=30)
        assert r.status_code == 200 and isinstance(r.json(), list) and r.json()
        assert "_id" not in r.json()[0]


# ---- driver verification / trips / bookings / earnings
class TestDriverFlow:
    def test_trip_forbidden_before_approval(self, driver):
        assert STATE["drv_submit_status"] in ("under_review", "approved")
        v = requests.post(f"{API}/vehicles", headers=h(driver), json={"make": "Maruti", "model": "Ertiga", "vtype": "muv",
                                                                       "reg_no": "KA01TE1234", "seats": 6, "ac": True}).json()
        STATE["veh"] = v["vehicle_id"]
        if STATE["drv_submit_status"] == "under_review":
            r = requests.post(f"{API}/trips", headers=h(driver), json=self._trip_body(future(3), True))
            assert r.status_code == 403

    def _trip_body(self, date, instant, seats=3, price=700):
        return {"origin": loc("Bengaluru"), "destination": loc("Chennai"), "pickup_point": "TEST Silk Board",
                "drop_point": "TEST Koyambedu", "date": date, "time": "09:00", "seats": seats, "price": price,
                "vehicle_id": STATE["veh"], "instant_booking": instant}

    def test_admin_approves_driver(self, admin, driver):
        pend = requests.get(f"{API}/admin/drivers", headers=h(admin)).json()
        if STATE["drv_submit_status"] == "under_review":
            assert any(u["user_id"] == STATE["drv_uid"] for u in pend)
        r = requests.post(f"{API}/admin/drivers/{STATE['drv_uid']}/review", headers=h(admin), json={"decision": "approved"})
        assert r.status_code == 200
        assert requests.get(f"{API}/auth/me", headers=h(driver)).json()["driver_status"] == "approved"

    def test_publish_and_search(self, driver):
        d = future(20)
        r = requests.post(f"{API}/trips", headers=h(driver), json=self._trip_body(d, True))
        assert r.status_code == 200, r.text
        t = r.json()
        STATE["trip_i"], STATE["date_i"] = t["trip_id"], d
        assert t["seats_available"] == 3 and t["distance_km"] > 300
        r2 = requests.post(f"{API}/trips", headers=h(driver), json=self._trip_body(future(21), False, seats=3, price=500))
        STATE["trip_r"] = r2.json()["trip_id"]
        o, de = loc("Bengaluru"), loc("Chennai")
        p = {"from_lat": o["lat"], "from_lng": o["lng"], "to_lat": de["lat"], "to_lng": de["lng"]}
        res = requests.get(f"{API}/trips/search", params={**p, "date": d, "sort": "price", "ac": "true", "max_price": 800}).json()
        assert any(x["trip_id"] == STATE["trip_i"] for x in res["trips"])
        none = requests.get(f"{API}/trips/search", params={**p, "date": future(19), "max_price": 701, "ac": "true"}).json()
        if not none["trips"]:
            assert any(a["date"] == d for a in none["alternative_dates"]), none["alternative_dates"]
        assert requests.post(f"{API}/bookings", headers=h(driver), json={"trip_id": STATE["trip_i"], "seats": 1}).status_code == 400

    def test_instant_booking_overbook_dup(self, driver):
        p1, _, _ = register("p1")
        STATE["p1"] = p1
        assert requests.post(f"{API}/bookings", headers=h(p1), json={"trip_id": STATE["trip_i"], "seats": 4}).status_code == 409
        r = requests.post(f"{API}/bookings", headers=h(p1), json={"trip_id": STATE["trip_i"], "seats": 3, "payment_method": "upi"})
        assert r.status_code == 200 and r.json()["status"] == "confirmed" and r.json()["fare_total"] == 2100
        STATE["b1"] = r.json()["booking_id"]
        assert requests.post(f"{API}/bookings", headers=h(p1), json={"trip_id": STATE["trip_i"], "seats": 1}).status_code == 409
        t = requests.get(f"{API}/trips/{STATE['trip_i']}", headers=h(driver)).json()
        assert t["seats_available"] == 0
        bk = requests.get(f"{API}/bookings/{STATE['b1']}", headers=h(p1)).json()
        assert bk["driver"].get("upi_id") is not None and "phone" in bk["driver"]

    def test_request_booking_accept_reject_concurrent(self, driver):
        toks = [register(f"r{i}")[0] for i in range(3)]
        bids = []
        for tk in toks:
            r = requests.post(f"{API}/bookings", headers=h(tk), json={"trip_id": STATE["trip_r"], "seats": 2})
            assert r.status_code == 200 and r.json()["status"] == "pending"
            bids.append(r.json()["booking_id"])
        # messages blocked while pending
        assert requests.post(f"{API}/bookings/{bids[0]}/messages", headers=h(toks[0]), json={"text": "hi"}).status_code == 400
        # concurrent accepts of 2+2 seats on a 3-seat trip: only one should succeed
        codes = []
        th = [threading.Thread(target=lambda b=b: codes.append(requests.post(f"{API}/bookings/{b}/accept", headers=h(driver)).status_code)) for b in bids[:2]]
        [x.start() for x in th]
        [x.join() for x in th]
        assert sorted(codes) == [200, 409], codes
        t = requests.get(f"{API}/trips/{STATE['trip_r']}", headers=h(driver)).json()
        assert t["seats_available"] == 1
        assert requests.post(f"{API}/bookings/{bids[2]}/reject", headers=h(driver), json={"reason": "TEST"}).status_code == 200
        assert requests.get(f"{API}/bookings/{bids[2]}", headers=h(toks[2])).json()["status"] == "rejected"
        # passenger cancels confirmed booking -> seats restored + ledger reversal
        confirmed = [b for b, tk in zip(bids[:2], toks[:2]) if requests.get(f"{API}/bookings/{b}", headers=h(tk)).json()["status"] == "confirmed"][0]
        tk = toks[bids.index(confirmed)]
        assert requests.post(f"{API}/bookings/{confirmed}/messages", headers=h(tk), json={"text": "TEST hello"}).status_code == 200
        assert requests.post(f"{API}/bookings/{confirmed}/cancel", headers=h(tk), json={"reason": "TEST"}).status_code == 200
        t = requests.get(f"{API}/trips/{STATE['trip_r']}", headers=h(driver)).json()
        assert t["seats_available"] == 3
        led = requests.get(f"{API}/earnings", headers=h(driver)).json()["history"]
        assert any(e["booking_id"] == confirmed and e["type"] == "expected_reversed" for e in led)

    def test_trip_cancel_cancels_bookings(self, driver):
        r = requests.post(f"{API}/trips", headers=h(driver), json=self._trip_body(future(22), True, seats=2))
        tid = r.json()["trip_id"]
        tk = register("pc")[0]
        bid = requests.post(f"{API}/bookings", headers=h(tk), json={"trip_id": tid, "seats": 1}).json()["booking_id"]
        assert requests.post(f"{API}/trips/{tid}/cancel", headers=h(driver), json={"reason": "TEST"}).status_code == 200
        assert requests.get(f"{API}/bookings/{bid}", headers=h(tk)).json()["status"] == "cancelled"

    def test_settle_start_complete_earnings_review(self, driver):
        b1, p1 = STATE["b1"], STATE["p1"]
        assert requests.post(f"{API}/reviews", headers=h(p1), json={"booking_id": b1, "target_id": STATE["drv_uid"], "rating": 5}).status_code == 400
        assert requests.post(f"{API}/bookings/{b1}/settle", headers=h(p1), json={"method": "upi"}).status_code == 403
        assert requests.post(f"{API}/bookings/{b1}/settle", headers=h(driver), json={"method": "upi"}).status_code == 200
        assert requests.post(f"{API}/bookings/{b1}/settle", headers=h(driver), json={"method": "upi"}).status_code == 409
        assert requests.post(f"{API}/trips/{STATE['trip_i']}/start", headers=h(driver)).status_code == 200
        assert requests.post(f"{API}/trips/{STATE['trip_i']}/complete", headers=h(driver)).status_code == 200
        assert requests.post(f"{API}/trips/{STATE['trip_i']}/complete", headers=h(driver)).status_code == 400
        assert requests.get(f"{API}/bookings/{b1}", headers=h(p1)).json()["status"] == "completed"
        e = requests.get(f"{API}/earnings", headers=h(driver)).json()
        s = e["summary"]
        assert s["completed"] == 2100 and s["upi"] == 2100 and s["expected"] == 0 and s["confirmed_value"] == 2100, s
        types = [x["type"] for x in e["history"] if x["booking_id"] == b1]
        assert len(types) == len(set(types)), types
        r = requests.post(f"{API}/reviews", headers=h(p1), json={"booking_id": b1, "target_id": STATE["drv_uid"], "rating": 5, "comment": "TEST"})
        assert r.status_code == 200
        assert requests.post(f"{API}/reviews", headers=h(p1), json={"booking_id": b1, "target_id": STATE["drv_uid"], "rating": 4}).status_code == 409
        n = requests.get(f"{API}/notifications", headers=h(p1)).json()
        assert n["items"] and "unread" in n

    def test_concurrent_settle_no_double_count(self, driver):
        r = requests.post(f"{API}/trips", headers=h(driver), json=self._trip_body(future(23), True, seats=1, price=300))
        tid = r.json()["trip_id"]
        tk = register("ps")[0]
        bid = requests.post(f"{API}/bookings", headers=h(tk), json={"trip_id": tid, "seats": 1}).json()["booking_id"]
        before = requests.get(f"{API}/earnings", headers=h(driver)).json()["summary"]["cash"]
        codes = []
        th = [threading.Thread(target=lambda: codes.append(requests.post(f"{API}/bookings/{bid}/settle", headers=h(driver), json={"method": "cash"}).status_code)) for _ in range(4)]
        [x.start() for x in th]
        [x.join() for x in th]
        e = requests.get(f"{API}/earnings", headers=h(driver)).json()
        sett = [s for s in e["settlements"] if s["booking_id"] == bid]
        assert codes.count(200) == 1 and len(sett) == 1, f"codes={codes} settlement_rows={len(sett)}"
        assert e["summary"]["cash"] - before == 300


# ---- instant approval / admin
class TestAdmin:
    def test_instant_driver_approval(self, admin):
        orig = requests.get(f"{API}/admin/settings", headers=h(admin)).json().get("instant_driver_approval", False)
        try:
            assert requests.put(f"{API}/admin/settings", headers=h(admin), json={"instant_driver_approval": True}).json()["instant_driver_approval"] is True
            tok = register("ia")[0]
            r = requests.post(f"{API}/driver/verification", headers=h(tok), json={
                "legal_name": "TEST Instant", "phone": "9876500000", "licence_no": "KA0120201111111",
                "licence_expiry": "01-01-2031", "rc_no": "KA01ZZ0001"})
            assert r.json()["status"] == "approved"
        finally:
            requests.put(f"{API}/admin/settings", headers=h(admin), json={"instant_driver_approval": orig})

    def test_suspend_blocks_login(self, admin):
        tok, user, email = register("sus")
        assert requests.post(f"{API}/admin/users/{user['user_id']}/suspend", headers=h(admin), json={"suspended": True}).status_code == 200
        r = requests.post(f"{API}/auth/login", json={"email": email, "password": "Passw0rd!x"})
        assert r.status_code == 403
        STATE["sus_old_token_code"] = requests.get(f"{API}/auth/me", headers=h(tok)).status_code
        requests.post(f"{API}/admin/users/{user['user_id']}/suspend", headers=h(admin), json={"suspended": False})
        assert STATE["sus_old_token_code"] in (401, 403), f"suspended user's existing JWT still works: {STATE['sus_old_token_code']}"

    def test_admin_lists_and_tickets(self, admin):
        for ep in ["stats", "users", "trips", "bookings", "vehicles", "tickets", "reviews"]:
            r = requests.get(f"{API}/admin/{ep}", headers=h(admin))
            assert r.status_code == 200, ep
        tok = register("tk")[0]
        assert requests.get(f"{API}/admin/stats", headers=h(tok)).status_code == 403
        t = requests.post(f"{API}/tickets", headers=h(tok), json={"type": "sos", "subject": "TEST sos", "message": "TEST help me"}).json()
        assert t["priority"] == "high"
        assert any(x["ticket_id"] == t["ticket_id"] for x in requests.get(f"{API}/tickets/mine", headers=h(tok)).json())
        assert requests.post(f"{API}/admin/tickets/{t['ticket_id']}/resolve", headers=h(admin), json={}).status_code in (200, 422)

    def test_popular_routes_add_delete(self, admin):
        r = requests.post(f"{API}/admin/routes", headers=h(admin), json={"origin": loc("Mysuru"), "destination": loc("Ooty"), "price_hint": 400})
        assert r.status_code == 200
        rid = r.json()["route_id"]
        assert any(x["route_id"] == rid for x in requests.get(f"{API}/routes/popular").json())
        requests.delete(f"{API}/admin/routes/{rid}", headers=h(admin))
        assert not any(x["route_id"] == rid for x in requests.get(f"{API}/routes/popular").json())

    def test_review_hide(self, admin):
        revs = [r for r in requests.get(f"{API}/admin/reviews", headers=h(admin)).json() if r.get("comment") == "TEST"]
        if not revs:
            pytest.skip("no TEST review")
        assert requests.delete(f"{API}/admin/reviews/{revs[0]['review_id']}", headers=h(admin)).status_code == 200
