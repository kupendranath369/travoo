"""Iteration 27 UI helper: python ui_setup_iter27.py docs <email> | cleanup <email> [<email>...]
docs -> uploads licence_front/back + id_proof for an email-only user (password Passw0rd!x); cleanup deletes that user's data by user_id."""
import sys
import uuid

import requests

from test_travoo_api import API, h
from test_iter8_admin_docs_reset import real_image
import test_iter15_lgd_local_hire as t

db = t._db()
cmd = sys.argv[1]
if cmd == "docs":
    tok = requests.post(f"{API}/auth/login", json={"email": sys.argv[2], "password": "Passw0rd!x"}).json()["token"]
    for k in ("licence_front", "licence_back", "id_proof"):
        r = requests.post(f"{API}/driver/documents/{k}", headers=h(tok), files={"file": ("a.jpg", real_image(uuid.uuid4().int % 900 + 1), "image/jpeg")}, timeout=120)
        print(k, r.status_code)
elif cmd == "cleanup":
    for email in sys.argv[2:]:
        u = db.users.find_one({"email": email.lower()})
        if not u:
            continue
        uid = u["user_id"]
        for c, f in (("pro_drivers", "user_id"), ("driver_documents", "user_id"), ("vehicles", "owner_id"), ("files", "owner_id"),
                     ("notifications", "user_id"), ("users", "user_id")):
            db[c].delete_many({f: uid})
        db.rate_limits.delete_many({"key": {"$regex": email.lower().replace(".", r"\.")}})
        print("cleaned", email, uid)
