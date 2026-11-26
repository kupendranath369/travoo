"""Fill PINs that have no coordinates or state with values from neighbouring PINs (same 4- then 3-digit prefix)."""
import asyncio, os, sys
sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
from motor.motor_asyncio import AsyncIOMotorClient
from geo import loc_doc, slug

async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    fixed = 0
    async for d in db.pincodes.find({"$or": [{"lat": None}, {"state": ""}]}):
        for n in (5, 4, 3):
            nb = await db.pincodes.find({"pin": {"$regex": f"^{d['pin'][:n]}"}, "lat": {"$ne": None}, "state": {"$ne": ""}}, {"lat": 1, "lng": 1, "state": 1, "district": 1}).to_list(50)
            if nb:
                break
        if not nb:
            continue
        upd = {}
        if d.get("lat") is None:
            upd["lat"] = sum(x["lat"] for x in nb) / len(nb); upd["lng"] = sum(x["lng"] for x in nb) / len(nb)
            upd["geo"] = {"type": "Point", "coordinates": [upd["lng"], upd["lat"]]}
        if not d.get("state"):
            upd["state"] = nb[0]["state"]
        if not d.get("district"):
            upd["district"] = nb[0]["district"]
        offices = [{**o, "state": o.get("state") or upd.get("state", d["state"]), "district": o.get("district") or upd.get("district", d["district"])} for o in d["offices"]]
        upd["offices"] = offices
        await db.pincodes.update_one({"pin": d["pin"]}, {"$set": upd})
        lat, lng = upd.get("lat", d.get("lat")), upd.get("lng", d.get("lng"))
        for o in offices:
            loc = loc_doc(o["name"], "post_office", o["district"], o["state"], d["pin"], lat, lng, [], source="india_post",
                          loc_id=f"pin_{d['pin']}_{slug(o['name'])}", precision="pin_area")
            await db.locations.update_one({"loc_id": loc["loc_id"]}, {"$set": loc}, upsert=True)
        fixed += 1
    print({"fixed": fixed})

asyncio.run(main())
