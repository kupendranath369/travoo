"""Iteration 17: unified Local Driver (Rent a Driver + Book a Driver), destination-taluk matching, availability, vehicles,
favourites, arriving, admin views. Run: cd /app/backend/tests && pytest test_iter17_unified_local_driver.py -c /dev/null -p no:xdist -v"""
from concurrent.futures import ThreadPoolExecutor

import requests

from test_travoo_api import API, h
import test_iter15_lgd_local_hire as t

S = t.S
HIRIYUR, HOLALKERE, GAJWEL = t.HIRIYUR, t.HOLALKERE, t.GAJWEL
VEH = [{"name": "TEST Innova", "reg_no": "KA 16 AB 1234", "category": "suv", "seats": 6, "day_rate": 1200}]
DATE = t.future_date(12)


def q(**kw):
    p = {"subdistrict_code": HIRIYUR, "date": DATE, "time": "10:00", "hours": 4, "pickup_subdistrict_code": GAJWEL}
    p.update(kw)
    return {x["user_id"]: x for x in t.local(p)["local"]}


def body(**kw):
    b = {"service": "rent", "service_type": "hourly", "date": DATE, "time": "10:00", "hours": 4, "city": S["city"], "pickup": "TEST Gajwel bus stand",
         "destination": "TEST Hiriyur", "passengers": 2, "vehicle_type": "", "subdistrict_code": HIRIYUR, "pickup_subdistrict_code": GAJWEL}
    b.update(kw)
    return b


class TestSetup:
    def test_setup(self):
        S["adm"] = t.admin_token()
        S["city"] = t.loc("Hiriyur")
        S["pax"], S["pax_id"], _ = t.reg("Pax17")
        S["R"] = t.make_driver("R17", HIRIYUR, services=["rent"])                                   # home = destination taluk
        S["B"] = t.make_driver("B17", HOLALKERE, services=["book"], service_taluks=[HIRIYUR], vehicles=VEH)  # serves destination via service area
        S["BOTH"] = t.make_driver("BOTH17", HIRIYUR, services=["rent", "book"], vehicles=VEH, accepts_outstation=True)
        S["G"] = t.make_driver("G17", GAJWEL, services=["rent", "book"], vehicles=VEH)               # pickup taluk only -> never local
        S["NEAR"] = t.make_driver("NEAR17", HOLALKERE, services=["rent"], accepts_outside_area=True)

    def test_book_requires_vehicle(self):
        tok, _, _ = t.reg("NoVeh17")
        r = requests.post(f"{API}/pro/register", headers=h(tok), json=t.pro_body(S["city"], HIRIYUR, services=["book"]))
        assert r.status_code == 400


class TestMatching:
    def test_rent_destination_taluk(self):
        got = q(service="rent", service_type="hourly")
        assert S["R"][1] in got and S["BOTH"][1] in got
        assert S["B"][1] not in got, "book-only driver must not get rent"
        assert S["G"][1] not in got, "pickup-taluk driver must not be local for destination"

    def test_book_destination_taluk(self):
        got = q(service="book", service_type="one_way", vehicle_type="suv", passengers=4)
        assert S["B"][1] in got and S["BOTH"][1] in got and S["R"][1] not in got and S["G"][1] not in got
        assert got[S["B"][1]]["match_vehicle"]["reg_no"] == "KA16AB1234"
        assert got[S["B"][1]]["estimate"] == 4 * 200 + 1200

    def test_book_vehicle_suitability(self):
        assert not ({S["B"][1], S["BOTH"][1]} & set(q(service="book", service_type="one_way", vehicle_type="suv", passengers=7)))
        assert not ({S["B"][1], S["BOTH"][1]} & set(q(service="book", service_type="one_way", vehicle_type="sedan")))

    def test_outstation_preference(self):
        got = q(service="rent", service_type="outstation", days=2)
        assert S["BOTH"][1] in got and S["R"][1] not in got

    def test_nearby_only_if_outside_area_allowed(self):
        d = t.local({"subdistrict_code": HIRIYUR, "date": DATE, "time": "10:00", "hours": 4, "service": "rent", "nearby": "true"})
        near = {x["user_id"] for x in d["nearby"]}
        assert S["NEAR"][1] in near and S["B"][1] not in near

    def test_busy_offline_excluded(self):
        tok = S["R"][0]
        for st in ("busy", "offline"):
            assert requests.put(f"{API}/pro/settings", headers=h(tok), json={"availability_status": st}).status_code == 200
            assert S["R"][1] not in q(service="rent")
        assert requests.put(f"{API}/pro/settings", headers=h(tok), json={"availability_status": "available"}).status_code == 200
        assert S["R"][1] in q(service="rent")

    def test_blocked_date(self):
        tok = S["R"][0]
        requests.put(f"{API}/pro/settings", headers=h(tok), json={"blocked_dates": [DATE]})
        assert S["R"][1] not in q(service="rent")
        requests.put(f"{API}/pro/settings", headers=h(tok), json={"blocked_dates": []})

    def test_disable_service(self):
        tok = S["BOTH"][0]
        requests.put(f"{API}/pro/settings", headers=h(tok), json={"services": ["book"]})
        assert S["BOTH"][1] not in q(service="rent")
        requests.put(f"{API}/pro/settings", headers=h(tok), json={"services": ["rent", "book"]})


class TestRequests:
    def test_book_request_dispatch_and_race(self):
        r = requests.post(f"{API}/hire/requests", headers=h(S["pax"]), json=body(service="book", service_type="round_trip", vehicle_type="suv"))
        assert r.status_code == 200, r.text
        rid = r.json()["request_id"]
        disp = {d["driver_id"] for d in t._db().hire_dispatches.find({"request_id": rid})}
        assert {S["B"][1], S["BOTH"][1]} <= disp and not ({S["R"][1], S["G"][1]} & disp), disp
        with ThreadPoolExecutor(2) as ex:
            res = list(ex.map(lambda k: requests.post(f"{API}/hire/requests/{rid}/accept", headers=h(S[k][0])), ["B", "BOTH"]))
        codes = sorted(x.status_code for x in res)
        assert codes == [200, 409], [x.text for x in res]
        bid = next(x.json()["booking_id"] for x in res if x.status_code == 200)
        hire = t._db().hires.find_one({"booking_id": bid})
        assert hire["service"] == "book" and hire["vehicle"]["category"] == "suv" and hire["dest_taluk"]["code"] == HIRIYUR
        drv = S["B"] if hire["driver_id"] == S["B"][1] else S["BOTH"]
        assert requests.post(f"{API}/hire/bookings/{bid}/arriving", headers=h(drv[0]), json={}).status_code == 200
        assert t._db().notifications.count_documents({"user_id": S["pax_id"], "type": "hire_arriving", "ref": bid}) == 1
        dash = requests.get(f"{API}/pro/dashboard", headers=h(drv[0])).json()
        assert any(x["booking_id"] == bid for x in dash["upcoming"])
        S["bid"], S["bdrv"] = bid, drv

    def test_rent_request_decline_all(self):
        r = requests.post(f"{API}/hire/requests", headers=h(S["pax"]), json=body(time="14:00", driver_id=S["R"][1]))
        assert r.status_code == 200, r.text
        rid = r.json()["request_id"]
        assert r.json()["notified"] == 1
        assert requests.post(f"{API}/hire/requests/{rid}/decline", headers=h(S["R"][0])).status_code == 200
        assert t._db().hire_requests.find_one({"request_id": rid})["status"] == "declined"
        assert t._db().notifications.count_documents({"user_id": S["pax_id"], "type": "local_hire_declined", "ref": rid}) == 1

    def test_favourite(self):
        assert requests.post(f"{API}/hire/favourites/{S['R'][1]}", headers=h(S["pax"])).json()["favourite"] is True
        assert any(f["user_id"] == S["R"][1] for f in requests.get(f"{API}/hire/favourites", headers=h(S["pax"])).json())
        assert q(service="rent", time="16:00")[S["R"][1]]["favourite"] is True

    def test_admin(self):
        d = requests.get(f"{API}/admin/hire-bookings", headers=h(S["adm"]), params={"service": "book"}).json()
        assert any(b["booking_id"] == S["bid"] for b in d["bookings"])
        assert all(b.get("service") == "book" for b in d["bookings"])
        rows = requests.get(f"{API}/admin/pro-drivers", headers=h(S["adm"]), params={"status": "approved", "service": "book"}).json()
        assert any(p["user_id"] == S["B"][1] for p in rows) and not any(p["user_id"] == S["R"][1] for p in rows)
        assert requests.get(f"{API}/admin/hire-reports", headers=h(S["adm"])).status_code == 200
