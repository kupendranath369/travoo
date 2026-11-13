"""TRAVOO geo service — India-wide location database built on open data.

Providers (each with its own rate limit, circuit breaker and fallback):
  * Photon (komoot, OpenStreetMap data)  — typo-tolerant autocomplete while typing
  * Nominatim (OpenStreetMap)            — geocoding, reverse geocoding, address details (max 1 req/s, no autocomplete)
  * India Post PIN API                   — official post-office / PIN code directory
  * OSRM (project-osrm + FOSSGIS mirror) — road routing, alternatives, toll segments
  * Overpass API (3 mirrors)             — nearby bus stops, stations, airports (Photon fallback)
Everything fetched is cached in MongoDB (2dsphere-indexed `locations`, TTL `geo_cache`) and refreshed by a daily sync.
Map data © OpenStreetMap contributors (ODbL). PIN data © India Post.
"""
import asyncio
import logging
import math
import os
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pymongo import ASCENDING, DESCENDING, GEOSPHERE, IndexModel

logger = logging.getLogger("travoo.geo")

UA = {"User-Agent": "Travoo-Carpool/1.0 (support@travoo.in)", "Accept-Language": "en"}
NOMINATIM = "https://nominatim.openstreetmap.org"
PHOTON = "https://photon.komoot.io"
INDIA_POST = "https://api.postalpincode.in"
OSRM = ["https://router.project-osrm.org", "https://routing.openstreetmap.de/routed-car"]
OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter",
            "https://maps.mail.ru/osm/tools/overpass/api/interpreter"]
INDIA_BBOX = "68.0,6.5,97.5,37.5"  # lon_min,lat_min,lon_max,lat_max
ATTRIBUTION = "Map data © OpenStreetMap contributors (ODbL) · PIN codes © India Post"
TOLL_RATE_PER_KM = 1.8  # ₹/km, approx. NHAI car single-journey rate on tolled sections
NH_TOLL_RATE_PER_KM = 1.2  # ₹/km averaged over all NH km (not every NH stretch is tolled)
LOC_OUT = {"_id": 0, "search_terms": 0, "geo": 0}

GEO_INDEXES = {
    "locations": [IndexModel([("osm_id", ASCENDING)], name="osm_id", sparse=True),
                  IndexModel([("source", ASCENDING), ("synced_at", ASCENDING)], name="source_sync"),
                  IndexModel([("state", ASCENDING), ("district", ASCENDING)], name="state_district")],
    "geo_cache": [IndexModel([("key", ASCENDING)], name="key", unique=True),
                  IndexModel([("expires_at", ASCENDING)], name="ttl", expireAfterSeconds=0)],
    "pincodes": [IndexModel([("pin", ASCENDING)], name="pin", unique=True), IndexModel([("geo", GEOSPHERE)], name="geo")],
    "geo_misses": [IndexModel([("q", ASCENDING)], name="q", unique=True), IndexModel([("count", DESCENDING)], name="count")],
}


# ---------------------------------------------------------------- helpers
def now() -> datetime:
    return datetime.now(timezone.utc)


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", norm(s)).strip("_")


def haversine(a: dict, b: dict) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, [a["lat"], a["lng"], b["lat"], b["lng"]])
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def in_india(lat: float, lng: float) -> bool:
    return 6.5 <= lat <= 37.5 and 68.0 <= lng <= 97.5


def loc_doc(name, ltype, district, state, pin, lat, lng, aliases, source="travoo", loc_id=None, **extra):
    terms = sorted({norm(x) for x in [name, *aliases, district or "", extra.get("sub_district") or "", state or "", pin or ""] if x})
    return {"loc_id": loc_id or f"in_{slug(name)}_{slug(state or '')}",
            "name": name, "type": ltype, "district": district, "state": state, "pin": pin, "lat": lat, "lng": lng,
            "aliases": aliases, "search_terms": terms, "geo": {"type": "Point", "coordinates": [lng, lat]}, "source": source, **extra}


def public(d: dict) -> dict:
    return {k: v for k, v in d.items() if k not in ("_id", "search_terms", "geo")}


def circle(lat: float, lng: float, km: float, n: int = 16) -> dict:
    """GeoJSON polygon approximating a circle (for $geoIntersects against route lines)."""
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        pts.append([lng + (km / (111.32 * math.cos(math.radians(lat)))) * math.cos(a), lat + (km / 110.57) * math.sin(a)])
    pts.append(pts[0])
    return {"type": "Polygon", "coordinates": [pts]}


def downsample(coords: list, max_pts: int) -> list:
    if len(coords) <= max_pts:
        return coords
    step = (len(coords) - 1) / (max_pts - 1)
    return [coords[round(i * step)] for i in range(max_pts)]


# ---------------------------------------------------------------- provider plumbing
class Provider:
    """Per-provider rate limiting (usage-policy compliant) + simple circuit breaker + health stats."""

    def __init__(self, name: str, min_interval: float, cooldown: float = 60):
        self.name, self.min_interval, self.cooldown = name, min_interval, cooldown
        self.lock = asyncio.Lock()
        self.last_call = 0.0
        self.failures = 0
        self.open_until = 0.0
        self.stats = {"ok": 0, "errors": 0, "last_ok_at": None, "last_error": None, "last_error_at": None}

    @property
    def available(self) -> bool:
        return time.monotonic() >= self.open_until

    async def get(self, url: str, timeout: float = 10, method: str = "GET", **kw):
        if not self.available:
            raise RuntimeError(f"{self.name} temporarily disabled after repeated failures")
        async with self.lock:
            wait = self.min_interval - (time.monotonic() - self.last_call)
            if wait > 0:
                await asyncio.sleep(wait)
            self.last_call = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=timeout, headers=UA, follow_redirects=True) as hc:
                r = await hc.request(method, url, **kw)
            r.raise_for_status()
            data = r.json()
        except Exception as exc:
            self.failures += 1
            self.stats.update(errors=self.stats["errors"] + 1, last_error=str(exc)[:200] or type(exc).__name__, last_error_at=now().isoformat())
            if self.failures >= 3:
                self.open_until = time.monotonic() + self.cooldown
            raise
        self.failures = 0
        self.stats.update(ok=self.stats["ok"] + 1, last_ok_at=now().isoformat())
        return data

    def health(self) -> dict:
        return {"name": self.name, "available": self.available, **self.stats}


P = {"photon": Provider("photon", 0.2), "nominatim": Provider("nominatim", 1.1), "india_post": Provider("india_post", 0.3),
     "osrm": Provider("osrm", 0.3), "osrm_fossgis": Provider("osrm_fossgis", 0.5), "overpass": Provider("overpass", 1.0, cooldown=900)}


# ---------------------------------------------------------------- normalisers
TYPE_MAP = {
    "city": "city", "town": "town", "village": "village", "hamlet": "village", "isolated_dwelling": "village",
    "suburb": "locality", "neighbourhood": "locality", "quarter": "locality", "locality": "locality", "borough": "locality",
    "county": "district", "state_district": "district", "district": "district", "state": "state", "municipality": "town",
    "aerodrome": "airport", "airport": "airport", "station": "railway_station", "halt": "railway_station",
    "bus_station": "bus_terminal", "bus_stop": "bus_stop", "post_office": "post_office", "postcode": "pin_area",
    "motorway": "road", "trunk": "road", "primary": "road", "secondary": "road", "tertiary": "road", "residential": "road",
    "unclassified": "road", "road": "road", "living_street": "road", "service": "road", "hospital": "hospital",
    "university": "university", "college": "university", "temple": "religious", "place_of_worship": "religious",
}


def classify(key: str, value: str, addresstype: str = "") -> str:
    if key == "highway" and value in ("bus_stop", "platform"):
        return "bus_stop"
    if key == "railway":
        return "railway_station"
    if key == "aeroway":
        return "airport"
    if key == "highway":
        return "road"
    if key == "boundary" and addresstype:
        return TYPE_MAP.get(addresstype, "district")
    if key in ("amenity", "tourism", "historic", "leisure", "shop", "building", "man_made", "natural"):
        return TYPE_MAP.get(value, "landmark")
    return TYPE_MAP.get(addresstype or value, TYPE_MAP.get(value, "place"))


def clean_district(s: str) -> str:
    return re.sub(r"\s+(District|district)$", "", s or "").strip()


def from_nominatim(it: dict) -> dict:
    a = it.get("address", {})
    name = it.get("name") or it.get("display_name", "").split(",")[0]
    otype = classify(it.get("category") or it.get("class", ""), it.get("type", ""), it.get("addresstype", ""))
    osm_id = f"{(it.get('osm_type') or 'x')[:1].upper()}{it.get('osm_id')}"
    return loc_doc(name, otype, clean_district(a.get("state_district") or a.get("district") or a.get("county") or a.get("city") or ""),
                   a.get("state", ""), a.get("postcode"), float(it["lat"]), float(it["lon"]), [], source="openstreetmap",
                   loc_id=f"osm_{osm_id.lower()}", osm_id=osm_id,
                   sub_district=a.get("county") or a.get("subdistrict") or a.get("municipality") or "",
                   address=it.get("display_name", ""), details_at=now(), synced_at=now())


def from_photon(f: dict) -> Optional[dict]:
    p = f.get("properties", {})
    if p.get("countrycode", "").upper() != "IN" or not p.get("name"):
        return None
    lng, lat = f["geometry"]["coordinates"][:2]
    otype = classify(p.get("osm_key", ""), p.get("osm_value", ""), p.get("type", "") if p.get("osm_key") == "boundary" else "")
    osm_id = f"{p.get('osm_type', 'X')}{p.get('osm_id')}"
    street = p.get("street") if otype in ("landmark", "bus_stop", "railway_station", "bus_terminal", "hospital", "religious") else None
    parts = [p.get("name"), street, p.get("locality") or p.get("district"), p.get("city"), p.get("county"), p.get("state")]
    return loc_doc(p["name"], otype, "", p.get("state", ""), p.get("postcode"), lat, lng, [], source="openstreetmap",
                   loc_id=f"osm_{osm_id.lower()}", osm_id=osm_id, sub_district=p.get("county", ""),
                   locality=p.get("city") or p.get("district") or "",
                   address=", ".join(dict.fromkeys(x for x in parts if x)), synced_at=now())


TYPE_RANK = {"city": 0, "town": 1, "village": 2, "district": 2, "state": 3, "union_territory": 3, "railway_station": 2, "airport": 2,
             "bus_terminal": 2, "pin_area": 1, "post_office": 3, "locality": 3, "bus_stop": 4, "landmark": 4, "road": 5}


def get_router(db, get_admin: Callable) -> APIRouter:
    r = APIRouter(prefix="/api")

    # ---------------------------------------------------------------- cache helpers
    async def cache_get(key: str):
        c = await db.geo_cache.find_one({"key": key, "expires_at": {"$gt": now()}}, {"_id": 0, "data": 1})
        return c["data"] if c else None

    async def cache_set(key: str, data, ttl: timedelta):
        await db.geo_cache.update_one({"key": key}, {"$set": {"data": data, "expires_at": now() + ttl}}, upsert=True)

    async def store(d: dict, refresh: bool = False) -> dict:
        """Upsert a provider result into the central database without wiping richer, previously enriched fields."""
        base = {"lat": d["lat"], "lng": d["lng"], "geo": d["geo"], "synced_at": now()}
        rich = {k: v for k, v in d.items() if v not in ("", None, [])}
        if refresh or d.get("details_at"):
            await db.locations.update_one({"loc_id": d["loc_id"]}, {"$set": {**rich, "stale": False}, "$setOnInsert": {"created_at": now()}}, upsert=True)
        else:
            ins = {k: v for k, v in d.items() if k not in base}
            await db.locations.update_one({"loc_id": d["loc_id"]}, {"$set": base, "$setOnInsert": {**ins, "created_at": now()}}, upsert=True)
        return d

    def dedupe(rows: list) -> list:
        out: list = []
        for x in rows:
            if any(o["loc_id"] == x["loc_id"] or (norm(o["name"]) == norm(x["name"]) and (haversine(o, x) < 3 or (
                    o.get("type") == x.get("type") in ("district", "state", "union_territory") and o.get("state") == x.get("state")))) for o in out):
                continue
            out.append(x)
        return out

    # ---------------------------------------------------------------- providers
    async def photon_search(q: str, limit: int, lat: Optional[float], lng: Optional[float]) -> list:
        params = {"q": q, "limit": limit, "lang": "en", "bbox": INDIA_BBOX}
        if lat is not None and lng is not None:
            params.update(lat=lat, lon=lng)
        data = await P["photon"].get(f"{PHOTON}/api", params=params, timeout=8)
        return [d for d in (from_photon(f) for f in data.get("features", [])) if d]

    async def nominatim_search(params: dict) -> list:
        data = await P["nominatim"].get(f"{NOMINATIM}/search", params={"countrycodes": "in", "format": "jsonv2", "addressdetails": 1,
                                                                        "limit": 8, "accept-language": "en", **params})
        return [from_nominatim(it) for it in data]

    async def google_search(q: str, limit: int, lat=None, lng=None) -> list:
        """Google Places (New) Text Search, India only. Returns [] when no key is configured."""
        key = os.environ.get("GOOGLE_PLACES_API_KEY", "").strip()
        if not key:
            return []
        body = {"textQuery": q, "pageSize": min(limit, 10), "languageCode": "en", "regionCode": "IN",
                "locationRestriction": {"rectangle": {"low": {"latitude": 6.4, "longitude": 68.1}, "high": {"latitude": 37.6, "longitude": 97.4}}}}
        headers = {"X-Goog-Api-Key": key, "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.location,places.types,places.addressComponents"}
        async with httpx.AsyncClient(timeout=8) as c:
            res = await c.post("https://places.googleapis.com/v1/places:searchText", json=body, headers=headers)
        if res.status_code != 200:
            raise RuntimeError(f"google places {res.status_code}: {res.text[:160]}")
        out = []
        for p in res.json().get("places", []):
            comps = {t: c.get("longText") for c in p.get("addressComponents", []) for t in c.get("types", [])}
            if comps.get("country") and comps.get("country") != "India":
                continue
            types = p.get("types", [])
            otype = next((v for k, v in (("airport", "airport"), ("train_station", "railway_station"), ("transit_station", "railway_station"),
                                          ("bus_station", "bus_terminal"), ("locality", "city"), ("sublocality", "locality"), ("neighborhood", "locality"),
                                          ("administrative_area_level_3", "district"), ("administrative_area_level_2", "district"),
                                          ("administrative_area_level_1", "state"), ("postal_code", "pin_area"), ("tourist_attraction", "landmark"),
                                          ("hospital", "hospital"), ("university", "university"), ("hindu_temple", "religious"), ("route", "road")) if k in types), "landmark")
            loc = p.get("location") or {}
            if "latitude" not in loc:
                continue
            out.append(loc_doc((p.get("displayName") or {}).get("text") or q, otype,
                               clean_district(comps.get("administrative_area_level_3") or comps.get("administrative_area_level_2") or ""),
                               comps.get("administrative_area_level_1", ""), comps.get("postal_code"), loc["latitude"], loc["longitude"], [],
                               source="google", loc_id=f"gpl_{p['id'].lower()[:60]}", google_place_id=p["id"],
                               locality=comps.get("locality") or comps.get("sublocality") or "",
                               address=p.get("formattedAddress", ""), synced_at=now()))
        return out

    async def online_search(q: str, limit: int, lat=None, lng=None) -> tuple[list, str]:
        key = f"s:{norm(q)}:{round(lat, 1) if lat else ''}:{round(lng, 1) if lng else ''}"
        cached = await cache_get(key)
        if cached is not None:
            return cached, "cache"
        rows, src = [], "photon"
        try:
            rows = await google_search(q, limit, lat, lng)
            src = "google" if rows else src
        except Exception as exc:
            logger.warning("google places failed (%s), using OpenStreetMap", exc)
        try:
            rows += await photon_search(q, limit, lat, lng)
        except Exception as exc:
            logger.warning("photon failed (%s), falling back to nominatim", exc)
            try:
                rows += await nominatim_search({"q": q})
                src = src if src == "google" else "nominatim"
            except Exception as exc2:
                logger.warning("nominatim failed: %s", exc2)
                if not rows:
                    return [], "unavailable"
        rows = [public(await store(d)) for d in dedupe(rows)]
        await cache_set(key, rows, timedelta(days=7))
        return rows, src

    async def pin_lookup(pin: str) -> Optional[dict]:
        doc = await db.pincodes.find_one({"pin": pin}, {"_id": 0})
        if doc and doc.get("synced_at") and doc["synced_at"].replace(tzinfo=timezone.utc) > now() - timedelta(days=30):
            return doc
        try:
            data = await P["india_post"].get(f"{INDIA_POST}/pincode/{pin}", timeout=10)
            offices = (data[0].get("PostOffice") or []) if data and data[0].get("Status") == "Success" else []
        except Exception as exc:
            logger.warning("india post failed: %s", exc)
            return doc
        if not offices:
            return None
        first = offices[0]
        center = None
        try:
            hits = await nominatim_search({"postalcode": pin, "limit": 1})
            if hits:
                center = (hits[0]["lat"], hits[0]["lng"])
        except Exception:
            pass
        if not center:
            with_ctx = [d for d in await photon_search(f"{first['Name']} {first['District']} {first['State']}", 3, None, None)]
            if with_ctx:
                center = (with_ctx[0]["lat"], with_ctx[0]["lng"])
        doc = {"pin": pin, "district": first["District"], "state": first["State"], "division": first.get("Division"),
               "offices": [{"name": o["Name"], "branch_type": o.get("BranchType"), "block": o.get("Block"), "district": o["District"],
                            "state": o["State"], "delivery": o.get("DeliveryStatus")} for o in offices],
               "lat": center[0] if center else None, "lng": center[1] if center else None, "synced_at": now()}
        if center:
            doc["geo"] = {"type": "Point", "coordinates": [center[1], center[0]]}
        await db.pincodes.update_one({"pin": pin}, {"$set": doc}, upsert=True)
        return doc

    def pin_locs(pdoc: dict) -> list:
        if pdoc.get("lat") is None:
            return []
        out = [loc_doc(f"{pdoc['pin']} · {pdoc['district']}", "pin_area", pdoc["district"], pdoc["state"], pdoc["pin"], pdoc["lat"], pdoc["lng"],
                       [], source="india_post", loc_id=f"pin_{pdoc['pin']}", precision="pin_area")]
        for o in pdoc["offices"]:
            out.append(loc_doc(o["name"], "post_office", o["district"], o["state"], pdoc["pin"], pdoc["lat"], pdoc["lng"], [],
                               source="india_post", loc_id=f"pin_{pdoc['pin']}_{slug(o['name'])}", sub_district=o.get("block") or "",
                               precision="pin_area"))
        return [public(x) for x in out]

    async def nominatim_reverse(lat: float, lng: float, zoom: int = 16) -> Optional[dict]:
        try:
            it = await P["nominatim"].get(f"{NOMINATIM}/reverse", params={"lat": lat, "lon": lng, "format": "jsonv2", "addressdetails": 1,
                                                                          "zoom": zoom, "accept-language": "en"})
            if "lat" in it:
                return from_nominatim(it)
        except Exception as exc:
            logger.warning("nominatim reverse failed: %s", exc)
        try:
            data = await P["photon"].get(f"{PHOTON}/reverse", params={"lat": lat, "lon": lng, "lang": "en"}, timeout=8)
            rows = [d for d in (from_photon(f) for f in data.get("features", [])) if d]
            return rows[0] if rows else None
        except Exception as exc:
            logger.warning("photon reverse failed: %s", exc)
        return None

    # ---------------------------------------------------------------- search
    async def search(q: str, limit: int = 12, lat: Optional[float] = None, lng: Optional[float] = None) -> dict:
        qn = norm(q)
        results, sources = [], []
        if re.fullmatch(r"\d{3,6}", qn):
            results += await db.locations.find({"pin": {"$regex": f"^{qn}"}, "stale": {"$ne": True}}, LOC_OUT).limit(10).to_list(10)
            if len(qn) == 6:
                pdoc = await pin_lookup(qn)
                if pdoc:
                    results += pin_locs(pdoc)
                    sources.append("india_post")
            sources.append("travoo")
            rows = dedupe(results)
        else:
            local = await db.locations.find({"search_terms": {"$regex": f"(^|\\s){re.escape(qn)}"}, "stale": {"$ne": True}}, LOC_OUT).limit(40).to_list(40)
            sources.append("travoo")
            online = []
            if len(qn) >= 2:
                online, src = await online_search(q.strip(), 10, lat, lng)
                sources.append(src)
            bias = {"lat": lat, "lng": lng} if lat is not None and lng is not None else None

            def score(x):
                names = [norm(n) for n in [x["name"], *x.get("aliases", [])]]
                exact = 0 if qn in names else 1 if any(n.startswith(qn) for n in names) else 2
                curated = 0 if x.get("source") in ("travoo", "community") else 1
                dist = haversine(bias, x) / 500 if bias else 0
                return (exact, TYPE_RANK.get(x.get("type"), 3) + curated * 0.5 + dist)
            rows = dedupe(sorted(local + online, key=score))
        rows = rows[:limit]
        if not rows and len(qn) >= 3:
            await db.geo_misses.update_one({"q": qn}, {"$inc": {"count": 1}, "$set": {"last_at": now()}}, upsert=True)
        return {"results": rows, "sources": sources, "attribution": ATTRIBUTION}

    @r.get("/geo/search")
    async def geo_search(q: str = Query(min_length=1, max_length=120), limit: int = Query(12, ge=1, le=30),
                         lat: Optional[float] = None, lng: Optional[float] = None):
        """Autocomplete across villages, towns, PIN codes, districts, states, streets, stations, bus stops and landmarks."""
        return await search(q, limit, lat, lng)

    @r.get("/locations/search")  # backwards-compatible list response
    async def legacy_search(q: str = Query(min_length=1, max_length=80), limit: int = Query(12, le=30)):
        return (await search(q, limit))["results"]

    @r.get("/locations/osm")  # backwards-compatible
    async def legacy_osm(q: str = Query(min_length=2, max_length=120)):
        rows, src = await online_search(q, 10)
        if src == "unavailable":
            raise HTTPException(503, "Map search is unavailable right now. Try again shortly.")
        return rows

    @r.get("/geo/pincode/{pin}")
    async def geo_pincode(pin: str):
        if not re.fullmatch(r"[1-9]\d{5}", pin):
            raise HTTPException(400, "Enter a valid 6-digit Indian PIN code")
        pdoc = await pin_lookup(pin)
        if not pdoc:
            raise HTTPException(404, "PIN code not found in the India Post directory")
        pdoc.pop("geo", None)
        return {**pdoc, "locations": pin_locs(pdoc)}

    async def reverse(lat: float, lng: float, exact: bool) -> dict:
        if not in_india(lat, lng):
            raise HTTPException(400, "This point is outside India")
        key = f"rev:{lat:.4f},{lng:.4f}"
        d = await cache_get(key)
        if d is None:
            found = await nominatim_reverse(lat, lng)
            if not found:
                raise HTTPException(503, "Map service unavailable — try again shortly")
            d = public(await store(found, refresh=True))
            await cache_set(key, d, timedelta(days=14))
        if exact:  # keep the user's exact pin, labelled with the nearest named place
            name = d["name"] if d.get("type") not in ("road",) else f"{d['name']}, {d.get('locality') or d.get('sub_district') or d.get('district') or ''}".strip(", ")
            d = {**d, "loc_id": f"pin_{lat:.5f}_{lng:.5f}", "name": name, "lat": round(lat, 6), "lng": round(lng, 6),
                 "source": "pin", "near": d["name"], "type": "pin"}
        return d

    @r.get("/geo/reverse")
    async def geo_reverse(lat: float = Query(ge=-90, le=90), lng: float = Query(ge=-180, le=180), exact: bool = False):
        return await reverse(lat, lng, exact)

    @r.get("/locations/reverse")  # backwards-compatible
    async def legacy_reverse(lat: float, lng: float):
        return await reverse(lat, lng, False)

    @r.get("/geo/place/{loc_id}")
    async def geo_place(loc_id: str):
        """Resolve a selected result: enrich OSM places with district / taluk / PIN, refine PIN-area post offices."""
        d = await db.locations.find_one({"loc_id": loc_id}, {"_id": 0})
        if not d and loc_id.startswith("pin_"):
            m = re.match(r"pin_(\d{6})(?:_(.+))?$", loc_id)
            pdoc = await pin_lookup(m.group(1)) if m else None
            d = next((x for x in pin_locs(pdoc) if x["loc_id"] == loc_id), None) if pdoc else None
            if d and d["type"] == "post_office":
                try:
                    hits = [h for h in await photon_search(f"{d['name']} {d['district']}", 5, d["lat"], d["lng"]) if haversine(h, d) < 25]
                    if hits:
                        d.update(lat=hits[0]["lat"], lng=hits[0]["lng"], precision="approximate")
                except Exception:
                    pass
            if d:
                return d
        if not d:
            raise HTTPException(404, "Place not found")
        if d.get("source") == "openstreetmap" and d.get("osm_id") and not d.get("details_at"):
            try:
                data = await P["nominatim"].get(f"{NOMINATIM}/lookup", params={"osm_ids": d["osm_id"], "format": "jsonv2", "addressdetails": 1,
                                                                               "accept-language": "en"})
                if data:
                    rich = from_nominatim(data[0])
                    rich["loc_id"] = d["loc_id"]
                    rich["name"] = d["name"]
                    await store(rich, refresh=True)
                    d = await db.locations.find_one({"loc_id": loc_id}, {"_id": 0})
            except Exception as exc:
                logger.info("lookup enrich skipped: %s", exc)
        return public(d)

    # ---------------------------------------------------------------- routing
    async def osrm_routes(pts: list, alternatives: bool) -> tuple[list, str]:
        coords = ";".join(f"{p['lng']:.6f},{p['lat']:.6f}" for p in pts)
        params = {"overview": "full", "geometries": "geojson", "steps": "true",
                  "alternatives": "true" if alternatives and len(pts) == 2 else "false"}
        for base, prov in ((OSRM[0], "osrm"), (OSRM[1], "osrm_fossgis")):
            try:
                data = await P[prov].get(f"{base}/route/v1/driving/{coords}", params=params, timeout=12)
                if data.get("code") == "Ok" and data.get("routes"):
                    return data["routes"], prov
            except Exception as exc:
                logger.warning("%s routing failed: %s", prov, exc)
        return [], "estimate"

    def summarise(rt: dict) -> dict:
        toll_m, nh_m, roads = 0.0, 0.0, {}
        for leg in rt.get("legs", []):
            for st in leg.get("steps", []):
                if any("toll" in (ix.get("classes") or []) for ix in st.get("intersections", [])):
                    toll_m += st.get("distance", 0)
                if re.match(r"^(NH|NE)\s?\d", st.get("ref") or "") or "expressway" in (st.get("name") or "").lower():
                    nh_m += st.get("distance", 0)
                ref = st.get("ref") or st.get("name")
                if ref:
                    roads[ref] = roads.get(ref, 0) + st.get("distance", 0)
        via = [k.split(";")[0] for k, _ in sorted(roads.items(), key=lambda kv: -kv[1])[:2]]
        line = downsample([[round(c[1], 5), round(c[0], 5)] for c in rt["geometry"]["coordinates"]], 400)
        # OSM toll tagging is sparse in India: use tagged toll sections when present, else national-highway/expressway km
        basis = "toll_tagged" if toll_m else "national_highway_km"
        toll_km = round((toll_m or nh_m) / 1000)
        rate = TOLL_RATE_PER_KM if toll_m else NH_TOLL_RATE_PER_KM
        return {"distance_km": round(rt["distance"] / 1000), "duration_min": round(rt["duration"] / 60), "via": via,
                "toll_km": toll_km, "toll_estimate": round(toll_km * rate), "toll_basis": basis, "geometry": line}

    async def route_options(pts: list, alternatives: bool = True) -> dict:
        key = "rt:" + ";".join(f"{p['lat']:.4f},{p['lng']:.4f}" for p in pts) + (":a" if alternatives else "")
        cached = await cache_get(key)
        if cached:
            return cached
        routes, src = await osrm_routes(pts, alternatives)
        if routes:
            out = {"source": src, "routes": [summarise(rt) for rt in routes[:3]], "attribution": ATTRIBUTION}
            await cache_set(key, out, timedelta(days=3))
            return out
        km = round(sum(haversine(pts[i], pts[i + 1]) for i in range(len(pts) - 1)) * 1.3)
        return {"source": "estimate", "attribution": ATTRIBUTION,
                "routes": [{"distance_km": km, "duration_min": int(km / 55 * 60), "via": [], "toll_km": 0, "toll_estimate": 0, "toll_basis": "none",
                            "geometry": [[p["lat"], p["lng"]] for p in pts]}]}

    r.route_options = route_options  # exposed to the trips module

    def parse_points(points: str) -> list:
        try:
            pts = [{"lat": float(a), "lng": float(b)} for a, b in (p.split(",") for p in points.split(";"))]
        except ValueError:
            raise HTTPException(400, "Invalid points")
        if not 2 <= len(pts) <= 10:
            raise HTTPException(400, "Need between 2 and 10 points")
        if not all(in_india(p["lat"], p["lng"]) for p in pts):
            raise HTTPException(400, "All points must be inside India")
        return pts

    @r.get("/geo/route")
    async def geo_route(points: str = Query(max_length=800), alternatives: bool = True):
        """points = 'lat,lng;lat,lng;...' → road distance, travel time, geometry, toll estimate and up to 3 alternatives."""
        return await route_options(parse_points(points), alternatives)

    @r.get("/route/estimate")  # backwards-compatible
    async def legacy_estimate(points: str = Query(max_length=800)):
        res = await route_options(parse_points(points), False)
        best = res["routes"][0]
        return {"distance_km": best["distance_km"], "duration_min": best["duration_min"], "source": "osrm" if res["source"].startswith("osrm") else "estimate"}

    # ---------------------------------------------------------------- nearby pickup points
    @r.get("/geo/nearby")
    async def geo_nearby(lat: float, lng: float, radius_m: int = Query(3000, ge=200, le=10000)):
        """Bus stops, bus stands, railway stations and airports around a point (Overpass, Photon fallback)."""
        if not in_india(lat, lng):
            raise HTTPException(400, "This point is outside India")
        key = f"nb:{lat:.3f},{lng:.3f}:{radius_m}"
        cached = await cache_get(key)
        if cached is not None:
            return cached
        here = {"lat": lat, "lng": lng}
        rows, src = [], "overpass"
        query = (f"[out:json][timeout:15];(nwr(around:{radius_m},{lat},{lng})[railway~\"^(station|halt)$\"][name];"
                 f"nwr(around:{radius_m},{lat},{lng})[amenity=bus_station][name];node(around:{radius_m},{lat},{lng})[highway=bus_stop][name];"
                 f"nwr(around:{radius_m * 5},{lat},{lng})[aeroway=aerodrome][iata];);out center 40;")
        for url in OVERPASS:
            try:
                if not P["overpass"].available:
                    break
                data = await P["overpass"].get(url, method="POST", data={"data": query}, timeout=7)
                for e in data.get("elements", []):
                    tg = e.get("tags", {})
                    la, lo = e.get("lat") or e.get("center", {}).get("lat"), e.get("lon") or e.get("center", {}).get("lon")
                    if la is None:
                        continue
                    key_ = next((k for k in ("railway", "amenity", "highway", "aeroway") if k in tg), "")
                    rows.append(loc_doc(tg.get("name:en") or tg["name"], classify(key_, tg.get(key_, "")), "", "", tg.get("addr:postcode"),
                                        la, lo, [x for x in [tg.get("name")] if x and x != tg.get("name:en")], source="openstreetmap",
                                        loc_id=f"osm_{e['type'][0]}{e['id']}", osm_id=f"{e['type'][0].upper()}{e['id']}", synced_at=now()))
                break
            except Exception as exc:
                logger.info("overpass mirror failed (%s): %s", url, exc)
        if not rows:
            src = "nominatim"
            dlat, dlng = radius_m / 111000, radius_m / (111000 * math.cos(math.radians(lat)))
            box = f"{lng - dlng},{lat + dlat},{lng + dlng},{lat - dlat}"
            for q in ("railway station", "bus station", "bus stop"):
                try:
                    rows += [d for d in await nominatim_search({"q": q, "viewbox": box, "bounded": 1, "limit": 10, "addressdetails": 0})]
                except Exception as exc:
                    logger.info("nominatim nearby failed: %s", exc)
                    break
        if not rows:
            src = "photon"
            for q, tag in (("railway station", "railway:station"), ("bus stand", "amenity:bus_station"), ("bus stop", "highway:bus_stop")):
                try:
                    data = await P["photon"].get(f"{PHOTON}/api", params={"q": q, "lat": lat, "lon": lng, "osm_tag": tag, "limit": 8, "lang": "en"}, timeout=8)
                    rows += [d for d in (from_photon(f) for f in data.get("features", [])) if d and haversine(here, d) * 1000 <= radius_m * 2]
                except Exception as exc:
                    logger.info("photon nearby failed: %s", exc)
        out = []
        for d in dedupe(sorted(rows, key=lambda x: haversine(here, x))):
            await store(d)
            out.append({**public(d), "distance_m": round(haversine(here, d) * 1000)})
        res = {"results": out[:25], "source": src if out else "none", "attribution": ATTRIBUTION}
        await cache_set(key, res, timedelta(days=7))
        return res

    # ---------------------------------------------------------------- synchronisation
    sync_lock = asyncio.Lock()

    async def run_sync(trigger: str = "schedule") -> dict:
        if sync_lock.locked():
            return {"status": "running"}
        async with sync_lock:
            started = now()
            stats = {"refreshed": 0, "moved": 0, "outdated": 0, "duplicates_merged": 0, "pins_refreshed": 0, "flagged_curated": 0}
            errors = []
            await db.geo_meta.update_one({"key": "sync"}, {"$set": {"running": True, "last_run_at": started}}, upsert=True)
            try:
                # 1) refresh cached OSM places older than 30 days (Nominatim lookup, 50 ids per call)
                cutoff = now() - timedelta(days=30)
                stale = await db.locations.find({"source": "openstreetmap", "osm_id": {"$exists": True},
                                                 "$or": [{"synced_at": {"$lt": cutoff}}, {"synced_at": {"$exists": False}}]},
                                                {"_id": 0, "loc_id": 1, "osm_id": 1, "lat": 1, "lng": 1, "name": 1}).limit(500).to_list(500)
                for i in range(0, len(stale), 50):
                    batch = stale[i:i + 50]
                    try:
                        data = await P["nominatim"].get(f"{NOMINATIM}/lookup", params={"osm_ids": ",".join(b["osm_id"] for b in batch),
                                                                                       "format": "jsonv2", "addressdetails": 1, "accept-language": "en"})
                    except Exception as exc:
                        errors.append(f"lookup: {exc}")
                        continue
                    found = {f"{(it.get('osm_type') or 'x')[:1].upper()}{it.get('osm_id')}": it for it in data}
                    for b in batch:
                        it = found.get(b["osm_id"])
                        if not it:
                            await db.locations.update_one({"loc_id": b["loc_id"]}, {"$set": {"stale": True, "synced_at": now()}})
                            stats["outdated"] += 1
                            continue
                        rich = from_nominatim(it)
                        rich.update(loc_id=b["loc_id"], name=b["name"])
                        if haversine(b, rich) > 0.2:
                            stats["moved"] += 1
                        await store(rich, refresh=True)
                        stats["refreshed"] += 1
                # 2) verify curated coordinates against OpenStreetMap (a few per run, 1 req/s)
                curated = await db.locations.find({"source": {"$in": ["travoo", "community"]}, "type": {"$nin": ["state", "union_territory"]},
                                                   "$or": [{"verified_at": {"$exists": False}}, {"verified_at": {"$lt": cutoff}}]},
                                                  {"_id": 0, "loc_id": 1, "name": 1, "state": 1, "lat": 1, "lng": 1}).limit(25).to_list(25)
                for c in curated:
                    try:
                        hits = await nominatim_search({"q": f"{c['name']}, {c['state']}", "limit": 1})
                    except Exception as exc:
                        errors.append(f"verify: {exc}")
                        break
                    off = round(haversine(c, hits[0]), 1) if hits else None
                    flag = off is not None and off > 25
                    stats["flagged_curated"] += int(flag)
                    await db.locations.update_one({"loc_id": c["loc_id"]}, {"$set": {"verified_at": now(), "osm_offset_km": off, "needs_review": flag}})
                # 3) refresh PIN directory entries older than 30 days
                for p in await db.pincodes.find({"synced_at": {"$lt": cutoff}}, {"_id": 0, "pin": 1}).limit(20).to_list(20):
                    await db.pincodes.update_one({"pin": p["pin"]}, {"$set": {"synced_at": cutoff - timedelta(days=1)}})
                    if await pin_lookup(p["pin"]):
                        stats["pins_refreshed"] += 1
                # 4) merge duplicates (same name & state within 1 km) — trips keep their own snapshots, so this is safe
                dup_groups = await db.locations.aggregate([
                    {"$match": {"stale": {"$ne": True}}},
                    {"$group": {"_id": {"n": {"$toLower": "$name"}, "s": "$state", "t": "$type"}, "ids": {"$push": "$loc_id"}, "c": {"$sum": 1}}},
                    {"$match": {"c": {"$gt": 1}}}, {"$limit": 500}]).to_list(500)
                prio = {"travoo": 0, "community": 1, "openstreetmap": 2}
                for g in dup_groups:
                    docs = await db.locations.find({"loc_id": {"$in": g["ids"]}}, {"_id": 0}).to_list(50)
                    docs.sort(key=lambda d: (prio.get(d.get("source"), 3), 0 if d.get("details_at") else 1))
                    keep = docs[0]
                    for d in docs[1:]:
                        if haversine(keep, d) <= 1.0:
                            aliases = sorted(set(keep.get("aliases", []) + d.get("aliases", [])))
                            await db.locations.update_one({"loc_id": keep["loc_id"]}, {"$set": {"aliases": aliases, "pin": keep.get("pin") or d.get("pin"),
                                                                                                  "district": keep.get("district") or d.get("district")},
                                                                                         "$addToSet": {"search_terms": {"$each": d.get("search_terms", [])}}})
                            await db.locations.delete_one({"loc_id": d["loc_id"]})
                            stats["duplicates_merged"] += 1
                status = "ok" if not errors else "partial"
            except Exception as exc:
                logger.exception("geo sync failed")
                errors.append(str(exc))
                status = "failed"
            meta = {"running": False, "last_status": status, "last_trigger": trigger, "last_stats": stats, "last_errors": errors[:10],
                    "last_duration_s": round((now() - started).total_seconds(), 1)}
            if status != "failed":
                meta["last_success_at"] = now()
            await db.geo_meta.update_one({"key": "sync"}, {"$set": meta}, upsert=True)
            return {"status": status, **stats, "errors": errors[:10]}

    async def sync_loop():
        await asyncio.sleep(90)
        while True:
            meta = await db.geo_meta.find_one({"key": "sync"}) or {}
            last = meta.get("last_success_at")
            if not last or last.replace(tzinfo=timezone.utc) < now() - timedelta(hours=24):
                try:
                    await run_sync("schedule")
                except Exception:
                    logger.exception("scheduled geo sync crashed")
            await asyncio.sleep(3600)

    r.sync_loop = sync_loop

    async def status_doc() -> dict:
        meta = await db.geo_meta.find_one({"key": "sync"}, {"_id": 0}) or {}
        counts = {"locations": await db.locations.estimated_document_count(),
                  "openstreetmap": await db.locations.count_documents({"source": "openstreetmap"}),
                  "curated": await db.locations.count_documents({"source": {"$in": ["travoo", "community"]}}),
                  "pincodes": await db.pincodes.estimated_document_count()}
        return {"last_success_at": meta.get("last_success_at"), "last_run_at": meta.get("last_run_at"), "last_status": meta.get("last_status"),
                "running": sync_lock.locked(), "counts": counts, "providers": [p.health() for p in P.values()],
                "attribution": ATTRIBUTION}

    @r.get("/geo/status")
    async def geo_status():
        return await status_doc()

    @r.post("/admin/geo/sync")
    async def admin_geo_sync(_: dict = Depends(get_admin)):
        """Starts a sync in the background; poll /admin/geo/report (running flag, last_stats)."""
        if sync_lock.locked():
            return {"status": "running"}
        r.sync_task = asyncio.create_task(run_sync("admin"))
        return {"status": "started"}

    @r.get("/admin/geo/report")
    async def admin_geo_report(_: dict = Depends(get_admin)):
        meta = await db.geo_meta.find_one({"key": "sync"}, {"_id": 0}) or {}
        return {**(await status_doc()), "last_stats": meta.get("last_stats"), "last_errors": meta.get("last_errors", []),
                "misses": await db.geo_misses.find({}, {"_id": 0}).sort("count", -1).limit(30).to_list(30),
                "flagged": await db.locations.find({"needs_review": True}, LOC_OUT).limit(30).to_list(30),
                "outdated": await db.locations.count_documents({"stale": True}),
                "pending_requests": await db.missing_locations.count_documents({"status": "pending"})}

    r.nominatim_reverse = nominatim_reverse
    return r
