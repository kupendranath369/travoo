"""Build main_towns (taluk/district HQ towns + known cities) with coordinates, used for route stop suggestions."""
import asyncio
import os
import re

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
SKIP = {"village", "post_office", "bus_stop", "hospital", "road", "landmark", "university", "religious", "airport", "railway_station", "beach", "tourist_attraction", "industrial_area", "state", "union_territory"}


def key(s: str) -> str:
    return re.sub(r"[^a-z]", "", (s or "").lower())


async def main():
    dists = {d["code"]: d["name"] async for d in db.lgd_districts.find({}, {"_id": 0, "code": 1, "name": 1})}
    towns = {}
    async for loc in db.locations.find({"type": {"$in": ["city", "town", "district"]}}, {"_id": 0, "loc_id": 1, "name": 1, "district": 1, "state": 1, "lat": 1, "lng": 1}):
        towns[(key(loc["name"]), key(loc.get("district")))] = loc
    async for sd in db.lgd_subdistricts.find({}, {"_id": 0, "name": 1, "district_code": 1}):
        dname = dists.get(sd["district_code"], "")
        k = (key(sd["name"]), key(dname))
        if k in towns:
            continue
        loc = None
        async for c in db.locations.find({"search_terms": sd["name"].lower(), "name": {"$in": list({sd["name"], sd["name"].title(), sd["name"].upper()})}, "lat": {"$ne": None}},
                                         {"_id": 0, "loc_id": 1, "name": 1, "district": 1, "state": 1, "lat": 1, "lng": 1, "type": 1}).limit(30):
            if key(c["name"]) == k[0] and key(c.get("district")) == k[1] and c.get("type") not in SKIP - {"post_office"}:
                loc = c
                break
        if loc:
            towns[k] = loc
    docs = [{**t, "geo": {"type": "Point", "coordinates": [t["lng"], t["lat"]]}} for t in towns.values() if t.get("lat") is not None]
    from pymongo import UpdateOne
    if docs:
        await db.main_towns.bulk_write([UpdateOne({"loc_id": d["loc_id"]}, {"$set": {k: v for k, v in d.items() if k != "type"}}, upsert=True) for d in docs])
    await db.main_towns.create_index([("geo", "2dsphere")])
    print("main towns:", len(docs))


asyncio.run(main())
