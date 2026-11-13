"""Stress: one driver accepts N overlapping requests at once (direct to backend :8001 for tight timing). Run: python race_stress_iter16.py; then python cleanup_iter15.py"""
import threading
from concurrent.futures import ThreadPoolExecutor

import requests

import test_iter15_lgd_local_hire as t
from test_travoo_api import h

API = "http://localhost:8001/api"
S = t.S
S["adm"] = t.admin_token()
S["city"] = t.loc("Hiriyur")
tok, uid = t.make_driver("RS", t.HIRIYUR, end_time="23:00")
N = 6
for rnd in range(3):
    d = t.future_date(30 + rnd)
    rids = []
    for i in range(N):
        pax = t.reg(f"HirePaxRS{rnd}{i}")[0]
        r = requests.post(f"{API}/hire/requests", headers=h(pax), json=t.req_body(date=d, time=f"{10 + i}:00", hours=3))
        assert r.status_code == 200, r.text
        rids.append(r.json()["request_id"])
    bar = threading.Barrier(N)

    def go(rid):
        bar.wait()
        return requests.post(f"{API}/hire/requests/{rid}/accept", headers=h(tok))
    with ThreadPoolExecutor(N) as ex:
        res = list(ex.map(go, rids))
    db = t._db()
    hires = list(db.hires.find({"driver_id": uid, "request_id": {"$in": rids}}, {"_id": 0, "time": 1}))
    states = [x["status"] for x in db.hire_requests.find({"request_id": {"$in": rids}})]
    print(f"round {rnd}: codes={[x.status_code for x in res]} hires={[x['time'] for x in hires]} states={states}")
    print("   details:", [x.json().get("detail", "ok")[:40] for x in res])
