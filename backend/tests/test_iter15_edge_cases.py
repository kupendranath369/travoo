"""Iteration 15 edge cases: concurrent accept on one request, booking window end, unique dispatch index.
Run after test_iter15_lgd_local_hire.py in the same session: pytest test_iter15_lgd_local_hire.py test_iter15_edge_cases.py -c /dev/null -p no:xdist"""
from concurrent.futures import ThreadPoolExecutor

import requests

from test_travoo_api import API, h
import test_iter15_lgd_local_hire as t

S = t.S


class TestEdges:
    def test_unique_dispatch_index(self):
        idx = t._db().hire_dispatches.index_information()
        assert any(v.get("unique") and [k for k, _ in v["key"]] == ["request_id", "driver_id"] for v in idx.values()), idx

    def test_concurrent_accept_single_winner(self):
        pax, _, _ = t.reg("HirePaxRace")
        r = requests.post(f"{API}/hire/requests", headers=h(pax), json=t.req_body(time="17:00", hours=2, date=t.future_date(5)))
        assert r.status_code == 200, r.text
        rid = r.json()["request_id"]
        S["requests"].append(rid)
        toks = [S["drivers"][k][0] for k in "AB"]
        with ThreadPoolExecutor(2) as ex:
            codes = list(ex.map(lambda tk: requests.post(f"{API}/hire/requests/{rid}/accept", headers=h(tk)).status_code, toks))
        assert sorted(codes) == [200, 409], codes
        assert t._db().hires.count_documents({"request_id": rid}) == 1

    def test_hire_end_beyond_driver_window(self):
        """Driver window 06:00-20:00; a 19:00 start for 4h ends 23:00 - should not match (reported if it does)."""
        d = t.local({"subdistrict_code": t.HIRIYUR, "date": t.future_date(6), "time": "19:00", "hours": 4})
        ids = {x["user_id"] for x in d["local"]}
        assert S["drivers"]["B"][1] not in ids, "driver matched although hire ends after availability window"
