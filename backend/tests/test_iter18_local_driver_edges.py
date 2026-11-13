"""Iteration 18: edge cases for unified Local Driver (Rent/Book a Driver).
Run: cd /app/backend/tests && pytest test_iter18_local_driver_edges.py -c /dev/null -p no:xdist -v"""
import requests

from test_travoo_api import API, h
import test_iter15_lgd_local_hire as t

S = t.S
HIRIYUR, HOLALKERE, GAJWEL = t.HIRIYUR, t.HOLALKERE, t.GAJWEL
VEH = [{"name": "TEST Ertiga", "reg_no": "KA 16 ZZ 9999", "category": "suv", "seats": 6, "day_rate": 1000}]
DATE = t.future_date(14)


def body(**kw):
    b = {"service": "rent", "service_type": "hourly", "date": DATE, "time": "10:00", "hours": 4, "city": S["city"], "pickup": "TEST Gajwel bus stand",
         "destination": "TEST Hiriyur", "passengers": 2, "vehicle_type": "", "subdistrict_code": HIRIYUR, "pickup_subdistrict_code": GAJWEL}
    b.update(kw)
    return b


def ids(**kw):
    p = {"subdistrict_code": HIRIYUR, "date": DATE, "time": "10:00", "hours": 4}
    p.update(kw)
    return {x["user_id"]: x for x in t.local(p)["local"]}


# Setup: fresh customer + drivers
class TestSetup:
    def test_setup(self):
        S["adm"] = t.admin_token()
        S["city"] = t.loc("Hiriyur")
        S["pax"], S["pax_id"], _ = t.reg("Pax18")
        S["pax2"], S["pax2_id"], _ = t.reg("Pax18b")
        S["LEG"] = t.make_driver("LEG18", HIRIYUR, services=["rent"])
        S["E"] = t.make_driver("E18", HIRIYUR, services=["rent"])
        S["BK"] = t.make_driver("BK18", HIRIYUR, services=["book"], vehicles=VEH)
        S["GO"] = t.make_driver("GO18", GAJWEL, services=["rent", "book"], vehicles=VEH)


# Legacy pro_drivers (no services field) are rent-only
class TestLegacy:
    def test_legacy_rent_only(self):
        t._db().pro_drivers.update_one({"user_id": S["LEG"][1]}, {"$unset": {"services": "", "availability_status": ""}})
        assert S["LEG"][1] in ids(service="rent")
        assert S["LEG"][1] not in ids(service="book", service_type="one_way", vehicle_type="any")
        got = ids(service="rent")[S["LEG"][1]]
        assert got["services"] == ["rent"]

    def test_legacy_admin_listing(self):
        rows = requests.get(f"{API}/admin/pro-drivers", headers=h(S["adm"]), params={"status": "approved", "service": "rent"}).json()
        row = next(p for p in rows if p["user_id"] == S["LEG"][1])
        assert row["services"] == ["rent"]


# Settings / vehicles validation
class TestSettingsVehicles:
    def test_book_without_vehicles_400(self):
        r = requests.put(f"{API}/pro/settings", headers=h(S["E"][0]), json={"services": ["rent", "book"]})
        assert r.status_code == 400, r.text
        assert "vehicle" in r.json()["detail"].lower()

    def test_put_vehicles_then_enable_book(self):
        r = requests.put(f"{API}/pro/vehicles", headers=h(S["E"][0]), json={"vehicles": VEH})
        assert r.status_code == 200, r.text
        assert r.json()["vehicles"][0]["reg_no"] == "KA16ZZ9999"
        me = requests.get(f"{API}/pro/me", headers=h(S["E"][0])).json()
        assert me["profile"]["vehicles"][0]["category"] == "suv"
        r = requests.put(f"{API}/pro/settings", headers=h(S["E"][0]), json={"services": ["rent", "book"]})
        assert r.status_code == 200, r.text
        assert S["E"][1] in ids(service="book", service_type="one_way", vehicle_type="suv")

    def test_empty_vehicles_with_book_400(self):
        r = requests.put(f"{API}/pro/vehicles", headers=h(S["E"][0]), json={"vehicles": []})
        assert r.status_code == 400, r.text
        requests.put(f"{API}/pro/settings", headers=h(S["E"][0]), json={"services": ["rent"]})

    def test_invalid_blocked_date_and_status(self):
        assert requests.put(f"{API}/pro/settings", headers=h(S["E"][0]), json={"blocked_dates": ["2026/01/01"]}).status_code == 400
        assert requests.put(f"{API}/pro/settings", headers=h(S["E"][0]), json={"availability_status": "sleeping"}).status_code == 422
        assert requests.put(f"{API}/pro/settings", headers=h(S["E"][0]), json={}).status_code == 400


# Matching: destination taluk only
class TestNoLocalMatch:
    def test_destination_without_drivers_404(self):
        db = t._db()
        busy = set(db.pro_drivers.distinct("home.subdistrict_code")) | set(db.pro_drivers.distinct("service_taluk_codes"))
        free = next(s["code"] for s in db.lgd_subdistricts.find({"district_code": "533"}, {"code": 1}) if s["code"] not in busy)
        S["free"] = free
        r = requests.post(f"{API}/hire/requests", headers=h(S["pax"]), json=body(subdistrict_code=free, time="11:00"))
        assert r.status_code == 404, r.text
        r = requests.post(f"{API}/hire/requests", headers=h(S["pax"]), json=body(subdistrict_code=free, time="11:00", driver_id=S["GO"][1]))
        assert r.status_code == 404, r.text
        d = t.local({"subdistrict_code": free, "date": DATE, "time": "11:00", "hours": 4, "pickup_subdistrict_code": GAJWEL})
        assert S["GO"][1] not in {x["user_id"] for x in d["local"]}


# Customer cancel of open request notifies drivers
class TestCancel:
    def test_cancel_notifies(self):
        r = requests.post(f"{API}/hire/requests", headers=h(S["pax2"]), json=body(service="book", service_type="one_way", vehicle_type="suv", time="12:00"))
        assert r.status_code == 200, r.text
        rid = r.json()["request_id"]
        disp = [d["driver_id"] for d in t._db().hire_dispatches.find({"request_id": rid})]
        assert S["BK"][1] in disp
        assert requests.post(f"{API}/hire/requests/{rid}/cancel", headers=h(S["BK"][0])).status_code == 403
        assert requests.post(f"{API}/hire/requests/{rid}/cancel", headers=h(S["pax2"])).status_code == 200
        assert t._db().hire_requests.find_one({"request_id": rid})["status"] == "cancelled"
        n = t._db().notifications.count_documents({"type": "local_hire_closed", "ref": rid, "user_id": {"$in": disp}})
        assert n == len(disp), (n, disp)
        assert requests.post(f"{API}/hire/requests/{rid}/accept", headers=h(S["BK"][0])).status_code == 409
        assert requests.post(f"{API}/hire/requests/{rid}/cancel", headers=h(S["pax2"])).status_code == 400


# Legacy driver booking lifecycle + dashboard earnings
class TestEarnings:
    def test_complete_and_earnings(self):
        r = requests.post(f"{API}/hire/requests", headers=h(S["pax"]), json=body(time="15:00", driver_id=S["LEG"][1]))
        assert r.status_code == 200, r.text
        rid = r.json()["request_id"]
        a = requests.post(f"{API}/hire/requests/{rid}/accept", headers=h(S["LEG"][0]))
        assert a.status_code == 200, a.text
        bid = a.json()["booking_id"]
        hire = t._db().hires.find_one({"booking_id": bid})
        assert hire["service"] == "rent" and hire["vehicle"] is None and hire["service_fee"] == 800
        assert t._db().notifications.count_documents({"user_id": S["pax_id"], "type": "hire_confirmed", "ref": bid}) == 1
        for act in ("arriving", "start", "complete"):
            x = requests.post(f"{API}/hire/bookings/{bid}/{act}", headers=h(S["LEG"][0]), json={})
            assert x.status_code == 200, (act, x.text)
        assert requests.post(f"{API}/hire/bookings/{bid}/arriving", headers=h(S["LEG"][0]), json={}).status_code == 400
        dash = requests.get(f"{API}/pro/dashboard", headers=h(S["LEG"][0])).json()
        e = dash["earnings"]
        assert e["completed"] == 1 and e["total"] == 800 and e["rent"] == 1 and e["book"] == 0, e
        assert any(x["booking_id"] == bid for x in dash["history"]) and not any(x["booking_id"] == bid for x in dash["upcoming"])
        assert dash["profile"]["availability_status"] == "available"
        S["done_bid"] = bid

    def test_customer_history_and_booking_detail(self):
        bk = requests.get(f"{API}/hire/bookings", headers=h(S["pax"]))
        assert bk.status_code == 200
        data = bk.json()
        rows = data if isinstance(data, list) else data.get("bookings", data.get("as_passenger", []))
        assert any(b.get("booking_id") == S["done_bid"] for b in rows), str(data)[:300]
        d = requests.get(f"{API}/hire/bookings/{S['done_bid']}", headers=h(S["pax"]))
        assert d.status_code == 200 and d.json()["status"] == "completed"

    def test_dashboard_unregistered(self):
        d = requests.get(f"{API}/pro/dashboard", headers=h(S["pax"])).json()
        assert d["earnings"] is None and d["upcoming"] == []

    def test_review_completed_hire(self):
        r = requests.post(f"{API}/reviews", headers=h(S["pax"]), json={"booking_id": S["done_bid"], "target_id": S["LEG"][1], "rating": 5, "comment": "TEST great"})
        assert r.status_code == 200, r.text
        assert requests.post(f"{API}/reviews", headers=h(S["pax"]), json={"booking_id": S["done_bid"], "target_id": S["LEG"][1], "rating": 4}).status_code == 409
        u = t._db().users.find_one({"user_id": S["LEG"][1]})
        assert u["rating_avg"] == 5 and u["rating_count"] == 1


# Admin hire reports pick up tickets on hire bookings
class TestReports:
    def test_report_visible_to_admin(self):
        r = requests.post(f"{API}/tickets", headers=h(S["pax"]), json={"type": "report_user", "subject": "TEST_report driver", "message": "TEST_report iter18 late driver", "booking_id": S["done_bid"], "reported_user_id": S["LEG"][1]})
        assert r.status_code in (200, 201), r.text
        rows = requests.get(f"{API}/admin/hire-reports", headers=h(S["adm"])).json()
        assert any(k.get("booking_id") == S["done_bid"] for k in rows), rows[:2]
