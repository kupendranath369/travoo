"""Iteration 10: vehicle seat caps, cost breakdown (fuel+tolls / seats), fuel-prices/mileage defaults, profile photo,
public photo gating, driver verification (registered phone, licence fields, no 'profile' kind), AI extract. Run with -p no:xdist."""
import os
import uuid
from datetime import datetime, timedelta

import pytest
import requests

from test_travoo_api import API, h
from test_iter8_admin_docs_reset import real_image, real_pdf

S = {}


def admin_token():
    if os.path.exists("/tmp/admtok"):
        tok = open("/tmp/admtok").read().strip()
        if requests.get(f"{API}/admin/settings", headers=h(tok)).status_code == 200:
            return tok
    r = requests.post(f"{API}/admin/auth/login", json={"email": "admin@travoo.in", "password": "TravooAdmin2026"})
    tok = r.json().get("token")
    open("/tmp/admtok", "w").write(tok or "")
    return tok


def loc(q):
    r = requests.get(f"{API}/locations/search", params={"q": q}).json()[0]
    return {k: r.get(k) for k in ("loc_id", "name", "type", "district", "state", "pin", "lat", "lng")}


def reg(name):
    email = f"test_{name.lower()}_{uuid.uuid4().hex[:6]}@example.com"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": "Passw0rd!x", "name": f"TEST_{name}", "consent": True}).json()
    return r["token"], r["user"]["user_id"], email


def upload_docs(tok):
    for i, k in enumerate(["licence_front", "licence_back", "id_proof", "vehicle"]):
        r = requests.post(f"{API}/driver/documents/{k}", headers=h(tok), files={"file": ("a.jpg", real_image(300 + i + uuid.uuid4().int % 500), "image/jpeg")}, timeout=120)
        assert r.status_code == 200, r.text
    r = requests.post(f"{API}/driver/documents/rc", headers=h(tok), files={"file": ("rc.pdf", real_pdf(900 + uuid.uuid4().int % 500), "application/pdf")}, timeout=120)
    assert r.status_code == 200, r.text


VER = {"vehicle_name": "Maruti Swift", "licence_no": "KA0120201234567", "licence_name": "TEST Driver", "licence_dob": "15-06-1990",
       "licence_issue": "01-01-2015", "licence_expiry": "01-01-2035", "vehicle_class": "lmv, mcwg", "rc_no": "KA05AB1234"}


def trip_body(vid, seats, price=300, days=5, **kw):
    d = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
    b = {"origin": loc("Bengaluru"), "destination": loc("Mysuru"), "pickup_point": "TEST pickup", "drop_point": "TEST drop", "date": d,
         "time": "10:00", "seats": seats, "price": price, "vehicle_id": vid, "fuel_price": 100, "mileage": 15, "tolls": 200}
    b.update(kw)
    return b


class TestSettingsAndFuel:
    # fuel-prices payload + admin mileage defaults
    def test_fuel_prices(self):
        S["adm"] = admin_token()
        S["orig"] = requests.get(f"{API}/admin/settings", headers=h(S["adm"])).json()
        d = requests.get(f"{API}/fuel-prices").json()
        assert set(d["mileage_defaults"]) >= {"hatchback", "sedan", "suv", "muv"}
        assert d["seat_caps"]["hatchback"] == 3 and d["seat_caps"]["sedan"] == 3 and d["seat_caps"]["suv"] == 8 and d["seat_caps"]["muv"] == 8
        assert "prices" in d

    def test_mileage_defaults_update(self):
        md = {**requests.get(f"{API}/fuel-prices").json()["mileage_defaults"]}
        S["orig_md"] = md
        r = requests.put(f"{API}/admin/settings", headers=h(S["adm"]), json={"mileage_defaults": {**md, "hatchback": 21}})
        assert r.status_code == 200, r.text
        assert requests.get(f"{API}/fuel-prices").json()["mileage_defaults"]["hatchback"] == 21
        assert requests.put(f"{API}/admin/settings", headers=h(S["adm"]), json={"mileage_defaults": {"sedan": 2}}).status_code == 422
        assert requests.put(f"{API}/admin/settings", headers=h(S["adm"]), json={"mileage_defaults": {"sedan": 61}}).status_code == 422
        requests.put(f"{API}/admin/settings", headers=h(S["adm"]), json={"mileage_defaults": md})


class TestVerification:
    # driver verification: no 'profile' kind, phone required, date validation, never auto approved
    def test_kinds_no_profile(self):
        S["drv"], S["drv_id"], _ = reg("CapDriver")
        kinds = [k["kind"] for k in requests.get(f"{API}/driver/profile", headers=h(S["drv"])).json()["kinds"]]
        assert "profile" not in kinds and "licence_front" in kinds

    def test_ai_extract_requires_licence(self):
        r = requests.post(f"{API}/driver/ai-extract", headers=h(S["drv"]))
        assert r.status_code == 400

    def test_submit_without_phone(self):
        # make sure instant approval is OFF for this test
        requests.put(f"{API}/admin/settings", headers=h(S["adm"]), json={"instant_driver_approval": False})
        upload_docs(S["drv"])
        r = requests.post(f"{API}/driver/verification", headers=h(S["drv"]), json=VER)
        assert r.status_code == 400 and "mobile" in r.text.lower(), r.text

    def test_ai_extract_synthetic(self):
        r = requests.post(f"{API}/driver/ai-extract", headers=h(S["drv"]), timeout=150)
        assert r.status_code in (200, 502), r.text
        if r.status_code == 200:
            d = r.json()
            for k in ("licence_no", "licence_name", "licence_dob", "licence_issue", "licence_expiry", "vehicle_class", "rc_no", "vehicle_name", "unclear", "missing"):
                assert k in d
            assert d["unclear"] is True
            S["ai"] = d
        st = requests.get(f"{API}/driver/profile", headers=h(S["drv"])).json()["status"]
        assert st not in ("approved", "under_review")

    def test_submit_invalid_dates(self):
        assert requests.put(f"{API}/me", headers=h(S["drv"]), json={"phone": "9876543210"}).status_code == 200
        for bad in ({"licence_expiry": "31-02-2030"}, {"licence_expiry": "01-01-2020"}, {"licence_dob": "40-13-1990"}, {"licence_name": ""}, {"vehicle_class": ""}):
            r = requests.post(f"{API}/driver/verification", headers=h(S["drv"]), json={**VER, **bad})
            assert r.status_code in (400, 422), (bad, r.text)

    def test_submit_ok_under_review(self):
        r = requests.post(f"{API}/driver/verification", headers=h(S["drv"]), json=VER)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "under_review"
        det = requests.get(f"{API}/admin/drivers/{S['drv_id']}/detail", headers=h(S["adm"])).json()
        docs = det.get("documents") or {}
        assert docs.get("licence_name") == "TEST Driver" and docs.get("vehicle_class") == "LMV, MCWG" and docs.get("phone") == "9876543210", docs
        assert docs.get("licence_dob") == "15-06-1990" and docs.get("licence_issue") == "01-01-2015"
        r = requests.post(f"{API}/admin/drivers/{S['drv_id']}/review", headers=h(S["adm"]), json={"decision": "approved"})
        assert r.status_code == 200, r.text
        requests.put(f"{API}/admin/settings", headers=h(S["adm"]), json={"instant_driver_approval": S["orig"].get("instant_driver_approval", False)})


class TestVehicleCaps:
    # seat caps by vehicle type
    @pytest.mark.parametrize("vtype,seats,ok", [("hatchback", 3, True), ("hatchback", 4, False), ("sedan", 4, False), ("sedan", 3, True),
                                                ("suv", 8, True), ("suv", 9, False), ("muv", 8, True), ("other", 3, False)])
    def test_caps(self, vtype, seats, ok):
        r = requests.post(f"{API}/vehicles", headers=h(S["drv"]), json={"make": "TEST", "model": "Car", "vtype": vtype, "reg_no": f"KA05{uuid.uuid4().hex[:4].upper()}", "seats": seats})
        assert (r.status_code == 200) == ok, r.text
        if ok:
            S.setdefault("veh", {})[vtype] = r.json()["vehicle_id"]


class TestTripCaps:
    # trip seat caps + cost breakdown
    def test_trip_seats_cap(self):
        r = requests.post(f"{API}/trips", headers=h(S["drv"]), json=trip_body(S["veh"]["sedan"], 4))
        assert r.status_code == 400, r.text

    def test_trip_breakdown(self):
        r = requests.post(f"{API}/trips", headers=h(S["drv"]), json=trip_body(S["veh"]["sedan"], 3, price=100, pickup_pin={"lat": 12.97, "lng": 77.59}, drop_pin={"lat": 12.3, "lng": 76.64}))
        assert r.status_code == 200, r.text
        t = r.json()
        S["tid"] = t["trip_id"]
        cb = t["cost_breakdown"]
        assert cb["sharers"] == 3 and cb["maintenance_cost"] == 0
        assert abs(cb["total"] - (cb["fuel_cost"] + cb["tolls"])) <= 1
        assert abs(cb["fuel_cost"] - t["distance_km"] / 15 * 100) <= 1
        assert cb["recommended"] == max(50, round(cb["total"] / 3))
        assert t.get("pickup_pin") == {"lat": 12.97, "lng": 77.59}
        S["rec"] = cb["recommended"]

    def test_price_cap(self):
        fac = requests.get(f"{API}/fuel-prices").json()["max_price_factor"]
        cap = round(S["rec"] * fac)
        r = requests.post(f"{API}/trips", headers=h(S["drv"]), json=trip_body(S["veh"]["sedan"], 3, price=cap + 10, days=6))
        assert r.status_code == 400 and "limit" in r.text, r.text

    def test_update_seats_cap(self):
        assert requests.put(f"{API}/trips/{S['tid']}", headers=h(S["drv"]), json={"seats": 4}).status_code == 400
        r = requests.put(f"{API}/trips/{S['tid']}", headers=h(S["drv"]), json={"seats": 2})
        assert r.status_code == 200 and r.json()["seats_total"] == 2

    def test_suv_trip(self):
        r = requests.post(f"{API}/trips", headers=h(S["drv"]), json=trip_body(S["veh"]["suv"], 8, price=60, days=7))
        assert r.status_code == 200, r.text
        S["tid2"] = r.json()["trip_id"]


class TestProfilePhoto:
    # profile photo upload, private access, public gating for approved drivers
    def test_upload_and_fetch(self):
        r = requests.post(f"{API}/me/photo", headers=h(S["drv"]), files={"file": ("p.png", real_image(7, "PNG"), "image/png")})
        assert r.status_code == 200, r.text
        fid = r.json()["file_id"]
        assert requests.get(f"{API}/auth/me", headers=h(S["drv"])).json()["picture"] == fid
        g = requests.get(f"{API}/files/{fid}", params={"token": S["drv"]})
        assert g.status_code == 200 and g.headers["content-type"].startswith("image/png")
        r2 = requests.post(f"{API}/me/photo", headers=h(S["drv"]), files={"file": ("p.jpg", real_image(8), "image/jpeg")})
        fid2 = r2.json()["file_id"]
        assert requests.get(f"{API}/files/{fid}", params={"token": S["drv"]}).status_code == 404  # old one deleted
        S["fid2"] = fid2
        assert requests.get(f"{API}/public/photo/{S['drv_id']}").status_code == 200  # approved driver

    def test_other_user_cannot_fetch_and_bad_files(self):
        pax, pax_id, email = reg("PhotoPax")
        S["pax"], S["pax_email"] = pax, email
        assert requests.get(f"{API}/files/{S['fid2']}", params={"token": pax}).status_code == 404
        assert requests.post(f"{API}/me/photo", headers=h(pax), files={"file": ("x.jpg", b"not an image" * 10, "image/jpeg")}).status_code == 400
        assert requests.post(f"{API}/me/photo", headers=h(pax), files={"file": ("x.pdf", real_pdf(3), "application/pdf")}).status_code == 400
        assert requests.post(f"{API}/me/photo", headers=h(pax), files={"file": ("big.jpg", b"\xff\xd8\xff" + b"0" * (5 * 1024 * 1024 + 10), "image/jpeg")}).status_code == 413
        assert requests.post(f"{API}/me/photo", headers=h(pax), files={"file": ("p.jpg", real_image(9), "image/jpeg")}).status_code == 200
        assert requests.get(f"{API}/public/photo/{pax_id}").status_code == 404  # not a driver

    def test_persists_after_relogin(self):
        r = requests.post(f"{API}/auth/login", json={"email": S["pax_email"], "password": "Passw0rd!x"})
        assert r.status_code == 200
        assert str(r.json()["user"].get("picture", "")).startswith("file_")


class TestCleanup:
    def test_cleanup(self):
        for t in (S.get("tid"), S.get("tid2")):
            if t:
                requests.post(f"{API}/trips/{t}/cancel", headers=h(S["drv"]), json={"reason": "TEST cleanup"})
        for v in S.get("veh", {}).values():
            requests.delete(f"{API}/vehicles/{v}", headers=h(S["drv"]))
        s = requests.get(f"{API}/admin/settings", headers=h(S["adm"])).json()
        assert s.get("instant_driver_approval") == S["orig"].get("instant_driver_approval")
