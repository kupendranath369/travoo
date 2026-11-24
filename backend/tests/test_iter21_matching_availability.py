"""Iteration 21: hire matching with ISO availability - window edges, fallback to days/time, POST /hire/requests + accept, has_clash on bookings.
Run: cd /app/backend/tests && pytest test_iter21_matching_availability.py -c /dev/null -p no:xdist -v"""
import requests

from test_travoo_api import API, h
import test_iter15_lgd_local_hire as t
import test_iter20_availability as a20

S = a20.S
D = t.future_date(9)
D2 = t.future_date(11)


def iso(d, hm):
    return f"{d}T{hm}:00+05:30"


def local(tok, **kw):
    p = {"subdistrict_code": t.HIRIYUR, "date": D, "time": "10:00", "hours": 2, "vehicle_type": "sedan"}
    p.update(kw)
    r = requests.get(f"{API}/hire/local-drivers", headers=h(tok), params=p)
    assert r.status_code == 200, r.text[:300]
    return {x["user_id"] for x in r.json()["local"]}


def body(**kw):
    b = {"service": "rent", "service_type": "hourly", "date": D, "time": "10:00", "hours": 2, "city": S["city"], "pickup": "TEST stand",
         "destination": "TEST Hiriyur", "passengers": 1, "vehicle_type": "", "subdistrict_code": t.HIRIYUR}
    b.update(kw)
    return b


class TestSetup:
    def test_setup(self):
        S["city"] = t.loc("Hiriyur")
        S["W"] = a20.make_driver("Av21W", [{"date": D, "from": iso(D, "09:00"), "to": iso(D, "13:00")}])
        S["N"] = a20.make_driver("Av21N")  # no availability -> fallback to days/start_time/end_time 06-20
        S["E"] = a20.make_driver("Av21E", [])  # empty list -> fallback
        tok, uid, _ = t.reg("Av21Pax")
        a20.CREATED_UIDS.append(uid)
        S["pax21"], S["pax21_id"] = tok, uid


# ---- window edges and fallback
class TestMatchingEdges:
    def test_exact_end_boundary_matches(self):
        assert S["W"][1] in local(S["pax21"], time="11:00", hours=2)

    def test_exact_start_boundary_matches(self):
        assert S["W"][1] in local(S["pax21"], time="09:00", hours=4)

    def test_overrun_not_matched(self):
        assert S["W"][1] not in local(S["pax21"], time="12:00", hours=2)

    def test_before_window_not_matched(self):
        assert S["W"][1] not in local(S["pax21"], time="08:00", hours=2)

    def test_other_date_not_matched(self):
        assert S["W"][1] not in local(S["pax21"], date=D2)

    def test_fallback_no_availability(self):
        ids = local(S["pax21"], time="15:00", hours=2)
        assert S["N"][1] in ids and S["E"][1] in ids and S["W"][1] not in ids

    def test_fallback_outside_hours(self):
        ids = local(S["pax21"], time="21:00", hours=2)
        assert S["N"][1] not in ids and S["E"][1] not in ids


# ---- request + accept + has_clash only on bookings
class TestRequestFlow:
    def test_request_to_window_driver(self):
        r = requests.post(f"{API}/hire/requests", headers=h(S["pax21"]), json=body(driver_id=S["W"][1]))
        assert r.status_code == 200, r.text
        S["rid"] = r.json()["request_id"]

    def test_accept(self):
        r = requests.post(f"{API}/hire/requests/{S['rid']}/accept", headers=h(S["W"][0]))
        assert r.status_code == 200, r.text
        S["bid"] = r.json()["booking_id"]

    def test_clash_after_booking(self):
        # W now has a confirmed booking 10-12; an 11:00 request overlaps and must not match W
        assert S["W"][1] not in local(S["pax21"], time="11:00", hours=2)

    def test_non_overlapping_still_matches(self):
        assert S["W"][1] in local(S["pax21"], time="12:00", hours=1)

    def test_broadcast_request_ok(self):
        r = requests.post(f"{API}/hire/requests", headers=h(S["pax21"]), json=body(time="15:00"))
        assert r.status_code == 200, r.text
        disp = {d["driver_id"] for d in t._db().hire_dispatches.find({"request_id": r.json()["request_id"]})}
        assert S["N"][1] in disp and S["W"][1] not in disp, disp


class TestCleanup:
    def test_cleanup(self):
        db = t._db()
        ids = [S["W"][1], S["N"][1], S["E"][1]]
        db.hires.delete_many({"driver_id": {"$in": ids}})
        rids = [r["request_id"] for r in db.hire_requests.find({"passenger_id": S["pax21_id"]})]
        db.hire_dispatches.delete_many({"request_id": {"$in": rids}})
        db.hire_requests.delete_many({"passenger_id": S["pax21_id"]})
        for uid in ids + [S["pax21_id"]]:
            db.pro_drivers.delete_one({"user_id": uid})
            db.driver_documents.delete_one({"user_id": uid})
            db.notifications.delete_many({"user_id": uid})
            db.users.delete_one({"user_id": uid})
