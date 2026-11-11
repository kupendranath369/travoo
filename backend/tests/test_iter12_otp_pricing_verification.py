"""Iteration 12: mobile OTP (disabled, no MSG91 keys), admin pricing rules + suggested price, manual driver verification (4 docs + 4 fields),
conversations/messages, India place search. Run with -p no:xdist."""
import uuid
from datetime import datetime, timedelta

import pytest
import requests

from test_travoo_api import API, h
from test_iter8_admin_docs_reset import real_image
from test_iter10_capacity_pricing_photo import admin_token, loc, reg

S = {}
VER = {"vehicle_name": "TEST Maruti Swift", "licence_no": "KA0120201234567", "licence_expiry": "01-01-2035", "rc_no": "KA05AB1234"}


def trip_body(vid, seats, price=200, days=6, **kw):
    d = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
    b = {"origin": loc("Bengaluru"), "destination": loc("Mysuru"), "pickup_point": "TEST pickup", "drop_point": "TEST drop",
         "date": d, "time": "10:00", "seats": seats, "price": price, "vehicle_id": vid}
    b.update(kw)
    return b


# ---- OTP endpoints (MSG91 not configured)
class TestOtp:
    def test_status(self):
        d = requests.get(f"{API}/auth/otp/status").json()
        assert d["enabled"] is False and d["countries"][0] == "91"

    def test_send_valid_503(self):
        r = requests.post(f"{API}/auth/otp/send", json={"country_code": "91", "phone": "9876543210"})
        assert r.status_code == 503 and "switched on" in r.json()["detail"]

    def test_send_invalid_400(self):
        r = requests.post(f"{API}/auth/otp/send", json={"country_code": "91", "phone": "12345678"})
        assert r.status_code == 400, r.text

    def test_verify_503(self):
        r = requests.post(f"{API}/auth/otp/verify", json={"country_code": "91", "phone": "9876543210", "otp": "123456"})
        assert r.status_code == 503, r.text

    def test_complete_bad_ticket(self):
        r = requests.post(f"{API}/auth/otp/complete", json={"ticket": "x" * 40, "name": "TEST Otp", "consent": True, "account_type": "passenger"})
        assert r.status_code == 400, r.text

    def test_me_phone_send_503_and_put_me(self):
        S["pax"], S["pax_id"], S["pax_email"] = reg("Pax12")
        r = requests.post(f"{API}/me/phone/send", headers=h(S["pax"]), json={"country_code": "91", "phone": "9876543210"})
        assert r.status_code == 503, r.text
        assert requests.put(f"{API}/me", headers=h(S["pax"]), json={"phone": "12345"}).status_code in (400, 422)
        r = requests.put(f"{API}/me", headers=h(S["pax"]), json={"phone": "9812345678"})
        assert r.status_code == 200 and r.json()["phone"] == "9812345678", r.text

    def test_duplicate_email_409(self):
        r = requests.post(f"{API}/auth/register", json={"email": S["pax_email"], "password": "Passw0rd!x", "name": "TEST dup", "consent": True})
        assert r.status_code == 409


# ---- pricing rules
class TestPricing:
    def test_suggest(self):
        S["adm"] = admin_token()
        S["orig"] = requests.get(f"{API}/admin/settings", headers=h(S["adm"])).json()
        d = requests.get(f"{API}/pricing/suggest", params={"km": 300, "vtype": "sedan", "seats": 3}).json()
        assert d["recommended"] == 700 and d["max"] == 1050, d

    def test_settings_pricing(self):
        assert "pricing" in requests.get(f"{API}/settings").json()
        bad = requests.put(f"{API}/admin/settings", headers=h(S["adm"]), json={"pricing": {"rate_per_km": {"sedan": 500}, "base_fare": 0, "min_fare": 50}})
        assert bad.status_code == 422
        r = requests.put(f"{API}/admin/settings", headers=h(S["adm"]),
                         json={"pricing": {"rate_per_km": {"hatchback": 6, "sedan": 8, "suv": 9, "muv": 9}, "base_fare": 20, "min_fare": 50}})
        assert r.status_code == 200, r.text
        d = requests.get(f"{API}/pricing/suggest", params={"km": 300, "vtype": "sedan", "seats": 3}).json()
        assert d["recommended"] == 820, d
        p = S["orig"].get("pricing") or {"rate_per_km": {"hatchback": 6, "sedan": 7, "suv": 9, "muv": 9}, "base_fare": 0, "min_fare": 50}
        requests.put(f"{API}/admin/settings", headers=h(S["adm"]), json={"pricing": p})
        assert requests.get(f"{API}/pricing/suggest", params={"km": 300, "vtype": "sedan", "seats": 3}).json()["recommended"] == 700


# ---- driver verification (manual)
class TestVerification:
    def test_kinds(self):
        S["drv"], S["drv_id"], S["drv_email"] = reg("Drv12")
        kinds = {k["kind"] for k in requests.get(f"{API}/driver/profile", headers=h(S["drv"])).json()["kinds"]}
        assert {"licence_front", "licence_back", "id_proof", "rc"} <= kinds and "vehicle" not in kinds, kinds

    def test_ai_extract_removed(self):
        assert requests.post(f"{API}/driver/ai-extract", headers=h(S["drv"])).status_code in (404, 405)

    def test_submit_missing_docs(self):
        r = requests.post(f"{API}/driver/verification", headers=h(S["drv"]), json=VER)
        assert r.status_code == 400 and "upload" in r.json()["detail"].lower()

    def test_upload_and_submit(self):
        for i, k in enumerate(["licence_front", "licence_back", "id_proof", "rc"]):
            r = requests.post(f"{API}/driver/documents/{k}", headers=h(S["drv"]),
                              files={"file": ("a.jpg", real_image(400 + i + uuid.uuid4().int % 500), "image/jpeg")}, timeout=120)
            assert r.status_code == 200, (k, r.text)
        r = requests.post(f"{API}/driver/verification", headers=h(S["drv"]), json=VER)
        assert r.status_code == 400 and "mobile" in r.json()["detail"].lower()  # no phone yet
        requests.put(f"{API}/me", headers=h(S["drv"]), json={"phone": "9900112233"})
        for bad in ("31-02-2030", "2030-01-01", "01-01-2020"):
            r = requests.post(f"{API}/driver/verification", headers=h(S["drv"]), json={**VER, "licence_expiry": bad})
            assert r.status_code in (400, 422), (bad, r.text)
        r = requests.post(f"{API}/driver/verification", headers=h(S["drv"]), json=VER)
        assert r.status_code == 200 and r.json()["status"] in ("under_review", "approved"), r.text

    def test_admin_detail_and_approve(self):
        d = requests.get(f"{API}/admin/drivers/{S['drv_id']}/detail", headers=h(S["adm"])).json()
        txt = str(d)
        for v in ("KA0120201234567", "KA05AB1234", "01-01-2035", "TEST Maruti Swift", "9900112233"):
            assert v in txt, v
        r = requests.post(f"{API}/admin/drivers/{S['drv_id']}/review", headers=h(S["adm"]), json={"decision": "approved"})
        assert r.status_code == 200, r.text


# ---- trips with suggested price
class TestTrips:
    def test_vehicle(self):
        r = requests.post(f"{API}/vehicles", headers=h(S["drv"]), json={"make": "Maruti", "model": "Dzire", "vtype": "sedan", "reg_no": "KA05TE1234", "seats": 3})
        assert r.status_code == 200, r.text
        S["vid"] = r.json()["vehicle_id"]

    def test_create_trip_no_fuel(self):
        r = requests.post(f"{API}/trips", headers=h(S["drv"]), json=trip_body(S["vid"], 3, price=5000))
        assert r.status_code == 400 and "maximum" in r.json()["detail"], r.text
        r = requests.post(f"{API}/trips", headers=h(S["drv"]), json=trip_body(S["vid"], 3, price=100))
        assert r.status_code == 200, r.text
        t = r.json()
        S["tid"], S["sug"] = t["trip_id"], t["price_suggestion"]
        assert t["price_suggestion"]["recommended"] >= 50 and "cost_breakdown" not in t

    def test_update_trip_max(self):
        r = requests.put(f"{API}/trips/{S['tid']}", headers=h(S["drv"]), json={"price": S["sug"]["max"] + 50})
        assert r.status_code == 400, r.text
        r = requests.put(f"{API}/trips/{S['tid']}", headers=h(S["drv"]), json={"seats": 1})
        assert r.status_code == 200 and r.json()["price_suggestion"]["seats"] == 1, r.text

    def test_booking_and_chat(self):
        requests.put(f"{API}/trips/{S['tid']}", headers=h(S["drv"]), json={"seats": 3})
        r = requests.post(f"{API}/bookings", headers=h(S["pax"]), json={"trip_id": S["tid"], "seats": 1})
        assert r.status_code == 200, r.text
        S["bid"] = r.json()["booking_id"]
        r = requests.post(f"{API}/bookings/{S['bid']}/messages", headers=h(S["pax"]), json={"text": "TEST hello"})
        assert r.status_code == 200, r.text
        c = requests.get(f"{API}/conversations", headers=h(S["drv"])).json()
        assert c["unread"] >= 1 and any(x["booking_id"] == S["bid"] for x in c["items"])
        msgs = requests.get(f"{API}/bookings/{S['bid']}/messages", headers=h(S["drv"])).json()
        assert msgs[-1]["text"] == "TEST hello"
        assert requests.get(f"{API}/conversations", headers=h(S["drv"])).json()["unread"] == 0
        outsider, _, _ = reg("Outsider12")
        assert requests.get(f"{API}/bookings/{S['bid']}/messages", headers=h(outsider)).status_code in (403, 404)
        assert requests.post(f"{API}/bookings/{S['bid']}/messages", headers=h(outsider), json={"text": "x"}).status_code in (403, 404)

    def test_cleanup(self):
        requests.post(f"{API}/bookings/{S['bid']}/cancel", headers=h(S["pax"]), json={})
        requests.post(f"{API}/trips/{S['tid']}/cancel", headers=h(S["drv"]), json={})


# ---- India place search
@pytest.mark.parametrize("q,expect", [("Kempegowda bus station", "bengal"), ("Port Blair", "port blair"), ("Leh", "leh"),
                                      ("Kohima", "kohima"), ("560001", "bengal"), ("Mumbai CSMT", "mumbai")])
def test_geo_search(q, expect):
    r = requests.get(f"{API}/geo/search", params={"q": q}, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    items = d if isinstance(d, list) else d.get("results", d.get("items", []))
    assert items, f"no results for {q}"
    assert any(expect in str(i).lower() for i in items[:5]), (q, [i.get("name") for i in items[:5]])
    keys = [(i.get("name"), i.get("district"), i.get("state")) for i in items]
    assert len(keys) == len(set(keys)), f"duplicates for {q}: {keys}"
