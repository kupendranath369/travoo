"""Iteration 41: driver reschedules a published trip via PUT /api/trips/{tid} (date/time) + passenger notifications."""
import uuid
from datetime import datetime, timedelta

import pytest
import requests

from test_travoo_api import API, IST, h, loc, register
import test_iter15_lgd_local_hire as t

db = t._db()
S = {}


def fut(days, hh="09:00"):
    return (datetime.now(IST) + timedelta(days=days)).strftime("%Y-%m-%d"), hh


@pytest.fixture(scope="module", autouse=True)
def setup():
    # carpool driver (approved directly in DB) + vehicle + trip + two passengers (one confirmed, one cancelled)
    dtok, du, _ = register("resdrv")
    db.users.update_one({"user_id": du["user_id"]}, {"$set": {"driver_status": "approved", "phone": "9876500041"}})
    v = requests.post(f"{API}/vehicles", headers=h(dtok), json={"make": "Maruti", "model": "Ertiga", "vtype": "muv",
                                                                 "reg_no": f"KA01R{uuid.uuid4().int % 9999:04d}", "seats": 6, "ac": True}).json()
    d, tm = fut(10)
    r = requests.post(f"{API}/trips", headers=h(dtok), json={
        "origin": loc("Bengaluru"), "destination": loc("Mysuru"), "pickup_point": "TEST Silk Board", "drop_point": "TEST Mysore bus stand",
        "date": d, "time": tm, "seats": 3, "price": 300, "vehicle_id": v["vehicle_id"], "instant_booking": True, "fuel_price": 102, "mileage": 15})
    assert r.status_code == 200, r.text
    S.update(dtok=dtok, duid=du["user_id"], trip=r.json(), vid=v["vehicle_id"])
    p1, pu1, _ = register("respax1")
    p2, pu2, _ = register("respax2")
    b1 = requests.post(f"{API}/bookings", headers=h(p1), json={"trip_id": S["trip"]["trip_id"], "seats": 1})
    assert b1.status_code == 200, b1.text
    b2 = requests.post(f"{API}/bookings", headers=h(p2), json={"trip_id": S["trip"]["trip_id"], "seats": 1}).json()
    db.bookings.update_one({"booking_id": b2["booking_id"]}, {"$set": {"status": "cancelled"}})
    S.update(p1=p1, pu1=pu1["user_id"], b1=b1.json()["booking_id"], p2=p2, pu2=pu2["user_id"], b2=b2["booking_id"])
    yield
    tid = S["trip"]["trip_id"]
    for uid in (S["duid"], S["pu1"], S["pu2"]):
        for c, f in (("notifications", "user_id"), ("user_sessions", "user_id"), ("vehicles", "owner_id"), ("users", "user_id")):
            db[c].delete_many({f: uid})
    db.messages.delete_many({"booking_id": {"$in": [S["b1"], S["b2"]]}})
    db.bookings.delete_many({"trip_id": tid})
    db.trips.delete_many({"trip_id": tid})


def put(body, tok=None, tid=None):
    return requests.put(f"{API}/trips/{tid or S['trip']['trip_id']}", headers=h(tok or S["dtok"]), json=body)


class TestReschedule:
    def test_reschedule_updates_trip_and_bookings(self):
        nd, nt = fut(12, "14:30")
        r = put({"date": nd, "time": nt})
        assert r.status_code == 200, r.text
        tr = r.json()
        assert tr["date"] == nd and tr["time"] == nt and tr.get("rescheduled_at")
        dep = datetime.strptime(f"{nd} {nt}", "%Y-%m-%d %H:%M").replace(tzinfo=IST)
        arr = dep + timedelta(minutes=tr["duration_min"])
        assert tr["arrival_time"] == arr.strftime("%H:%M") and tr["arrival_date"] == arr.strftime("%Y-%m-%d")
        raw = db.trips.find_one({"trip_id": tr["trip_id"]})
        assert raw["departure_at"].strftime("%Y-%m-%d %H:%M") == (dep - timedelta(hours=5, minutes=30)).strftime("%Y-%m-%d %H:%M")
        for bid in (S["b1"], S["b2"]):
            b = db.bookings.find_one({"booking_id": bid})
            assert b["date"] == nd and b["time"] == nt
        g = requests.get(f"{API}/bookings/{S['b1']}", headers=h(S["p1"])).json()
        assert g.get("date") == nd and g.get("time") == nt
        S["nd"], S["nt"] = nd, nt

    def test_notifications_only_active_passengers(self):
        n1 = list(db.notifications.find({"user_id": S["pu1"], "type": "trip_rescheduled"}))
        assert len(n1) == 1, n1
        p = n1[0].get("params") or {}
        assert p.get("date") == S["nd"] and p.get("time") == S["nt"] and p.get("route")
        assert db.notifications.count_documents({"user_id": S["pu2"], "type": "trip_rescheduled"}) == 0
        api_n = requests.get(f"{API}/notifications", headers=h(S["p1"])).json()
        items = api_n if isinstance(api_n, list) else api_n.get("items") or api_n.get("notifications") or []
        assert any(x.get("type") == "trip_rescheduled" for x in items), str(api_n)[:300]

    def test_other_edits_send_trip_updated(self):
        r = put({"notes": "TEST new note", "pickup_point": "TEST Hebbal", "drop_point": "TEST Mysore palace", "seats": 4,
                 "date": S["nd"], "time": S["nt"]})
        assert r.status_code == 200, r.text
        tr = r.json()
        assert tr["notes"] == "TEST new note" and tr["pickup_point"] == "TEST Hebbal" and tr["seats_total"] == 4 and tr["seats_available"] == 2
        assert tr["date"] == S["nd"]
        assert db.notifications.count_documents({"user_id": S["pu1"], "type": "trip_updated"}) == 1
        assert db.notifications.count_documents({"user_id": S["pu1"], "type": "trip_rescheduled"}) == 1

    def test_time_only_change(self):
        r = put({"time": "06:15"})
        assert r.status_code == 200 and r.json()["time"] == "06:15" and r.json()["date"] == S["nd"]
        assert db.notifications.count_documents({"user_id": S["pu1"], "type": "trip_rescheduled"}) == 2

    def test_past_and_too_soon_400(self):
        now = datetime.now(IST)
        for dt in (now - timedelta(days=1), now + timedelta(minutes=10)):
            r = put({"date": dt.strftime("%Y-%m-%d"), "time": dt.strftime("%H:%M")})
            assert r.status_code == 400 and "30 minutes" in r.json().get("detail", ""), r.text
        tr = requests.get(f"{API}/trips/{S['trip']['trip_id']}", headers=h(S["dtok"])).json()
        assert tr["time"] == "06:15"

    @pytest.mark.parametrize("body", [{"date": "2026/12/01"}, {"time": "9:00"}, {"date": "26-12-01"}, {"time": "0900"}])
    def test_bad_format_422(self, body):
        assert put(body).status_code == 422

    def test_invalid_calendar_400(self):
        r = put({"date": "2027-02-30", "time": "10:00"})
        assert r.status_code == 400, r.text
        r = put({"date": fut(5)[0], "time": "25:99"})
        assert r.status_code == 400, r.text

    def test_non_owner_404(self):
        r = put({"date": fut(15)[0], "time": "10:00"}, tok=S["p1"])
        assert r.status_code == 404

    def test_price_change_blocked_with_bookings(self):
        r = put({"price": 250})
        assert r.status_code == 400 and "bookings" in r.json()["detail"]

    def test_cancelled_trip_not_editable(self):
        db.trips.update_one({"trip_id": S["trip"]["trip_id"]}, {"$set": {"status": "cancelled"}})
        try:
            assert put({"date": fut(15)[0], "time": "10:00"}).status_code == 404
        finally:
            db.trips.update_one({"trip_id": S["trip"]["trip_id"]}, {"$set": {"status": "scheduled"}})
