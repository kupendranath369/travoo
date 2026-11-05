import asyncio
import logging
import math
import os
import re
import secrets
import uuid
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Literal, Optional

import bcrypt
import httpx
import jwt
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr, Field
from pymongo import ASCENDING, DESCENDING, GEOSPHERE, IndexModel, ReturnDocument
from pymongo.errors import DuplicateKeyError
from starlette.middleware.cors import CORSMiddleware

from seed_data import PLACES, POPULAR_ROUTES, STATES

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]
JWT_SECRET = os.environ["JWT_SECRET"]
IST = timezone(timedelta(hours=5, minutes=30))
EMERGENT_SESSION_URL = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"
NOMINATIM = "https://nominatim.openstreetmap.org"
OSM_HEADERS = {"User-Agent": "Travoo-Carpool/1.0 (support@travoo.in)"}

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("travoo")

INDEXES: dict[str, list[IndexModel]] = {
    "users": [IndexModel([("email", ASCENDING)], name="email", unique=True),
              IndexModel([("user_id", ASCENDING)], name="user_id", unique=True),
              IndexModel([("driver_status", ASCENDING)], name="driver_status")],
    "user_sessions": [IndexModel([("session_token", ASCENDING)], name="token", unique=True),
                      IndexModel([("expires_at", ASCENDING)], name="ttl", expireAfterSeconds=0)],
    "locations": [IndexModel([("loc_id", ASCENDING)], name="loc_id", unique=True),
                  IndexModel([("search_terms", ASCENDING)], name="terms"),
                  IndexModel([("pin", ASCENDING)], name="pin"),
                  IndexModel([("geo", GEOSPHERE)], name="geo")],
    "vehicles": [IndexModel([("vehicle_id", ASCENDING)], name="vid", unique=True),
                 IndexModel([("owner_id", ASCENDING)], name="owner")],
    "trips": [IndexModel([("trip_id", ASCENDING)], name="tid", unique=True),
              IndexModel([("origin.geo", GEOSPHERE)], name="origin_geo"),
              IndexModel([("status", ASCENDING), ("date", ASCENDING)], name="status_date"),
              IndexModel([("driver_id", ASCENDING)], name="driver")],
    "bookings": [IndexModel([("booking_id", ASCENDING)], name="bid", unique=True),
                 IndexModel([("active_key", ASCENDING)], name="active_key", unique=True, sparse=True),
                 IndexModel([("trip_id", ASCENDING)], name="trip"),
                 IndexModel([("passenger_id", ASCENDING)], name="passenger"),
                 IndexModel([("driver_id", ASCENDING)], name="driver")],
    "earnings_ledger": [IndexModel([("booking_id", ASCENDING), ("type", ASCENDING)], name="uniq_entry", unique=True),
                        IndexModel([("driver_id", ASCENDING), ("created_at", DESCENDING)], name="driver_time")],
    "reviews": [IndexModel([("booking_id", ASCENDING), ("reviewer_id", ASCENDING), ("target_id", ASCENDING)], name="uniq_review", unique=True),
                IndexModel([("target_id", ASCENDING)], name="target")],
    "messages": [IndexModel([("booking_id", ASCENDING), ("created_at", ASCENDING)], name="booking_time")],
    "notifications": [IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)], name="user_time")],
    "tickets": [IndexModel([("ticket_id", ASCENDING)], name="tkid", unique=True), IndexModel([("user_id", ASCENDING)], name="user")],
    "popular_routes": [IndexModel([("route_id", ASCENDING)], name="rid", unique=True)],
    "audit_logs": [IndexModel([("created_at", DESCENDING)], name="time")],
}


async def ensure_indexes() -> None:
    for collection, models in INDEXES.items():
        for model in models:
            try:
                await db[collection].create_indexes([model])
            except Exception as exc:
                logger.error("ensure_indexes(%s.%s): %s", collection, model.document["name"], exc)


app = FastAPI(title="Travoo API")


@app.get("/health", include_in_schema=False)
@app.head("/health", include_in_schema=False)
async def health():
    return {"status": "ok"}


api = APIRouter(prefix="/api")


# ---------------------------------------------------------------- helpers
def now() -> datetime:
    return datetime.now(timezone.utc)


def nid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def hash_pw(p: str) -> str:
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()


def check_pw(p: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(p.encode(), h.encode())
    except ValueError:
        return False


def make_token(user_id: str) -> str:
    return jwt.encode({"sub": user_id, "exp": now() + timedelta(days=7), "iat": now()}, JWT_SECRET, algorithm="HS256")


def haversine(a: dict, b: dict) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, [a["lat"], a["lng"], b["lat"], b["lng"]])
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def route_label(trip: dict) -> str:
    return f"{trip['origin']['name']} → {trip['destination']['name']}"


USER_PRIVATE = {"_id": 0, "password_hash": 0}
PUBLIC_FIELDS = {"_id": 0, "user_id": 1, "name": 1, "picture": 1, "rating_avg": 1, "rating_count": 1,
                 "driver_status": 1, "created_at": 1, "bio": 1}


async def public_user(uid: str) -> dict:
    return await db.users.find_one({"user_id": uid}, PUBLIC_FIELDS) or {"user_id": uid, "name": "Unknown"}


async def audit(actor: str, action: str, target: str, extra: Optional[dict] = None):
    await db.audit_logs.insert_one({"actor": actor, "action": action, "target": target, "extra": extra or {}, "created_at": now()})


async def notify(user_id: str, ntype: str, params: dict, ref: Optional[str] = None):
    await db.notifications.insert_one({"notif_id": nid("ntf"), "user_id": user_id, "type": ntype, "params": params,
                                       "ref": ref, "read": False, "created_at": now()})


async def ledger(driver_id: str, booking: dict, etype: str, amount: int, method: Optional[str] = None):
    """Append-only earnings ledger. Unique (booking_id, type) prevents duplicate entries."""
    try:
        await db.earnings_ledger.insert_one({"entry_id": nid("led"), "driver_id": driver_id, "booking_id": booking["booking_id"],
                                             "trip_id": booking["trip_id"], "type": etype, "amount": amount, "method": method,
                                             "route": booking.get("route"), "created_at": now()})
    except DuplicateKeyError:
        pass


async def get_settings() -> dict:
    s = await db.settings.find_one({"key": "platform"}, {"_id": 0})
    return s or {}


# ---------------------------------------------------------------- auth
async def get_user(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Not authenticated")
    token = auth[7:]
    uid = None
    try:
        uid = jwt.decode(token, JWT_SECRET, algorithms=["HS256"]).get("sub")
    except jwt.InvalidTokenError:
        sess = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
        if sess:
            exp = sess["expires_at"]
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp > now():
                uid = sess["user_id"]
    if not uid:
        raise HTTPException(401, "Invalid or expired session")
    user = await db.users.find_one({"user_id": uid}, USER_PRIVATE)
    if not user:
        raise HTTPException(401, "User not found")
    if user.get("suspended"):
        raise HTTPException(403, "Account suspended. Contact support.")
    return user


async def get_admin(user: dict = Depends(get_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin access required")
    return user


def new_user_doc(email: str, name: str, **extra) -> dict:
    return {"user_id": nid("user"), "email": email.lower(), "name": name, "phone": extra.get("phone", ""),
            "role": extra.get("role", "user"), "language": extra.get("language", "en"), "picture": extra.get("picture"),
            "upi_id": "", "bio": "", "driver_status": extra.get("driver_status", "not_submitted"),
            "rating_avg": 0, "rating_count": 0, "suspended": False, "consent_at": now(), "created_at": now(),
            "auth_provider": extra.get("auth_provider", "password"), "is_demo": extra.get("is_demo", False)}


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=2, max_length=80)
    phone: str = Field(default="", max_length=15)
    language: str = "en"
    consent: bool


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class SessionIn(BaseModel):
    session_id: str


@api.post("/auth/register")
async def register(body: RegisterIn):
    if not body.consent:
        raise HTTPException(400, "Consent is required")
    doc = new_user_doc(body.email, body.name.strip(), phone=body.phone, language=body.language)
    doc["password_hash"] = hash_pw(body.password)
    try:
        await db.users.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(409, "Email already registered")
    user = await db.users.find_one({"user_id": doc["user_id"]}, USER_PRIVATE)
    return {"token": make_token(doc["user_id"]), "user": user}


@api.post("/auth/login")
async def login(body: LoginIn):
    user = await db.users.find_one({"email": body.email.lower()})
    if not user or not user.get("password_hash") or not check_pw(body.password, user["password_hash"]):
        raise HTTPException(401, "Incorrect email or password")
    if user.get("suspended"):
        raise HTTPException(403, "Account suspended. Contact support.")
    return {"token": make_token(user["user_id"]), "user": await db.users.find_one({"user_id": user["user_id"]}, USER_PRIVATE)}


@api.post("/auth/session")
async def google_session(body: SessionIn):
    async with httpx.AsyncClient(timeout=15) as hc:
        r = await hc.get(EMERGENT_SESSION_URL, headers={"X-Session-ID": body.session_id})
    if r.status_code != 200:
        raise HTTPException(401, "Invalid session")
    data = r.json()
    email = data["email"].lower()
    existing = await db.users.find_one({"email": email}, {"_id": 0, "user_id": 1, "suspended": 1})
    if existing:
        if existing.get("suspended"):
            raise HTTPException(403, "Account suspended. Contact support.")
        uid = existing["user_id"]
        await db.users.update_one({"user_id": uid}, {"$set": {"picture": data.get("picture")}})
    else:
        doc = new_user_doc(email, data.get("name") or email.split("@")[0], picture=data.get("picture"), auth_provider="google")
        await db.users.insert_one(doc)
        uid = doc["user_id"]
    token = data["session_token"]
    await db.user_sessions.insert_one({"session_token": token, "user_id": uid, "created_at": now(), "expires_at": now() + timedelta(days=7)})
    return {"session_token": token, "user": await db.users.find_one({"user_id": uid}, USER_PRIVATE)}


@api.get("/auth/me")
async def me(user: dict = Depends(get_user)):
    return user


@api.post("/auth/logout")
async def logout(request: Request):
    token = request.headers.get("Authorization", "")[7:]
    await db.user_sessions.delete_one({"session_token": token})
    return {"ok": True}


class ProfileIn(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=80)
    phone: Optional[str] = Field(default=None, max_length=15)
    upi_id: Optional[str] = Field(default=None, max_length=60)
    language: Optional[str] = Field(default=None, max_length=8)
    bio: Optional[str] = Field(default=None, max_length=300)


@api.put("/me")
async def update_me(body: ProfileIn, user: dict = Depends(get_user)):
    upd = {k: v for k, v in body.model_dump().items() if v is not None}
    if upd.get("upi_id") and not re.fullmatch(r"[\w.\-]{2,}@[a-zA-Z]{2,}", upd["upi_id"]):
        raise HTTPException(400, "Enter a valid UPI ID like name@bank")
    if upd:
        await db.users.update_one({"user_id": user["user_id"]}, {"$set": upd})
    return await db.users.find_one({"user_id": user["user_id"]}, USER_PRIVATE)


@api.get("/users/{uid}")
async def user_profile(uid: str, _: dict = Depends(get_user)):
    u = await public_user(uid)
    reviews = await db.reviews.find({"target_id": uid, "hidden": {"$ne": True}}, {"_id": 0}).sort("created_at", -1).to_list(20)
    return {"user": u, "reviews": reviews}


# ---------------------------------------------------------------- locations
def loc_doc(name, ltype, district, state, pin, lat, lng, aliases, source="travoo", loc_id=None):
    terms = sorted({norm(x) for x in [name, *aliases, district or "", state or ""] if x})
    return {"loc_id": loc_id or f"in_{re.sub(r'[^a-z0-9]+', '_', norm(name))}_{re.sub(r'[^a-z0-9]+', '_', norm(state or ''))}",
            "name": name, "type": ltype, "district": district, "state": state, "pin": pin, "lat": lat, "lng": lng,
            "aliases": aliases, "search_terms": terms, "geo": {"type": "Point", "coordinates": [lng, lat]}, "source": source}


LOC_OUT = {"_id": 0, "search_terms": 0, "geo": 0}


@api.get("/locations/search")
async def search_locations(q: str = Query(min_length=1, max_length=80), limit: int = Query(12, le=30)):
    qn = norm(q)
    if qn.isdigit():
        filt = {"pin": {"$regex": f"^{re.escape(qn)}"}}
    else:
        filt = {"search_terms": {"$regex": f"(^|\\s){re.escape(qn)}"}}
    rows = await db.locations.find(filt, LOC_OUT).limit(60).to_list(60)
    type_rank = {"city": 0, "town": 1, "airport": 2, "railway_station": 2, "bus_terminal": 2}

    def score(r):
        exact = 0 if norm(r["name"]).startswith(qn) else 1
        return (exact, type_rank.get(r["type"], 3), r["name"])
    rows.sort(key=score)
    return rows[:limit]


def osm_to_loc(item: dict) -> dict:
    a = item.get("address", {})
    name = item.get("name") or item.get("display_name", "").split(",")[0]
    district = a.get("state_district") or a.get("county") or a.get("city_district") or a.get("city") or ""
    otype = item.get("addresstype") or item.get("type") or "place"
    mapping = {"village": "village", "hamlet": "village", "town": "town", "city": "city", "suburb": "locality",
               "neighbourhood": "locality", "aerodrome": "airport", "station": "railway_station", "bus_station": "bus_terminal"}
    ltype = mapping.get(otype, mapping.get(item.get("type", ""), "landmark" if item.get("class") in ("amenity", "tourism", "historic") else "place"))
    return loc_doc(name, ltype, district.replace(" District", ""), a.get("state", ""), a.get("postcode"),
                   float(item["lat"]), float(item["lon"]), [], source="openstreetmap",
                   loc_id=f"osm_{item.get('osm_type', 'x')[:1]}{item.get('osm_id')}")


@api.get("/locations/osm")
async def osm_search(q: str = Query(min_length=2, max_length=120)):
    """Searches OpenStreetMap (Nominatim, © OpenStreetMap contributors, ODbL) for villages/landmarks; caches results."""
    try:
        async with httpx.AsyncClient(timeout=10, headers=OSM_HEADERS) as hc:
            r = await hc.get(f"{NOMINATIM}/search", params={"q": q, "countrycodes": "in", "format": "jsonv2",
                                                              "addressdetails": 1, "limit": 8, "accept-language": "en"})
        items = r.json() if r.status_code == 200 else []
    except Exception as exc:
        logger.warning("osm search failed: %s", exc)
        raise HTTPException(503, "Map search is unavailable right now. Try the built-in list.")
    out = []
    for it in items:
        d = osm_to_loc(it)
        await db.locations.update_one({"loc_id": d["loc_id"]}, {"$setOnInsert": d}, upsert=True)
        out.append({k: v for k, v in d.items() if k not in ("search_terms", "geo")})
    return out


@api.get("/locations/reverse")
async def osm_reverse(lat: float, lng: float):
    try:
        async with httpx.AsyncClient(timeout=10, headers=OSM_HEADERS) as hc:
            r = await hc.get(f"{NOMINATIM}/reverse", params={"lat": lat, "lon": lng, "format": "jsonv2", "addressdetails": 1, "zoom": 14, "accept-language": "en"})
        item = r.json()
    except Exception:
        raise HTTPException(503, "Map service unavailable")
    if "lat" not in item:
        raise HTTPException(404, "No place found here")
    d = osm_to_loc(item)
    await db.locations.update_one({"loc_id": d["loc_id"]}, {"$setOnInsert": d}, upsert=True)
    return {k: v for k, v in d.items() if k not in ("search_terms", "geo")}


@api.get("/geo/states")
async def states():
    return await db.locations.find({"type": {"$in": ["state", "union_territory"]}}, LOC_OUT).sort("name", 1).to_list(50)


class LocIn(BaseModel):
    loc_id: str
    name: str
    type: str = "place"
    district: Optional[str] = ""
    state: Optional[str] = ""
    pin: Optional[str] = None
    lat: float
    lng: float


def loc_snapshot(l: LocIn) -> dict:
    d = l.model_dump()
    d["geo"] = {"type": "Point", "coordinates": [l.lng, l.lat]}
    return d


# ---------------------------------------------------------------- popular routes / settings
@api.get("/routes/popular")
async def popular_routes():
    return await db.popular_routes.find({"active": True}, {"_id": 0}).sort("order", 1).to_list(30)


@api.get("/settings")
async def public_settings():
    s = await get_settings()
    return {k: s.get(k) for k in ("passenger_cancel_hours", "driver_cancel_hours", "cancellation_reasons", "instant_driver_approval")}


# ---------------------------------------------------------------- driver verification & vehicles
class VerificationIn(BaseModel):
    legal_name: str = Field(min_length=3, max_length=100)
    phone: str = Field(pattern=r"^[6-9]\d{9}$")
    licence_no: str = Field(min_length=8, max_length=20)
    licence_expiry: str = Field(pattern=r"^\d{2}-\d{2}-\d{4}$")
    rc_no: str = Field(min_length=6, max_length=15)


def mask(v: str) -> str:
    return v[:2] + "•" * max(0, len(v) - 6) + v[-4:] if v else v


@api.get("/driver/profile")
async def driver_profile(user: dict = Depends(get_user)):
    doc = await db.driver_documents.find_one({"user_id": user["user_id"]}, {"_id": 0}) or {}
    if doc:
        doc["licence_no"] = mask(doc.get("licence_no", ""))
        doc["rc_no"] = mask(doc.get("rc_no", ""))
    vehicles = await db.vehicles.find({"owner_id": user["user_id"], "deleted": {"$ne": True}}, {"_id": 0}).to_list(20)
    return {"status": user.get("driver_status", "not_submitted"), "documents": doc, "vehicles": vehicles}


@api.post("/driver/verification")
async def submit_verification(body: VerificationIn, user: dict = Depends(get_user)):
    if user.get("driver_status") in ("under_review", "approved"):
        raise HTTPException(400, "Verification already submitted")
    settings = await get_settings()
    status = "approved" if settings.get("instant_driver_approval") else "under_review"
    doc = {**body.model_dump(), "licence_no": body.licence_no.upper(), "rc_no": body.rc_no.upper(),
           "user_id": user["user_id"], "submitted_at": now(), "admin_note": "", "reviewed_at": None}
    await db.driver_documents.update_one({"user_id": user["user_id"]}, {"$set": doc}, upsert=True)
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"driver_status": status, "phone": body.phone}})
    if status == "approved":
        await notify(user["user_id"], "driver_approved", {})
    await audit(user["user_id"], "driver.submit", user["user_id"], {"status": status})
    return {"status": status}


class VehicleIn(BaseModel):
    make: str = Field(min_length=2, max_length=40)
    model: str = Field(min_length=1, max_length=40)
    vtype: Literal["hatchback", "sedan", "suv", "muv", "other"] = "sedan"
    color: str = Field(default="", max_length=20)
    reg_no: str = Field(min_length=6, max_length=15)
    seats: int = Field(ge=1, le=8)
    ac: bool = True
    luggage: Literal["small", "medium", "large"] = "medium"


@api.post("/vehicles")
async def add_vehicle(body: VehicleIn, user: dict = Depends(get_user)):
    v = {**body.model_dump(), "reg_no": body.reg_no.upper().replace(" ", ""), "vehicle_id": nid("veh"),
         "owner_id": user["user_id"], "verified": user.get("driver_status") == "approved", "created_at": now()}
    await db.vehicles.insert_one(v)
    v.pop("_id", None)
    return v


@api.delete("/vehicles/{vid}")
async def delete_vehicle(vid: str, user: dict = Depends(get_user)):
    r = await db.vehicles.update_one({"vehicle_id": vid, "owner_id": user["user_id"]}, {"$set": {"deleted": True}})
    if not r.matched_count:
        raise HTTPException(404, "Vehicle not found")
    return {"ok": True}


# ---------------------------------------------------------------- trips
class TripIn(BaseModel):
    origin: LocIn
    destination: LocIn
    pickup_point: str = Field(min_length=2, max_length=150)
    drop_point: str = Field(min_length=2, max_length=150)
    stops: List[LocIn] = Field(default_factory=list, max_length=6)
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    time: str = Field(pattern=r"^\d{2}:\d{2}$")
    seats: int = Field(ge=1, le=8)
    price: int = Field(ge=50, le=20000)
    vehicle_id: str
    instant_booking: bool = True
    notes: str = Field(default="", max_length=500)


class TripUpdate(BaseModel):
    pickup_point: Optional[str] = Field(default=None, min_length=2, max_length=150)
    drop_point: Optional[str] = Field(default=None, min_length=2, max_length=150)
    price: Optional[int] = Field(default=None, ge=50, le=20000)
    seats: Optional[int] = Field(default=None, ge=1, le=8)
    instant_booking: Optional[bool] = None
    notes: Optional[str] = Field(default=None, max_length=500)


def trip_metrics(origin: dict, dest: dict, stops: list, date: str, time: str):
    pts = [origin, *stops, dest]
    straight = sum(haversine(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
    road_km = round(straight * 1.3)  # road-distance estimate when no routing provider is configured
    minutes = int(road_km / 55 * 60) + 10 * len(stops)
    dep = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M").replace(tzinfo=IST)
    arr = dep + timedelta(minutes=minutes)
    return road_km, minutes, dep, arr


async def build_trip(body: TripIn, driver: dict, vehicle: dict, is_demo=False) -> dict:
    o, d = loc_snapshot(body.origin), loc_snapshot(body.destination)
    stops = [loc_snapshot(s) for s in body.stops]
    km, mins, dep, arr = trip_metrics(o, d, stops, body.date, body.time)
    return {"trip_id": nid("trip"), "driver_id": driver["user_id"], "origin": o, "destination": d, "stops": stops,
            "pickup_point": body.pickup_point, "drop_point": body.drop_point, "date": body.date, "time": body.time,
            "departure_at": dep.astimezone(timezone.utc), "arrival_time": arr.strftime("%H:%M"),
            "arrival_date": arr.strftime("%Y-%m-%d"), "distance_km": km, "duration_min": mins,
            "seats_total": body.seats, "seats_available": body.seats, "price": body.price,
            "vehicle": {k: vehicle.get(k) for k in ("vehicle_id", "make", "model", "vtype", "color", "ac", "luggage", "verified")},
            "instant_booking": body.instant_booking, "notes": body.notes, "status": "scheduled",
            "is_demo": is_demo, "created_at": now()}


TRIP_OUT = {"_id": 0, "origin.geo": 0, "destination.geo": 0, "stops.geo": 0}


@api.post("/trips")
async def create_trip(body: TripIn, user: dict = Depends(get_user)):
    if user.get("driver_status") != "approved":
        raise HTTPException(403, "Only approved drivers can publish rides")
    vehicle = await db.vehicles.find_one({"vehicle_id": body.vehicle_id, "owner_id": user["user_id"], "deleted": {"$ne": True}}, {"_id": 0})
    if not vehicle:
        raise HTTPException(400, "Select one of your vehicles")
    if body.seats > vehicle["seats"]:
        raise HTTPException(400, f"This vehicle has only {vehicle['seats']} passenger seats")
    if body.origin.loc_id == body.destination.loc_id:
        raise HTTPException(400, "Origin and destination must be different")
    trip = await build_trip(body, user, vehicle)
    if trip["departure_at"] < now():
        raise HTTPException(400, "Departure must be in the future")
    await db.trips.insert_one(trip)
    await audit(user["user_id"], "trip.create", trip["trip_id"])
    return await db.trips.find_one({"trip_id": trip["trip_id"]}, TRIP_OUT)


@api.put("/trips/{tid}")
async def update_trip(tid: str, body: TripUpdate, user: dict = Depends(get_user)):
    trip = await db.trips.find_one({"trip_id": tid, "driver_id": user["user_id"]}, {"_id": 0})
    if not trip or trip["status"] != "scheduled":
        raise HTTPException(404, "Editable trip not found")
    upd = {k: v for k, v in body.model_dump().items() if v is not None and k != "seats"}
    if body.seats is not None:
        booked = trip["seats_total"] - trip["seats_available"]
        if body.seats < booked:
            raise HTTPException(400, f"{booked} seats are already booked")
        upd["seats_total"] = body.seats
        upd["seats_available"] = body.seats - booked
    if "price" in upd and await db.bookings.count_documents({"trip_id": tid, "status": {"$in": ["pending", "confirmed"]}}):
        raise HTTPException(400, "Price cannot change after bookings are made")
    await db.trips.update_one({"trip_id": tid}, {"$set": upd})
    return await db.trips.find_one({"trip_id": tid}, TRIP_OUT)


async def enrich_trips(trips: list) -> list:
    ids = list({t["driver_id"] for t in trips})
    drivers = {u["user_id"]: u for u in await db.users.find({"user_id": {"$in": ids}}, PUBLIC_FIELDS).to_list(len(ids) or 1)}
    for t in trips:
        t["driver"] = drivers.get(t["driver_id"], {"name": "Driver"})
    return trips


@api.get("/trips/search")
async def search_trips(from_lat: float, from_lng: float, to_lat: float, to_lng: float,
                       date: Optional[str] = None, seats: int = Query(1, ge=1, le=8),
                       sort: Literal["early", "price", "rating"] = "early", ac: bool = False,
                       max_price: Optional[int] = None, vtype: Optional[str] = None, radius_km: int = Query(35, le=100)):
    base = {"status": "scheduled", "seats_available": {"$gte": seats}, "departure_at": {"$gt": now()},
            "origin.geo": {"$geoWithin": {"$centerSphere": [[from_lng, from_lat], radius_km / 6378.1]}}}
    if ac:
        base["vehicle.ac"] = True
    if max_price:
        base["price"] = {"$lte": max_price}
    if vtype:
        base["vehicle.vtype"] = vtype
    to = {"lat": to_lat, "lng": to_lng}

    def dest_ok(t):
        return haversine(t["destination"], to) <= radius_km or any(haversine(s, to) <= radius_km for s in t.get("stops", []))

    q = {**base, **({"date": date} if date else {})}
    rows = [t for t in await db.trips.find(q, TRIP_OUT).limit(300).to_list(300) if dest_ok(t)]
    rows = await enrich_trips(rows)
    if sort == "price":
        rows.sort(key=lambda t: (t["price"], t["departure_at"]))
    elif sort == "rating":
        rows.sort(key=lambda t: (-(t["driver"].get("rating_avg") or 0), t["departure_at"]))
    else:
        rows.sort(key=lambda t: t["departure_at"])
    alt = []
    if not rows and date:
        others = [t for t in await db.trips.find(base, {"date": 1, "destination": 1, "stops": 1, "_id": 0}).limit(300).to_list(300) if dest_ok(t)]
        counts: dict = {}
        for t in others:
            counts[t["date"]] = counts.get(t["date"], 0) + 1
        alt = [{"date": k, "count": v} for k, v in sorted(counts.items())[:7]]
    return {"trips": rows, "alternative_dates": alt}


@api.get("/trips/mine")
async def my_trips(user: dict = Depends(get_user)):
    trips = await db.trips.find({"driver_id": user["user_id"]}, TRIP_OUT).sort("departure_at", -1).to_list(200)
    for t in trips:
        t["pending_count"] = await db.bookings.count_documents({"trip_id": t["trip_id"], "status": "pending"})
    return trips


@api.get("/trips/{tid}")
async def get_trip(tid: str, user: dict = Depends(get_user)):
    trip = await db.trips.find_one({"trip_id": tid}, TRIP_OUT)
    if not trip:
        raise HTTPException(404, "Trip not found")
    trip["driver"] = await public_user(trip["driver_id"])
    trip["is_driver"] = trip["driver_id"] == user["user_id"]
    if trip["is_driver"] or user.get("role") == "admin":
        bookings = await db.bookings.find({"trip_id": tid}, {"_id": 0}).sort("created_at", 1).to_list(100)
        for b in bookings:
            p = await db.users.find_one({"user_id": b["passenger_id"]}, {"_id": 0, "name": 1, "phone": 1, "picture": 1, "rating_avg": 1})
            if b["status"] not in ("confirmed", "started", "completed"):
                p.pop("phone", None)
            b["passenger"] = p
        trip["bookings"] = bookings
    else:
        trip["my_booking"] = await db.bookings.find_one({"trip_id": tid, "passenger_id": user["user_id"],
                                                         "status": {"$in": ["pending", "confirmed", "started", "completed"]}}, {"_id": 0})
    return trip


class ReasonIn(BaseModel):
    reason: str = Field(default="", max_length=300)
    refund_note: str = Field(default="", max_length=300)


async def driver_trip(tid: str, user: dict) -> dict:
    trip = await db.trips.find_one({"trip_id": tid}, {"_id": 0})
    if not trip or (trip["driver_id"] != user["user_id"] and user.get("role") != "admin"):
        raise HTTPException(404, "Trip not found")
    return trip


async def cancel_booking_record(b: dict, by: str, reason: str, refund_note: str = ""):
    was_confirmed = b["status"] in ("confirmed", "started")
    res = await db.bookings.update_one({"booking_id": b["booking_id"], "status": b["status"]},
                                       {"$set": {"status": "cancelled", "cancelled_by": by, "cancel_reason": reason,
                                                 "refund_note": refund_note, "was_confirmed": was_confirmed, "cancelled_at": now()},
                                        "$unset": {"active_key": ""}})
    if not res.modified_count:
        return False
    await db.cancellations.insert_one({"booking_id": b["booking_id"], "trip_id": b["trip_id"], "by": by, "reason": reason,
                                       "refund_note": refund_note, "was_confirmed": was_confirmed, "created_at": now()})
    if was_confirmed:
        await db.trips.update_one({"trip_id": b["trip_id"]}, {"$inc": {"seats_available": b["seats"]}})
        await ledger(b["driver_id"], b, "expected_reversed", -b["fare_total"])
    return True


@api.post("/trips/{tid}/cancel")
async def cancel_trip(tid: str, body: ReasonIn, user: dict = Depends(get_user)):
    trip = await driver_trip(tid, user)
    if trip["status"] != "scheduled":
        raise HTTPException(400, "Only scheduled trips can be cancelled")
    await db.trips.update_one({"trip_id": tid}, {"$set": {"status": "cancelled", "cancel_reason": body.reason, "cancelled_at": now()}})
    async for b in db.bookings.find({"trip_id": tid, "status": {"$in": ["pending", "confirmed"]}}, {"_id": 0}):
        await cancel_booking_record(b, "driver", body.reason or "Trip cancelled by driver")
        await notify(b["passenger_id"], "trip_cancelled", {"route": route_label(trip)}, b["booking_id"])
    await audit(user["user_id"], "trip.cancel", tid, {"reason": body.reason})
    return {"ok": True}


@api.post("/trips/{tid}/start")
async def start_trip(tid: str, user: dict = Depends(get_user)):
    trip = await driver_trip(tid, user)
    if trip["status"] != "scheduled":
        raise HTTPException(400, "Trip cannot be started")
    await db.trips.update_one({"trip_id": tid}, {"$set": {"status": "started", "started_at": now()}})
    async for b in db.bookings.find({"trip_id": tid, "status": "confirmed"}, {"_id": 0}):
        await db.bookings.update_one({"booking_id": b["booking_id"]}, {"$set": {"status": "started"}})
        await notify(b["passenger_id"], "trip_started", {"route": route_label(trip)}, b["booking_id"])
    await db.bookings.update_many({"trip_id": tid, "status": "pending"}, {"$set": {"status": "rejected", "reject_reason": "Trip started"}})
    return {"ok": True}


@api.post("/trips/{tid}/complete")
async def complete_trip(tid: str, user: dict = Depends(get_user)):
    trip = await driver_trip(tid, user)
    if trip["status"] not in ("scheduled", "started"):
        raise HTTPException(400, "Trip cannot be completed")
    await db.trips.update_one({"trip_id": tid}, {"$set": {"status": "completed", "completed_at": now()}})
    async for b in db.bookings.find({"trip_id": tid, "status": {"$in": ["confirmed", "started"]}}, {"_id": 0}):
        await db.bookings.update_one({"booking_id": b["booking_id"]}, {"$set": {"status": "completed", "completed_at": now()}})
        await ledger(b["driver_id"], b, "finalized", b["fare_total"])
        await notify(b["passenger_id"], "trip_completed", {"route": route_label(trip)}, b["booking_id"])
    await db.bookings.update_many({"trip_id": tid, "status": "pending"}, {"$set": {"status": "rejected", "reject_reason": "Trip completed"}})
    return {"ok": True}


# ---------------------------------------------------------------- bookings
class BookingIn(BaseModel):
    trip_id: str
    seats: int = Field(ge=1, le=8)
    passenger_names: List[str] = Field(default_factory=list, max_length=8)
    payment_method: Literal["cash", "upi"] = "cash"


async def reserve_seats(trip_id: str, seats: int) -> Optional[dict]:
    """Atomic seat decrement: only succeeds when enough seats remain (prevents overbooking)."""
    return await db.trips.find_one_and_update({"trip_id": trip_id, "status": "scheduled", "seats_available": {"$gte": seats}},
                                              {"$inc": {"seats_available": -seats}}, return_document=ReturnDocument.AFTER)


@api.post("/bookings")
async def create_booking(body: BookingIn, user: dict = Depends(get_user)):
    trip = await db.trips.find_one({"trip_id": body.trip_id}, {"_id": 0})
    if not trip or trip["status"] != "scheduled" or trip["departure_at"].replace(tzinfo=timezone.utc) < now():
        raise HTTPException(400, "This ride is not available for booking")
    if trip["driver_id"] == user["user_id"]:
        raise HTTPException(400, "You cannot book your own ride")
    if await db.bookings.find_one({"trip_id": body.trip_id, "passenger_id": user["user_id"], "status": {"$in": ["pending", "confirmed"]}}):
        raise HTTPException(409, "You already have a booking on this ride")
    if trip["seats_available"] < body.seats:
        raise HTTPException(409, "Not enough seats available")
    names = [n.strip()[:60] for n in body.passenger_names if n.strip()] or [user["name"]]
    status = "pending"
    if trip["instant_booking"]:
        if not await reserve_seats(trip["trip_id"], body.seats):
            raise HTTPException(409, "Not enough seats available")
        status = "confirmed"
    b = {"booking_id": "TRV-" + secrets.token_hex(4).upper(), "trip_id": trip["trip_id"], "driver_id": trip["driver_id"],
         "passenger_id": user["user_id"], "seats": body.seats, "passenger_names": names, "price": trip["price"],
         "fare_total": trip["price"] * body.seats, "payment_method": body.payment_method, "status": status,
         "route": route_label(trip), "date": trip["date"], "time": trip["time"],
         "active_key": f"{trip['trip_id']}:{user['user_id']}",
         "settlement": {"status": "unpaid"}, "created_at": now()}
    try:
        await db.bookings.insert_one(b)
    except DuplicateKeyError:
        if status == "confirmed":
            await db.trips.update_one({"trip_id": trip["trip_id"]}, {"$inc": {"seats_available": body.seats}})
        raise HTTPException(409, "You already have a booking on this ride")
    if status == "confirmed":
        await ledger(trip["driver_id"], b, "expected", b["fare_total"])
        await notify(trip["driver_id"], "new_booking", {"route": b["route"]}, b["booking_id"])
        await notify(user["user_id"], "booking_confirmed", {"route": b["route"]}, b["booking_id"])
    else:
        await notify(trip["driver_id"], "booking_request", {"route": b["route"]}, b["booking_id"])
    b.pop("_id", None)
    return b


@api.get("/bookings/mine")
async def my_bookings(user: dict = Depends(get_user)):
    rows = await db.bookings.find({"passenger_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(200)
    tids = list({r["trip_id"] for r in rows})
    trips = {t["trip_id"]: t for t in await db.trips.find({"trip_id": {"$in": tids}}, TRIP_OUT).to_list(len(tids) or 1)}
    for r in rows:
        r["trip"] = trips.get(r["trip_id"])
    return rows


async def booking_for(bid: str, user: dict) -> dict:
    b = await db.bookings.find_one({"booking_id": bid}, {"_id": 0})
    if not b or (user["user_id"] not in (b["passenger_id"], b["driver_id"]) and user.get("role") != "admin"):
        raise HTTPException(404, "Booking not found")
    return b


@api.get("/bookings/{bid}")
async def get_booking(bid: str, user: dict = Depends(get_user)):
    b = await booking_for(bid, user)
    b["trip"] = await db.trips.find_one({"trip_id": b["trip_id"]}, TRIP_OUT)
    active = b["status"] in ("confirmed", "started", "completed")
    d = await db.users.find_one({"user_id": b["driver_id"]}, {"_id": 0, "user_id": 1, "name": 1, "picture": 1, "rating_avg": 1,
                                                              "rating_count": 1, "driver_status": 1, "phone": 1, "upi_id": 1})
    if not active:
        d.pop("phone", None)
    b["driver"] = d
    p = await db.users.find_one({"user_id": b["passenger_id"]}, {"_id": 0, "user_id": 1, "name": 1, "picture": 1, "rating_avg": 1, "phone": 1})
    if not active:
        p.pop("phone", None)
    b["passenger"] = p
    b["is_driver"] = user["user_id"] == b["driver_id"]
    b["my_reviews"] = await db.reviews.find({"booking_id": bid, "reviewer_id": user["user_id"]}, {"_id": 0}).to_list(5)
    return b


@api.post("/bookings/{bid}/accept")
async def accept_booking(bid: str, user: dict = Depends(get_user)):
    b = await booking_for(bid, user)
    if b["driver_id"] != user["user_id"] or b["status"] != "pending":
        raise HTTPException(400, "Only pending requests can be accepted")
    if not await reserve_seats(b["trip_id"], b["seats"]):
        raise HTTPException(409, "Not enough seats left on this ride")
    res = await db.bookings.update_one({"booking_id": bid, "status": "pending"}, {"$set": {"status": "confirmed", "confirmed_at": now()}})
    if not res.modified_count:  # raced with a cancel: give the seats back
        await db.trips.update_one({"trip_id": b["trip_id"]}, {"$inc": {"seats_available": b["seats"]}})
        raise HTTPException(409, "Booking changed, please refresh")
    await ledger(b["driver_id"], b, "expected", b["fare_total"])
    await notify(b["passenger_id"], "booking_confirmed", {"route": b["route"]}, bid)
    return {"ok": True}


@api.post("/bookings/{bid}/reject")
async def reject_booking(bid: str, body: ReasonIn, user: dict = Depends(get_user)):
    b = await booking_for(bid, user)
    if b["driver_id"] != user["user_id"]:
        raise HTTPException(403, "Only the driver can reject")
    res = await db.bookings.update_one({"booking_id": bid, "status": "pending"}, {"$set": {"status": "rejected", "reject_reason": body.reason}, "$unset": {"active_key": ""}})
    if not res.modified_count:
        raise HTTPException(400, "Only pending requests can be rejected")
    await notify(b["passenger_id"], "booking_rejected", {"route": b["route"]}, bid)
    return {"ok": True}


@api.post("/bookings/{bid}/cancel")
async def cancel_booking(bid: str, body: ReasonIn, user: dict = Depends(get_user)):
    b = await booking_for(bid, user)
    if b["status"] not in ("pending", "confirmed"):
        raise HTTPException(400, "This booking cannot be cancelled")
    by = "driver" if user["user_id"] == b["driver_id"] else "passenger"
    if not await cancel_booking_record(b, by, body.reason, body.refund_note):
        raise HTTPException(409, "Booking changed, please refresh")
    other = b["passenger_id"] if by == "driver" else b["driver_id"]
    await notify(other, "booking_cancelled", {"route": b["route"]}, bid)
    return {"ok": True}


class SettleIn(BaseModel):
    method: Literal["cash", "upi"]
    note: str = Field(default="", max_length=200)


@api.post("/bookings/{bid}/settle")
async def settle_booking(bid: str, body: SettleIn, user: dict = Depends(get_user)):
    """Driver declares the fare was received directly (cash/UPI). Travoo does not verify payments."""
    b = await booking_for(bid, user)
    if b["driver_id"] != user["user_id"]:
        raise HTTPException(403, "Only the driver can record settlement")
    if b["status"] not in ("confirmed", "started", "completed"):
        raise HTTPException(400, "Booking is not active")
    if b.get("settlement", {}).get("status") == "received":
        raise HTTPException(409, "Already marked as received")
    rec = {"status": "received", "method": body.method, "note": body.note, "declared_by": user["user_id"], "declared_at": now()}
    res = await db.bookings.update_one({"booking_id": bid, "settlement.status": {"$ne": "received"}}, {"$set": {"settlement": rec}})
    if not res.modified_count:
        raise HTTPException(409, "Already marked as received")
    await db.settlements.insert_one({"booking_id": bid, "driver_id": b["driver_id"], "amount": b["fare_total"], **rec})
    await ledger(b["driver_id"], b, f"settled_{body.method}", b["fare_total"], body.method)
    return {"ok": True}


# ---------------------------------------------------------------- earnings
@api.get("/earnings")
async def earnings(user: dict = Depends(get_user)):
    uid = user["user_id"]
    rows = await db.bookings.find({"driver_id": uid}, {"_id": 0}).to_list(2000)
    sums = {"completed": 0, "expected": 0, "confirmed_value": 0, "cancelled": 0, "cash": 0, "upi": 0, "seats": 0}
    by_trip: dict = {}
    for b in rows:
        st, fare = b["status"], b["fare_total"]
        if st in ("confirmed", "started"):
            sums["expected"] += fare
        if st in ("confirmed", "started", "completed"):
            sums["confirmed_value"] += fare
            sums["seats"] += b["seats"]
            t = by_trip.setdefault(b["trip_id"], {"trip_id": b["trip_id"], "route": b["route"], "date": b["date"], "seats": 0,
                                                   "expected": 0, "completed": 0, "price": b["price"]})
            t["seats"] += b["seats"]
            t["expected" if st != "completed" else "completed"] += fare
        if st == "completed":
            sums["completed"] += fare
        if st == "cancelled" and b.get("was_confirmed"):
            sums["cancelled"] += fare
        s = b.get("settlement", {})
        if s.get("status") == "received" and st != "cancelled":
            sums[s["method"]] += fare
    sums["completed_trips"] = await db.trips.count_documents({"driver_id": uid, "status": "completed"})
    history = await db.earnings_ledger.find({"driver_id": uid}, {"_id": 0}).sort("created_at", -1).to_list(100)
    settlements = await db.settlements.find({"driver_id": uid}, {"_id": 0}).sort("declared_at", -1).to_list(100)
    return {"summary": sums, "by_trip": sorted(by_trip.values(), key=lambda x: x["date"], reverse=True),
            "history": history, "settlements": settlements}


# ---------------------------------------------------------------- reviews
class ReviewIn(BaseModel):
    booking_id: str
    target_id: str
    rating: int = Field(ge=1, le=5)
    comment: str = Field(default="", max_length=500)


@api.post("/reviews")
async def add_review(body: ReviewIn, user: dict = Depends(get_user)):
    b = await booking_for(body.booking_id, user)
    if b["status"] != "completed":
        raise HTTPException(400, "You can review after the trip is completed")
    parties = {b["passenger_id"], b["driver_id"]}
    if body.target_id not in parties or body.target_id == user["user_id"]:
        raise HTTPException(400, "Invalid review target")
    doc = {"review_id": nid("rev"), **body.model_dump(), "reviewer_id": user["user_id"], "reviewer_name": user["name"],
           "role": "driver" if body.target_id == b["driver_id"] else "passenger", "route": b["route"], "created_at": now()}
    try:
        await db.reviews.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(409, "Already reviewed")
    await recompute_rating(body.target_id)
    return {"ok": True}


async def recompute_rating(uid: str):
    agg = await db.reviews.aggregate([{"$match": {"target_id": uid, "hidden": {"$ne": True}}},
                                      {"$group": {"_id": None, "avg": {"$avg": "$rating"}, "n": {"$sum": 1}}}]).to_list(1)
    avg, n = (round(agg[0]["avg"], 1), agg[0]["n"]) if agg else (0, 0)
    await db.users.update_one({"user_id": uid}, {"$set": {"rating_avg": avg, "rating_count": n}})


# ---------------------------------------------------------------- messages
class MessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


@api.get("/bookings/{bid}/messages")
async def get_messages(bid: str, user: dict = Depends(get_user)):
    await booking_for(bid, user)
    return await db.messages.find({"booking_id": bid}, {"_id": 0}).sort("created_at", 1).to_list(500)


@api.post("/bookings/{bid}/messages")
async def post_message(bid: str, body: MessageIn, user: dict = Depends(get_user)):
    b = await booking_for(bid, user)
    if b["status"] not in ("confirmed", "started", "completed"):
        raise HTTPException(400, "Chat opens after the booking is confirmed")
    msg = {"message_id": nid("msg"), "booking_id": bid, "sender_id": user["user_id"], "sender_name": user["name"],
           "text": body.text.strip(), "created_at": now()}
    await db.messages.insert_one(msg)
    other = b["passenger_id"] if user["user_id"] == b["driver_id"] else b["driver_id"]
    await notify(other, "new_message", {"route": b["route"]}, bid)
    msg.pop("_id", None)
    return msg


# ---------------------------------------------------------------- notifications
@api.get("/notifications")
async def notifications(user: dict = Depends(get_user)):
    rows = await db.notifications.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return {"items": rows, "unread": sum(1 for r in rows if not r["read"])}


@api.post("/notifications/read")
async def read_notifications(user: dict = Depends(get_user)):
    await db.notifications.update_many({"user_id": user["user_id"], "read": False}, {"$set": {"read": True}})
    return {"ok": True}


# ---------------------------------------------------------------- support / reports / SOS
class TicketIn(BaseModel):
    type: Literal["complaint", "report_user", "question", "sos"]
    subject: str = Field(min_length=3, max_length=120)
    message: str = Field(min_length=5, max_length=2000)
    booking_id: Optional[str] = None
    reported_user_id: Optional[str] = None


@api.post("/tickets")
async def create_ticket(body: TicketIn, user: dict = Depends(get_user)):
    t = {"ticket_id": "TKT-" + secrets.token_hex(3).upper(), **body.model_dump(), "user_id": user["user_id"],
         "user_name": user["name"], "status": "open", "priority": "high" if body.type == "sos" else "normal", "created_at": now()}
    await db.tickets.insert_one(t)
    t.pop("_id", None)
    return t


@api.get("/tickets/mine")
async def my_tickets(user: dict = Depends(get_user)):
    return await db.tickets.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(100)


# ---------------------------------------------------------------- admin
@api.get("/admin/stats")
async def admin_stats(_: dict = Depends(get_admin)):
    c = db.bookings.count_documents
    value = await db.bookings.aggregate([{"$match": {"status": {"$in": ["confirmed", "started", "completed"]}}},
                                         {"$group": {"_id": None, "v": {"$sum": "$fare_total"}}}]).to_list(1)
    earned = await db.bookings.aggregate([{"$match": {"status": "completed"}}, {"$group": {"_id": None, "v": {"$sum": "$fare_total"}}}]).to_list(1)
    monthly = await db.bookings.aggregate([{"$group": {"_id": {"$dateToString": {"format": "%Y-%m", "date": "$created_at"}},
                                                       "bookings": {"$sum": 1},
                                                       "completed": {"$sum": {"$cond": [{"$eq": ["$status", "completed"]}, 1, 0]}}}},
                                           {"$sort": {"_id": -1}}, {"$limit": 6}]).to_list(6)
    growth = await db.users.aggregate([{"$group": {"_id": {"$dateToString": {"format": "%Y-%m", "date": "$created_at"}}, "users": {"$sum": 1}}},
                                       {"$sort": {"_id": -1}}, {"$limit": 6}]).to_list(6)
    top = await db.bookings.aggregate([{"$match": {"status": "completed"}}, {"$group": {"_id": "$driver_id", "v": {"$sum": "$fare_total"}, "trips": {"$addToSet": "$trip_id"}}},
                                       {"$sort": {"v": -1}}, {"$limit": 5}]).to_list(5)
    for t in top:
        t["name"] = (await public_user(t["_id"])).get("name")
        t["trips"] = len(t["trips"])
    routes = await db.bookings.aggregate([{"$group": {"_id": "$route", "n": {"$sum": 1}}}, {"$sort": {"n": -1}}, {"$limit": 5}]).to_list(5)
    drivers = await db.users.count_documents({"driver_status": {"$ne": "not_submitted"}})
    users = await db.users.count_documents({"role": "user"})
    return {"users": users, "passengers": len(await db.bookings.distinct("passenger_id")), "drivers": drivers,
            "verified": await db.users.count_documents({"driver_status": "approved"}),
            "pending": await db.users.count_documents({"driver_status": "under_review"}),
            "trips": await db.trips.count_documents({}), "active": await db.trips.count_documents({"status": {"$in": ["scheduled", "started"]}}),
            "bookings": await c({}), "completed": await c({"status": "completed"}), "cancelled": await c({"status": "cancelled"}),
            "value": value[0]["v"] if value else 0, "earnings": earned[0]["v"] if earned else 0,
            "monthly": monthly, "growth": growth, "top_drivers": top, "top_routes": routes}


@api.get("/admin/users")
async def admin_users(q: str = "", _: dict = Depends(get_admin)):
    filt = {"$or": [{"name": {"$regex": re.escape(q), "$options": "i"}}, {"email": {"$regex": re.escape(q), "$options": "i"}}]} if q else {}
    return await db.users.find(filt, USER_PRIVATE).sort("created_at", -1).to_list(200)


class SuspendIn(BaseModel):
    suspended: bool


@api.post("/admin/users/{uid}/suspend")
async def admin_suspend(uid: str, body: SuspendIn, admin: dict = Depends(get_admin)):
    if uid == admin["user_id"]:
        raise HTTPException(400, "You cannot suspend yourself")
    await db.users.update_one({"user_id": uid}, {"$set": {"suspended": body.suspended}})
    await db.user_sessions.delete_many({"user_id": uid}) if body.suspended else None
    await audit(admin["user_id"], "user.suspend" if body.suspended else "user.unsuspend", uid)
    return {"ok": True}


@api.get("/admin/drivers")
async def admin_drivers(status: str = "under_review", _: dict = Depends(get_admin)):
    users = await db.users.find({"driver_status": status}, USER_PRIVATE).to_list(200)
    for u in users:
        u["documents"] = await db.driver_documents.find_one({"user_id": u["user_id"]}, {"_id": 0})
        u["vehicles"] = await db.vehicles.find({"owner_id": u["user_id"], "deleted": {"$ne": True}}, {"_id": 0}).to_list(10)
    return users


class DriverReviewIn(BaseModel):
    decision: Literal["approved", "rejected", "resubmit"]
    note: str = Field(default="", max_length=300)


@api.post("/admin/drivers/{uid}/review")
async def admin_review_driver(uid: str, body: DriverReviewIn, admin: dict = Depends(get_admin)):
    if not await db.driver_documents.find_one({"user_id": uid}):
        raise HTTPException(400, "This user has not submitted verification details")
    r = await db.users.update_one({"user_id": uid}, {"$set": {"driver_status": body.decision}})
    if not r.matched_count:
        raise HTTPException(404, "User not found")
    await db.driver_documents.update_one({"user_id": uid}, {"$set": {"admin_note": body.note, "reviewed_at": now(), "reviewed_by": admin["user_id"]}})
    if body.decision == "approved":
        await db.vehicles.update_many({"owner_id": uid}, {"$set": {"verified": True}})
    await notify(uid, "driver_approved" if body.decision == "approved" else "driver_rejected", {})
    await audit(admin["user_id"], f"driver.{body.decision}", uid, {"note": body.note})
    return {"ok": True}


@api.get("/admin/trips")
async def admin_trips(status: Optional[str] = None, _: dict = Depends(get_admin)):
    rows = await db.trips.find({"status": status} if status else {}, TRIP_OUT).sort("departure_at", -1).to_list(200)
    return await enrich_trips(rows)


@api.get("/admin/bookings")
async def admin_bookings(status: Optional[str] = None, _: dict = Depends(get_admin)):
    return await db.bookings.find({"status": status} if status else {}, {"_id": 0}).sort("created_at", -1).to_list(200)


@api.get("/admin/vehicles")
async def admin_vehicles(_: dict = Depends(get_admin)):
    return await db.vehicles.find({"deleted": {"$ne": True}}, {"_id": 0}).sort("created_at", -1).to_list(200)


@api.get("/admin/tickets")
async def admin_tickets(_: dict = Depends(get_admin)):
    return await db.tickets.find({}, {"_id": 0}).sort([("status", -1), ("created_at", -1)]).to_list(200)


@api.post("/admin/tickets/{tid}/resolve")
async def admin_resolve(tid: str, admin: dict = Depends(get_admin)):
    await db.tickets.update_one({"ticket_id": tid}, {"$set": {"status": "resolved", "resolved_at": now()}})
    await audit(admin["user_id"], "ticket.resolve", tid)
    return {"ok": True}


@api.get("/admin/reviews")
async def admin_reviews(_: dict = Depends(get_admin)):
    return await db.reviews.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)


@api.delete("/admin/reviews/{rid}")
async def admin_hide_review(rid: str, admin: dict = Depends(get_admin)):
    r = await db.reviews.find_one_and_update({"review_id": rid}, {"$set": {"hidden": True}})
    if r:
        await recompute_rating(r["target_id"])
    await audit(admin["user_id"], "review.hide", rid)
    return {"ok": True}


class RouteIn(BaseModel):
    origin: LocIn
    destination: LocIn
    price_hint: int = Field(ge=50, le=20000)


@api.post("/admin/routes")
async def admin_add_route(body: RouteIn, admin: dict = Depends(get_admin)):
    n = await db.popular_routes.count_documents({})
    doc = {"route_id": nid("rt"), "origin": body.origin.model_dump(), "destination": body.destination.model_dump(),
           "price_hint": body.price_hint, "active": True, "order": n}
    await db.popular_routes.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api.delete("/admin/routes/{rid}")
async def admin_del_route(rid: str, admin: dict = Depends(get_admin)):
    await db.popular_routes.delete_one({"route_id": rid})
    await audit(admin["user_id"], "route.delete", rid)
    return {"ok": True}


class SettingsIn(BaseModel):
    instant_driver_approval: Optional[bool] = None
    passenger_cancel_hours: Optional[int] = Field(default=None, ge=0, le=72)
    driver_cancel_hours: Optional[int] = Field(default=None, ge=0, le=72)


@api.get("/admin/settings")
async def admin_get_settings(_: dict = Depends(get_admin)):
    return await get_settings()


@api.put("/admin/settings")
async def admin_put_settings(body: SettingsIn, admin: dict = Depends(get_admin)):
    upd = {k: v for k, v in body.model_dump().items() if v is not None}
    await db.settings.update_one({"key": "platform"}, {"$set": upd}, upsert=True)
    await audit(admin["user_id"], "settings.update", "platform", upd)
    return await get_settings()


# ---------------------------------------------------------------- seeding
async def seed():
    if not await db.locations.find_one({"type": "state"}):
        docs = [loc_doc(n, t, None, n, None, 0, 0, a) for n, t, a in STATES]
        caps = {p[3]: p for p in PLACES}
        for d in docs:  # state centroid approximated by a city in that state
            c = caps.get(d["name"])
            if c:
                d.update(lat=c[5], lng=c[6], geo={"type": "Point", "coordinates": [c[6], c[5]]})
        await db.locations.insert_many(docs)
    for p in PLACES:
        d = loc_doc(*p)
        await db.locations.update_one({"loc_id": d["loc_id"]}, {"$setOnInsert": d}, upsert=True)
    await db.settings.update_one({"key": "platform"}, {"$setOnInsert": {
        "instant_driver_approval": False, "passenger_cancel_hours": 6, "driver_cancel_hours": 12,
        "cancellation_reasons": ["Change of plans", "Found another ride", "Driver/passenger unreachable", "Safety concern", "Other"]}}, upsert=True)
    by_name = {p[0]: loc_doc(*p) for p in PLACES}

    def snap(name):
        d = by_name[name]
        return {k: d[k] for k in ("loc_id", "name", "type", "district", "state", "pin", "lat", "lng")}
    if not await db.popular_routes.find_one({}):
        await db.popular_routes.insert_many([{"route_id": nid("rt"), "origin": snap(o), "destination": snap(d), "price_hint": p, "active": True, "order": i}
                                             for i, (o, d, p) in enumerate(POPULAR_ROUTES)])
    admin_email = os.environ["ADMIN_EMAIL"].lower()
    if not await db.users.find_one({"email": admin_email}):
        doc = new_user_doc(admin_email, "Travoo Admin", role="admin")
        doc["password_hash"] = hash_pw(os.environ["ADMIN_PASSWORD"])
        await db.users.insert_one(doc)
    if not await db.users.find_one({"email": "driver@travoo.in"}):
        drv = new_user_doc("driver@travoo.in", "Arjun Rao (Demo)", phone="9876543210", driver_status="approved", is_demo=True)
        drv.update(password_hash=hash_pw("Driver@2026"), upi_id="arjun.demo@upi", rating_avg=4.8, rating_count=0)
        await db.users.insert_one(drv)
        await db.driver_documents.insert_one({"user_id": drv["user_id"], "legal_name": "Arjun Rao", "phone": "9876543210",
                                              "licence_no": "KA0120200001234", "licence_expiry": "31-12-2035", "rc_no": "KA01AB1234",
                                              "submitted_at": now(), "admin_note": "Demo driver", "reviewed_at": now()})
        veh = {"vehicle_id": nid("veh"), "owner_id": drv["user_id"], "make": "Maruti Suzuki", "model": "Ertiga", "vtype": "muv",
               "color": "White", "reg_no": "KA01AB1234", "seats": 4, "ac": True, "luggage": "large", "verified": True, "created_at": now()}
        await db.vehicles.insert_one(veh)
        pas = new_user_doc("passenger@travoo.in", "Priya Sharma (Demo)", phone="9123456780", is_demo=True)
        pas["password_hash"] = hash_pw("Passenger@2026")
        await db.users.insert_one(pas)
        today = datetime.now(IST).date()
        demo = [("Bengaluru", "Chennai", 1, "07:00", 700, "Silk Board Junction", "Koyambedu Bus Terminus", ["Krishnagiri", "Vellore"]),
                ("Bengaluru", "Chennai", 2, "15:30", 650, "Majestic", "Guindy", []),
                ("Mumbai", "Pune", 1, "09:00", 450, "Dadar East", "Shivajinagar", ["Lonavala"]),
                ("New Delhi", "Jaipur", 3, "06:30", 650, "Dhaula Kuan", "Sindhi Camp", ["Gurugram"]),
                ("Hyderabad", "Vijayawada", 2, "08:00", 550, "LB Nagar", "Benz Circle", []),
                ("Chennai", "Puducherry", 4, "10:00", 400, "Tambaram", "White Town", ["Mahabalipuram"])]
        for o, d, plus, tm, price, pu, dr, stops in demo:
            body = TripIn(origin=LocIn(**snap(o)), destination=LocIn(**snap(d)), pickup_point=pu, drop_point=dr,
                          stops=[LocIn(**snap(s)) for s in stops], date=(today + timedelta(days=plus)).isoformat(), time=tm,
                          seats=3, price=price, vehicle_id=veh["vehicle_id"], instant_booking=plus % 2 == 1,
                          notes="DEMO RIDE — sample listing for testing.")
            await db.trips.insert_one(await build_trip(body, drv, veh, is_demo=True))


app.include_router(api)
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
async def startup():
    await ensure_indexes()
    await seed()


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
