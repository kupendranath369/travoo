"""UI setup for iteration 12: approved TEST driver w/ vehicle + trip, TEST passenger with booking + unread message, unverified TEST driver w/o docs."""
import json
import sys

sys.path.insert(0, "/app/backend/tests")
import requests  # noqa: E402
from test_iter10_capacity_pricing_photo import API, h, admin_token, reg  # noqa: E402
from test_iter12_otp_pricing_verification import VER, trip_body, real_image  # noqa: E402

adm = admin_token()
c = {"pw": "Passw0rd!x"}
drv, c["drv_id"], c["drv_email"] = reg("UiDrv12")
for i, k in enumerate(["licence_front", "licence_back", "id_proof", "rc"]):
    requests.post(f"{API}/driver/documents/{k}", headers=h(drv), files={"file": ("a.jpg", real_image(610 + i), "image/jpeg")}, timeout=120)
requests.put(f"{API}/me", headers=h(drv), json={"phone": "9900223344"})
print("verify", requests.post(f"{API}/driver/verification", headers=h(drv), json=VER).json())
c["vid"] = requests.post(f"{API}/vehicles", headers=h(drv), json={"make": "Maruti", "model": "Dzire", "vtype": "sedan", "reg_no": "KA05UI1234", "seats": 3}).json()["vehicle_id"]
c["pending_drv_id"] = c["drv_id"]
print("approve", requests.post(f"{API}/admin/drivers/{c['drv_id']}/review", headers=h(adm), json={"decision": "approved"}).status_code)
t = requests.post(f"{API}/trips", headers=h(drv), json=trip_body(c["vid"], 3, price=100, days=7, instant_booking=True)).json()
c["tid"] = t["trip_id"]
pax, c["pax_id"], c["pax_email"] = reg("UiPax12")
b = requests.post(f"{API}/bookings", headers=h(pax), json={"trip_id": c["tid"], "seats": 1}).json()
c["bid"] = b["booking_id"]
requests.post(f"{API}/bookings/{c['bid']}/messages", headers=h(drv), json={"text": "TEST hi from driver"})
# a second driver with an under-review submission for the admin review page
d2, c["rev_id"], _ = reg("UiRev12")
for i, k in enumerate(["licence_front", "licence_back", "id_proof", "rc"]):
    requests.post(f"{API}/driver/documents/{k}", headers=h(d2), files={"file": ("a.jpg", real_image(710 + i), "image/jpeg")}, timeout=120)
requests.put(f"{API}/me", headers=h(d2), json={"phone": "9900334455"})
print("rev submit", requests.post(f"{API}/driver/verification", headers=h(d2), json=VER).json())
c["new_email"] = reg("UiNew12")[2]
json.dump(c, open("/tmp/ui12.json", "w"))
print(json.dumps(c))
