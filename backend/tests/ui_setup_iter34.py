"""Iteration 29 UI setup (driver bottom tabs): python ui_setup_iter29.py create|hire|state|cleanup. State in /tmp/ui34.json
drv = approved local driver (rent), account_type driver; pax = passenger who sends hire requests to drv; fresh = driver-mode user without profile"""
import json
import sys
import uuid

import requests

from test_travoo_api import API, h
from test_iter8_admin_docs_reset import real_image
import test_iter15_lgd_local_hire as t

db = t._db()
F = "/tmp/ui34.json"
ADMIN_PW = "TravooAdmin2026x"


def st():
    try:
        return json.load(open(F))
    except Exception:
        return {}


def mk(name, mode, docs=False):
    email = f"test_{name.lower()}_{uuid.uuid4().hex[:6]}@example.com"
    d = requests.post(f"{API}/auth/register", json={"email": email, "password": "Passw0rd!x", "name": f"TEST_{name}", "consent": True}).json()
    tok, uid = d["token"], d["user"]["user_id"]
    requests.put(f"{API}/me", headers=h(tok), json={"phone": f"98{uuid.uuid4().int % 10**8:08d}", "dob": "12-03-1990", "gender": "male", "account_type": mode})
    if docs:
        for k in ("licence_front", "licence_back", "id_proof"):
            requests.post(f"{API}/driver/documents/{k}", headers=h(tok), files={"file": ("a.jpg", real_image(uuid.uuid4().int % 900 + 1), "image/jpeg")}, timeout=120)
    return {"email": email, "tok": tok, "uid": uid}


cmd = sys.argv[1]
s = st()
if cmd == "create":
    a = requests.post(f"{API}/admin/auth/login", json={"email": "admin@travoo.in", "password": ADMIN_PW}).json()["token"]
    s = {"drv": mk("UiDrv34", "driver", True), "pax": mk("UiPax34", "passenger"), "fresh": mk("UiFresh34", "driver")}
    body = {"home": {"subdistrict_code": "5436", "city": "TEST Town", "place": {"loc_id": "TEST_ui34", "name": "TEST Gokak", "type": "town", "lat": 16.167, "lng": 74.833}},
            "languages": ["Kannada"], "licence_no": "KA0120201234567", "licence_expiry": "01-01-2035", "services": ["rent"], "vehicle_ids": []}
    print("reg", requests.post(f"{API}/pro/register", headers=h(s["drv"]["tok"]), json=body).status_code)
    print("approve", requests.post(f"{API}/admin/pro-drivers/{s['drv']['uid']}/review", headers=h(a), json={"decision": "approved", "note": ""}).status_code)
    json.dump(s, open(F, "w"))
    print(json.dumps({k: v["email"] for k, v in s.items()}))
elif cmd == "hire":
    tok = s["drv"]["tok"]
    print("online", requests.put(f"{API}/pro/settings", headers=h(tok), json={"availability_status": "available"}).status_code)
    for i, hh in enumerate(sys.argv[2:] or ["10:00"]):
        b = {"service": "rent", "service_type": "hourly", "date": t.future_date(3 + i), "time": hh, "hours": 3,
             "city": {"loc_id": "TEST_ui34", "name": "TEST Gokak", "type": "town", "lat": 16.167, "lng": 74.833},
             "pickup": "TEST bus stand", "destination": "TEST temple", "passengers": 1, "subdistrict_code": "5436"}
        r = requests.post(f"{API}/hire/requests", headers=h(s["pax"]["tok"]), json=b)
        print(r.status_code, r.text[:150])
elif cmd == "state":
    for k in ("drv", "fresh"):
        r = requests.get(f"{API}/hire/requests", headers=h(s[k]["tok"])).json()
        print(k, "inbox", len(r.get("inbox", [])), "mine", len(r.get("mine", [])))
    print("drv bookings", [(x["booking_id"], x["status"], x.get("driver_id") == s["drv"]["uid"]) for x in requests.get(f"{API}/hire/bookings", headers=h(s["drv"]["tok"])).json()])
elif cmd == "cleanup":
    for k in ("drv", "pax", "fresh"):
        uid = s[k]["uid"]
        for c, f in (("pro_drivers", "user_id"), ("driver_documents", "user_id"), ("vehicles", "owner_id"), ("files", "owner_id"),
                     ("hire_requests", "passenger_id"), ("hire_dispatches", "driver_id"), ("hires", "driver_id"), ("hires", "passenger_id"),
                     ("earnings_ledger", "user_id"), ("notifications", "user_id"), ("user_sessions", "user_id"), ("users", "user_id")):
            db[c].delete_many({f: uid})
    print("cleaned")
