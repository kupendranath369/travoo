"""Helper (iteration 3): create TEST users for UI tests. A = 4 photos uploaded, not submitted. B = submitted (under_review) for admin Drivers tab."""
import io
import uuid

import requests
from PIL import Image
from test_iter3_retests import API, KINDS, VERIF, h, register


def photo(color):
    b = io.BytesIO()
    Image.new("RGB", (240, 200), color).save(b, "JPEG")
    return b.getvalue()


COLORS = {"profile": (250, 250, 250), "licence": (230, 220, 120), "rc": (120, 200, 230), "vehicle": (40, 40, 40)}
out = {}
for name in ("uiA", "uiB"):
    tok, u = register(name)
    for k in KINDS:
        r = requests.post(f"{API}/driver/documents/{k}", headers=h(tok), files={"file": (f"{k}.jpg", io.BytesIO(photo(COLORS[k])), "image/jpeg")}, timeout=60)
        assert r.status_code == 200, r.text
    out[name] = (u["email"], u["user_id"])
r = requests.post(f"{API}/auth/login", json={"email": out["uiB"][0], "password": "Passw0rd!x"}).json()
print(requests.post(f"{API}/driver/verification", headers=h(r["token"]), json={**VERIF, "legal_name": "TEST UiB Driver"}).json())
for k, v in out.items():
    print(k, "EMAIL", v[0], "UID", v[1], "PASS Passw0rd!x")
