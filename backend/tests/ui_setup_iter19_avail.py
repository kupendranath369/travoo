"""Iteration 19: create a TEST_ approved local driver with one registration availability schedule for dashboard UI test.
Run: cd /app/backend/tests && python ui_setup_iter19_avail.py  (prints email/password/user_id; writes /tmp/iter19_driver.txt)"""
import uuid

import requests

from test_travoo_api import API, h
from test_iter8_admin_docs_reset import real_image
import test_iter15_lgd_local_hire as t

tok, uid, email = t.reg("Avail19")
assert requests.put(f"{API}/me", headers=h(tok), json={"phone": f"98{uuid.uuid4().int % 10**8:08d}"}).status_code == 200
assert requests.post(f"{API}/me/photo", headers=h(tok), files={"file": ("p.jpg", real_image(uuid.uuid4().int % 900), "image/jpeg")}, timeout=120).status_code == 200
r = requests.post(f"{API}/driver/documents/licence_front", headers=h(tok), files={"file": ("l.jpg", real_image(uuid.uuid4().int % 900 + 1), "image/jpeg")}, timeout=120)
assert r.status_code == 200, r.text
d = t.future_date(10)
city = t.loc("Hiriyur")
body = t.pro_body(city, t.HIRIYUR, availability=[{"date": d, "from": f"{d}T09:00:00+05:30", "to": f"{d}T13:00:00+05:30"}])
r = requests.post(f"{API}/pro/register", headers=h(tok), json=body)
print("register", r.status_code, r.text[:200])
# approve only this TEST user's own record
t._db().pro_drivers.update_one({"user_id": uid}, {"$set": {"status": "approved"}})
me = requests.get(f"{API}/pro/me", headers=h(tok)).json()
print("status", me["profile"]["status"], "availability", me["profile"].get("availability"))
open("/tmp/iter19_driver.txt", "w").write(f"{email}\n{uid}\n")
print(email, "Passw0rd!x", uid)
