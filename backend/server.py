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
import requests
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, FastAPI, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr, Field
from pymongo import ASCENDING, DESCENDING, GEOSPHERE, IndexModel, ReturnDocument
from pymongo.errors import DuplicateKeyError
from starlette.middleware.cors import CORSMiddleware

from html import escape as html_escape
import base64
import json as jsonlib

from email_service import send_email
from emergentintegrations.llm.chat import ImageContent, LlmChat, StreamDone, TextDelta, UserMessage
from geo import GEO_INDEXES, LOC_OUT, circle, get_router, haversine, loc_doc
from seed_data import PLACES, POPULAR_ROUTES, STATES

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]
JWT_SECRET = os.environ["JWT_SECRET"]
IST = timezone(timedelta(hours=5, minutes=30))
EMERGENT_SESSION_URL = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"

# Email configuration
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:19006")

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
    "licence_verifications": [IndexModel([("user_id", ASCENDING)], name="uid", unique=True),
                              IndexModel([("status", ASCENDING)], name="status")],
    "vehicles": [IndexModel([("vehicle_id", ASCENDING)], name="vid", unique=True),
                 IndexModel([("owner_id", ASCENDING)], name="owner")],
    "trips": [IndexModel([("trip_id", ASCENDING)], name="tid", unique=True),
              IndexModel([("origin.geo", GEOSPHERE)], name="origin_geo"),
              IndexModel([("route_line", GEOSPHERE)], name="route_line"),
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
    "files": [IndexModel([("file_id", ASCENDING)], name="fid", unique=True), IndexModel([("owner_id", ASCENDING)], name="owner")],
    "pro_drivers": [IndexModel([("user_id", ASCENDING)], name="uid", unique=True), IndexModel([("city.geo", GEOSPHERE)], name="city_geo"),
                    IndexModel([("status", ASCENDING)], name="status")],
    "hires": [IndexModel([("booking_id", ASCENDING)], name="bid", unique=True), IndexModel([("driver_id", ASCENDING), ("date", ASCENDING)], name="driver_date"),
              IndexModel([("passenger_id", ASCENDING)], name="customer")],
    "searches": [IndexModel([("user_id", ASCENDING), ("key", ASCENDING)], name="uniq", unique=True)],
    "missing_locations": [IndexModel([("request_id", ASCENDING)], name="rid", unique=True)],
    "contact_access": [IndexModel([("viewer_id", ASCENDING), ("owner_id", ASCENDING), ("booking_id", ASCENDING)], name="uniq", unique=True)],
    "fuel_prices": [IndexModel([("state", ASCENDING), ("fuel_type", ASCENDING)], name="uniq", unique=True)],
    "popular_routes": [IndexModel([("route_id", ASCENDING)], name="rid", unique=True)],
    "audit_logs": [IndexModel([("created_at", DESCENDING)], name="time")],
}
for _c, _m in GEO_INDEXES.items():
    INDEXES[_c] = INDEXES.get(_c, []) + _m


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
    if ref and ntype in SYS_EVENTS:
        await sys_message(ref, ntype, params)


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
    return await user_from_token(auth[7:])


async def user_from_token(token: str) -> dict:
    uid = None
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        if not payload.get("purpose"):
            uid = payload.get("sub")
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


class ForgotPasswordIn(BaseModel):
    email: EmailStr


@api.post("/auth/forgot-password")
async def forgot_password(body: ForgotPasswordIn):
    """Send password reset email"""
    user = await db.users.find_one({"email": body.email.lower()})
    generic = {"message": "If the email exists, a reset link will be sent"}
    if not user:
        # Don't reveal if email exists for security
        return generic
    # Throttle: at most one reset email per account per minute
    last = user.get("reset_requested_at")
    if last and (last.replace(tzinfo=timezone.utc) if last.tzinfo is None else last) > now() - timedelta(seconds=60):
        return generic
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"reset_requested_at": now()}})

    # Generate reset token
    reset_token = jwt.encode(
        {"sub": user["user_id"], "purpose": "reset", "ph": (user.get("password_hash") or "")[-12:],
         "exp": now() + timedelta(hours=1), "iat": now()},
        JWT_SECRET, algorithm="HS256")
    reset_link = f"{FRONTEND_URL}/reset-password?token={reset_token}"
    
    # Send email
    subject = "Reset your TRAVOO password"
    name = html_escape(user.get("name") or "there")
    link = html_escape(reset_link, quote=True)
    html = (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6fb;padding:24px 0">'
        '<tr><td align="center"><table role="presentation" width="480" cellpadding="0" cellspacing="0" '
        'style="background:#ffffff;border-radius:12px;padding:32px;font-family:Arial,sans-serif;color:#1a1f36">'
        '<tr><td style="font-size:22px;font-weight:bold;color:#1565d8;padding-bottom:16px">TRAVOO</td></tr>'
        f'<tr><td style="font-size:16px;padding-bottom:12px">Hi {name},</td></tr>'
        '<tr><td style="font-size:15px;line-height:22px;padding-bottom:24px">We received a request to reset your TRAVOO password. '
        'Tap the button below to choose a new one. This link expires in 1 hour and can be used once.</td></tr>'
        f'<tr><td style="padding-bottom:24px"><a href="{link}" style="background:#1565d8;color:#ffffff;text-decoration:none;'
        'padding:12px 24px;border-radius:8px;font-weight:bold;display:inline-block">Reset password</a></td></tr>'
        '<tr><td style="font-size:13px;color:#6b7280;line-height:20px">If you didn\'t ask for this, you can ignore this email — your password stays the same.</td></tr>'
        '<tr><td style="font-size:12px;color:#9ca3af;padding-top:24px">Sent by TRAVOO. We never ask for your password by email.</td></tr>'
        '</table></td></tr></table>'
    )
    async def _send(to: str):
        if await send_email(to=to, subject=subject, html=html):
            logger.info("Password reset email sent to %s", to)
        else:
            logger.warning("Password reset email could not be sent to %s", to)

    # Send in the background so response time doesn't reveal whether the account exists
    asyncio.create_task(_send(user["email"]))
    return generic


class ResetPasswordIn(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


@api.post("/auth/reset-password")
async def reset_password(body: ResetPasswordIn):
    """Reset password using the token"""
    try:
        payload = jwt.decode(body.token, JWT_SECRET, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        raise HTTPException(400, "Invalid or expired reset token")
    uid = payload.get("sub")
    user = await db.users.find_one({"user_id": uid}) if payload.get("purpose") == "reset" else None
    if not user or payload.get("ph") != (user.get("password_hash") or "")[-12:]:
        raise HTTPException(400, "Invalid or expired reset token")
    
    new_hash = hash_pw(body.new_password)
    await db.users.update_one({"user_id": uid}, {"$set": {"password_hash": new_hash}})
    await audit(uid, "password.reset", uid, {})
    
    return {"message": "Password reset successfully"}


class OCRDataIn(BaseModel):
    licence_front_text: str = Field(default="")
    licence_back_text: str = Field(default="")
    rc_text: str = Field(default="")
    confidence: float = Field(default=0.0)


@api.post("/driver/ocr-verification")
async def ocr_verification(body: OCRDataIn, user: dict = Depends(get_user)):
    """Process OCR data and validate extracted information"""
    if user.get("driver_status") in ("under_review", "approved"):
        raise HTTPException(400, "Verification already submitted")
    
    # Extract information from OCR text
    licence_info = extract_licence_info(body.licence_front_text + " " + body.licence_back_text)
    rc_info = extract_rc_info(body.rc_text)
    
    # Get user profile for name matching
    user_profile = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0, "name": 1})
    
    # Validation checks
    validation = {
        "licence_no_extracted": bool(licence_info["licence_no"]),
        "expiry_extracted": bool(licence_info["expiry"]),
        "name_extracted": bool(licence_info["name"]),
        "rc_no_extracted": bool(rc_info["rc_no"]),
        "vehicle_class_extracted": bool(licence_info["vehicle_class"]),
        "ocr_confidence": body.confidence,
        "extracted_licence_no": licence_info["licence_no"],
        "extracted_expiry": licence_info["expiry"],
        "extracted_name": licence_info["name"],
        "extracted_rc_no": rc_info["rc_no"],
        "extracted_vehicle_class": licence_info["vehicle_class"],
    }
    
    # Validate expiry date
    if licence_info["expiry"]:
        try:
            expiry_date = datetime.strptime(licence_info["expiry"], "%d-%m-%Y")
            validation["expiry_valid"] = expiry_date > now()
            validation["days_until_expiry"] = (expiry_date - now()).days
        except:
            validation["expiry_valid"] = False
            validation["days_until_expiry"] = None
    else:
        validation["expiry_valid"] = False
        validation["days_until_expiry"] = None
    
    # Validate name matching
    if licence_info["name"] and user_profile:
        # Simple similarity check (case-insensitive)
        extracted_name = licence_info["name"].lower().replace(" ", "")
        profile_name = user_profile["name"].lower().replace(" ", "")
        validation["name_match_score"] = 0
        if extracted_name in profile_name or profile_name in extracted_name:
            validation["name_match_score"] = 100
        elif any(word in profile_name for word in extracted_name.split()):
            validation["name_match_score"] = 50
        validation["name_matched"] = validation["name_match_score"] >= 50
    else:
        validation["name_matched"] = False
        validation["name_match_score"] = 0
    
    # Validate RC matches vehicle class
    if licence_info["vehicle_class"] and rc_info["vehicle_class"]:
        validation["vehicle_class_match"] = licence_info["vehicle_class"] == rc_info["vehicle_class"]
    else:
        validation["vehicle_class_match"] = False
    
    # Overall validation score
    validation["overall_score"] = (
        (validation["licence_no_extracted"] * 20) +
        (validation["expiry_extracted"] * 20) +
        (validation["name_extracted"] * 20) +
        (validation["rc_no_extracted"] * 20) +
        (validation["vehicle_class_extracted"] * 20)
    )
    
    # Store OCR results for admin review
    await db.driver_documents.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"ocr_data": validation, "verification_method": "ai", "ocr_confidence": body.confidence}},
        upsert=True
    )
    
    return {"validation": validation, "message": "OCR data processed successfully"}


def extract_licence_info(text: str) -> dict:
    """Extract licence information from OCR text"""
    text_upper = text.upper()
    
    # Extract licence number (Indian format: KA0120200001234)
    licence_no = None
    licence_match = re.search(r'[A-Z]{2}\d{2}\d{4}\d{7}', text_upper)
    if licence_match:
        licence_no = licence_match.group(0)
    
    # Extract expiry date (DD-MM-YYYY or DD/MM/YYYY format)
    expiry = None
    expiry_match = re.search(r'\d{2}[-/]\d{2}[-/]\d{4}', text_upper)
    if expiry_match:
        expiry = expiry_match.group(0).replace('/', '-')
    
    # Extract name (first line before licence number)
    name = None
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    if lines:
        # Try to find name (usually first line, remove numbers and special chars)
        first_line = re.sub(r'[^A-Z\s]', '', lines[0]).strip()
        if len(first_line) > 2:
            name = first_line
    
    # Extract vehicle class
    vehicle_class = None
    class_match = re.search(r'MCWG|LMV|MGV|HMV|TRAILER', text_upper)
    if class_match:
        vehicle_class = class_match.group(0)
    
    return {
        "licence_no": licence_no,
        "expiry": expiry,
        "name": name,
        "vehicle_class": vehicle_class,
    }


def extract_rc_info(text: str) -> dict:
    """Extract RC information from OCR text"""
    text_upper = text.upper()
    
    # Extract RC number (Indian format: KA01AB1234)
    rc_no = None
    rc_match = re.search(r'[A-Z]{2}\d{2}[A-Z]{2}\d{4}', text_upper)
    if rc_match:
        rc_no = rc_match.group(0)
    
    # Extract registration date
    reg_date = None
    date_match = re.search(r'\d{2}[-/]\d{2}[-/]\d{4}', text_upper)
    if date_match:
        reg_date = date_match.group(0).replace('/', '-')
    
    # Extract vehicle class
    vehicle_class = None
    class_match = re.search(r'MCWG|LMV|MGV|HMV|TRAILER', text_upper)
    if class_match:
        vehicle_class = class_match.group(0)
    
    # Extract fuel type
    fuel_type = None
    fuel_match = re.search(r'PETROL|DIESEL|CNG|ELECTRIC|LPG', text_upper)
    if fuel_match:
        fuel_type = fuel_match.group(0)
    
    return {
        "rc_no": rc_no,
        "reg_date": reg_date,
        "vehicle_class": vehicle_class,
        "fuel_type": fuel_type,
    }


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
    bio: Optional[str] = Field(default=None, max_length=500)


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


# ---------------------------------------------------------------- locations (search/geocoding/routing live in geo.py)
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
    vehicle_name: str = Field(min_length=2, max_length=80)
    phone: str = Field(pattern=r"^[6-9]\d{9}$")
    licence_no: str = Field(min_length=8, max_length=20)
    licence_expiry: str = Field(pattern=r"^\d{2}-\d{2}-\d{4}$")
    rc_no: str = Field(min_length=6, max_length=15)


class LicenceVerificationIn(BaseModel):
    licence_front: str = Field(..., description="File ID of licence front")
    licence_back: str = Field(..., description="File ID of licence back")
    ocr_data: Optional[dict] = Field(default=None, description="OCR extracted data")
    manual_licence_no: str = Field(min_length=8, max_length=20)
    manual_expiry: str = Field(pattern=r"^\d{2}-\d{2}-\d{4}$")
    manual_name: str = Field(min_length=3, max_length=100)


class LicenceReviewIn(BaseModel):
    decision: Literal["verified", "rejected", "resubmit_required"]
    reason: str = Field(default="", max_length=500)
    verification_method: Literal["ocr", "manual", "parivahan", "digilocker"] = "manual"
    official_verified: bool = Field(default=False, description="Only true if verified through official government source")


def mask(v: str) -> str:
    return v[:2] + "•" * max(0, len(v) - 6) + v[-4:] if v else v


# ---------------------------------------------------------------- secure document storage (Emergent Object Storage)
STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
STORAGE_APP = "travoo"
DOC_KINDS = ["profile", "licence", "rc", "vehicle"]
MAX_UPLOAD = 8 * 1024 * 1024
_storage_key: Optional[str] = None


def init_storage() -> str:
    global _storage_key
    if not _storage_key:
        r = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": os.environ["EMERGENT_LLM_KEY"]}, timeout=30)
        r.raise_for_status()
        _storage_key = r.json()["storage_key"]
    return _storage_key


def _storage_call(method: str, path: str, **kw) -> requests.Response:
    global _storage_key
    for attempt in range(2):
        r = requests.request(method, f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": init_storage(), **kw.pop("headers", {})}, timeout=120, **kw)
        if r.status_code == 503 and attempt == 0:
            _storage_key = None
            continue
        return r
    return r


def put_object(path: str, data: bytes, content_type: str) -> dict:
    r = _storage_call("PUT", path, data=data, headers={"Content-Type": content_type})
    if r.status_code == 402:
        raise HTTPException(402, "Storage credits exhausted. Please try again later.")
    r.raise_for_status()
    return r.json()


def get_object(path: str) -> tuple[bytes, str]:
    r = _storage_call("GET", path)
    r.raise_for_status()
    return r.content, r.headers.get("Content-Type", "application/octet-stream")


def sniff_image(data: bytes) -> Optional[tuple[str, str]]:
    """Validate real image bytes (magic numbers); never trust the client-declared type."""
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg", "jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png", "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", "webp"
    if data[4:8] == b"ftyp" and data[8:12] in (b"heic", b"heix", b"mif1", b"msf1", b"heif"):
        return "image/heic", "heic"
    return None


@api.post("/driver/documents/{kind}")
async def upload_document(kind: str, file: UploadFile = File(...), user: dict = Depends(get_user)):
    if kind not in DOC_KINDS:
        raise HTTPException(400, "Unknown document type")
    if user.get("driver_status") in ("under_review", "approved"):
        raise HTTPException(400, "Documents are locked while under review or approved")
    ctype = (file.content_type or "").lower()
    data = await file.read()
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "Image is too large (max 8 MB)")
    sniffed = sniff_image(data)
    if not sniffed:
        raise HTTPException(400, "Please upload a JPEG, PNG, WEBP or HEIC photo")
    ctype, ext = sniffed
    path = f"{STORAGE_APP}/driver-docs/{user['user_id']}/{kind}-{uuid.uuid4().hex}.{ext}"
    res = await run_in_threadpool(put_object, path, data, ctype)
    fid = nid("file")
    await db.files.insert_one({"file_id": fid, "owner_id": user["user_id"], "path": res["path"], "kind": kind,
                               "content_type": ctype, "size": len(data), "original_name": file.filename, "created_at": now()})
    await db.driver_documents.update_one({"user_id": user["user_id"]}, {"$set": {f"photos.{kind}": fid, "user_id": user["user_id"]}}, upsert=True)
    await db.files.update_many({"owner_id": user["user_id"], "kind": kind, "file_id": {"$ne": fid}}, {"$set": {"deleted": True}})
    return {"file_id": fid, "kind": kind}


@api.get("/files/{fid}")
async def get_file(fid: str, request: Request, token: Optional[str] = None):
    auth = request.headers.get("Authorization", "")
    tok = auth[7:] if auth.startswith("Bearer ") else token
    if not tok:
        raise HTTPException(401, "Not authenticated")
    user = await user_from_token(tok)
    f = await db.files.find_one({"file_id": fid, "deleted": {"$ne": True}}, {"_id": 0})
    if not f or (f["owner_id"] != user["user_id"] and user.get("role") != "admin"):
        raise HTTPException(404, "File not found")
    data, ctype = await run_in_threadpool(get_object, f["path"])
    return Response(content=data, media_type=f.get("content_type") or ctype,
                    headers={"Cache-Control": "private, max-age=3600", "X-Content-Type-Options": "nosniff",
                             "Content-Security-Policy": "default-src 'none'; sandbox"})


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
    existing = await db.driver_documents.find_one({"user_id": user["user_id"]}, {"_id": 0, "photos": 1}) or {}
    missing = [k for k in DOC_KINDS if not (existing.get("photos") or {}).get(k)]
    if missing:
        raise HTTPException(400, f"Please upload: {', '.join(missing)} photo")
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


AI_EXTRACT_PROMPT = (
    "You read Indian driving documents. Image 1 is a driving licence, image 2 is a vehicle Registration Certificate (RC). "
    "Return ONLY a JSON object with keys: legal_name (licence holder's full name), licence_no (no spaces), "
    "licence_expiry (DD-MM-YYYY, the non-transport validity date), rc_no (vehicle registration number, no spaces), "
    "vehicle_name (maker and model from RC). Use an empty string for anything you cannot read clearly. No extra text."
)


@api.post("/driver/ai-extract")
async def ai_extract(user: dict = Depends(get_user)):
    """Read the uploaded licence + RC photos with an AI vision model and return the fields to pre-fill."""
    if user.get("driver_status") in ("under_review", "approved"):
        raise HTTPException(400, "Verification already submitted")
    doc = await db.driver_documents.find_one({"user_id": user["user_id"]}, {"_id": 0, "photos": 1}) or {}
    photos = doc.get("photos") or {}
    missing = [k for k in ("licence", "rc") if not photos.get(k)]
    if missing:
        raise HTTPException(400, f"Please upload: {', '.join(missing)} photo")
    images = []
    for k in ("licence", "rc"):
        f = await db.files.find_one({"file_id": photos[k], "owner_id": user["user_id"]}, {"_id": 0})
        if not f:
            raise HTTPException(400, f"Please upload: {k} photo")
        if f.get("content_type") == "image/heic":
            raise HTTPException(400, "AI reading needs JPEG or PNG photos. Please retake the photo.")
        data, _ = await run_in_threadpool(get_object, f["path"])
        images.append(ImageContent(image_base64=base64.b64encode(data).decode()))
    chat = LlmChat(api_key=os.environ["EMERGENT_LLM_KEY"], session_id=f"ai-extract-{user['user_id']}-{uuid.uuid4().hex[:8]}",
                   system_message="You extract fields from document photos and answer with strict JSON.").with_model("openai", "gpt-5.4")
    out = ""
    try:
        async for ev in chat.stream_message(UserMessage(text=AI_EXTRACT_PROMPT, file_contents=images)):
            if isinstance(ev, TextDelta):
                out += ev.content
            elif isinstance(ev, StreamDone):
                break
    except Exception as exc:
        logger.error("AI extract failed: %s", exc)
        raise HTTPException(502, "AI could not read the photos right now. Please fill the details yourself.")
    m = re.search(r"\{.*\}", out, re.S)
    try:
        parsed = jsonlib.loads(m.group(0)) if m else {}
    except ValueError:
        parsed = {}
    keys = ("legal_name", "licence_no", "licence_expiry", "rc_no", "vehicle_name")
    res = {k: str(parsed.get(k) or "").strip() for k in keys}
    res["licence_no"] = res["licence_no"].replace(" ", "").upper()
    res["rc_no"] = res["rc_no"].replace(" ", "").upper()
    if not re.fullmatch(r"\d{2}-\d{2}-\d{4}", res["licence_expiry"]):
        res["licence_expiry"] = ""
    await audit(user["user_id"], "driver.ai_extract", user["user_id"], {"found": [k for k in keys if res[k]]})
    return res


class VehicleIn(BaseModel):
    make: str = Field(min_length=2, max_length=40)
    model: str = Field(min_length=1, max_length=40)
    vtype: Literal["hatchback", "sedan", "suv", "muv", "other"] = "sedan"
    color: str = Field(default="", max_length=20)
    reg_no: str = Field(min_length=6, max_length=15)
    seats: int = Field(ge=1, le=8)
    ac: bool = True
    luggage: Literal["small", "medium", "large"] = "medium"
    fuel_type: Literal["petrol", "diesel", "cng", "electric"] = "petrol"
    mileage: Optional[float] = Field(default=None, gt=0, le=60)  # km/l, km/kg (CNG) or km/kWh (EV)


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
    fuel_price: Optional[float] = Field(default=None, gt=0, le=500)
    mileage: Optional[float] = Field(default=None, gt=0, le=60)
    tolls: float = Field(default=0, ge=0, le=20000)
    tolls_estimated: bool = True
    maintenance_per_km: Optional[float] = Field(default=None, ge=0, le=20)
    share_mode: Literal["equal", "passenger"] = "equal"
    return_date: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    return_time: Optional[str] = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    route_choice: int = Field(default=0, ge=0, le=2)


async def road_route(pts: list, choice: int = 0) -> Optional[dict]:
    """Road route (OSRM on OpenStreetMap data, with mirror fallback). None if no routing provider answered."""
    res = await geo_router.route_options(pts, alternatives=True)
    if not res["source"].startswith("osrm"):
        return None
    return res["routes"][min(choice, len(res["routes"]) - 1)]


def cost_breakdown(km: float, mileage: float, fuel_price: float, tolls: float, maint: float, seats: int, mode: str, fuel_type: str) -> dict:
    fuel_units = km / mileage
    fuel_cost = fuel_units * fuel_price
    maint_cost = km * maint
    total = fuel_cost + tolls + maint_cost
    sharers = seats + 1 if mode == "equal" else seats
    return {"distance_km": km, "fuel_type": fuel_type, "mileage": mileage, "fuel_price": fuel_price,
            "fuel_units": round(fuel_units, 2), "fuel_cost": round(fuel_cost), "tolls": round(tolls),
            "maintenance_per_km": maint, "maintenance_cost": round(maint_cost), "total": round(total),
            "share_mode": mode, "sharers": sharers, "recommended": max(50, round(total / sharers))}


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
    if haversine(o, d) < 2:
        raise HTTPException(400, "Origin and destination are too close — TRAVOO is for intercity trips")
    km, mins, dep, arr = trip_metrics(o, d, stops, body.date, body.time)
    route_source, extra = "estimate", {}
    if not is_demo:
        road = await road_route([o, *stops, d], body.route_choice if not stops else 0)
        if road:
            km, mins, route_source = road["distance_km"], road["duration_min"] + 10 * len(stops), "osrm"
            arr = dep + timedelta(minutes=mins)
            geom = road["geometry"]
            line = []
            for p in [*geom[:: max(1, len(geom) // 200)], geom[-1]]:
                if not line or line[-1] != [p[1], p[0]]:
                    line.append([p[1], p[0]])
            extra = {"route_via": road["via"], "toll_km": road["toll_km"], "toll_estimate": road["toll_estimate"]}
            if len(line) >= 2:
                extra["route_line"] = {"type": "LineString", "coordinates": line}
    return {"trip_id": nid("trip"), "driver_id": driver["user_id"], "origin": o, "destination": d, "stops": stops,
            "pickup_point": body.pickup_point, "drop_point": body.drop_point, "date": body.date, "time": body.time,
            "departure_at": dep.astimezone(timezone.utc), "arrival_time": arr.strftime("%H:%M"),
            "arrival_date": arr.strftime("%Y-%m-%d"), "distance_km": km, "duration_min": mins, "route_source": route_source,
            "seats_total": body.seats, "seats_available": body.seats, "price": body.price,
            "vehicle": {k: vehicle.get(k) for k in ("vehicle_id", "make", "model", "vtype", "color", "ac", "luggage", "verified", "fuel_type")},
            "instant_booking": body.instant_booking, "notes": body.notes, "status": "scheduled",
            "is_demo": is_demo, "created_at": now(), **extra}


TRIP_OUT = {"_id": 0, "origin.geo": 0, "destination.geo": 0, "stops.geo": 0, "route_line": 0}


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
    settings = await get_settings()
    mileage = body.mileage or vehicle.get("mileage")
    if not (body.fuel_price and mileage):
        raise HTTPException(400, "Enter vehicle mileage and fuel price so the cost-sharing contribution can be calculated")
    if body.fuel_price and mileage:
        maint = body.maintenance_per_km if body.maintenance_per_km is not None else settings.get("maintenance_per_km", 2)
        cb = cost_breakdown(trip["distance_km"], mileage, body.fuel_price, body.tolls, maint, body.seats, body.share_mode, vehicle.get("fuel_type", "petrol"))
        cb["tolls_estimated"] = body.tolls_estimated
        cap = round(cb["recommended"] * settings.get("max_price_factor", 1.5))
        if body.price > cap:
            raise HTTPException(400, f"Price exceeds the cost-sharing limit of ₹{cap} per seat for this trip")
        trip["cost_breakdown"] = cb
    trips = [trip]
    if body.return_date and body.return_time:
        rb = body.model_copy(update={"origin": body.destination, "destination": body.origin, "stops": list(reversed(body.stops)),
                                     "pickup_point": body.drop_point, "drop_point": body.pickup_point, "date": body.return_date, "time": body.return_time})
        rt = await build_trip(rb, user, vehicle)
        if rt["departure_at"] <= trip["departure_at"]:
            raise HTTPException(400, "Return must be after the outbound departure")
        if trip.get("cost_breakdown"):
            rt["cost_breakdown"] = trip["cost_breakdown"]
        rt["return_of"] = trip["trip_id"]
        trips.append(rt)
    await db.trips.insert_many(trips)
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
    async for b in db.bookings.find({"trip_id": tid, "status": {"$in": ["pending", "confirmed"]}}, {"_id": 0}):
        await notify(b["passenger_id"], "trip_updated", {"route": b["route"]}, b["booking_id"])
    return await db.trips.find_one({"trip_id": tid}, TRIP_OUT)


async def enrich_trips(trips: list) -> list:
    ids = list({t["driver_id"] for t in trips})
    drivers = {u["user_id"]: u for u in await db.users.find({"user_id": {"$in": ids}}, PUBLIC_FIELDS).to_list(len(ids) or 1)}
    with_photo = set(await db.driver_documents.distinct("user_id", {"user_id": {"$in": ids}, "photos.profile": {"$exists": True}}))
    for d in drivers.values():
        d["has_photo"] = d["user_id"] in with_photo and d.get("driver_status") == "approved"
    for t in trips:
        t["driver"] = drivers.get(t["driver_id"], {"name": "Driver"})
    return trips


@api.get("/trips/search")
async def search_trips(from_lat: float, from_lng: float, to_lat: float, to_lng: float,
                       date: Optional[str] = None, seats: int = Query(1, ge=1, le=8),
                       sort: Literal["early", "price", "rating"] = "early", ac: bool = False,
                       max_price: Optional[int] = None, vtype: Optional[str] = None, radius_km: int = Query(35, le=100)):
    along_km = min(radius_km, 12)
    base = {"status": "scheduled", "seats_available": {"$gte": seats}, "departure_at": {"$gt": now()},
            "$or": [{"origin.geo": {"$geoWithin": {"$centerSphere": [[from_lng, from_lat], radius_km / 6378.1]}}},
                    {"route_line": {"$geoIntersects": {"$geometry": circle(from_lat, from_lng, along_km)}}}]}
    if ac:
        base["vehicle.ac"] = True
    if max_price:
        base["price"] = {"$lte": max_price}
    if vtype:
        base["vehicle.vtype"] = vtype
    to, frm = {"lat": to_lat, "lng": to_lng}, {"lat": from_lat, "lng": from_lng}
    out_proj = {k: v for k, v in TRIP_OUT.items() if k != "route_line"}

    def nearest(pts: list, p: dict) -> tuple[int, float]:
        return min(((i, haversine({"lat": c[1], "lng": c[0]}, p)) for i, c in enumerate(pts)), key=lambda x: x[1])

    def match(t) -> Optional[dict]:
        """Direct match (origin & destination/stop nearby) or along-route match (driver passes pickup, then drop)."""
        from_near = haversine(t["origin"], frm) <= radius_km
        if from_near and (haversine(t["destination"], to) <= radius_km or any(haversine(s, to) <= radius_km for s in t.get("stops", []))):
            return {"type": "direct"}
        pts = (t.get("route_line") or {}).get("coordinates") or []
        if len(pts) < 2:
            return None
        (ia, da), (ib, db_) = (0, 0.0) if from_near else nearest(pts, frm), nearest(pts, to)
        if ib > ia and da <= along_km and db_ <= along_km:
            hh, mm = map(int, t["time"].split(":"))
            eta = hh * 60 + mm + round((t.get("duration_min") or 0) * ia / (len(pts) - 1))
            return {"type": "along_route", "pickup_km": round(da, 1), "drop_km": round(db_, 1),
                    "pickup_eta": f"{eta // 60 % 24:02d}:{eta % 60:02d}"}
        return None

    def keep(t) -> bool:
        m = match(t)
        t.pop("route_line", None)
        if m:
            t["match"] = m
        return bool(m)

    q = {**base, **({"date": date} if date else {})}
    rows = [t for t in await db.trips.find(q, out_proj).limit(300).to_list(300) if keep(t)]
    rows = await enrich_trips(rows)
    if sort == "price":
        rows.sort(key=lambda t: (t["price"], t["departure_at"]))
    elif sort == "rating":
        rows.sort(key=lambda t: (-(t["driver"].get("rating_avg") or 0), t["departure_at"]))
    else:
        rows.sort(key=lambda t: t["departure_at"])
    alt = []
    others = [t for t in await db.trips.find(base, {"date": 1, "time": 1, "duration_min": 1, "origin": 1, "destination": 1, "stops": 1, "route_line": 1, "_id": 0}).limit(500).to_list(500) if keep(t)]
    counts: dict = {}
    for t in others:
        counts[t["date"]] = counts.get(t["date"], 0) + 1
    available = [{"date": k, "count": v} for k, v in sorted(counts.items())]
    if not rows and date:
        alt = available[:7]
    return {"trips": rows, "alternative_dates": alt, "available_dates": available}


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
    line = await db.trips.find_one({"trip_id": tid}, {"_id": 0, "route_line": 1})
    trip["route"] = [[c[1], c[0]] for c in line["route_line"]["coordinates"]] if line.get("route_line") else None
    trip["driver"] = await public_user(trip["driver_id"])
    trip["driver"]["has_photo"] = trip["driver"].get("driver_status") == "approved" and await has_badge_photo(trip["driver_id"])
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
    b = await db.bookings.find_one({"booking_id": bid}, {"_id": 0}) or await db.hires.find_one({"booking_id": bid}, {"_id": 0})
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
    elif user["user_id"] == b["passenger_id"]:
        await log_contact(user["user_id"], b["driver_id"], bid)
    b["driver"] = d
    p = await db.users.find_one({"user_id": b["passenger_id"]}, {"_id": 0, "user_id": 1, "name": 1, "picture": 1, "rating_avg": 1, "phone": 1})
    if not active:
        p.pop("phone", None)
    elif user["user_id"] == b["driver_id"]:
        await log_contact(user["user_id"], b["passenger_id"], bid)
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
    await db.messages.update_many({"booking_id": bid, "sender_id": {"$ne": user["user_id"]}, "read_by": {"$ne": user["user_id"]}},
                                  {"$addToSet": {"read_by": user["user_id"]}})
    rows = await db.messages.find({"booking_id": bid}, {"_id": 0}).sort("created_at", 1).to_list(500)
    for m in rows:
        m["status"] = "read" if any(r != m["sender_id"] for r in m.get("read_by", [])) else "delivered"
    return rows


@api.post("/bookings/{bid}/messages")
async def post_message(bid: str, body: MessageIn, user: dict = Depends(get_user)):
    b = await booking_for(bid, user)
    if not body.text.strip():
        raise HTTPException(400, "Message cannot be empty")
    if b["status"] not in ("pending", "confirmed", "started", "completed"):
        raise HTTPException(400, "Chat is closed for this booking")
    msg = {"message_id": nid("msg"), "booking_id": bid, "sender_id": user["user_id"], "sender_name": user["name"],
           "sender_picture": user.get("picture"), "text": body.text.strip(), "read_by": [], "created_at": now()}
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
    users = await db.users.find(filt, USER_PRIVATE).sort("created_at", -1).to_list(200)
    # Enrich with additional stats
    for u in users:
        u["trip_count"] = await db.trips.count_documents({"driver_id": u["user_id"]})
        u["booking_count"] = await db.bookings.count_documents({"passenger_id": u["user_id"]})
        u["rating"] = u.get("rating_avg", 0)
    return users


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
        u["trip_count"] = await db.trips.count_documents({"driver_id": u["user_id"]})
        u["booking_count"] = await db.bookings.count_documents({"driver_id": u["user_id"]})
        u["earnings"] = await db.earnings_ledger.aggregate([
            {"$match": {"driver_id": u["user_id"]}},
            {"$group": {"_id": "$driver_id", "total": {"$sum": "$amount"}}}
        ]).to_list(1)
        u["total_earnings"] = u["earnings"][0]["total"] if u["earnings"] else 0
    return users


@api.get("/admin/passengers")
async def admin_passengers(q: str = "", _: dict = Depends(get_admin)):
    """Get all passengers with their booking history and stats"""
    filt = {"$or": [{"name": {"$regex": re.escape(q), "$options": "i"}}, {"email": {"$regex": re.escape(q), "$options": "i"}}]} if q else {}
    users = await db.users.find(filt, USER_PRIVATE).to_list(200)
    for u in users:
        u["booking_count"] = await db.bookings.count_documents({"passenger_id": u["user_id"]})
        u["completed_trips"] = await db.bookings.count_documents({"passenger_id": u["user_id"], "status": "completed"})
        u["cancelled_trips"] = await db.bookings.count_documents({"passenger_id": u["user_id"], "status": "cancelled"})
        u["total_spent"] = await db.bookings.aggregate([
            {"$match": {"passenger_id": u["user_id"], "status": "completed"}},
            {"$group": {"_id": "$passenger_id", "total": {"$sum": "$fare_total"}}}
        ]).to_list(1)
        u["total_spent"] = u["total_spent"][0]["total"] if u["total_spent"] else 0
        u["recent_bookings"] = await db.bookings.find({"passenger_id": u["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(5)
    return users


class DriverReviewIn(BaseModel):
    decision: Literal["approved", "rejected", "resubmit"]
    note: str = Field(default="", max_length=300)


@api.post("/admin/drivers/{uid}/review")
async def admin_review_driver(uid: str, body: DriverReviewIn, admin: dict = Depends(get_admin)):
    doc = await db.driver_documents.find_one({"user_id": uid}, {"_id": 0, "submitted_at": 1})
    target = await db.users.find_one({"user_id": uid}, {"_id": 0, "driver_status": 1})
    if not doc or not doc.get("submitted_at") or not target:
        raise HTTPException(400, "This user has not submitted verification details")
    if target["driver_status"] not in ("under_review", "approved"):
        raise HTTPException(400, "Only submitted verifications can be reviewed")
    r = await db.users.update_one({"user_id": uid}, {"$set": {"driver_status": body.decision}})
    if not r.matched_count:
        raise HTTPException(404, "User not found")
    await db.driver_documents.update_one({"user_id": uid}, {"$set": {"admin_note": body.note, "reviewed_at": now(), "reviewed_by": admin["user_id"]}})
    if body.decision == "approved":
        await db.vehicles.update_many({"owner_id": uid}, {"$set": {"verified": True}})
    await notify(uid, "driver_approved" if body.decision == "approved" else "driver_rejected", {})
    await audit(admin["user_id"], f"driver.{body.decision}", uid, {"note": body.note})
    return {"ok": True}


# ---------------------------------------------------------------- Licence Verification System
@api.post("/driver/licence-verification")
async def submit_licence_verification(body: LicenceVerificationIn, user: dict = Depends(get_user)):
    """Submit driving licence for verification with front/back images and OCR data."""
    if user.get("driver_status") in ("under_review", "approved"):
        raise HTTPException(400, "Verification already submitted")
    
    # Verify file ownership
    for fid in [body.licence_front, body.licence_back]:
        f = await db.files.find_one({"file_id": fid, "owner_id": user["user_id"], "deleted": {"$ne": True}}, {"_id": 0})
        if not f:
            raise HTTPException(400, f"File {fid} not found or not owned by user")
    
    # Store licence verification record
    verification = {
        "verification_id": nid("lic"),
        "user_id": user["user_id"],
        "licence_front": body.licence_front,
        "licence_back": body.licence_back,
        "ocr_data": body.ocr_data or {},
        "manual_licence_no": body.manual_licence_no.upper(),
        "manual_expiry": body.manual_expiry,
        "manual_name": body.manual_name.strip(),
        "status": "pending",
        "submitted_at": now(),
        "reviewed_at": None,
        "reviewed_by": None,
        "admin_note": "",
        "official_verified": False,
        "verification_method": "manual",
    }
    
    await db.licence_verifications.update_one({"user_id": user["user_id"]}, {"$set": verification}, upsert=True)
    await audit(user["user_id"], "licence.verification.submit", user["user_id"], {"verification_id": verification["verification_id"]})
    
    return {"verification_id": verification["verification_id"], "status": "pending"}


@api.get("/driver/licence-verification")
async def get_licence_verification(user: dict = Depends(get_user)):
    """Get current licence verification status."""
    verification = await db.licence_verifications.find_one({"user_id": user["user_id"]}, {"_id": 0})
    if not verification:
        return {"status": "not_submitted"}
    # Mask sensitive data
    if "manual_licence_no" in verification:
        verification["manual_licence_no"] = mask(verification["manual_licence_no"])
    return verification


@api.get("/admin/licence-verifications")
async def admin_licence_verifications(status: str = "pending", _: dict = Depends(get_admin)):
    """Get all licence verifications for admin review."""
    verifications = await db.licence_verifications.find({"status": status}, {"_id": 0}).sort("submitted_at", -1).to_list(100)
    for v in verifications:
        v["user"] = await db.users.find_one({"user_id": v["user_id"]}, {"_id": 0, "user_id": 1, "name": 1, "email": 1})
        # Mask sensitive data
        if "manual_licence_no" in v:
            v["manual_licence_no"] = mask(v["manual_licence_no"])
    return verifications


@api.post("/admin/licence-verifications/{verification_id}/review")
async def review_licence_verification(verification_id: str, body: LicenceReviewIn, admin: dict = Depends(get_admin)):
    """Admin review of licence verification."""
    verification = await db.licence_verifications.find_one({"verification_id": verification_id}, {"_id": 0})
    if not verification:
        raise HTTPException(404, "Verification not found")
    
    if verification["status"] not in ("pending", "under_review"):
        raise HTTPException(400, "This verification has already been reviewed")
    
    # Only mark as officially verified if verified through government source
    if body.official_verified and body.verification_method not in ("parivahan", "digilocker"):
        raise HTTPException(400, "Official verification only allowed through Parivahan or DigiLocker")
    
    update = {
        "status": body.decision,
        "admin_note": body.reason,
        "reviewed_at": now(),
        "reviewed_by": admin["user_id"],
        "verification_method": body.verification_method,
        "official_verified": body.official_verified,
    }
    
    await db.licence_verifications.update_one({"verification_id": verification_id}, {"$set": update})
    
    # Update driver status if verified
    if body.decision == "verified":
        await db.users.update_one({"user_id": verification["user_id"]}, {"$set": {"driver_status": "under_review"}})
    
    await audit(admin["user_id"], f"licence.{body.decision}", verification["user_id"], {
        "verification_id": verification_id,
        "method": body.verification_method,
        "official": body.official_verified,
        "reason": body.reason
    })
    
    return {"ok": True}


@api.get("/admin/licence-verifications/{verification_id}/documents")
async def get_licence_documents(verification_id: str, _: dict = Depends(get_admin)):
    """Get licence document images for admin review (admin only)."""
    verification = await db.licence_verifications.find_one({"verification_id": verification_id}, {"_id": 0})
    if not verification:
        raise HTTPException(404, "Verification not found")
    
    # Get file URLs for front and back
    front_fid = verification.get("licence_front")
    back_fid = verification.get("licence_back")
    
    return {
        "verification_id": verification_id,
        "licence_front": fileUrl(front_fid) if front_fid else None,
        "licence_back": fileUrl(back_fid) if back_fid else None,
        "ocr_data": verification.get("ocr_data", {}),
        "manual_data": {
            "licence_no": mask(verification.get("manual_licence_no", "")),
            "expiry": verification.get("manual_expiry"),
            "name": verification.get("manual_name"),
        }
    }


# ---------------------------------------------------------------- Parivahan Integration (Manual Verification Only)
@api.get("/admin/parivahan/check/{licence_no}")
async def check_parivahan(licence_no: str, _: dict = Depends(get_admin)):
    """
    Generate Parivahan verification link for manual verification.
    NOTE: This does NOT scrape Parivahan or bypass authentication.
    Admins should manually check https://parivahan.gov.in/parivahan/
    This endpoint only provides a structured link for manual verification.
    """
    # Parivahan DL info page URL with pre-filled licence number
    parivahan_url = f"https://parivahan.gov.in/parivahan/en/fw/dlinfo/"
    
    # Log the verification attempt for audit
    logger.info(f"Parivahan verification requested for licence: {licence_no}")
    await audit("admin", "parivahan.check", licence_no, {"manual_verification": True})
    
    return {
        "message": "Manual verification required",
        "parivahan_url": parivahan_url,
        "licence_no": licence_no,
        "instructions": "Visit the official Parivahan portal to verify licence details manually",
        "disclaimer": "Do not scrape or bypass authentication. Official API integration requires government approval.",
        "verification_method": "manual"
    }


# ---------------------------------------------------------------- DigiLocker Integration (Disabled Until Official Approval)
@api.get("/admin/digilocker/status")
async def digilocker_status(_: dict = Depends(get_admin)):
    """
    Check DigiLocker integration status.
    NOTE: This is DISABLED until Travoo receives official partner approval and API credentials.
    """
    digilocker_enabled = os.environ.get("DIGILOCKER_ENABLED", "false").lower() == "true"
    
    if not digilocker_enabled:
        return {
            "enabled": False,
            "message": "DigiLocker integration is disabled. Requires official government partner approval and API credentials.",
            "instructions": "Contact DigiLocker for official API access: https://www.digilocker.gov.in/",
            "disclaimer": "Do not attempt to integrate without official approval."
        }
    
    # If enabled, return the status (placeholder for when credentials are available)
    return {
        "enabled": True,
        "message": "DigiLocker integration is active",
        "instructions": "Use DigiLocker API to fetch documents directly with user consent",
        "disclaimer": "Only use with official government-approved credentials."
    }


@api.post("/admin/digilocker/fetch-document")
async def fetch_digilocker_document(body: dict, _: dict = Depends(get_admin)):
    """
    Fetch document from DigiLocker (placeholder - requires official API credentials).
    NOTE: This is DISABLED until Travoo receives official partner approval and API credentials.
    """
    digilocker_enabled = os.environ.get("DIGILOCKER_ENABLED", "false").lower() == "true"
    
    if not digilocker_enabled:
        raise HTTPException(403, "DigiLocker integration is disabled. Requires official government partner approval.")
    
    # Placeholder for actual DigiLocker API integration
    # When credentials are available, this would:
    # 1. Authenticate with DigiLocker API
    # 2. Request document with user consent
    # 3. Fetch and return the document
    
    return {
        "message": "DigiLocker API integration not yet implemented. Requires official credentials.",
        "instructions": "Implement DigiLocker API integration with official credentials."
    }


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
    maintenance_per_km: Optional[float] = Field(default=None, ge=0, le=20)
    max_price_factor: Optional[float] = Field(default=None, ge=1, le=3)


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


# ---------------------------------------------------------------- v2: contacts, chat, profiles, searches, places, fuel, hire-a-driver
async def log_contact(viewer: str, owner: str, bid: str):
    await db.contact_access.update_one({"viewer_id": viewer, "owner_id": owner, "booking_id": bid},
                                       {"$setOnInsert": {"first_at": now()}, "$set": {"last_at": now()}}, upsert=True)


SYS_EVENTS = {"booking_confirmed", "booking_rejected", "booking_cancelled", "trip_cancelled", "trip_started", "trip_completed",
              "booking_request", "new_booking", "hire_request", "hire_confirmed", "hire_rejected", "hire_cancelled", "hire_completed", "trip_updated"}


async def sys_message(bid: str, ntype: str, params: dict):
    await db.messages.update_one({"booking_id": bid, "sys_type": ntype},
                                 {"$setOnInsert": {"message_id": nid("msg"), "booking_id": bid, "sender_id": "system", "sender_name": "Travoo",
                                                   "sys_type": ntype, "params": params, "text": "", "read_by": [], "created_at": now()}}, upsert=True)


def mask_phone(p: Optional[str]) -> str:
    return f"{p[:2]}••••••{p[-2:]}" if p and len(p) >= 6 else ""


@api.get("/public/photo/{uid}")
async def public_driver_photo(uid: str):
    """Verified badge photo: only the profile photo of an APPROVED driver is public. Documents stay private."""
    u = await db.users.find_one({"user_id": uid}, {"_id": 0, "driver_status": 1})
    pro = await db.pro_drivers.find_one({"user_id": uid, "status": "approved"}, {"_id": 1})
    doc = await db.driver_documents.find_one({"user_id": uid}, {"_id": 0, "photos.profile": 1})
    fid = ((doc or {}).get("photos") or {}).get("profile")
    if not fid or not (pro or (u and u.get("driver_status") == "approved")):
        raise HTTPException(404, "No verified photo")
    f = await db.files.find_one({"file_id": fid, "deleted": {"$ne": True}}, {"_id": 0})
    if not f:
        raise HTTPException(404, "No verified photo")
    data, ctype = await run_in_threadpool(get_object, f["path"])
    return Response(content=data, media_type=f.get("content_type") or ctype,
                    headers={"Cache-Control": "public, max-age=86400", "X-Content-Type-Options": "nosniff"})


async def has_badge_photo(uid: str) -> bool:
    return bool(await db.driver_documents.find_one({"user_id": uid, "photos.profile": {"$exists": True}}, {"_id": 1}))


@api.get("/users/{uid}/profile")
async def full_public_profile(uid: str, _: dict = Depends(get_user)):
    u = await public_user(uid)
    pro = await db.pro_drivers.find_one({"user_id": uid}, {"_id": 0, "licence_no": 0, "licence_expiry": 0, "phone": 0, "email": 0})
    verified = u.get("driver_status") == "approved" or (pro or {}).get("status") == "approved"
    u["has_photo"] = verified and await has_badge_photo(uid)
    vehicles = await db.vehicles.find({"owner_id": uid, "deleted": {"$ne": True}}, {"_id": 0, "make": 1, "model": 1, "vtype": 1, "ac": 1, "verified": 1}).to_list(10)
    completed = await db.trips.count_documents({"driver_id": uid, "status": "completed"}) + await db.hires.count_documents({"driver_id": uid, "status": "completed"})
    reviews = await db.reviews.find({"target_id": uid, "hidden": {"$ne": True}}, {"_id": 0}).sort("created_at", -1).to_list(20)
    return {"user": u, "pro": pro if (pro or {}).get("status") == "approved" else None, "vehicles": vehicles,
            "completed_journeys": completed, "reviews": reviews, "verified": verified}


@api.get("/conversations")
async def conversations(user: dict = Depends(get_user)):
    uid = user["user_id"]
    q = {"$or": [{"passenger_id": uid}, {"driver_id": uid}], "status": {"$in": ["pending", "confirmed", "started", "completed"]}}
    rows = [{**b, "kind": "carpool"} for b in await db.bookings.find(q, {"_id": 0}).to_list(300)]
    rows += [{**h, "kind": "hire"} for h in await db.hires.find(q, {"_id": 0}).to_list(300)]
    out = []
    for b in rows:
        last = await db.messages.find_one({"booking_id": b["booking_id"]}, {"_id": 0}, sort=[("created_at", -1)])
        if not last and b["status"] == "completed":
            continue
        other_id = b["driver_id"] if uid == b["passenger_id"] else b["passenger_id"]
        other = await db.users.find_one({"user_id": other_id}, {"_id": 0, "user_id": 1, "name": 1, "picture": 1})
        unread = await db.messages.count_documents({"booking_id": b["booking_id"], "sender_id": {"$ne": uid}, "read_by": {"$ne": uid}})
        out.append({"booking_id": b["booking_id"], "kind": b["kind"], "route": b.get("route"), "date": b.get("date"), "status": b["status"],
                    "other": other, "last": last, "unread": unread, "sort": (last or {}).get("created_at") or b["created_at"]})
    out.sort(key=lambda x: x["sort"], reverse=True)
    return {"items": out, "unread": sum(x["unread"] for x in out)}


class SearchIn(BaseModel):
    kind: Literal["intercity", "hire"]
    origin: Optional[LocIn] = None
    destination: Optional[LocIn] = None
    date: Optional[str] = None
    seats: int = 1
    service: Optional[str] = None


@api.post("/searches")
async def save_search(body: SearchIn, user: dict = Depends(get_user)):
    key = f"{body.kind}:{body.origin.loc_id if body.origin else ''}:{body.destination.loc_id if body.destination else ''}:{body.service or ''}"
    await db.searches.update_one({"user_id": user["user_id"], "key": key},
                                 {"$set": {**body.model_dump(), "user_id": user["user_id"], "key": key, "at": now()}}, upsert=True)
    return {"ok": True}


@api.get("/searches")
async def list_searches(user: dict = Depends(get_user)):
    return await db.searches.find({"user_id": user["user_id"]}, {"_id": 0}).sort("at", -1).to_list(10)


@api.delete("/searches")
async def clear_searches(user: dict = Depends(get_user)):
    await db.searches.delete_many({"user_id": user["user_id"]})
    return {"ok": True}


class MissingPlaceIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    local_name: str = Field(default="", max_length=100)
    ltype: Literal["village", "town", "locality", "landmark", "bus_terminal", "railway_station", "other"] = "village"
    district: str = Field(min_length=2, max_length=80)
    state: str = Field(min_length=2, max_length=80)
    pin: Optional[str] = Field(default=None, pattern=r"^\d{6}$")
    lat: float = Field(ge=6, le=37.5)
    lng: float = Field(ge=68, le=97.5)


@api.post("/locations/missing")
async def submit_missing_place(body: MissingPlaceIn, user: dict = Depends(get_user)):
    doc = {"request_id": nid("mlr"), **body.model_dump(), "user_id": user["user_id"], "user_name": user["name"], "status": "pending", "created_at": now()}
    await db.missing_locations.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api.get("/admin/locations/missing")
async def admin_missing_places(_: dict = Depends(get_admin)):
    return await db.missing_locations.find({}, {"_id": 0}).sort([("status", -1), ("created_at", -1)]).to_list(200)


class DecisionIn(BaseModel):
    decision: Literal["approved", "rejected"]
    note: str = Field(default="", max_length=300)


@api.post("/admin/locations/missing/{rid}")
async def admin_review_place(rid: str, body: DecisionIn, admin: dict = Depends(get_admin)):
    r = await db.missing_locations.find_one({"request_id": rid, "status": "pending"}, {"_id": 0})
    if not r:
        raise HTTPException(404, "Pending request not found")
    if body.decision == "approved":
        d = loc_doc(r["name"], r["ltype"], r["district"], r["state"], r.get("pin"), r["lat"], r["lng"],
                    [x for x in [r.get("local_name")] if x], source="community", loc_id=f"cm_{rid}")
        await db.locations.update_one({"loc_id": d["loc_id"]}, {"$setOnInsert": d}, upsert=True)
    await db.missing_locations.update_one({"request_id": rid}, {"$set": {"status": body.decision, "note": body.note, "reviewed_at": now()}})
    await audit(admin["user_id"], f"place.{body.decision}", rid)
    return {"ok": True}


class FuelPriceIn(BaseModel):
    state: str = Field(default="default", max_length=80)
    fuel_type: Literal["petrol", "diesel", "cng", "electric"]
    price: float = Field(gt=0, le=500)


@api.get("/fuel-prices")
async def fuel_prices(state: str = ""):
    rows = await db.fuel_prices.find({"state": {"$in": [state, "default"]}}, {"_id": 0}).to_list(50)
    out: dict = {}
    for r in sorted(rows, key=lambda x: x["state"] != "default"):  # state-specific overrides default
        out[r["fuel_type"]] = r
    s = await get_settings()
    return {"prices": out, "maintenance_per_km": s.get("maintenance_per_km", 2), "max_price_factor": s.get("max_price_factor", 1.5)}


@api.post("/admin/fuel-prices")
async def admin_set_fuel(body: FuelPriceIn, admin: dict = Depends(get_admin)):
    await db.fuel_prices.update_one({"state": body.state, "fuel_type": body.fuel_type},
                                    {"$set": {**body.model_dump(), "updated_at": now(), "updated_by": admin["user_id"]}}, upsert=True)
    await audit(admin["user_id"], "fuel.set", f"{body.state}:{body.fuel_type}", {"price": body.price})
    return {"ok": True}


# ---- Hire a Driver (TRAVOO DRIVER): customer supplies the car, verified professional driver drives it
SERVICE_HOURS = {"hourly": None, "half_day": 4, "full_day": 8, "one_way": None, "airport": None, "outstation": None, "custom": None}


class ProDriverIn(BaseModel):
    city: LocIn
    areas: List[str] = Field(default_factory=list, max_length=15)
    languages: List[str] = Field(min_length=1, max_length=10)
    experience_years: int = Field(ge=1, le=50)
    licence_no: str = Field(min_length=8, max_length=20)
    licence_expiry: str = Field(pattern=r"^\d{2}-\d{2}-\d{4}$")
    vehicle_types: List[Literal["hatchback", "sedan", "suv", "muv", "luxury", "automatic", "ev"]] = Field(min_length=1)
    days: List[int] = Field(min_length=1, max_length=7)  # 0=Mon..6=Sun
    start_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    end_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    bio: str = Field(min_length=20, max_length=500)
    rate_hourly: int = Field(ge=50, le=5000)
    rate_half_day: int = Field(ge=100, le=20000)
    rate_full_day: int = Field(ge=200, le=40000)
    rate_one_way: Optional[int] = Field(default=None, ge=100, le=40000)


@api.get("/pro/me")
async def pro_me(user: dict = Depends(get_user)):
    p = await db.pro_drivers.find_one({"user_id": user["user_id"]}, {"_id": 0})
    doc = await db.driver_documents.find_one({"user_id": user["user_id"]}, {"_id": 0, "photos": 1}) or {}
    if p:
        p["licence_no"] = mask(p["licence_no"])
    return {"profile": p, "photos": doc.get("photos", {})}


@api.post("/pro/register")
async def pro_register(body: ProDriverIn, user: dict = Depends(get_user)):
    if not (user.get("phone") and re.fullmatch(r"[6-9]\d{9}", user["phone"])):
        raise HTTPException(400, "Add a valid registered mobile number in your profile first")
    existing = await db.pro_drivers.find_one({"user_id": user["user_id"]}, {"_id": 0, "status": 1})
    if existing and existing["status"] in ("under_review", "approved"):
        raise HTTPException(400, "Local driver profile already submitted")
    doc = await db.driver_documents.find_one({"user_id": user["user_id"]}, {"_id": 0, "photos": 1}) or {}
    missing = [k for k in ("profile", "licence") if not (doc.get("photos") or {}).get(k)]
    if missing:
        raise HTTPException(400, f"Please upload: {', '.join(missing)} photo")
    status = "approved" if (await get_settings()).get("instant_driver_approval") else "under_review"
    rec = {**body.model_dump(), "city": loc_snapshot(body.city), "licence_no": body.licence_no.upper(), "user_id": user["user_id"],
           "name": user["name"], "status": status, "submitted_at": now(), "admin_note": ""}
    await db.pro_drivers.update_one({"user_id": user["user_id"]}, {"$set": rec}, upsert=True)
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"bio": body.bio}})
    if status == "approved":
        await notify(user["user_id"], "driver_approved", {})
    await audit(user["user_id"], "pro.submit", user["user_id"], {"status": status})
    return {"status": status}


def hire_estimate(p: dict, service: str, hours: int) -> int:
    if service == "half_day":
        return p["rate_half_day"]
    if service == "full_day":
        return p["rate_full_day"]
    if service in ("one_way", "airport") and p.get("rate_one_way"):
        return p["rate_one_way"]
    if service == "outstation":
        return p["rate_full_day"] * max(1, math.ceil(hours / 8))
    return p["rate_hourly"] * max(1, hours)


@api.get("/hire/drivers")
async def hire_search(lat: float, lng: float, date: str = Query(pattern=r"^\d{4}-\d{2}-\d{2}$"), service: str = "hourly",
                      hours: int = Query(4, ge=1, le=72), vehicle_type: Optional[str] = None, language: Optional[str] = None,
                      min_exp: int = 0, user: dict = Depends(get_user)):
    weekday = datetime.strptime(date, "%Y-%m-%d").weekday()
    q = {"status": "approved", "days": weekday, "experience_years": {"$gte": min_exp}, "user_id": {"$ne": user["user_id"]},
         "city.geo": {"$geoWithin": {"$centerSphere": [[lng, lat], 60 / 6378.1]}}}
    if vehicle_type:
        q["vehicle_types"] = vehicle_type
    if language:
        q["languages"] = {"$regex": f"^{re.escape(language)}$", "$options": "i"}
    rows = await db.pro_drivers.find(q, {"_id": 0, "licence_no": 0, "licence_expiry": 0, "city.geo": 0}).to_list(100)
    out = []
    for p in rows:
        busy = await db.hires.count_documents({"driver_id": p["user_id"], "date": date, "status": {"$in": ["confirmed", "started"]}})
        if busy:
            continue
        u = await public_user(p["user_id"])
        out.append({**p, "user": {**u, "has_photo": await has_badge_photo(p["user_id"])}, "estimate": hire_estimate(p, service, hours)})
    out.sort(key=lambda x: (-(x["user"].get("rating_avg") or 0), x["estimate"]))
    return out


class HireIn(BaseModel):
    driver_id: str
    service_type: Literal["hourly", "half_day", "full_day", "one_way", "airport", "outstation", "custom"]
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    time: str = Field(pattern=r"^\d{2}:\d{2}$")
    hours: int = Field(ge=1, le=72)
    city: LocIn
    pickup: str = Field(min_length=2, max_length=150)
    destination: str = Field(default="", max_length=150)
    vehicle_type: str = Field(max_length=20)
    vehicle_desc: str = Field(min_length=2, max_length=80)
    notes: str = Field(default="", max_length=500)


@api.post("/hire/bookings")
async def hire_book(body: HireIn, user: dict = Depends(get_user)):
    p = await db.pro_drivers.find_one({"user_id": body.driver_id, "status": "approved"}, {"_id": 0})
    if not p or body.driver_id == user["user_id"]:
        raise HTTPException(400, "This driver is not available")
    dt = datetime.strptime(f"{body.date} {body.time}", "%Y-%m-%d %H:%M").replace(tzinfo=IST)
    if dt < now():
        raise HTTPException(400, "Start time must be in the future")
    if await db.hires.find_one({"driver_id": body.driver_id, "passenger_id": user["user_id"], "date": body.date, "status": {"$in": ["pending", "confirmed"]}}):
        raise HTTPException(409, "You already requested this driver for this date")
    h = {"booking_id": "HIR-" + secrets.token_hex(4).upper(), **body.model_dump(), "city": loc_snapshot(body.city), "passenger_id": user["user_id"],
         "service_fee": hire_estimate(p, body.service_type, body.hours), "route": f"{body.city.name} · {body.pickup}" + (f" → {body.destination}" if body.destination else ""),
         "status": "pending", "starts_at": dt.astimezone(timezone.utc), "settlement": {"status": "unpaid"}, "created_at": now()}
    await db.hires.insert_one(h)
    await notify(body.driver_id, "hire_request", {"route": h["route"]}, h["booking_id"])
    await sys_message(h["booking_id"], "hire_request", {"route": h["route"]})
    h.pop("_id", None)
    return h


@api.get("/hire/bookings")
async def hire_list(user: dict = Depends(get_user)):
    uid = user["user_id"]
    return await db.hires.find({"$or": [{"passenger_id": uid}, {"driver_id": uid}]}, {"_id": 0, "city.geo": 0}).sort("starts_at", -1).to_list(200)


@api.get("/hire/bookings/{bid}")
async def hire_get(bid: str, user: dict = Depends(get_user)):
    h = await db.hires.find_one({"booking_id": bid}, {"_id": 0, "city.geo": 0})
    if not h or (user["user_id"] not in (h["passenger_id"], h["driver_id"]) and user.get("role") != "admin"):
        raise HTTPException(404, "Booking not found")
    active = h["status"] in ("confirmed", "started", "completed")
    for role, uid in (("driver", h["driver_id"]), ("customer", h["passenger_id"])):
        u = await db.users.find_one({"user_id": uid}, {"_id": 0, "user_id": 1, "name": 1, "picture": 1, "rating_avg": 1, "rating_count": 1, "phone": 1})
        u["phone"] = u.get("phone") if active else mask_phone(u.get("phone"))
        u["phone_masked"] = not active
        if active and uid != user["user_id"]:
            await log_contact(user["user_id"], uid, bid)
        h[role] = u
    h["driver"]["has_photo"] = await has_badge_photo(h["driver_id"])
    h["is_driver"] = user["user_id"] == h["driver_id"]
    h["my_reviews"] = await db.reviews.find({"booking_id": bid, "reviewer_id": user["user_id"]}, {"_id": 0}).to_list(5)
    return h


@api.post("/hire/bookings/{bid}/{action}")
async def hire_action(bid: str, action: Literal["accept", "reject", "start", "complete", "cancel"], body: ReasonIn, user: dict = Depends(get_user)):
    h = await db.hires.find_one({"booking_id": bid}, {"_id": 0})
    if not h or user["user_id"] not in (h["passenger_id"], h["driver_id"]):
        raise HTTPException(404, "Booking not found")
    is_driver = user["user_id"] == h["driver_id"]
    rules = {"accept": (["pending"], "confirmed", True), "reject": (["pending"], "rejected", True), "start": (["confirmed"], "started", True),
             "complete": (["started"], "completed", True), "cancel": (["pending", "confirmed"], "cancelled", None)}
    allowed, new, driver_only = rules[action]
    if driver_only and not is_driver:
        raise HTTPException(403, "Only the driver can do this")
    upd = {"status": new, f"{action}_at": now()}
    if action in ("cancel", "reject"):
        upd.update(cancel_reason=body.reason, cancelled_by="driver" if is_driver else "customer", refund_note=body.refund_note)
    res = await db.hires.update_one({"booking_id": bid, "status": {"$in": allowed}}, {"$set": upd})
    if not res.modified_count:
        raise HTTPException(400, f"Cannot {action} this booking now")
    ntype = {"accept": "hire_confirmed", "reject": "hire_rejected", "cancel": "hire_cancelled", "complete": "hire_completed", "start": "trip_started"}[action]
    other = h["passenger_id"] if is_driver else h["driver_id"]
    await notify(other, ntype, {"route": h["route"]}, bid)
    await sys_message(bid, ntype, {"route": h["route"]})
    if action == "complete":
        await db.hires.update_one({"booking_id": bid}, {"$set": {"completed_at": now()}})
    return {"ok": True}


@api.get("/admin/pro-drivers")
async def admin_pro_drivers(status: str = "under_review", _: dict = Depends(get_admin)):
    rows = await db.pro_drivers.find({"status": status}, {"_id": 0, "city.geo": 0}).to_list(200)
    for r in rows:
        r["documents"] = await db.driver_documents.find_one({"user_id": r["user_id"]}, {"_id": 0, "photos": 1})
        r["email"] = (await db.users.find_one({"user_id": r["user_id"]}, {"_id": 0, "email": 1}) or {}).get("email")
    return rows


@api.post("/admin/pro-drivers/{uid}/review")
async def admin_review_pro(uid: str, body: DriverReviewIn, admin: dict = Depends(get_admin)):
    r = await db.pro_drivers.update_one({"user_id": uid, "status": {"$in": ["under_review", "approved"]}},
                                        {"$set": {"status": body.decision, "admin_note": body.note, "reviewed_at": now()}})
    if not r.modified_count:
        raise HTTPException(400, "Only submitted local-driver profiles can be reviewed")
    await notify(uid, "driver_approved" if body.decision == "approved" else "driver_rejected", {})
    await audit(admin["user_id"], f"pro.{body.decision}", uid, {"note": body.note})
    return {"ok": True}


geo_router = get_router(db, get_admin)
app.include_router(api)
app.include_router(geo_router)
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
async def startup():
    await ensure_indexes()
    await seed()
    app.state.geo_sync = asyncio.create_task(geo_router.sync_loop())
    try:
        await run_in_threadpool(init_storage)
    except Exception as exc:
        logger.error("object storage init failed: %s", exc)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
