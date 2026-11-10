"""Iteration 9: driver reviews on trip detail + paid featured rides (UPI, admin approval). Run with -p no:xdist (sequential flow)."""
import os
import uuid
from datetime import datetime, timedelta

import pytest
import requests

from test_travoo_api import API, h
from test_iter8_admin_docs_reset import real_image, real_pdf

S = {}


def admin_token():
    tok = os.environ.get("ADMIN_TOKEN") or (open("/tmp/admtok").read().strip() if os.path.exists("/tmp/admtok") else None)
    if not tok:
        r = requests.post(f"{API}/admin/auth/login", json={"email": "admin@travoo.in", "password": os.environ.get("ADMIN_PASSWORD", "TravooAdmin2026")})
        tok = r.json().get("token")
    return tok


def loc(q):
    r = requests.get(f"{API}/locations/search", params={"q": q}).json()[0]
    return {k: r.get(k) for k in ("loc_id", "name", "type", "district", "state", "pin", "lat", "lng")}


def reg(name):
    email = f"test_{name.lower()}_{uuid.uuid4().hex[:6]}@example.com"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": "Passw0rd!x", "name": f"TEST_{name}", "consent": True}).json()
    return r["token"], r["user"]["user_id"], email


def mk_trip(tok, days, vid):
    d = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
    r = requests.post(f"{API}/trips", headers=h(tok), json={"origin": loc("Bengaluru"), "destination": loc("Chennai"), "pickup_point": "TEST pickup",
                      "drop_point": "TEST drop", "date": d, "time": "10:00", "seats": 3, "price": 600, "vehicle_id": vid, "instant_booking": True, "fuel_price": 100, "mileage": 15})
    assert r.status_code == 200, r.text
    return r.json()["trip_id"]


class TestSetup:
    # setup: admin, approved driver w/ vehicle, two trips, passengers
    def test_setup(self):
        S["adm"] = admin_token()
        assert requests.get(f"{API}/admin/settings", headers=h(S["adm"])).status_code == 200
        S["orig_settings"] = requests.get(f"{API}/admin/settings", headers=h(S["adm"])).json()
        S["drv"], S["drv_id"], S["drv_email"] = reg("FeatDriver")
        for i, k in enumerate(["licence_front", "licence_back", "id_proof", "vehicle"]):
            r = requests.post(f"{API}/driver/documents/{k}", headers=h(S["drv"]), files={"file": ("a.jpg", real_image(200 + i + uuid.uuid4().int % 500), "image/jpeg")}, timeout=120)
            assert r.status_code == 200, r.text
        r = requests.post(f"{API}/driver/documents/rc", headers=h(S["drv"]), files={"file": ("rc.pdf", real_pdf(900 + uuid.uuid4().int % 500), "application/pdf")}, timeout=120)
        assert r.status_code == 200, r.text
        r = requests.post(f"{API}/driver/verification", headers=h(S["drv"]), json={"vehicle_name": "Honda City", "phone": "9876512345",
                          "licence_no": "KA0120209999123", "licence_expiry": "01-01-2032", "rc_no": "KA05FT0009"})
        assert r.status_code == 200, r.text
        v = requests.post(f"{API}/vehicles", headers=h(S["drv"]), json={"make": "Honda", "model": "City", "vtype": "sedan", "reg_no": "KA05FT0009", "seats": 4}).json()
        S["vid"] = v["vehicle_id"]
        r = requests.post(f"{API}/admin/drivers/{S['drv_id']}/review", headers=h(S["adm"]), json={"decision": "approved"})
        assert r.status_code == 200, r.text
        S["trip_done"] = mk_trip(S["drv"], 2, S["vid"])
        S["trip_feat"] = mk_trip(S["drv"], 30, S["vid"])
        S["pax"], S["pax_id"], S["pax_email"] = reg("FeatPax")
        S["pax2"], S["pax2_id"], S["pax2_email"] = reg("FeatPax2")


class TestDriverReviews:
    # reviews: complete booking -> review -> visible in GET /trips/{tid}.driver_reviews
    def test_review_flow(self):
        r = requests.post(f"{API}/bookings", headers=h(S["pax"]), json={"trip_id": S["trip_done"], "seats": 1})
        assert r.status_code == 200, r.text
        bid = r.json()["booking_id"]
        assert r.json()["status"] == "confirmed"
        r2 = requests.post(f"{API}/bookings", headers=h(S["pax2"]), json={"trip_id": S["trip_done"], "seats": 1})
        assert r2.status_code == 200, r2.text
        S["bid2"] = r2.json()["booking_id"]
        assert requests.post(f"{API}/trips/{S['trip_done']}/complete", headers=h(S["drv"])).status_code == 200
        r = requests.post(f"{API}/reviews", headers=h(S["pax"]), json={"booking_id": bid, "target_id": S["drv_id"], "rating": 4, "comment": "TEST_ smooth ride"})
        assert r.status_code == 200, r.text
        r = requests.post(f"{API}/reviews", headers=h(S["pax2"]), json={"booking_id": S["bid2"], "target_id": S["drv_id"], "rating": 2, "comment": "TEST_ to be hidden"})
        assert r.status_code == 200, r.text
        assert requests.post(f"{API}/reviews", headers=h(S["pax2"]), json={"booking_id": S["bid2"], "target_id": S["drv_id"], "rating": 2}).status_code == 409

    def test_trip_detail_has_driver_reviews_for_rider(self):
        r = requests.get(f"{API}/trips/{S['trip_feat']}", headers=h(S["pax2"]))
        assert r.status_code == 200
        d = r.json()
        assert d["is_driver"] is False
        revs = d["driver_reviews"]
        assert len(revs) == 2
        assert revs[0]["created_at"] >= revs[1]["created_at"]
        S["review_id"] = revs[0]["review_id"]
        rv = revs[1]
        assert set(rv.keys()) == {"review_id", "reviewer_name", "rating", "comment", "route", "created_at"}
        assert rv["rating"] == 4 and rv["comment"] == "TEST_ smooth ride" and rv["reviewer_name"] == "TEST_FeatPax"
        assert d["driver"]["rating_avg"] == 3 and d["driver"]["rating_count"] == 2

    def test_hidden_review_excluded(self):
        # admin hides (DELETE /admin/reviews) -> no longer in driver_reviews
        r = requests.delete(f"{API}/admin/reviews/{S['review_id']}", headers=h(S["adm"]))
        assert r.status_code == 200, r.text
        d = requests.get(f"{API}/trips/{S['trip_feat']}", headers=h(S["pax2"])).json()
        assert all(x["review_id"] != S["review_id"] for x in d["driver_reviews"]) and len(d["driver_reviews"]) == 1
        assert d["driver"]["rating_avg"] == 4 and d["driver"]["rating_count"] == 1


class TestFeatured:
    # featured: settings, request validation, admin approve/reject/end, public list
    def test_public_settings_defaults(self):
        d = requests.get(f"{API}/settings").json()
        assert d["featured_days"] == 7 and isinstance(d["featured_price"], int)

    def test_feature_closed_without_upi(self):
        if S["orig_settings"].get("featured_upi_id"):
            pytest.skip("UPI already configured")
        r = requests.post(f"{API}/trips/{S['trip_feat']}/feature", headers=h(S["drv"]), json={"payment_ref": "TESTREF123"})
        assert r.status_code == 400 and "not open" in r.json()["detail"]

    def test_admin_set_featured_settings(self):
        r = requests.put(f"{API}/admin/settings", headers=h(S["adm"]), json={"featured_price": 249, "featured_upi_id": "travoo.test@okaxis"})
        assert r.status_code == 200, r.text
        d = requests.get(f"{API}/settings").json()
        assert d["featured_price"] == 249 and d["featured_upi_id"] == "travoo.test@okaxis"

    def test_settings_requires_admin(self):
        r = requests.put(f"{API}/admin/settings", headers=h(S["drv"]), json={"featured_price": 1})
        assert r.status_code in (401, 403)

    def test_feature_validation(self):
        u = f"{API}/trips/{S['trip_feat']}/feature"
        assert requests.post(u, headers=h(S["drv"]), json={"payment_ref": "abc"}).status_code == 422
        assert requests.post(u, headers=h(S["drv"]), json={"payment_ref": "bad ref!!"}).status_code == 422
        assert requests.post(u, headers=h(S["pax2"]), json={"payment_ref": "TESTREF123"}).status_code == 404
        r = requests.post(f"{API}/trips/{S['trip_done']}/feature", headers=h(S["drv"]), json={"payment_ref": "TESTREF123"})
        assert r.status_code == 400 and "upcoming" in r.json()["detail"]

    def test_feature_request_create_and_get(self):
        r = requests.post(f"{API}/trips/{S['trip_feat']}/feature", headers=h(S["drv"]), json={"payment_ref": "testref-001"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "pending" and d["amount"] == 249 and d["days"] == 7 and d["payment_ref"] == "TESTREF-001"
        S["fid"] = d["feature_id"]
        g = requests.get(f"{API}/trips/{S['trip_feat']}/feature", headers=h(S["drv"])).json()
        assert g["feature_id"] == S["fid"] and "_id" not in g
        r = requests.post(f"{API}/trips/{S['trip_feat']}/feature", headers=h(S["drv"]), json={"payment_ref": "TESTREF002"})
        assert r.status_code == 409

    def test_admin_list_pending(self):
        rows = requests.get(f"{API}/admin/featured", params={"status": "pending"}, headers=h(S["adm"])).json()
        assert any(x["feature_id"] == S["fid"] for x in rows)
        assert requests.get(f"{API}/admin/featured", headers=h(S["drv"])).status_code in (401, 403)

    def test_admin_approve_and_public_list(self):
        assert requests.post(f"{API}/admin/featured/{S['fid']}/end", headers=h(S["adm"]), json={}).status_code == 400
        r = requests.post(f"{API}/admin/featured/{S['fid']}/approve", headers=h(S["adm"]), json={"note": "ok"})
        assert r.status_code == 200, r.text
        assert requests.post(f"{API}/admin/featured/{S['fid']}/approve", headers=h(S["adm"]), json={}).status_code == 400
        act = requests.get(f"{API}/admin/featured", params={"status": "active"}, headers=h(S["adm"])).json()
        f = next(x for x in act if x["feature_id"] == S["fid"])
        exp = datetime.fromisoformat(f["expires_at"].replace("Z", ""))
        appr = datetime.fromisoformat(f["approved_at"].replace("Z", ""))
        assert abs((exp - appr).total_seconds() - 7 * 86400) < 5
        pub = requests.get(f"{API}/featured").json()
        assert any(t["trip_id"] == S["trip_feat"] for t in pub)
        t = next(t for t in pub if t["trip_id"] == S["trip_feat"])
        assert "driver" in t and "_id" not in t and "route_line" not in t
        notifs = requests.get(f"{API}/notifications", headers=h(S["drv"])).json()
        items = notifs if isinstance(notifs, list) else notifs.get("items", notifs.get("notifications", []))
        assert any(n.get("type") == "featured_approved" for n in items), str(notifs)[:300]
        # 409 while active
        assert requests.post(f"{API}/trips/{S['trip_feat']}/feature", headers=h(S["drv"]), json={"payment_ref": "TESTREF003"}).status_code == 409

    def test_admin_end(self):
        r = requests.post(f"{API}/admin/featured/{S['fid']}/end", headers=h(S["adm"]), json={})
        assert r.status_code == 200
        ended = requests.get(f"{API}/admin/featured", params={"status": "ended"}, headers=h(S["adm"])).json()
        assert any(x["feature_id"] == S["fid"] for x in ended)
        assert all(t["trip_id"] != S["trip_feat"] for t in requests.get(f"{API}/featured").json())

    def test_reject_flow(self):
        r = requests.post(f"{API}/trips/{S['trip_feat']}/feature", headers=h(S["drv"]), json={"payment_ref": "TESTREF004"})
        assert r.status_code == 200, r.text
        fid = r.json()["feature_id"]
        assert requests.post(f"{API}/admin/featured/{fid}/reject", headers=h(S["adm"]), json={"note": "TEST_ no payment"}).status_code == 200
        rej = requests.get(f"{API}/admin/featured", params={"status": "rejected"}, headers=h(S["adm"])).json()
        assert any(x["feature_id"] == fid and x["admin_note"] == "TEST_ no payment" for x in rej)
        assert requests.post(f"{API}/admin/featured/nope/approve", headers=h(S["adm"]), json={}).status_code == 404
        assert requests.post(f"{API}/admin/featured/{fid}/bogus", headers=h(S["adm"]), json={}).status_code == 422
        # leave an active spot for UI testing
        r = requests.post(f"{API}/trips/{S['trip_feat']}/feature", headers=h(S["drv"]), json={"payment_ref": "TESTREF005"})
        assert r.status_code == 200
        assert requests.post(f"{API}/admin/featured/{r.json()['feature_id']}/approve", headers=h(S["adm"]), json={}).status_code == 200
        with open("/tmp/iter9_state.txt", "w") as f:
            f.write(f"{S['drv_email']} {S['pax2_email']} {S['trip_feat']} {S['trip_done']} {S['drv_id']}\n")


class TestCleanup:
    # cleanup: end TEST featured spots, cancel TEST trips, restore featured settings to original values
    def test_cleanup(self):
        for st in ("active", "pending"):
            for f in requests.get(f"{API}/admin/featured", params={"status": st}, headers=h(S["adm"])).json():
                if f["driver_id"] == S["drv_id"]:
                    requests.post(f"{API}/admin/featured/{f['feature_id']}/{'end' if st == 'active' else 'reject'}", headers=h(S["adm"]), json={})
        requests.post(f"{API}/trips/{S['trip_feat']}/cancel", headers=h(S["drv"]), json={"reason": "Other"})
        from pymongo import MongoClient
        env = dict(l.strip().split("=", 1) for l in open("/app/backend/.env") if "=" in l)
        db = MongoClient(env["MONGO_URL"].strip('"'))[env["DB_NAME"].strip('"')]
        o = S["orig_settings"]
        unset = {k: "" for k in ("featured_price", "featured_upi_id") if o.get(k) is None or (k == "featured_price" and o.get(k) == 199)}
        setv = {k: o[k] for k in ("featured_price", "featured_upi_id") if k not in unset}
        upd = {**({"$unset": unset} if unset else {}), **({"$set": setv} if setv else {})}
        if upd:
            db.settings.update_one({"key": "platform"}, upd)
        assert requests.get(f"{API}/featured").status_code == 200
