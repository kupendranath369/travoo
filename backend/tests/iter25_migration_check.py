"""Iteration 25 migration check: python iter25_migration_check.py insert|verify|cleanup (restart backend between insert and verify)."""
import sys
from datetime import datetime, timezone
from pymongo import MongoClient

env = dict(l.strip().split("=", 1) for l in open("/app/backend/.env") if "=" in l)
db = MongoClient(env["MONGO_URL"].strip('"'))[env["DB_NAME"].strip('"')]
UIDS = ["user_TEST_mig25a", "user_TEST_mig25b"]
cmd = sys.argv[1]
if cmd == "insert":
    for uid, st in zip(UIDS, ("approved", "under_review")):
        db.pro_drivers.insert_one({"user_id": uid, "name": "TEST_mig", "status": st, "acceptOutstationTrips": True,
                                   "availability": [{"from": "2030-01-01T08:00:00+05:30", "to": "2030-01-01T12:00:00+05:30"}],
                                   "vehicles": [{"vehicle_id": "pv_x1", "name": "TEST Innova", "reg_no": "KA 01 MG 2501", "category": "muv", "seats": 7, "day_rate": 900},
                                                {"vehicle_id": "pv_x2", "name": "TEST Van", "reg_no": "KA01MG2502", "category": "van", "seats": 12, "day_rate": 500}],
                                   "submitted_at": datetime.now(timezone.utc)})
    print("inserted")
elif cmd == "verify":
    for uid, exp in zip(UIDS, ("approved", "pending")):
        p = db.pro_drivers.find_one({"user_id": uid})
        vs = list(db.vehicles.find({"owner_id": uid}))
        print(uid, "migrated", p.get("vehicles_migrated"), "ids", p.get("vehicle_ids"), "outstation", p.get("acceptOutstationTrips"),
              "avail", [(a.get("id"), a.get("status")) for a in p.get("availability", [])])
        for v in vs:
            print("   ", v["reg_no"], v["vtype"], v["seats"], v["commercial_status"], v.get("day_rate"))
        assert p.get("vehicles_migrated") is True and len(vs) == 2 and len(p["vehicle_ids"]) == 2
        assert all(v["commercial_status"] == exp for v in vs)
        assert p["acceptOutstationTrips"] is True and p["availability"][0]["status"] == "active"
    print("VERIFY OK")
elif cmd == "rerun":  # force a re-run to check that an existing reg is reused (no duplicate)
    db.pro_drivers.update_many({"user_id": {"$in": UIDS}}, {"$unset": {"vehicles_migrated": ""}})
    print("unset")
elif cmd == "cleanup":
    for uid in UIDS:
        db.pro_drivers.delete_many({"user_id": uid}); db.vehicles.delete_many({"owner_id": uid})
    print("cleaned")
