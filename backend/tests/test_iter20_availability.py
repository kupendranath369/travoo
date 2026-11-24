"""Iteration 20: local-driver availability schedules - /pro/register + /pro/settings storage/validation, and hire matching regression.
Run: cd /app/backend/tests && pytest test_iter20_availability.py -c /dev/null -p no:xdist -v"""
import uuid

import pytest
import requests

from test_travoo_api import API, h
from test_iter8_admin_docs_reset import real_image
import test_iter15_lgd_local_hire as t

S = {}
CREATED_UIDS = []


def make_driver(name, availability=None):
    tok, uid, email = t.reg(name)
    CREATED_UIDS.append(uid)
    assert requests.put(f"{API}/me", headers=h(tok), json={"phone": f"98{uuid.uuid4().int % 10**8:08d}"}).status_code == 200
    assert requests.post(f"{API}/me/photo", headers=h(tok), files={"file": ("p.jpg", real_image(uuid.uuid4().int % 900), "image/jpeg")}, timeout=120).status_code == 200
    r = requests.post(f"{API}/driver/documents/licence_front", headers=h(tok), files={"file": ("l.jpg", real_image(uuid.uuid4().int % 900 + 1), "image/jpeg")}, timeout=120)
    assert r.status_code == 200, r.text
    kw = {"availability": availability} if availability is not None else {}
    r = requests.post(f"{API}/pro/register", headers=h(tok), json=t.pro_body(S["city"], t.HIRIYUR, **kw))
    assert r.status_code == 200, r.text
    t._db().pro_drivers.update_one({"user_id": uid}, {"$set": {"status": "approved"}})
    return tok, uid


@pytest.fixture(scope="module", autouse=True)
def setup_and_cleanup():
    S["city"] = t.loc("Hiriyur")
    S["d"] = t.future_date(6)
    S["d2"] = t.future_date(7)
    yield
    db = t._db()
    for uid in CREATED_UIDS:
        db.pro_drivers.delete_one({"user_id": uid})
        db.driver_documents.delete_one({"user_id": uid})
        db.hire_requests.delete_many({"passenger_id": uid})
        db.notifications.delete_many({"user_id": uid})
        db.users.delete_one({"user_id": uid})


def iso(d, hm):
    return f"{d}T{hm}:00+05:30"


# ---- register stores availability with ids
class TestRegister:
    def test_register_stores_ids(self):
        d = S["d"]
        tok, uid = make_driver("Av20A", [{"date": d, "from": iso(d, "09:00"), "to": iso(d, "13:00")}])
        S["A"] = (tok, uid)
        p = requests.get(f"{API}/pro/me", headers=h(tok)).json()["profile"]
        av = p["availability"]
        assert len(av) == 1 and isinstance(av[0]["id"], str) and av[0]["id"]
        assert av[0]["from"][11:16] == "09:00" and av[0]["to"][11:16] == "13:00" and av[0]["status"] == "active"

    def test_register_invalid_end_before_start(self):
        tok, uid, _ = t.reg("Av20Bad")
        CREATED_UIDS.append(uid)
        assert requests.put(f"{API}/me", headers=h(tok), json={"phone": f"98{uuid.uuid4().int % 10**8:08d}"}).status_code == 200
        assert requests.post(f"{API}/me/photo", headers=h(tok), files={"file": ("p.jpg", real_image(uuid.uuid4().int % 900), "image/jpeg")}, timeout=120).status_code == 200
        requests.post(f"{API}/driver/documents/licence_front", headers=h(tok), files={"file": ("l.jpg", real_image(uuid.uuid4().int % 900 + 1), "image/jpeg")}, timeout=120)
        d = S["d"]
        r = requests.post(f"{API}/pro/register", headers=h(tok), json=t.pro_body(S["city"], t.HIRIYUR, availability=[{"date": d, "from": iso(d, "13:00"), "to": iso(d, "09:00")}]))
        assert r.status_code == 400, r.text


# ---- /pro/settings availability
class TestSettings:
    def test_put_with_ids_persists(self):
        tok, _ = S["A"]
        d, d2 = S["d"], S["d2"]
        body = {"availability": [{"id": "fixedid1", "date": d, "from": iso(d, "09:00"), "to": iso(d, "18:00")},
                                 {"date": d2, "from": iso(d2, "08:30"), "to": iso(d2, "12:15")}]}
        r = requests.put(f"{API}/pro/settings", headers=h(tok), json=body)
        assert r.status_code == 200, r.text
        av = requests.get(f"{API}/pro/me", headers=h(tok)).json()["profile"]["availability"]
        assert len(av) == 2
        assert av[0]["id"] == "fixedid1" and av[0]["from"][11:16] == "09:00" and av[0]["to"][11:16] == "18:00"
        assert av[1]["id"] and av[1]["id"] != "fixedid1" and av[1]["from"][11:16] == "08:30"
        S["gen_id"] = av[1]["id"]

    def test_delete_one_keeps_other(self):
        tok, _ = S["A"]
        av = requests.get(f"{API}/pro/me", headers=h(tok)).json()["profile"]["availability"]
        keep = [a for a in av if a["id"] == S["gen_id"]]
        r = requests.put(f"{API}/pro/settings", headers=h(tok), json={"availability": [{k: a[k] for k in ("id", "date", "from", "to")} for a in keep]})
        assert r.status_code == 200
        av2 = requests.get(f"{API}/pro/me", headers=h(tok)).json()["profile"]["availability"]
        assert [a["id"] for a in av2] == [S["gen_id"]]

    @pytest.mark.parametrize("item", [
        {"date": "2026-12-01", "from": "2026-12-01T18:00:00+05:30", "to": "2026-12-01T09:00:00+05:30"},
        {"date": "2026-12-01", "from": "2026-12-01T09:00:00+05:30", "to": "2026-12-01T09:00:00+05:30"},
        {"date": "01-12-2026", "from": "2026-12-01T09:00:00+05:30", "to": "2026-12-01T18:00:00+05:30"},
        {"date": "2026-12-01", "from": "2026-12-01T25:00:00+05:30", "to": "2026-12-01T26:00:00+05:30"},
        {"date": "2026-12-01", "from": "garbage", "to": "2026-12-01T18:00:00+05:30"},
    ])
    def test_invalid_returns_400(self, item):
        tok, _ = S["A"]
        r = requests.put(f"{API}/pro/settings", headers=h(tok), json={"availability": [item]})
        assert r.status_code == 400, r.text

    def test_empty_list_clears(self):
        tok, _ = S["A"]
        d = S["d"]
        r = requests.put(f"{API}/pro/settings", headers=h(tok), json={"availability": []})
        assert r.status_code == 200
        assert requests.get(f"{API}/pro/me", headers=h(tok)).json()["profile"]["availability"] == []
        # restore 09:00-13:00 for matching tests
        r = requests.put(f"{API}/pro/settings", headers=h(tok), json={"availability": [{"date": d, "from": iso(d, "09:00"), "to": iso(d, "13:00")}]})
        assert r.status_code == 200


# ---- hire matching regression with ISO availability
class TestMatching:
    def _local(self, tok, **kw):
        params = {"subdistrict_code": t.HIRIYUR, "date": S["d"], "time": "10:00", "hours": 2, "vehicle_type": "sedan"}
        params.update(kw)
        return requests.get(f"{API}/hire/local-drivers", headers=h(tok), params=params)

    def test_pax(self):
        tok, uid, _ = t.reg("Av20Pax")
        CREATED_UIDS.append(uid)
        S["pax"] = tok

    def test_inside_window_matches(self):
        r = self._local(S["pax"])
        assert r.status_code == 200, r.text[:300]
        assert S["A"][1] in {x["user_id"] for x in r.json()["local"]}, "driver available 09:00-13:00 should match 10:00 x2h"

    def test_outside_window_not_matched(self):
        r = self._local(S["pax"], time="15:00")
        assert r.status_code == 200, r.text[:300]
        assert S["A"][1] not in {x["user_id"] for x in r.json()["local"]}

    def test_other_date_not_matched(self):
        r = self._local(S["pax"], date=S["d2"])
        assert r.status_code == 200, r.text[:300]
        assert S["A"][1] not in {x["user_id"] for x in r.json()["local"]}

    def test_hire_search_ok(self):
        r = requests.get(f"{API}/hire/drivers", headers=h(S["pax"]), params={"lat": S["city"]["lat"], "lng": S["city"]["lng"], "date": S["d"]})
        assert r.status_code == 200, r.text[:300]
