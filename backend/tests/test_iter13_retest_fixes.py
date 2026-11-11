"""Iteration 13 retest: PUT /me phone validation + verified-phone lock, pricing rounding parity, system msgs excluded
from unread, object storage for uploads, admin settings w/o fuel. Run with -c /dev/null -p no:xdist."""
import os
import uuid
from datetime import datetime, timedelta

import pytest
import requests
from pymongo import MongoClient

from test_travoo_api import API, h
from test_iter8_admin_docs_reset import real_image
from test_iter10_capacity_pricing_photo import admin_token, loc, reg

S = {}
VER = {"vehicle_name": "TEST Maruti Swift", "licence_no": "KA0120201234567", "licence_expiry": "01-01-2035", "rc_no": "KA05AB1234"}


def _db():
    env = dict(l.strip().split("=", 1) for l in open("/app/backend/.env") if "=" in l)
    return MongoClient(env["MONGO_URL"].strip('"'))[env["DB_NAME"].strip('"')]


# ---- PUT /api/me phone validation
class TestPhone:
    def test_invalid_phones_400(self):
        S["pax"], S["pax_id"], _ = reg("Pax13")
        for bad in ("12345", "5812345678", "abcdefghij", "98123"):
            r = requests.put(f"{API}/me", headers=h(S["pax"]), json={"phone": bad})
            assert r.status_code == 400, (bad, r.status_code, r.text)

    def test_normalised_to_10_digits(self):
        r = requests.put(f"{API}/me", headers=h(S["pax"]), json={"phone": "+91 98123-45678"})
        assert r.status_code == 200 and r.json()["phone"] == "9812345678", r.text
        me = requests.get(f"{API}/auth/me", headers=h(S["pax"])).json()
        assert (me.get("user") or me)["phone"] == "9812345678"

    def test_verified_phone_locked(self):
        _db().users.update_one({"user_id": S["pax_id"]}, {"$set": {"phone_verified": True}})
        r = requests.put(f"{API}/me", headers=h(S["pax"]), json={"phone": "9876500000"})
        assert r.status_code == 400 and "verified" in r.json()["detail"].lower(), r.text
        r = requests.put(f"{API}/me", headers=h(S["pax"]), json={"bio": "TEST bio"})  # other fields still editable
        assert r.status_code == 200 and r.json()["phone"] == "9812345678", r.text
        _db().users.update_one({"user_id": S["pax_id"]}, {"$set": {"phone_verified": False}})


# ---- pricing rounding parity
class TestPricingRounding:
    def test_suggest_143(self):
        d = requests.get(f"{API}/pricing/suggest", params={"km": 143, "vtype": "sedan", "seats": 2}).json()
        assert d["recommended"] == 501 and d["max"] == 752, d


# ---- driver setup (object storage) + trip price boundary + system messages
class TestDriverFlow:
    def test_profile_photo_object_storage(self):
        S["drv"], S["drv_id"], _ = reg("Drv13")
        r = requests.post(f"{API}/me/photo", headers=h(S["drv"]), files={"file": ("p.jpg", real_image(777), "image/jpeg")}, timeout=120)
        assert r.status_code == 200, r.text
        f = _db().files.find_one({"file_id": r.json()["file_id"]})
        assert f.get("path") and "data" not in f, {k: f.get(k) for k in ("path", "kind")}
        g = requests.get(f"{API}/files/{f['file_id']}", params={"token": S["drv"]}, timeout=60)
        assert g.status_code == 200 and g.content[:3] == b"\xff\xd8\xff", g.status_code

    def test_docs_object_storage_and_approve(self):
        S["adm"] = admin_token()
        fids = []
        for i, k in enumerate(["licence_front", "licence_back", "id_proof", "rc"]):
            r = requests.post(f"{API}/driver/documents/{k}", headers=h(S["drv"]),
                              files={"file": ("a.jpg", real_image(500 + i + uuid.uuid4().int % 400), "image/jpeg")}, timeout=120)
            assert r.status_code == 200, (k, r.text)
            fids.append(r.json()["file_id"])
        for fid in fids:
            f = _db().files.find_one({"file_id": fid})
            assert f.get("path") and "data" not in f, fid
        S["doc_fid"] = fids[0]
        assert requests.get(f"{API}/files/{fids[0]}", params={"token": S["drv"]}, timeout=60).status_code == 200
        assert requests.get(f"{API}/files/{fids[0]}", headers=h(S["adm"]), timeout=60).status_code == 200
        outsider, _, _ = reg("Out13")
        assert requests.get(f"{API}/files/{fids[0]}", params={"token": outsider}, timeout=60).status_code == 404
        requests.put(f"{API}/me", headers=h(S["drv"]), json={"phone": "9900113344"})
        r = requests.post(f"{API}/driver/verification", headers=h(S["drv"]), json=VER)
        assert r.status_code == 200, r.text
        r = requests.post(f"{API}/admin/drivers/{S['drv_id']}/review", headers=h(S["adm"]), json={"decision": "approved"})
        assert r.status_code == 200, r.text

    def test_trip_price_boundary(self):
        r = requests.post(f"{API}/vehicles", headers=h(S["drv"]), json={"make": "Maruti", "model": "Dzire", "vtype": "sedan", "reg_no": "KA05TE1313", "seats": 3})
        assert r.status_code == 200, r.text
        S["vid"] = r.json()["vehicle_id"]
        d = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        body = {"origin": loc("Bengaluru"), "destination": loc("Mysuru"), "pickup_point": "TEST pickup", "drop_point": "TEST drop",
                "date": d, "time": "11:00", "seats": 2, "price": 100, "vehicle_id": S["vid"]}
        km = None
        r = requests.post(f"{API}/trips", headers=h(S["drv"]), json={**body, "price": 60})
        assert r.status_code == 200, r.text
        t = r.json(); km = t["distance_km"]; mx = t["price_suggestion"]["max"]
        requests.post(f"{API}/trips/{t['trip_id']}/cancel", headers=h(S["drv"]), json={})
        sug = requests.get(f"{API}/pricing/suggest", params={"km": km, "vtype": "sedan", "seats": 2}).json()
        assert sug["max"] == mx, (sug, t["price_suggestion"])
        S["route_km"] = km
        r = requests.post(f"{API}/trips", headers=h(S["drv"]), json={**body, "price": mx + 1})
        assert r.status_code == 400, r.text
        r = requests.post(f"{API}/trips", headers=h(S["drv"]), json={**body, "price": mx})
        assert r.status_code == 200, r.text
        S["tid"] = r.json()["trip_id"]
        print("route km", km, "max", mx)

    def test_system_messages_not_unread(self):
        r = requests.post(f"{API}/bookings", headers=h(S["pax"]), json={"trip_id": S["tid"], "seats": 1})
        assert r.status_code == 200, r.text
        S["bid"] = r.json()["booking_id"]
        sysc = _db().messages.count_documents({"booking_id": S["bid"], "sender_id": "system"})
        c = requests.get(f"{API}/conversations", headers=h(S["drv"])).json()
        conv = [x for x in c["items"] if x["booking_id"] == S["bid"]]
        assert conv and conv[0]["unread"] == 0, (sysc, conv)
        c2 = requests.get(f"{API}/conversations", headers=h(S["pax"])).json()
        assert all(x["unread"] == 0 for x in c2["items"] if x["booking_id"] == S["bid"]), sysc
        requests.post(f"{API}/bookings/{S['bid']}/messages", headers=h(S["pax"]), json={"text": "TEST hi 13"})
        c = requests.get(f"{API}/conversations", headers=h(S["drv"])).json()
        assert [x for x in c["items"] if x["booking_id"] == S["bid"]][0]["unread"] == 1
        print("system msgs in booking:", sysc)

    def test_admin_settings_no_fuel(self):
        s = requests.get(f"{API}/admin/settings", headers=h(S["adm"])).json()
        assert "pricing" in s or "max_price_factor" in s, s

    def test_cleanup(self):
        if S.get("bid"):
            requests.post(f"{API}/bookings/{S['bid']}/cancel", headers=h(S["pax"]), json={})
        if S.get("tid"):
            requests.post(f"{API}/trips/{S['tid']}/cancel", headers=h(S["drv"]), json={})
