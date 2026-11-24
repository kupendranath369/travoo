"""Iteration 24: verify UI-registered local drivers (YES/NO vehicle switch) via /pro/me, then approve (DB) and check
/hire/local-drivers matching for Rent vs Book on the availability date. Needs /tmp/iter23_users.txt (NO user line 1, YES user line 2)
already registered via the UI with home subdistrict 5916 and availability 2026-12-05 09:00-18:00.
Run: cd /app/backend/tests && pytest test_iter24_hasvehicle_e2e.py -c /dev/null -p no:xdist -v"""
import requests

from test_travoo_api import API, h, login
import test_iter15_lgd_local_hire as t

USERS = [ln.split() for ln in open("/tmp/iter23_users.txt").read().split("\n") if ln.strip()]
NO_EMAIL, NO_UID = USERS[0]
YES_EMAIL, YES_UID = USERS[1]
SD = "5916"
DATE = "2026-12-05"
S = {}


def tok(email):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": "Passw0rd!x"}, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["token"]


def search(**kw):
    p = {"subdistrict_code": SD, "date": DATE, "time": "10:00", "hours": 4, "service": "rent", "service_type": "hourly", "vehicle_type": ""}
    p.update(kw)
    r = requests.get(f"{API}/hire/local-drivers", headers=h(S["pax"]), params=p, timeout=30)
    assert r.status_code == 200, r.text[:300]
    return {x["user_id"] for x in r.json()["local"]}


# ---- /pro/me persisted what the UI sent
class TestProMe:
    def test_no_driver(self):
        p = requests.get(f"{API}/pro/me", headers=h(tok(NO_EMAIL))).json()["profile"]
        assert p["status"] == "under_review"
        assert p["services"] == ["rent"]
        assert p["vehicles"] == []
        assert p["days"] == list(range(7)) and p["start_time"] == "00:00" and p["end_time"] == "23:59"
        assert p["availability"][0]["date"] == DATE

    def test_yes_driver(self):
        p = requests.get(f"{API}/pro/me", headers=h(tok(YES_EMAIL))).json()["profile"]
        assert sorted(p["services"]) == ["book", "rent"]
        assert len(p["vehicles"]) == 1
        v = p["vehicles"][0]
        assert v["reg_no"] == "KA01AB2424" and v["category"] == "suv" and v["day_rate"] == 1200 and v["vehicle_id"]


# ---- matching after approval
class TestMatching:
    def test_setup(self):
        db = t._db()
        db.pro_drivers.update_many({"user_id": {"$in": [NO_UID, YES_UID]}}, {"$set": {"status": "approved"}})
        _, uid, _ = t.reg("Veh24Pax")
        S["pax_id"] = uid
        S["pax"] = tok(db.users.find_one({"user_id": uid})["email"])

    def test_rent_finds_both(self):
        ids = search()
        assert NO_UID in ids and YES_UID in ids

    def test_book_finds_only_yes(self):
        ids = search(service="book", service_type="one_way", vehicle_type="any", passengers=2)
        assert YES_UID in ids and NO_UID not in ids

    def test_book_suv_finds_yes(self):
        assert YES_UID in search(service="book", service_type="one_way", vehicle_type="suv")

    def test_book_too_many_passengers(self):
        assert YES_UID not in search(service="book", service_type="one_way", vehicle_type="any", passengers=6)

    def test_other_date_not_found(self):
        ids = search(date="2026-12-06")
        assert NO_UID not in ids and YES_UID not in ids

    def test_outside_window_not_found(self):
        ids = search(time="16:00", hours=4)  # ends 20:00 > 18:00
        assert NO_UID not in ids and YES_UID not in ids

    def test_cleanup(self):
        db = t._db()
        for uid in [NO_UID, YES_UID, S["pax_id"]]:
            db.pro_drivers.delete_one({"user_id": uid})
            db.driver_documents.delete_one({"user_id": uid})
            db.notifications.delete_many({"user_id": uid})
            db.users.delete_one({"user_id": uid})
