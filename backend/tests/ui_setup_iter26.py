"""Iteration 26 UI setup: python ui_setup_iter26.py create|cleanup. State in /tmp/ui26.json
drv  = approved local driver with services [rent, book] but vehicle pending -> book_ready False
res  = local driver in 'resubmit' (licence_back flagged) for the wizard pro-error check"""
import json
import sys
import uuid

import requests

from test_travoo_api import API, h
from test_iter8_admin_docs_reset import real_image
import test_iter15_lgd_local_hire as t

db = t._db()
F = "/tmp/ui26.json"
ADMIN_PW = "TravooAdmin2026x"


def mk(name):
    email = f"test_{name.lower()}_{uuid.uuid4().hex[:6]}@example.com"
    d = requests.post(f"{API}/auth/register", json={"email": email, "password": "Passw0rd!x", "name": f"TEST_{name}", "consent": True}).json()
    tok, uid = d["token"], d["user"]["user_id"]
    requests.put(f"{API}/me", headers=h(tok), json={"phone": f"98{uuid.uuid4().int % 10**8:08d}", "dob": "12-03-1990", "gender": "male"})
    for k in ("licence_front", "licence_back", "id_proof"):
        requests.post(f"{API}/driver/documents/{k}", headers=h(tok), files={"file": ("a.jpg", real_image(uuid.uuid4().int % 900 + 1), "image/jpeg")}, timeout=120)
    return {"email": email, "tok": tok, "uid": uid}


def body(services, vids):
    return {"home": {"subdistrict_code": "5508", "city": "TEST Town", "place": {"loc_id": "TEST_ui26", "name": "TEST Hiriyur", "type": "town", "lat": 13.944, "lng": 76.617}},
            "languages": ["Kannada"], "licence_no": "KA0120201234567", "licence_expiry": "01-01-2035", "services": services, "vehicle_ids": vids}


cmd = sys.argv[1]
if cmd == "create":
    a = requests.post(f"{API}/admin/auth/login", json={"email": "admin@travoo.in", "password": ADMIN_PW}).json()["token"]
    s = {"drv": mk("UiBook26"), "res": mk("UiRes26")}
    tok = s["drv"]["tok"]
    rc = requests.post(f"{API}/driver/documents/vehicle_rc", headers=h(tok), files={"file": ("rc.jpg", real_image(777), "image/jpeg")}, timeout=120).json()
    v = requests.post(f"{API}/vehicles", headers=h(tok), json={"make": "Maruti", "model": "Dzire", "vtype": "sedan", "seats": 3, "reg_no": f"KA{uuid.uuid4().int % 10**8:08d}",
                                                               "name": "TEST car", "rc_file_id": rc["file_id"], "permit_no": "TESTP1", "insurance_expiry": "01-01-2034"}).json()
    print("reg drv", requests.post(f"{API}/pro/register", headers=h(tok), json=body(["rent", "book"], [v["vehicle_id"]])).text)
    print("approve drv", requests.post(f"{API}/admin/pro-drivers/{s['drv']['uid']}/review", headers=h(a), json={"decision": "approved", "note": ""}).text)
    rtok = s["res"]["tok"]
    print("reg res", requests.post(f"{API}/pro/register", headers=h(rtok), json=body(["rent"], [])).text)
    print("resubmit", requests.post(f"{API}/admin/pro-drivers/{s['res']['uid']}/review", headers=h(a),
                                    json={"decision": "resubmit", "note": "TEST licence back blurry", "items": ["licence_back"]}).text)
    print("me drv book_ready", requests.get(f"{API}/pro/me", headers=h(tok)).json().get("book_ready"))
    json.dump(s, open(F, "w"))
    print(json.dumps({k: v["email"] for k, v in s.items()}))
elif cmd == "cleanup":
    s = json.load(open(F))
    for k in s:
        uid = s[k]["uid"]
        for c, f in (("pro_drivers", "user_id"), ("driver_documents", "user_id"), ("vehicles", "owner_id"), ("files", "owner_id"),
                     ("hire_requests", "passenger_id"), ("hires", "driver_id"), ("notifications", "user_id"), ("users", "user_id")):
            db[c].delete_many({f: uid})
    print("cleaned")
