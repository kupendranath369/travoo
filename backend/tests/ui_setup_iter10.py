"""UI setup for iteration 10: approved TEST driver with phone + sedan vehicle + profile photo; plain TEST user with phone (for verification UI)."""
import json
import sys

sys.path.insert(0, "/app/backend/tests")
import requests  # noqa: E402
from test_iter10_capacity_pricing_photo import API, h, admin_token, reg, upload_docs, VER, real_image  # noqa: E402

adm = admin_token()
drv, drv_id, drv_email = reg("UIDriver10")
requests.put(f"{API}/me", headers=h(drv), json={"phone": "9876500010"})
upload_docs(drv)
assert requests.post(f"{API}/driver/verification", headers=h(drv), json=VER).status_code == 200
assert requests.post(f"{API}/admin/drivers/{drv_id}/review", headers=h(adm), json={"decision": "approved"}).status_code == 200
v = requests.post(f"{API}/vehicles", headers=h(drv), json={"make": "Honda", "model": "City", "vtype": "sedan", "reg_no": "KA05UI1010", "seats": 3, "mileage": 16}).json()
requests.post(f"{API}/me/photo", headers=h(drv), files={"file": ("p.jpg", real_image(42), "image/jpeg")})
pax, pax_id, pax_email = reg("UIVerify10")
out = {"drv_email": drv_email, "drv_id": drv_id, "vid": v["vehicle_id"], "pax_email": pax_email, "pax_id": pax_id, "pw": "Passw0rd!x"}
json.dump(out, open("/tmp/ui10.json", "w"))
print(out)
