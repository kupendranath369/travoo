"""Iteration 25 UI setup: python ui_setup_iter25.py create|approve|hire|cleanup. State in /tmp/ui25.json"""
import json
import sys
import uuid

import requests

from test_travoo_api import API, h
from test_iter8_admin_docs_reset import real_image
import test_iter15_lgd_local_hire as t

db = t._db()
F = "/tmp/ui25.json"
ADMIN_PW = "TravooAdmin2026x"


def st():
    try:
        return json.load(open(F))
    except Exception:
        return {}


def save(s):
    json.dump(s, open(F, "w"))


def mk(name):
    email = f"test_{name.lower()}_{uuid.uuid4().hex[:6]}@example.com"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": "Passw0rd!x", "name": f"TEST_{name}", "consent": True})
    d = r.json()
    tok, uid = d["token"], d["user"]["user_id"]
    requests.put(f"{API}/me", headers=h(tok), json={"phone": f"98{uuid.uuid4().int % 10**8:08d}", "dob": "12-03-1990", "gender": "male"})
    return {"email": email, "tok": tok, "uid": uid}


cmd = sys.argv[1]
s = st()
if cmd == "create":
    d = mk("UiDrv25")
    db.users.update_one({"user_id": d["uid"]}, {"$set": {"driver_status": "approved"}})
    db.driver_documents.update_one({"user_id": d["uid"]}, {"$set": {"user_id": d["uid"], "licence_no": "KA0920190007777", "licence_expiry": "01-01-2036"}}, upsert=True)
    for k in ("licence_front", "licence_back", "id_proof"):
        r = requests.post(f"{API}/driver/documents/{k}", headers=h(d["tok"]), files={"file": ("a.jpg", real_image(uuid.uuid4().int % 900), "image/jpeg")}, timeout=120)
        print(k, r.status_code)
    s["drv"] = d
    s["pax"] = mk("UiPax25")
    save(s)
    print(json.dumps({k: v["email"] for k, v in s.items()}))
elif cmd == "approve":
    a = requests.post(f"{API}/admin/auth/login", json={"email": "admin@travoo.in", "password": ADMIN_PW}).json()["token"]
    print(requests.post(f"{API}/admin/pro-drivers/{s['drv']['uid']}/review", headers=h(a), json={"decision": "approved", "note": ""}).text)
    for v in db.vehicles.find({"owner_id": s["drv"]["uid"], "deleted": {"$ne": True}}):
        print(v["reg_no"], requests.post(f"{API}/admin/vehicles/{v['vehicle_id']}/commercial", headers=h(a), json={"decision": "approved"}).text)
elif cmd == "hire":  # passenger requests a Rent hire for the UI driver (needs driver online)
    tok = s["drv"]["tok"]
    print(requests.put(f"{API}/pro/settings", headers=h(tok), json={"availability_status": "available"}).status_code)
    b = {"service": "rent", "service_type": "hourly", "date": t.future_date(3), "time": "10:00", "hours": 3,
         "city": {"loc_id": "TEST_ui25", "name": "TEST Hiriyur", "type": "town", "lat": 13.944, "lng": 76.617},
         "pickup": "TEST bus stand", "destination": "TEST temple", "passengers": 1, "subdistrict_code": "5508"}
    r = requests.post(f"{API}/hire/requests", headers=h(s["pax"]["tok"]), json=b)
    print(r.status_code, r.text[:200])
elif cmd == "cleanup":
    for k in ("drv", "pax"):
        uid = s[k]["uid"]
        for c, f in (("pro_drivers", "user_id"), ("driver_documents", "user_id"), ("vehicles", "owner_id"), ("files", "owner_id"),
                     ("hire_requests", "passenger_id"), ("hire_dispatches", "driver_id"), ("hires", "driver_id"), ("hires", "passenger_id"),
                     ("notifications", "user_id"), ("users", "user_id")):
            db[c].delete_many({f: uid})
    print("cleaned")
