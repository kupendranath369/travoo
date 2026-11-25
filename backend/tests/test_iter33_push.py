"""Iteration 33: push relay (register-push auth/validation) + hire request still succeeds when push upstream fails.
Run: cd /app/backend/tests && pytest test_iter33_push.py -c /dev/null -p no:xdist -v"""
import glob
import uuid

import pytest
import requests

from test_travoo_api import API, h
from test_iter8_admin_docs_reset import real_image
import test_iter15_lgd_local_hire as t

db = t._db()
S = {}
UIDS = []
ADMIN_PW = "TravooAdmin2026x"
CITY = {"loc_id": "TEST_ui33", "name": "TEST Gokak", "type": "town", "lat": 13.944, "lng": 76.617}


def log_count():
    n = 0
    for f in glob.glob("/var/log/supervisor/backend*.log"):
        n += open(f, errors="ignore").read().count("push failed (non-blocking)")
    return n


def mk(name, mode, docs=False):
    email = f"test_{name.lower()}_{uuid.uuid4().hex[:6]}@example.com"
    d = requests.post(f"{API}/auth/register", json={"email": email, "password": "Passw0rd!x", "name": f"TEST_{name}", "consent": True}).json()
    tok, uid = d["token"], d["user"]["user_id"]
    UIDS.append(uid)
    requests.put(f"{API}/me", headers=h(tok), json={"phone": f"98{uuid.uuid4().int % 10**8:08d}", "dob": "12-03-1990", "gender": "male", "account_type": mode})
    if docs:
        for k in ("licence_front", "licence_back", "id_proof"):
            requests.post(f"{API}/driver/documents/{k}", headers=h(tok), files={"file": ("a.jpg", real_image(uuid.uuid4().int % 900 + 1), "image/jpeg")}, timeout=120)
    return tok, uid


def mk_driver(name, admin):
    tok, uid = mk(name, "driver", True)
    body = {"home": {"subdistrict_code": "5436", "city": "TEST Town", "place": CITY}, "languages": ["Kannada"],
            "licence_no": "KA0120201234567", "licence_expiry": "01-01-2035", "services": ["rent"], "vehicle_ids": []}
    r = requests.post(f"{API}/pro/register", headers=h(tok), json=body)
    assert r.status_code == 200, r.text
    r = requests.post(f"{API}/admin/pro-drivers/{uid}/review", headers=h(admin), json={"decision": "approved", "note": ""})
    assert r.status_code == 200, r.text
    return tok, uid


@pytest.fixture(scope="module", autouse=True)
def setup():
    a = requests.post(f"{API}/admin/auth/login", json={"email": "admin@travoo.in", "password": ADMIN_PW}).json()["token"]
    S["pax"] = mk("Pax33", "passenger")
    S["on"] = mk_driver("On33", a)
    S["sch"] = mk_driver("Sch33", a)
    S["d"] = t.future_date(5)
    yield
    for uid in UIDS:
        for c, f in (("pro_drivers", "user_id"), ("driver_documents", "user_id"), ("vehicles", "owner_id"), ("files", "owner_id"),
                     ("hire_requests", "passenger_id"), ("hire_dispatches", "driver_id"), ("hires", "driver_id"), ("hires", "passenger_id"),
                     ("earnings_ledger", "user_id"), ("notifications", "user_id"), ("user_sessions", "user_id"), ("users", "user_id")):
            db[c].delete_many({f: uid})


# register-push: auth + validation + preview placeholder key
class TestRegisterPush:
    def test_no_auth(self):
        r = requests.post(f"{API}/register-push", json={"platform": "android", "device_token": "x" * 20})
        assert r.status_code in (401, 403)

    def test_invalid_platform_422(self):
        r = requests.post(f"{API}/register-push", headers=h(S["pax"][0]), json={"platform": "web", "device_token": "x" * 20})
        assert r.status_code == 422

    def test_short_token_422(self):
        r = requests.post(f"{API}/register-push", headers=h(S["pax"][0]), json={"platform": "ios", "device_token": "abc"})
        assert r.status_code == 422

    @pytest.mark.parametrize("plat", ["android", "ios"])
    def test_with_auth_placeholder_key(self, plat):
        r = requests.post(f"{API}/register-push", headers=h(S["pax"][0]), json={"platform": plat, "device_token": "ExponentPushToken[" + "a" * 22 + "]"})
        assert r.status_code == 500, r.text
        assert "EMERGENT_PUSH_KEY" in r.json().get("detail", "")


# hire request: online driver gets push attempt (fails non-blocking), scheduled-only driver gets none
class TestHireWithPush:
    def test_hire_online_and_scheduled(self):
        d = S["d"]
        on_tok, on_uid = S["on"]
        sch_tok, sch_uid = S["sch"]
        assert requests.put(f"{API}/pro/settings", headers=h(on_tok), json={"availability_status": "available"}).status_code == 200
        r = requests.put(f"{API}/pro/settings", headers=h(sch_tok), json={"availability_status": "offline",
                         "availability": [{"date": d, "from": f"{d}T06:00:00+05:30", "to": f"{d}T20:00:00+05:30"}]})
        assert r.status_code == 200, r.text
        before = log_count()
        b = {"service": "rent", "service_type": "hourly", "date": d, "time": "10:00", "hours": 3, "city": CITY,
             "pickup": "TEST bus stand", "destination": "TEST temple", "passengers": 1, "subdistrict_code": "5436"}
        r = requests.post(f"{API}/hire/requests", headers=h(S["pax"][0]), json=b, timeout=60)
        assert r.status_code == 200, r.text
        j = r.json()
        rid = j["request_id"]
        assert "_id" not in j
        assert j["notified"] >= 2
        disp = {x["driver_id"] for x in db.hire_dispatches.find({"request_id": rid})}
        assert on_uid in disp and sch_uid in disp
        for uid in (on_uid, sch_uid):
            assert db.notifications.count_documents({"user_id": uid, "type": "local_hire_request"}) >= 1
        import time
        time.sleep(1)
        delta = log_count() - before
        print("push failed log delta:", delta)
        assert delta == 1, f"expected exactly 1 push attempt (online driver only), got {delta}"
        # inbox visible to both drivers
        for tok in (on_tok, sch_tok):
            inbox = requests.get(f"{API}/hire/requests", headers=h(tok)).json().get("inbox", [])
            assert any(x.get("request_id") == rid for x in inbox)
