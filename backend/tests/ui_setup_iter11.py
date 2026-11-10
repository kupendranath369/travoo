"""UI setup for iteration 11 (needs /tmp/ui10.json): tokens for driver + verify user, licence_front photo for verify user, a TEST trip."""
import json
import sys

sys.path.insert(0, "/app/backend/tests")
import requests  # noqa: E402
from test_iter10_capacity_pricing_photo import API, h, real_image, trip_body  # noqa: E402

c = json.load(open("/tmp/ui10.json"))
tok = lambda e: requests.post(f"{API}/auth/login", json={"email": e, "password": c["pw"]}).json()["token"]  # noqa: E731
c["drv_tok"], c["pax_tok"] = tok(c["drv_email"]), tok(c["pax_email"])
r = requests.post(f"{API}/driver/documents/licence_front", headers=h(c["pax_tok"]), files={"file": ("l.jpg", real_image(777), "image/jpeg")}, timeout=120)
print("licence upload", r.status_code)
t = requests.post(f"{API}/trips", headers=h(c["drv_tok"]), json=trip_body(c["vid"], 3, price=100, days=8)).json()
c["tid"] = t.get("trip_id")
print("trip", c["tid"], t.get("route_source"), t.get("duration_min"), t.get("cost_breakdown"))
json.dump(c, open("/tmp/ui11.json", "w"))
