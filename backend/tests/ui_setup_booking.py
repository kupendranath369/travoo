"""UI test helper: TEST driver (approved) publishes a trip and a TEST passenger is registered. Prints ids."""
import json
import sys
import uuid
from datetime import datetime, timedelta

import requests

API = open("/app/frontend/.env").read().split("EXPO_PUBLIC_BACKEND_URL=")[1].split()[0].strip('"').rstrip("/") + "/api"
lg = lambda e, p: requests.post(f"{API}/auth/login", json={"email": e, "password": p}).json()["token"]
H = lambda t: {"Authorization": f"Bearer {t}"}
loc = lambda q: {k: requests.get(f"{API}/locations/search", params={"q": q}).json()[0].get(k) for k in ("loc_id", "name", "type", "district", "state", "pin", "lat", "lng")}
drv = lg(sys.argv[1], sys.argv[2])
v = requests.post(f"{API}/vehicles", headers=H(drv), json={"make": "Maruti", "model": "Dzire", "vtype": "sedan", "reg_no": "KA05MN4321", "seats": 4, "ac": True}).json()
d = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
t = requests.post(f"{API}/trips", headers=H(drv), json={"origin": loc("Bengaluru"), "destination": loc("Chennai"), "pickup_point": "TEST pickup", "drop_point": "TEST drop",
                                                      "date": d, "time": "10:00", "seats": 3, "price": 600, "vehicle_id": v["vehicle_id"], "instant_booking": True}).json()
email = f"test_pax_{uuid.uuid4().hex[:6]}@example.com"
requests.post(f"{API}/auth/register", json={"email": email, "password": "Passw0rd!x", "name": "TEST Pax", "consent": True})
print(json.dumps({"trip_id": t.get("trip_id"), "vehicle_id": v.get("vehicle_id"), "pax": email, "err": None if t.get("trip_id") else t}))
