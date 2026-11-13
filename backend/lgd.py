"""India administrative locations from the official Local Government Directory (LGD, Govt. of India).

Data: State -> District -> Sub-district (Taluk / Tehsil / Mandal / Taluka / Circle / Block) -> Village, mirrored
daily as Parquet by the open LGD dataset project (https://ramseraph.github.io/opendata/lgd/). Imported into MongoDB
(lgd_* collections) by `import_lgd()`; re-running is idempotent (upsert by LGD code) and never deletes rows.
"""
import io
import logging
import re
from datetime import datetime, timezone
from typing import Optional

import httpx
from pymongo import ASCENDING, IndexModel, UpdateOne

logger = logging.getLogger("travoo.lgd")
INDEX_URL = "https://ramseraph.github.io/opendata/lgd/datasets/"
DATA_BASE = "https://ramseraph.github.io/opendata/lgd/data/"
DATASETS = ("states", "districts", "subdistricts", "villages")

# What each state calls its sub-district (shown in the UI; data level is the same LGD sub-district)
SUB_LABEL = {
    "karnataka": "Taluk", "tamil nadu": "Taluk", "kerala": "Taluk", "puducherry": "Taluk",
    "andhra pradesh": "Mandal", "telangana": "Mandal",
    "maharashtra": "Taluka", "gujarat": "Taluka", "goa": "Taluka", "the dadra and nagar haveli and daman and diu": "Taluka",
    "west bengal": "Block", "jharkhand": "Block", "bihar": "Block",
    "assam": "Circle", "arunachal pradesh": "Circle", "nagaland": "Circle", "manipur": "Sub-division", "mizoram": "Sub-division",
    "meghalaya": "Block", "tripura": "Sub-division", "sikkim": "Sub-division",
}


def sub_label(state_name: str) -> str:
    return SUB_LABEL.get((state_name or "").strip().lower(), "Tehsil")


def norm(s: str) -> str:
    s = re.sub(r"\(.*?\)", " ", (s or "").lower())
    s = re.sub(r"\b(taluka?|tehsil|mandal|sub[- ]?division|circle|block|district|dist|cd|rural|urban|north|south|east|west)\b", " ", s)
    return re.sub(r"[^a-z0-9]+", "", s)


LGD_INDEXES = {
    "lgd_states": [IndexModel([("code", ASCENDING)], unique=True, name="code")],
    "lgd_districts": [IndexModel([("code", ASCENDING)], unique=True, name="code"), IndexModel([("state_code", ASCENDING), ("norm", ASCENDING)], name="state_norm")],
    "lgd_subdistricts": [IndexModel([("code", ASCENDING)], unique=True, name="code"), IndexModel([("district_code", ASCENDING), ("norm", ASCENDING)], name="district_norm"),
                         IndexModel([("norm", ASCENDING)], name="norm")],
    "lgd_villages": [IndexModel([("code", ASCENDING)], unique=True, name="code"), IndexModel([("subdistrict_code", ASCENDING), ("norm", ASCENDING)], name="sub_norm"),
                     IndexModel([("district_code", ASCENDING), ("norm", ASCENDING)], name="district_norm")],
}


async def dataset_urls() -> dict:
    """Current Parquet URLs from the dataset's metadata.json (file names change with each daily refresh)."""
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as c:
        meta = (await c.get(DATA_BASE + "metadata.json")).json()
    out = {}
    for name in DATASETS:
        url = (((meta.get("datasets") or {}).get(name) or {}).get("daily") or {}).get("file", {}).get("url")
        if url:
            out[name] = url
    missing = [n for n in DATASETS if n not in out]
    if missing:
        raise RuntimeError(f"LGD index missing datasets: {missing}")
    return out


def _rows(blob: bytes) -> list:
    import pyarrow.parquet as pq
    return pq.read_table(io.BytesIO(blob)).to_pylist()


async def import_lgd(db) -> dict:
    """Download the latest LGD Parquet files and upsert them. Returns counts."""
    for coll, models in LGD_INDEXES.items():
        await db[coll].create_indexes(models)
    urls = await dataset_urls()
    counts = {}
    async with httpx.AsyncClient(timeout=180, follow_redirects=True) as c:
        for name in DATASETS:
            rows = _rows((await c.get(urls[name])).content)
            ops = []
            for r in rows:
                if name == "states":
                    d = {"code": r["state_code"], "name": r["state_name"].title() if r["state_name"].isupper() else r["state_name"], "is_ut": r.get("state_or_ut") == "U"}
                    d["sub_label"] = sub_label(d["name"])
                elif name == "districts":
                    d = {"code": r["district_code"], "name": r["district_name"], "state_code": r["state_code"], "state_name": r["state_name"]}
                elif name == "subdistricts":
                    d = {"code": r["subdistrict_code"], "name": r["subdistrict_name"], "district_code": r["district_code"], "district_name": r["district_name"],
                         "state_code": r["state_code"], "state_name": r["state_name"]}
                else:
                    d = {"code": r["village_code"], "name": r["village_name"], "subdistrict_code": r["subdistrict_code"], "subdistrict_name": r["subdistrict_name"],
                         "district_code": r["district_code"], "state_code": r["state_code"], "category": r.get("village_category") or "",
                         "inhabited": (r.get("village_status") or "").lower().startswith("inhabit")}
                d["norm"] = norm(d["name"])
                ops.append(UpdateOne({"code": d["code"]}, {"$set": d}, upsert=True))
                if len(ops) >= 5000:
                    await db[f"lgd_{name}"].bulk_write(ops, ordered=False)
                    ops = []
            if ops:
                await db[f"lgd_{name}"].bulk_write(ops, ordered=False)
            counts[name] = len(rows)
            logger.info("LGD %s: %d rows", name, len(rows))
    await db.lgd_meta.update_one({"key": "lgd"}, {"$set": {"counts": counts, "urls": urls, "imported_at": datetime.now(timezone.utc)}}, upsert=True)
    return counts


async def identify(db, *, state: str = "", district: str = "", sub_hint: str = "", place_names: Optional[list] = None) -> Optional[dict]:
    """Map a geocoded place (state/district names + sub-district hint + place names) to an LGD sub-district.
    Order: sub-district name hint -> village/town name in the district -> place name equals a sub-district HQ name."""
    st = None
    if state:
        st = await db.lgd_states.find_one({"norm": norm(state)}, {"_id": 0}) or await db.lgd_states.find_one({"name": {"$regex": f"^{re.escape(state)}", "$options": "i"}}, {"_id": 0})
    dist = None
    if st and district:
        dist = await db.lgd_districts.find_one({"state_code": st["code"], "norm": norm(district)}, {"_id": 0})
        if not dist:  # e.g. "Bengaluru Urban" vs "Bangalore Urban" style spellings: try prefix/contains
            n = norm(district)
            async for d in db.lgd_districts.find({"state_code": st["code"]}, {"_id": 0}):
                if n and (d["norm"].startswith(n[:5]) or n in d["norm"] or d["norm"] in n):
                    dist = d
                    break
    q_base = {"district_code": dist["code"]} if dist else ({"state_code": st["code"]} if st else {})
    if not q_base:
        return None
    cands = [sub_hint] + list(place_names or [])
    for how, names in (("subdistrict_hq", place_names or []), ("subdistrict_name", [sub_hint])):
        for nm in names:
            n = norm(nm)
            if len(n) < 3:
                continue
            sd = await db.lgd_subdistricts.find_one({**q_base, "norm": n}, {"_id": 0})
            if sd:
                return {"subdistrict": sd, "method": how, "confidence": "high" if dist else "medium"}
    for nm in cands:
        n = norm(nm)
        if len(n) < 3:
            continue
        vs = await db.lgd_villages.find({**q_base, "norm": n}, {"_id": 0, "subdistrict_code": 1}).to_list(5)
        codes = {v["subdistrict_code"] for v in vs}
        if len(codes) == 1:
            sd = await db.lgd_subdistricts.find_one({"code": codes.pop()}, {"_id": 0})
            if sd:
                return {"subdistrict": sd, "method": "village_name", "confidence": "medium"}
    return {"subdistrict": None, "district": dist, "state": st, "method": "unmatched", "confidence": "low"}
