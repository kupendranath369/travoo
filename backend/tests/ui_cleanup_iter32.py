"""Iteration 32 cleanup: delete the role-chooser TEST users (by email given on argv) and verify/restore demo modes."""
import sys

import test_iter15_lgd_local_hire as t

db = t._db()
for email in sys.argv[1:]:
    u = db.users.find_one({"email": email, "name": {"$regex": "^TEST"}})
    if not u:
        print("not found", email)
        continue
    uid = u["user_id"]
    for c, f in (("pro_drivers", "user_id"), ("driver_documents", "user_id"), ("notifications", "user_id"), ("user_sessions", "user_id"), ("searches", "user_id"), ("users", "user_id")):
        db[c].delete_many({f: uid})
    print("deleted", email)
for email, mode in (("driver@travoo.in", "driver"), ("passenger@travoo.in", "passenger")):
    db.users.update_one({"email": email}, {"$set": {"account_type": mode}})
    u = db.users.find_one({"email": email})
    print(email, u.get("account_type"), u.get("mode_chosen"))
