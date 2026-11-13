"""Iteration 16: retest of iter15 local-hire fixes - window end/overnight, multi-clash, expiry, same-driver accept race,
notification params, rate limit only on success. Run: pytest test_iter16_hire_fixes.py -c /dev/null -p no:xdist -v ; then python cleanup_iter15.py"""
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import requests

from test_travoo_api import API, h
import test_iter15_lgd_local_hire as t

S = t.S
IST = timezone(timedelta(hours=5, minutes=30))
INSERTED_HIRES, INSERTED_REQS = [], []


def ids(params, tok=None):
    return {x["user_id"] for x in t.local({"subdistrict_code": t.HIRIYUR, **params}, tok)["local"]}


def ist_utc(date, time):
    return datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M").replace(tzinfo=IST).astimezone(timezone.utc)


# ---- setup: W 06-20, N overnight 20-06, M 06-22 (used for clashes)
class TestSetup:
    def test_setup(self):
        S["adm"] = t.admin_token()
        assert S["adm"]
        S["city"] = t.loc("Hiriyur")
        S["pax"], S["pax_id"], _ = t.reg("HirePax16")
        S["W"] = t.make_driver("W", t.HIRIYUR)
        S["N"] = t.make_driver("N", t.HIRIYUR, start_time="20:00", end_time="06:00")
        S["M"] = t.make_driver("M", t.HIRIYUR, end_time="22:00")


# ---- time window: whole hire inside window, overnight windows
class TestWindow:
    def test_day_window_end_excluded(self):
        assert S["W"][1] not in ids({"date": t.future_date(10), "time": "19:00", "hours": 4})

    def test_day_window_inside_included(self):
        assert S["W"][1] in ids({"date": t.future_date(10), "time": "10:00", "hours": 4})

    def test_day_window_exact_end_included(self):
        assert S["W"][1] in ids({"date": t.future_date(10), "time": "16:00", "hours": 4})

    def test_day_window_before_start_excluded(self):
        assert S["W"][1] not in ids({"date": t.future_date(10), "time": "05:00", "hours": 2})

    def test_overnight_22_included(self):
        got = ids({"date": t.future_date(10), "time": "22:00", "hours": 4})
        assert S["N"][1] in got and S["W"][1] not in got

    def test_overnight_04_plus4_excluded(self):
        assert S["N"][1] not in ids({"date": t.future_date(10), "time": "04:00", "hours": 4})

    def test_overnight_early_morning_inside_included(self):
        assert S["N"][1] in ids({"date": t.future_date(10), "time": "02:00", "hours": 3})

    def test_overnight_midday_excluded(self):
        assert S["N"][1] not in ids({"date": t.future_date(10), "time": "12:00", "hours": 2})


# ---- has_clash loops all overlapping hires
class TestMultiClash:
    def test_multiple_hires(self):
        db, d = t._db(), t.future_date(11)
        for tm, hrs in (("08:00", 2), ("13:00", 3)):
            bid = "TEST-HIR-" + uuid.uuid4().hex[:6].upper()
            db.hires.insert_one({"booking_id": bid, "driver_id": S["M"][1], "passenger_id": S["pax_id"], "status": "confirmed",
                                 "date": d, "time": tm, "hours": hrs, "starts_at": ist_utc(d, tm), "created_at": datetime.now(timezone.utc)})
            INSERTED_HIRES.append(bid)
        m = S["M"][1]
        assert m not in ids({"date": d, "time": "14:00", "hours": 2}), "second (later) clashing hire ignored"
        assert m not in ids({"date": d, "time": "07:00", "hours": 2}), "first clashing hire ignored"
        assert m not in ids({"date": d, "time": "09:00", "hours": 6}), "hire spanning both clashes not excluded"
        assert m in ids({"date": d, "time": "10:30", "hours": 2}), "free gap between hires should match"
        assert m in ids({"date": d, "time": "16:00", "hours": 2}), "slot right after second hire should match"


# ---- expiry + accept on past request
class TestExpiry:
    def _past_request(self, driver_uid, minutes_ago=30):
        db = t._db()
        st = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
        rid = "LHR-TEST" + uuid.uuid4().hex[:4].upper()
        db.hire_requests.insert_one({"request_id": rid, "service_type": "hourly", "date": st.astimezone(IST).strftime("%Y-%m-%d"),
                                     "time": st.astimezone(IST).strftime("%H:%M"), "hours": 2, "city": S["city"], "pickup": "TEST past",
                                     "destination": "", "passengers": 1, "vehicle_type": "sedan", "vehicle_desc": "TEST car", "notes": "",
                                     "passenger_id": S["pax_id"], "pickup_taluk": {"code": t.HIRIYUR, "name": "Hiriyur"}, "status": "open",
                                     "starts_at": st, "created_at": st - timedelta(hours=1), "driver_id": None, "booking_id": None})
        db.hire_dispatches.insert_one({"request_id": rid, "driver_id": driver_uid, "group": "local", "notified_at": st, "seen_at": None, "response": None})
        INSERTED_REQS.append(rid)
        return rid

    def test_list_marks_expired(self):
        rid = self._past_request(S["W"][1])
        r = requests.get(f"{API}/hire/requests", headers=h(S["W"][0]))
        assert r.status_code == 200, r.text
        row = next(x for x in r.json()["inbox"] if x["request_id"] == rid)
        assert row["status"] == "expired"
        mine = requests.get(f"{API}/hire/requests", headers=h(S["pax"])).json()["mine"]
        assert next(x for x in mine if x["request_id"] == rid)["status"] == "expired"

    def test_accept_past_request_400(self):
        rid = self._past_request(S["W"][1], 5)
        r = requests.post(f"{API}/hire/requests/{rid}/accept", headers=h(S["W"][0]))
        assert r.status_code == 400, r.text
        doc = t._db().hire_requests.find_one({"request_id": rid})
        assert doc["status"] == "expired" and t._db().hires.count_documents({"request_id": rid}) == 0


# ---- same driver accepting two overlapping requests concurrently
class TestSameDriverRace:
    def test_concurrent_overlapping_accepts(self):
        d = t.future_date(12)
        rids = []
        for i in range(2):
            pax, _, _ = t.reg(f"HirePaxR{i}")
            r = requests.post(f"{API}/hire/requests", headers=h(pax), json=t.req_body(date=d, time="10:00" if i == 0 else "11:00", hours=3))
            assert r.status_code == 200, r.text
            rids.append(r.json()["request_id"])
        S["requests"] += rids
        tok, uid = S["M"]
        with ThreadPoolExecutor(2) as ex:
            res = list(ex.map(lambda rid: requests.post(f"{API}/hire/requests/{rid}/accept", headers=h(tok)), rids))
        codes = sorted(x.status_code for x in res)
        db = t._db()
        n = db.hires.count_documents({"driver_id": uid, "request_id": {"$in": rids}})
        states = {rr["request_id"]: rr["status"] for rr in db.hire_requests.find({"request_id": {"$in": rids}})}
        print("codes", codes, "hires", n, "states", states, [x.text for x in res])
        assert n <= 1, f"driver double-booked: {n} hires"
        assert list(states.values()).count("fulfilled") == n
        assert codes == [200, 409], f"expected exactly one winner, got {codes} (both rolled back?)"
        loser = [rid for rid, x in zip(rids, res) if x.status_code == 409][0]
        assert states[loser] == "open", "loser request should be back to open"
        # sequential re-attempt on the loser is still rejected (pre-check)
        assert requests.post(f"{API}/hire/requests/{loser}/accept", headers=h(tok)).status_code == 409
        # another driver (W) can still take the loser request
        r = requests.post(f"{API}/hire/requests/{loser}/accept", headers=h(S["W"][0]))
        assert r.status_code == 200, r.text


    def test_race_stress_rounds(self):
        """5 rounds with a barrier so both accepts hit the claim/rollback path at once; never >1 hire, ideally exactly 1 winner."""
        import threading
        tok, uid = S["M"]
        pax = [t.reg(f"HirePaxS{i}")[0] for i in range(2)]
        outcomes = []
        for rnd in range(5):
            d = t.future_date(20 + rnd)
            rids = []
            for i in range(2):
                r = requests.post(f"{API}/hire/requests", headers=h(pax[i]), json=t.req_body(date=d, time="10:00" if i == 0 else "11:00", hours=3))
                assert r.status_code == 200, r.text
                rids.append(r.json()["request_id"])
            S["requests"] += rids
            bar = threading.Barrier(2)

            def go(rid):
                bar.wait()
                return requests.post(f"{API}/hire/requests/{rid}/accept", headers=h(tok))
            with ThreadPoolExecutor(2) as ex:
                res = list(ex.map(go, rids))
            n = t._db().hires.count_documents({"driver_id": uid, "request_id": {"$in": rids}})
            outcomes.append((sorted(x.status_code for x in res), n, [x.json().get("detail", "ok") for x in res]))
        print("stress", outcomes)
        assert all(o[1] <= 1 for o in outcomes), f"double booking: {outcomes}"
        assert all(o[0] == [200, 409] for o in outcomes), f"rounds without a winner: {outcomes}"


# ---- notification params
class TestNotification:
    def test_notification_params(self):
        d = t.future_date(13)
        r = requests.post(f"{API}/hire/requests", headers=h(S["pax"]), json=t.req_body(date=d, time="09:00", hours=2, pickup="TEST Hiriyur Bus Stand"))
        assert r.status_code == 200, r.text
        rid = r.json()["request_id"]
        S["requests"].append(rid)
        n = t._db().notifications.find_one({"user_id": S["W"][1], "type": "local_hire_request", "ref": rid})
        assert n, "driver W not notified"
        p = n["params"]
        assert p["pickup"] == "TEST Hiriyur Bus Stand"
        assert p["taluk"] == "Hiriyur Taluk"
        assert p["date"] == datetime.strptime(d, "%Y-%m-%d").strftime("%d %b %Y")
        assert p["time"] == "09:00" and p["passengers"] == 2 and p["local"] is True


# ---- rate limit counts only successful creates
class TestRateLimit:
    def test_failed_attempts_not_counted(self):
        pax, _, _ = t.reg("HirePaxRL")
        for _ in range(12):  # 404: no luxury drivers
            r = requests.post(f"{API}/hire/requests", headers=h(pax), json=t.req_body(date=t.future_date(14), vehicle_type="luxury"))
            assert r.status_code == 404, r.text
        r = requests.post(f"{API}/hire/requests", headers=h(pax), json=t.req_body(date=t.future_date(14), time="07:00", hours=1))
        assert r.status_code == 200, f"success blocked after 404s: {r.status_code} {r.text}"
        S["requests"].append(r.json()["request_id"])
        for _ in range(11):  # 409 duplicates
            r2 = requests.post(f"{API}/hire/requests", headers=h(pax), json=t.req_body(date=t.future_date(14), time="07:00", hours=1))
            assert r2.status_code == 409, r2.text
        r = requests.post(f"{API}/hire/requests", headers=h(pax), json=t.req_body(date=t.future_date(15), time="07:00", hours=1))
        assert r.status_code == 200, f"success blocked after 409s: {r.status_code} {r.text}"
        S["requests"].append(r.json()["request_id"])


class TestZCleanupInserted:
    def test_cleanup(self):
        db = t._db()
        db.hires.delete_many({"booking_id": {"$in": INSERTED_HIRES}})
        db.hire_dispatches.delete_many({"request_id": {"$in": INSERTED_REQS}})
        db.hire_requests.delete_many({"request_id": {"$in": INSERTED_REQS}})
