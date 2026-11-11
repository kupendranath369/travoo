"""Iteration 14: PUT /me phone edge cases (unchanged/empty/different/verified) + return-leg price_suggestion & cap. Run with -c /dev/null -p no:xdist."""
import random
import uuid
from datetime import datetime, timedelta

import requests

from test_travoo_api import API, h
from test_iter8_admin_docs_reset import real_image
from test_iter10_capacity_pricing_photo import admin_token, loc, reg
from test_iter13_retest_fixes import _db

S = {}
VER = {"vehicle_name": "TEST Maruti Swift", "licence_no": "KA0120201234567", "licence_expiry": "01-01-2035", "rc_no": "KA05AB1234"}


def ph():
    return f"98{random.randint(10000000, 99999999)}"


# ---- PUT /api/me phone handling
class TestProfilePhone:
    def test_no_phone_user_saves_name_bio_upi(self):
        tok, uid, _ = reg("NoPh14")
        r = requests.put(f"{API}/me", headers=h(tok), json={"name": "TEST_NoPh14 New", "bio": "TEST bio", "upi_id": "test14@okaxis"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["name"] == "TEST_NoPh14 New" and d["bio"] == "TEST bio" and d["upi_id"] == "test14@okaxis" and "_id" not in d

    def test_unverified_change_and_clear_phone(self):
        tok, uid, _ = reg("Unv14")
        p1, p2 = ph(), ph()
        assert requests.put(f"{API}/me", headers=h(tok), json={"phone": p1}).json()["phone"] == p1
        assert requests.put(f"{API}/me", headers=h(tok), json={"phone": p2}).json()["phone"] == p2
        r = requests.put(f"{API}/me", headers=h(tok), json={"phone": ""})
        assert r.status_code == 200 and r.json()["phone"] == "", r.text
        assert requests.put(f"{API}/me", headers=h(tok), json={"phone": "12345"}).status_code == 400

    def test_alpha_phone_rejected(self):
        # non-digit garbage should be a 400, not silently treated as empty
        tok, uid, _ = reg("Alp14")
        p1 = ph()
        requests.put(f"{API}/me", headers=h(tok), json={"phone": p1})
        r = requests.put(f"{API}/me", headers=h(tok), json={"phone": "abcdefghij"})
        me = requests.get(f"{API}/auth/me", headers=h(tok)).json()
        stored = (me.get("user") or me).get("phone")
        print("alpha phone on user with phone:", r.status_code, "stored:", stored)
        assert r.status_code == 400 and stored == p1, (r.status_code, stored)

    def test_verified_user(self):
        tok, uid, _ = reg("Ver14")
        p1 = ph()
        requests.put(f"{API}/me", headers=h(tok), json={"phone": p1})
        _db().users.update_one({"user_id": uid}, {"$set": {"phone_verified": True, "phone_e164": "91" + p1}})
        try:
            r = requests.put(f"{API}/me", headers=h(tok), json={"name": "TEST_Ver14 X", "upi_id": "v14@okhdfc"})
            assert r.status_code == 200 and r.json()["name"] == "TEST_Ver14 X", r.text
            r = requests.put(f"{API}/me", headers=h(tok), json={"name": "TEST_Ver14 Y", "phone": "+91 " + p1})
            assert r.status_code == 200 and r.json()["phone"] == p1, r.text
            r = requests.put(f"{API}/me", headers=h(tok), json={"phone": ph()})
            assert r.status_code == 400 and "verified" in r.json()["detail"].lower(), r.text
            r = requests.put(f"{API}/me", headers=h(tok), json={"phone": ""})
            assert r.status_code == 400, r.text
            assert (requests.get(f"{API}/auth/me", headers=h(tok)).json().get("user") or {}).get("phone", p1) == p1
        finally:
            _db().users.update_one({"user_id": uid}, {"$unset": {"phone_e164": ""}, "$set": {"phone_verified": False}})


# ---- return-leg pricing
class TestReturnLeg:
    def test_setup_driver(self):
        S["adm"] = admin_token()
        S["drv"], S["drv_id"], _ = reg("Drv14")
        for i, k in enumerate(["licence_front", "licence_back", "id_proof", "rc"]):
            r = requests.post(f"{API}/driver/documents/{k}", headers=h(S["drv"]),
                              files={"file": ("a.jpg", real_image(400 + i + uuid.uuid4().int % 500), "image/jpeg")}, timeout=120)
            assert r.status_code == 200, r.text
        requests.put(f"{API}/me", headers=h(S["drv"]), json={"phone": ph()})
        assert requests.post(f"{API}/driver/verification", headers=h(S["drv"]), json=VER).status_code == 200
        r = requests.post(f"{API}/admin/drivers/{S['drv_id']}/review", headers=h(S["adm"]), json={"decision": "approved"})
        assert r.status_code == 200, r.text
        r = requests.post(f"{API}/vehicles", headers=h(S["drv"]), json={"make": "Maruti", "model": "Dzire", "vtype": "sedan", "reg_no": "KA05TF1414", "seats": 3})
        assert r.status_code == 200, r.text
        S["vid"] = r.json()["vehicle_id"]

    def _body(self, price):
        d = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        rd = (datetime.now() + timedelta(days=8)).strftime("%Y-%m-%d")
        return {"origin": loc("Bengaluru"), "destination": loc("Mysuru"), "pickup_point": "TEST pickup", "drop_point": "TEST drop",
                "date": d, "time": "10:00", "seats": 3, "price": price, "vehicle_id": S["vid"], "return_date": rd, "return_time": "17:00"}

    def test_over_cap_rejected(self):
        r = requests.post(f"{API}/trips", headers=h(S["drv"]), json=self._body(9999))
        assert r.status_code == 400 and "per person" in r.json()["detail"], r.text

    def test_return_trip_has_suggestion(self):
        r = requests.post(f"{API}/trips", headers=h(S["drv"]), json=self._body(100))
        assert r.status_code == 200, r.text
        out = r.json()
        S["tid"] = out["trip_id"]
        rt = _db().trips.find_one({"return_of": S["tid"]})
        assert rt is not None
        S["rtid"] = rt["trip_id"]
        print("outbound sug:", out["price_suggestion"], "return sug:", rt.get("price_suggestion"), "km", out["distance_km"], rt["distance_km"])
        assert rt.get("price_suggestion") and rt["price_suggestion"]["max"] >= 50 and "cost_breakdown" not in rt
        assert rt["origin"]["loc_id"] == out["destination"]["loc_id"]
        # also exposed via the API
        g = requests.get(f"{API}/trips/{S['rtid']}", headers=h(S["drv"])).json()
        assert (g.get("trip") or g).get("price_suggestion"), g

    def test_return_cap_enforced(self):
        # force a lower max for return by checking the return's own max: price = min(out max, ret max)+1 must fail
        rt = _db().trips.find_one({"trip_id": S["rtid"]})
        out = _db().trips.find_one({"trip_id": S["tid"]})
        lim = min(rt["price_suggestion"]["max"], out["price_suggestion"]["max"])
        assert requests.post(f"{API}/trips", headers=h(S["drv"]), json=self._body(lim + 1)).status_code == 400
        r = requests.post(f"{API}/trips", headers=h(S["drv"]), json=self._body(lim))
        assert r.status_code == 200, r.text
        S["tid2"] = r.json()["trip_id"]
        S["rtid2"] = _db().trips.find_one({"return_of": S["tid2"]})["trip_id"]

    def test_cleanup(self):
        for k in ("tid", "rtid", "tid2", "rtid2"):
            if S.get(k):
                requests.post(f"{API}/trips/{S[k]}/cancel", headers=h(S["drv"]), json={})
