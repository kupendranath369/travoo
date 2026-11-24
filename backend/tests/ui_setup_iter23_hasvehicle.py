"""Iteration 23: create TEST_ users (not yet local drivers) with phone, profile photo, licence front/back and Aadhaar
uploaded, for UI testing of /hire/register 'Do you have a vehicle?' switch. Writes /tmp/iter23_users.txt (email uid per line).
Run: cd /app/backend/tests && python ui_setup_iter23_hasvehicle.py"""
import uuid

import requests

from test_travoo_api import API, h
from test_iter8_admin_docs_reset import real_image
from test_iter10_capacity_pricing_photo import reg

out = []
for key in ("Veh23No", "Veh23Yes"):
    tok, uid, email = reg(key)
    assert requests.put(f"{API}/me", headers=h(tok), json={"phone": f"98{uuid.uuid4().int % 10**8:08d}"}).status_code == 200
    assert requests.post(f"{API}/me/photo", headers=h(tok), files={"file": ("p.jpg", real_image(uuid.uuid4().int % 900), "image/jpeg")}, timeout=120).status_code == 200
    for kind in ("licence_front", "licence_back", "id_proof"):
        r = requests.post(f"{API}/driver/documents/{kind}", headers=h(tok), files={"file": (f"{kind}.jpg", real_image(uuid.uuid4().int % 900 + 1), "image/jpeg")}, timeout=120)
        assert r.status_code == 200, (kind, r.text)
    out.append(f"{email} {uid}")
    print(key, email, uid)
open("/tmp/iter23_users.txt", "w").write("\n".join(out) + "\n")
