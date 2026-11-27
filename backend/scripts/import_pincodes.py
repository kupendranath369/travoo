"""Import every Indian PIN code and post office (India Post directory via the indiapins package) into MongoDB."""
import asyncio, bz2, json, os, re, sys
from collections import defaultdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
import indiapins
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import UpdateOne
from geo import GEO_INDEXES, in_india, loc_doc, slug

SMALL = {"and", "of", "the"}


def title(s: str) -> str:
    return " ".join(w if w.lower() in SMALL else w.capitalize() for w in (s or "").strip().lower().split())


def office_name(n: str) -> str:
    return re.sub(r"\s+(B\.?O|S\.?O|H\.?O|P\.?O)\.?$", "", (n or "").strip(), flags=re.I).strip()


def coords(o):
    try:
        lat, lng = float(o.get("Latitude")), float(o.get("Longitude"))
    except (TypeError, ValueError):
        return None
    return (lat, lng) if in_india(lat, lng) else None


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    for coll in ("pincodes", "locations"):
        await db[coll].create_indexes(GEO_INDEXES[coll])
    path = os.path.join(os.path.dirname(indiapins.__file__), "pins.json.bz2")
    with bz2.open(path, "rt") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    by_pin = defaultdict(list)
    for o in rows:
        by_pin[str(o["Pincode"]).zfill(6)].append(o)
    now = datetime.now(timezone.utc)
    pin_ops, loc_ops = [], []

    async def flush(force=False):
        nonlocal pin_ops, loc_ops
        if pin_ops and (force or len(pin_ops) >= 2000):
            await db.pincodes.bulk_write(pin_ops, ordered=False); pin_ops = []
        if loc_ops and (force or len(loc_ops) >= 5000):
            await db.locations.bulk_write(loc_ops, ordered=False); loc_ops = []

    for pin, offices in by_pin.items():
        pts = [c for c in map(coords, offices) if c]
        center = (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)) if pts else None
        first = offices[0]
        doc = {"pin": pin, "district": title(first["District"]), "state": title(first["State"]), "division": first.get("Division"),
               "offices": [{"name": office_name(o["Name"]), "branch_type": o.get("BranchType"), "block": "", "district": title(o["District"]),
                            "state": title(o["State"]), "delivery": o.get("DeliveryStatus")} for o in offices],
               "lat": center[0] if center else None, "lng": center[1] if center else None, "synced_at": now, "source": "indiapins"}
        if center:
            doc["geo"] = {"type": "Point", "coordinates": [center[1], center[0]]}
        pin_ops.append(UpdateOne({"pin": pin}, {"$set": doc}, upsert=True))
        for o in offices:
            c = coords(o) or center
            if not c:
                continue
            name = office_name(o["Name"])
            d = loc_doc(name, "post_office", title(o["District"]), title(o["State"]), pin, c[0], c[1], [],
                        source="india_post", loc_id=f"pin_{pin}_{slug(name)}", precision="post_office", synced_at=now)
            loc_ops.append(UpdateOne({"loc_id": d["loc_id"]}, {"$set": d, "$setOnInsert": {"created_at": now}}, upsert=True))
        await flush()
    await flush(True)
    print({"pincodes": len(by_pin), "post_offices": len(rows)}, flush=True)


asyncio.run(main())
