"""UI setup iter13: approved TEST driver w/ sedan + trip; TEST passenger with booking + 1 unread driver message (system msgs exist too)."""
import json, sys
sys.path.insert(0, "/app/backend/tests")
import requests  # noqa: E402
from test_iter10_capacity_pricing_photo import API, h, admin_token, reg  # noqa: E402
from test_iter12_otp_pricing_verification import VER, trip_body, real_image  # noqa: E402

adm = admin_token()
c = {"pw": "Passw0rd!x"}
drv, c["drv_id"], c["drv_email"] = reg("UiDrv13")
for i, k in enumerate(["licence_front", "licence_back", "id_proof", "rc"]):
    requests.post(f"{API}/driver/documents/{k}", headers=h(drv), files={"file": ("a.jpg", real_image(810 + i), "image/jpeg")}, timeout=120)
requests.put(f"{API}/me", headers=h(drv), json={"phone": "9900225566"})
requests.post(f"{API}/driver/verification", headers=h(drv), json=VER)
c["vid"] = requests.post(f"{API}/vehicles", headers=h(drv), json={"make": "Maruti", "model": "Dzire", "vtype": "sedan", "reg_no": "KA05UI1313", "seats": 3}).json()["vehicle_id"]
print("approve", requests.post(f"{API}/admin/drivers/{c['drv_id']}/review", headers=h(adm), json={"decision": "approved"}).status_code)
t = requests.post(f"{API}/trips", headers=h(drv), json=trip_body(c["vid"], 3, price=100, days=8, instant_booking=True)).json()
c["tid"] = t["trip_id"]
pax, c["pax_id"], c["pax_email"] = reg("UiPax13")
c["bid"] = requests.post(f"{API}/bookings", headers=h(pax), json={"trip_id": c["tid"], "seats": 1}).json()["booking_id"]
requests.post(f"{API}/bookings/{c['bid']}/messages", headers=h(drv), json={"text": "TEST hi from driver 13"})
print("pax unread", requests.get(f"{API}/conversations", headers=h(pax)).json()["unread"])
json.dump(c, open("/tmp/ui13.json", "w"))
print(json.dumps(c))
