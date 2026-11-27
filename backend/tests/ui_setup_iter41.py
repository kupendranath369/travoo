"""Iteration 41 UI setup (trip reschedule): python ui_setup_iter41.py create|cleanup. State in /tmp/ui41.json
Creates an approved carpool driver + vehicle + scheduled trip, and books it as test.rider@example.com."""
import json
import sys
import uuid
from datetime import datetime, timedelta

import requests

from test_travoo_api import API, IST, h, loc, login
import test_iter15_lgd_local_hire as t

db = t._db()
F = "/tmp/ui41.json"
cmd = sys.argv[1]
if cmd == "create":
    email = f"test_resdrv41_{uuid.uuid4().hex[:6]}@example.com"
    d = requests.post(f"{API}/auth/register", json={"email": email, "password": "Passw0rd!x", "name": "TEST_ResDriver41", "consent": True}).json()
    tok, uid = d["token"], d["user"]["user_id"]
    requests.put(f"{API}/me", headers=h(tok), json={"phone": f"98{uuid.uuid4().int % 10**8:08d}", "dob": "12-03-1990", "gender": "male", "account_type": "driver"})
    db.users.update_one({"user_id": uid}, {"$set": {"driver_status": "approved"}})
    v = requests.post(f"{API}/vehicles", headers=h(tok), json={"make": "Maruti", "model": "Ertiga", "vtype": "muv",
                                                                "reg_no": f"KA01U{uuid.uuid4().int % 9999:04d}", "seats": 6, "ac": True}).json()
    date = (datetime.now(IST) + timedelta(days=10)).strftime("%Y-%m-%d")
    r = requests.post(f"{API}/trips", headers=h(tok), json={
        "origin": loc("Bengaluru"), "destination": loc("Mysuru"), "pickup_point": "TEST Silk Board", "drop_point": "TEST Mysore bus stand",
        "date": date, "time": "09:00", "seats": 3, "price": 300, "vehicle_id": v["vehicle_id"], "instant_booking": True, "fuel_price": 102, "mileage": 15})
    print("trip", r.status_code, r.text[:120])
    trip = r.json()
    rtok = login("test.rider@example.com", "Test@12345")
    b = requests.post(f"{API}/bookings", headers=h(rtok), json={"trip_id": trip["trip_id"], "seats": 1})
    print("booking", b.status_code, b.text[:120])
    s = {"email": email, "uid": uid, "tok": tok, "trip": trip["trip_id"], "vid": v["vehicle_id"], "booking": b.json().get("booking_id"), "date": date}
    json.dump(s, open(F, "w"))
    print(json.dumps(s))
elif cmd == "cleanup":
    s = json.load(open(F))
    rider = db.users.find_one({"email": "test.rider@example.com"}, {"user_id": 1})
    db.notifications.delete_many({"user_id": rider["user_id"], "ref": s["booking"]})
    db.notifications.delete_many({"user_id": rider["user_id"], "ref_id": s["booking"]})
    db.messages.delete_many({"booking_id": s["booking"]})
    db.bookings.delete_many({"trip_id": s["trip"]})
    db.trips.delete_many({"trip_id": s["trip"]})
    for c, f in (("notifications", "user_id"), ("user_sessions", "user_id"), ("vehicles", "owner_id"), ("users", "user_id")):
        db[c].delete_many({f: s["uid"]})
    print("cleaned")
