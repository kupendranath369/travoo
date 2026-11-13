"""Cleanup iter15 TEST data: hire requests/dispatches/hires/notifications created by the iter15 suites + TEST pro_drivers they created.
Only touches records linked to TEST_ users that were dispatched/created in this feature's new collections."""
from pymongo import MongoClient

env = dict(l.strip().split("=", 1) for l in open("/app/backend/.env") if "=" in l)
db = MongoClient(env["MONGO_URL"].strip('"'))[env["DB_NAME"].strip('"')]

drivers = [p["user_id"] for p in db.pro_drivers.find({}, {"user_id": 1, "name": 1}) if str(p.get("name", "")).startswith("TEST_")]
reqs = list(db.hire_requests.find({}, {"request_id": 1, "passenger_id": 1, "booking_id": 1}))
pax = {r["passenger_id"] for r in reqs}
pax_names = {u["user_id"]: u["name"] for u in db.users.find({"user_id": {"$in": list(pax)}}, {"user_id": 1, "name": 1})}
mine = [r for r in reqs if str(pax_names.get(r["passenger_id"], "")).startswith("TEST_")]
rids = [r["request_id"] for r in mine]
bids = [h["booking_id"] for h in db.hires.find({"request_id": {"$in": rids}}, {"booking_id": 1})]
print("drivers", len(drivers), "requests", len(rids), "of", len(reqs), "hires", len(bids))
print(db.hire_dispatches.delete_many({"request_id": {"$in": rids}}).deleted_count,
      db.notifications.delete_many({"ref": {"$in": rids + bids}}).deleted_count,
      db.hires.delete_many({"booking_id": {"$in": bids}}).deleted_count,
      db.hire_requests.delete_many({"request_id": {"$in": rids}}).deleted_count,
      db.pro_drivers.delete_many({"user_id": {"$in": drivers}}).deleted_count)
