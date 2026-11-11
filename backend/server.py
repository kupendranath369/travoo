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
from typing import Dict, List, Literal, Optional

import bcrypt
import httpx
import jwt
import requests
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, FastAPI, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr, Field, field_validator
from pymongo import ASCENDING, DESCENDING, GEOSPHERE, IndexModel, ReturnDocument
from pymongo.errors import DuplicateKeyError
from starlette.middleware.cors import CORSMiddleware

from html import escape as html_escape
import base64
import json as jsonlib

import hashlib

from email_service import EmailNotConfigured, EmailSendFailed, email_configured, send_email, send_email_quietly
try:
    from emergentintegrations.llm.chat import ImageContent, LlmChat, StreamDone, TextDelta, UserMessage
except ImportError:
    ImageContent = LlmChat = StreamDone = TextDelta = UserMessage = None
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
FRONTEND_URL = os.environ["FRONTEND_URL"].rstrip("/")
APP_SCHEME = "travoo"
RESET_TTL_MIN = 30
ADMIN_SESSION_HOURS = 8
ADMIN_REMEMBER_DAYS = 7

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("travoo")

INDEXES: dict[str, list[IndexModel]] = {
    "users": [IndexModel([("email", ASCENDING)], name="email_partial", unique=True, partialFilterExpression={"email": {"$type": "string"}}),
              IndexModel([("phone_e164", ASCENDING)], name="phone_e164", unique=True, partialFilterExpression={"phone_e164": {"$type": "string"}}),
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
    "phone_tickets": [IndexModel([("ticket_hash", ASCENDING)], name="ticket", unique=True), IndexModel([("expires_at", ASCENDING)], name="ttl", expireAfterSeconds=0)],
    "featured": [IndexModel([("feature_id", ASCENDING)], name="feaid", unique=True), IndexModel([("trip_id", ASCENDING)], name="trip"),
                 IndexModel([("status", ASCENDING), ("expires_at", ASCENDING)], name="status_exp")],
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
    "audit_logs": [IndexModel([("created_at", DESCENDING)], name="time"), IndexModel([("actor", ASCENDING)], name="actor")],
    "rate_limits": [IndexModel([("key", ASCENDING), ("at", DESCENDING)], name="key_at"),
                    IndexModel([("expires_at", ASCENDING)], name="ttl", expireAfterSeconds=0)],
    "password_resets": [IndexModel([("token_hash", ASCENDING)], name="token_hash", unique=True),
                        IndexModel([("user_id", ASCENDING)], name="user"),
                        IndexModel([("expires_at", ASCENDING)], name="ttl", expireAfterSeconds=86400)],
    "admin_sessions": [IndexModel([("token_hash", ASCENDING)], name="token_hash", unique=True),
                       IndexModel([("user_id", ASCENDING)], name="user"),
                       IndexModel([("expires_at", ASCENDING)], name="ttl", expireAfterSeconds=0)],
    "admin_notifications": [IndexModel([("created_at", DESCENDING)], name="time"), IndexModel([("read", ASCENDING)], name="read")],
    "driver_verification_events": [IndexModel([("user_id", ASCENDING), ("at", DESCENDING)], name="user_time")],
    "driver_documents": [IndexModel([("user_id", ASCENDING)], name="uid")],
}
for _c, _m in GEO_INDEXES.items():
    INDEXES[_c] = INDEXES.get(_c, []) + _m


async def ensure_indexes() -> None:
    try:  # phone-only accounts have no email: replace the old full unique email index with a partial one
        if "email_1" in await db.users.index_information() or "email" in await db.users.index_information():
            info = await db.users.index_information()
            for name in ("email", "email_1"):
                if name in info and not info[name].get("partialFilterExpression"):
                    await db.users.drop_index(name)
    except Exception as exc:
        logger.error("email index migration: %s", exc)
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


def sha256(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() or (request.client.host if request.client else "unknown")


async def rate_limit(key: str, limit: int, window_s: int, msg: str = "Too many attempts. Please wait a few minutes and try again."):
    """Sliding-window limiter backed by MongoDB (works across workers, entries expire via TTL)."""
    since = now() - timedelta(seconds=window_s)
    if await db.rate_limits.count_documents({"key": key, "at": {"$gt": since}}) >= limit:
        raise HTTPException(429, msg)
    await db.rate_limits.insert_one({"key": key, "at": now(), "expires_at": now() + timedelta(seconds=window_s)})


async def admin_alert(kind: str, title: str, ref: Optional[str] = None, extra: Optional[dict] = None):
    with suppress(Exception):
        await db.admin_notifications.insert_one({"notif_id": nid("anf"), "kind": kind, "title": title, "ref": ref,
                                                 "extra": extra or {}, "read": False, "created_at": now()})


def email_shell(title: str, body_html: str) -> str:
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6fb;padding:24px 12px">'
        '<tr><td align="center"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="max-width:480px;background:#ffffff;border-radius:14px;padding:28px;font-family:Arial,Helvetica,sans-serif;color:#1a1f36">'
        '<tr><td style="font-size:26px;font-weight:800;color:#1565d8;letter-spacing:0.5px;padding-bottom:4px">travoo</td></tr>'
        '<tr><td style="font-size:12px;color:#f28c28;font-weight:bold;padding-bottom:20px">Enjoy Your Ride</td></tr>'
        f'<tr><td style="font-size:20px;font-weight:bold;padding-bottom:12px">{title}</td></tr>'
        f'{body_html}'
        '<tr><td style="font-size:12px;color:#9ca3af;padding-top:24px;border-top:1px solid #eef0f4">'
        'Sent by Travoo. We will never ask for your password by email.</td></tr>'
        '</table></td></tr></table>'
    )


async def notify_driver_status_email(uid: str, decision: str, note: str):
    u = await db.users.find_one({"user_id": uid}, {"_id": 0, "email": 1, "name": 1})
    if not u or not u.get("email") or not email_configured():
        return
    msgs = {"approved": ("You're verified on Travoo", "Your documents were approved. You can now publish rides."),
            "rejected": ("Your Travoo verification was rejected", "Your documents could not be approved."),
            "resubmit": ("Please resubmit your Travoo documents", "Some documents need to be uploaded again.")}
    subject, line = msgs[decision]
    reason = f'<tr><td style="font-size:14px;padding-bottom:12px"><b>Reason:</b> {html_escape(note)}</td></tr>' if note else ""
    html = email_shell(html_escape(subject), f'<tr><td style="font-size:15px;line-height:22px;padding-bottom:12px">Hi {html_escape(u.get("name") or "there")}, {line}</td></tr>{reason}'
                       '<tr><td style="font-size:14px;color:#6b7280">Open the Travoo app → Driver verification to see details.</td></tr>')
    await send_email_quietly(to=u["email"], subject=subject, html=html)


# ---------------------------------------------------------------- auth
async def get_user(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Not authenticated")
    return await user_from_token(auth[7:])


async def user_from_token(token: str) -> dict:
    uid, iat, admin_session = None, None, False
    if token.startswith("adm_"):
        sess = await db.admin_sessions.find_one({"token_hash": sha256(token)}, {"_id": 0})
        if not sess or sess["expires_at"].replace(tzinfo=timezone.utc) <= now():
            raise HTTPException(401, "Admin session expired. Please sign in again.")
        uid, admin_session = sess["user_id"], True
        await db.admin_sessions.update_one({"token_hash": sha256(token)}, {"$set": {"last_seen": now()}})
    else:
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            if not payload.get("purpose"):
                uid, iat = payload.get("sub"), payload.get("iat")
        except jwt.InvalidTokenError:
            pass
    if not uid and not admin_session:
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
    changed = user.get("password_changed_at")
    if iat is not None and changed and int(changed.replace(tzinfo=timezone.utc).timestamp()) > int(iat):
        raise HTTPException(401, "Your password was changed. Please sign in again.")
    if admin_session:
        if user.get("role") != "admin":
            raise HTTPException(401, "Invalid admin session")
        user["_admin_session"] = True
    return user


async def get_admin_any(user: dict = Depends(get_user)) -> dict:
    """Admin signed in through the Admin Portal (server-side session); may still need to set a password."""
    if user.get("role") != "admin" or not user.get("_admin_session"):
        raise HTTPException(403, "Admin access required")
    return user


async def get_admin(user: dict = Depends(get_admin_any)) -> dict:
    if user.get("must_change_password"):
        raise HTTPException(403, "Please set a new password before using the admin portal")
    return user


def new_user_doc(email: Optional[str], name: str, **extra) -> dict:
    doc = {"user_id": nid("user"), "name": name, "phone": extra.get("phone", ""),
            "role": extra.get("role", "user"), "language": extra.get("language", "en"), "picture": extra.get("picture"),
            "upi_id": "", "bio": "", "driver_status": extra.get("driver_status", "not_submitted"),
            "rating_avg": 0, "rating_count": 0, "suspended": False, "consent_at": now(), "created_at": now(),
            "auth_provider": extra.get("auth_provider", "password"), "is_demo": extra.get("is_demo", False),
            "account_type": extra.get("account_type", "passenger")}
    if email:
        doc["email"] = email.lower()
    if extra.get("phone_e164"):
        doc.update(phone_e164=extra["phone_e164"], phone_verified=True, phone_verified_at=now())
    return doc


# ---------------------------------------------------------------- mobile number + OTP (MSG91)
MSG91_BASE = "https://control.msg91.com/api/v5/otp"
COUNTRY_CODES = {"91": 10, "971": 9, "1": 10, "44": 10, "65": 8, "977": 10, "880": 10, "94": 9, "61": 9, "966": 9, "974": 8, "968": 8, "973": 8, "965": 8}


def otp_configured() -> bool:
    return bool(os.environ.get("MSG91_AUTH_KEY", "").strip() and os.environ.get("MSG91_TEMPLATE_ID", "").strip())


def e164(cc: str, number: str) -> str:
    cc, number = re.sub(r"\D", "", cc or "91"), re.sub(r"\D", "", number or "")
    if cc == "91":
        number = number[-10:] if len(number) > 10 and number.startswith(("0", "91")) else number
        if not re.fullmatch(r"[6-9]\d{9}", number):
            raise HTTPException(400, "Enter a valid 10-digit Indian mobile number")
    elif cc not in COUNTRY_CODES or not re.fullmatch(r"\d{6,12}", number):
        raise HTTPException(400, "Enter a valid mobile number for the selected country")
    return cc + number


async def msg91(method: str, path: str, params: dict) -> dict:
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.request(method, f"{MSG91_BASE}{path}", params=params, headers={"authkey": os.environ["MSG91_AUTH_KEY"].strip()})
    try:
        data = r.json()
    except Exception:
        data = {"type": "error", "message": r.text[:200]}
    if r.status_code >= 500:
        raise HTTPException(502, "The SMS service is not responding. Please try again in a minute.")
    return data


class OtpSendIn(BaseModel):
    country_code: str = Field(default="91", max_length=4)
    phone: str = Field(min_length=6, max_length=15)
    resend: bool = False


class OtpVerifyIn(BaseModel):
    country_code: str = Field(default="91", max_length=4)
    phone: str = Field(min_length=6, max_length=15)
    otp: str = Field(pattern=r"^\d{4,8}$")


class OtpCompleteIn(BaseModel):
    ticket: str = Field(min_length=20, max_length=100)
    name: str = Field(min_length=2, max_length=80)
    account_type: Literal["passenger", "driver"] = "passenger"
    language: str = "en"
    consent: bool


async def send_otp(full: str, resend: bool, ip: str):
    if not otp_configured():
        raise HTTPException(503, "Mobile OTP sign-in isn't switched on yet (SMS service not configured). Please use email sign-in for now.")
    await rate_limit(f"otp:ip:{ip}", 20, 3600, "Too many OTP requests from this network. Please try again later.")
    await rate_limit(f"otp:phone:{full}", 5, 3600, "Too many OTPs sent to this number. Please wait an hour and try again.")
    if resend:
        data = await msg91("GET", "/retry", {"mobile": full, "retrytype": "text"})
    else:
        data = await msg91("POST", "", {"template_id": os.environ["MSG91_TEMPLATE_ID"].strip(), "mobile": full, "otp_length": 6, "otp_expiry": 10})
    if data.get("type") != "success":
        logger.warning("msg91 send failed for %s: %s", full[-4:], data.get("message"))
        raise HTTPException(502, "We couldn't send the OTP. Check the number and try again.")


async def check_otp(full: str, otp: str):
    if not otp_configured():
        raise HTTPException(503, "Mobile OTP sign-in isn't switched on yet.")
    await rate_limit(f"otpverify:{full}", 8, 900, "Too many wrong codes. Please request a new OTP after 15 minutes.")
    data = await msg91("GET", "/verify", {"mobile": full, "otp": otp})
    if data.get("type") != "success":
        msg = str(data.get("message", "")).lower()
        raise HTTPException(400, "This OTP has expired. Please request a new one." if "expire" in msg else "Incorrect OTP. Please check the code and try again.")


@api.get("/auth/otp/status")
async def otp_status():
    return {"enabled": otp_configured(), "countries": sorted(COUNTRY_CODES, key=lambda c: c != "91")}


@api.post("/auth/otp/send")
async def otp_send(body: OtpSendIn, request: Request):
    full = e164(body.country_code, body.phone)
    await send_otp(full, body.resend, client_ip(request))
    return {"sent": True, "phone": f"+{full}", "expires_in_min": 10}


@api.post("/auth/otp/verify")
async def otp_verify(body: OtpVerifyIn):
    """Verified number → sign in. Existing account found by verified number, or (once) by matching saved number.
    Unknown number → returns a short sign-up ticket so the account is only created after the OTP is verified."""
    full = e164(body.country_code, body.phone)
    await check_otp(full, body.otp)
    user = await db.users.find_one({"phone_e164": full})
    if not user and full.startswith("91"):
        local = full[2:]
        matches = await db.users.find({"phone_e164": {"$exists": False}, "role": {"$ne": "admin"},
                                       "phone": {"$in": [local, f"+91{local}", f"91{local}", f"0{local}"]}}).to_list(3)
        if len(matches) == 1:  # safe automatic link of an existing email account
            user = matches[0]
            await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"phone_e164": full, "phone": local, "phone_verified": True, "phone_verified_at": now()}})
            await audit(user["user_id"], "auth.phone_linked_auto", user["user_id"])
    if user:
        if user.get("suspended"):
            raise HTTPException(403, "Account suspended. Contact support.")
        if user.get("role") == "admin":
            raise HTTPException(403, "Administrators must sign in through the Travoo Admin Portal.")
        return {"token": make_token(user["user_id"]), "user": await db.users.find_one({"user_id": user["user_id"]}, USER_PRIVATE)}
    ticket = secrets.token_urlsafe(32)
    await db.phone_tickets.insert_one({"ticket_hash": sha256(ticket), "phone_e164": full, "expires_at": now() + timedelta(minutes=15)})
    return {"needs_profile": True, "ticket": ticket, "phone": f"+{full}"}


@api.post("/auth/otp/complete")
async def otp_complete(body: OtpCompleteIn):
    if not body.consent:
        raise HTTPException(400, "Consent is required")
    t = await db.phone_tickets.find_one_and_delete({"ticket_hash": sha256(body.ticket), "expires_at": {"$gt": now()}})
    if not t:
        raise HTTPException(400, "Your verification expired. Please request a new OTP.")
    full = t["phone_e164"]
    doc = new_user_doc(None, body.name.strip(), phone=full[2:] if full.startswith("91") else full, phone_e164=full,
                       language=body.language, auth_provider="phone", account_type=body.account_type)
    try:
        await db.users.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(409, "This mobile number is already registered. Please sign in with OTP.")
    await admin_alert("registration", f"New {body.account_type} registration: {doc['name']} (+{full})", doc["user_id"])
    return {"token": make_token(doc["user_id"]), "user": await db.users.find_one({"user_id": doc["user_id"]}, USER_PRIVATE)}


@api.post("/me/phone/send")
async def me_phone_send(body: OtpSendIn, request: Request, user: dict = Depends(get_user)):
    full = e164(body.country_code, body.phone)
    other = await db.users.find_one({"phone_e164": full, "user_id": {"$ne": user["user_id"]}}, {"_id": 1})
    if other:
        raise HTTPException(409, "This mobile number is already linked to another Travoo account")
    await send_otp(full, body.resend, client_ip(request))
    return {"sent": True, "phone": f"+{full}"}


@api.post("/me/phone/verify")
async def me_phone_verify(body: OtpVerifyIn, user: dict = Depends(get_user)):
    full = e164(body.country_code, body.phone)
    await check_otp(full, body.otp)
    try:
        await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"phone_e164": full, "phone": full[2:] if full.startswith("91") else full,
                                                                          "phone_verified": True, "phone_verified_at": now()}})
    except DuplicateKeyError:
        raise HTTPException(409, "This mobile number is already linked to another Travoo account")
    await audit(user["user_id"], "auth.phone_linked", user["user_id"])
    return await db.users.find_one({"user_id": user["user_id"]}, USER_PRIVATE)


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
    await admin_alert("registration", f"New registration: {doc['name']}", doc["user_id"])
    return {"token": make_token(doc["user_id"]), "user": user}


@api.post("/auth/login")
async def login(body: LoginIn, request: Request):
    email = body.email.lower()
    await rate_limit(f"login:ip:{client_ip(request)}", 30, 900)
    await rate_limit(f"login:email:{email}", 10, 900)
    user = await db.users.find_one({"email": email})
    if not user or not user.get("password_hash") or not check_pw(body.password, user["password_hash"]):
        raise HTTPException(401, "Incorrect email or password")
    if user.get("suspended"):
        raise HTTPException(403, "Account suspended. Contact support.")
    if user.get("role") == "admin":
        raise HTTPException(403, "Administrators must sign in through the Travoo Admin Portal.")
    return {"token": make_token(user["user_id"]), "user": await db.users.find_one({"user_id": user["user_id"]}, USER_PRIVATE)}


class ForgotPasswordIn(BaseModel):
    email: EmailStr
    portal: Literal["app", "admin"] = "app"


GENERIC_RESET = {"status": "accepted", "message": "If an account exists for this email, we've sent a password reset link. It expires in 30 minutes."}


def reset_email_html(name: str, web_link: str, app_link: str) -> str:
    web, app_ = html_escape(web_link, quote=True), html_escape(app_link, quote=True)
    return email_shell("Reset your password", (
        f'<tr><td style="font-size:15px;line-height:22px;padding-bottom:20px">Hi {html_escape(name)}, we received a request to reset the password '
        'for your Travoo account. Tap the button below to choose a new password.</td></tr>'
        f'<tr><td style="padding-bottom:16px"><a href="{web}" style="background:#1565d8;color:#ffffff;text-decoration:none;'
        'padding:14px 28px;border-radius:10px;font-weight:bold;font-size:16px;display:inline-block">Reset Password</a></td></tr>'
        f'<tr><td style="font-size:13px;padding-bottom:16px"><a href="{app_}" style="color:#1565d8">Open in the Travoo app instead</a></td></tr>'
        f'<tr><td style="font-size:14px;color:#1a1f36;padding-bottom:12px"><b>This link expires in {RESET_TTL_MIN} minutes</b> and can be used only once.</td></tr>'
        '<tr><td style="font-size:13px;line-height:20px;color:#6b7280;background:#fff7ed;border-radius:8px;padding:12px">'
        '<b>Didn\'t request this?</b> You can safely ignore this email — your password will not change. '
        'If you keep receiving these emails, contact Travoo support.</td></tr>'))


@api.post("/auth/forgot-password")
async def forgot_password(body: ForgotPasswordIn, request: Request):
    email = body.email.lower()
    await rate_limit(f"forgot:ip:{client_ip(request)}", 10, 900)
    await rate_limit(f"forgot:email:{email}", 3, 900, "Too many reset requests for this email. Please wait 15 minutes.")
    if not email_configured():
        logger.error("forgot-password requested but email service is not configured (RESEND_API_KEY / RESEND_FROM)")
        # Return a generic success message even if email is not configured to prevent email enumeration
        # But log the error for admin visibility
        return {"message": "If the email exists, a reset link will be sent"}
    user = await db.users.find_one({"email": email}, {"_id": 0, "user_id": 1, "name": 1, "email": 1, "role": 1, "suspended": 1})
    if not user or user.get("suspended"):
        return GENERIC_RESET
    raw = secrets.token_urlsafe(32)
    rid = nid("rst")
    await db.password_resets.update_many({"user_id": user["user_id"], "used_at": None}, {"$set": {"used_at": now(), "superseded": True}})
    await db.password_resets.insert_one({"request_id": rid, "user_id": user["user_id"], "token_hash": sha256(raw), "created_at": now(),
                                         "expires_at": now() + timedelta(minutes=RESET_TTL_MIN), "used_at": None,
                                         "ip": client_ip(request), "provider_status": "pending"})
    path = "reset-password"
    web_link, app_link = f"{FRONTEND_URL}/{path}?token={raw}", f"{APP_SCHEME}://{path}?token={raw}"
    try:
        email_id = await send_email(to=user["email"], subject="Reset Your Travoo Password",
                                    html=reset_email_html(user.get("name") or "there", web_link, app_link),
                                    text=f"Reset your Travoo password: {web_link}\nThis link expires in {RESET_TTL_MIN} minutes. If you did not request this, ignore this email.",
                                    idempotency_key=f"password-reset/{rid}")
    except (EmailNotConfigured, EmailSendFailed):
        await db.password_resets.update_one({"request_id": rid}, {"$set": {"provider_status": "failed", "used_at": now()}})
        raise HTTPException(502, "We couldn't send the reset email right now. Please try again in a few minutes.")
    await db.password_resets.update_one({"request_id": rid}, {"$set": {"provider_status": "accepted", "provider_email_id": email_id}})
    await audit(user["user_id"], "password.reset_requested", user["user_id"], {"request_id": rid})
    return GENERIC_RESET


def check_password_strength(p: str):
    if len(p) < 8 or not re.search(r"[A-Za-z]", p) or not re.search(r"\d", p):
        raise HTTPException(400, "Password must be at least 8 characters and include letters and numbers")


class ResetPasswordIn(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    new_password: str = Field(min_length=8, max_length=128)


@api.post("/auth/reset-password")
async def reset_password(body: ResetPasswordIn, request: Request):
    await rate_limit(f"reset:ip:{client_ip(request)}", 20, 900)
    check_password_strength(body.new_password)
    rec = await db.password_resets.find_one_and_update(
        {"token_hash": sha256(body.token), "used_at": None, "expires_at": {"$gt": now()}, "provider_status": "accepted"},
        {"$set": {"used_at": now()}})
    if not rec:
        raise HTTPException(400, "This reset link is invalid, expired or has already been used. Please request a new one.")
    uid = rec["user_id"]
    user = await db.users.find_one({"user_id": uid}, {"_id": 0, "role": 1})
    if not user:
        raise HTTPException(400, "This reset link is invalid, expired or has already been used. Please request a new one.")
    upd = {"password_hash": hash_pw(body.new_password), "password_changed_at": now()}
    if user.get("role") == "admin":
        upd["must_change_password"] = False
    await db.users.update_one({"user_id": uid}, {"$set": upd})
    await db.password_resets.update_many({"user_id": uid, "used_at": None}, {"$set": {"used_at": now(), "superseded": True}})
    await db.user_sessions.delete_many({"user_id": uid})
    await db.admin_sessions.delete_many({"user_id": uid})
    await audit(uid, "password.reset", uid, {})
    return {"status": "password_changed", "role": "admin" if user.get("role") == "admin" else "user",
            "message": "Your password has been changed. Please sign in with your new password."}


# ---------------------------------------------------------------- admin portal authentication
class AdminLoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    remember: bool = False


async def admin_out(uid: str) -> dict:
    u = await db.users.find_one({"user_id": uid}, {"_id": 0, "user_id": 1, "email": 1, "name": 1, "role": 1, "must_change_password": 1, "last_admin_login": 1})
    u["must_change_password"] = bool(u.get("must_change_password"))
    return u


@api.post("/admin/auth/login")
async def admin_login(body: AdminLoginIn, request: Request):
    email, ip = body.email.lower(), client_ip(request)
    await rate_limit(f"adminlogin:ip:{ip}", 20, 900)
    await rate_limit(f"adminlogin:email:{email}", 5, 900, "Too many sign-in attempts. This account is locked for 15 minutes.")
    user = await db.users.find_one({"email": email})
    if not user or user.get("role") != "admin" or not user.get("password_hash") or not check_pw(body.password, user["password_hash"]):
        await audit(user["user_id"] if user else "anonymous", "admin.login_failed", email, {"ip": ip})
        raise HTTPException(401, "Incorrect email or password")
    if user.get("suspended"):
        raise HTTPException(403, "Account suspended")
    raw = "adm_" + secrets.token_urlsafe(40)
    exp = now() + (timedelta(days=ADMIN_REMEMBER_DAYS) if body.remember else timedelta(hours=ADMIN_SESSION_HOURS))
    await db.admin_sessions.insert_one({"token_hash": sha256(raw), "user_id": user["user_id"], "created_at": now(), "expires_at": exp,
                                        "remember": body.remember, "ip": ip, "user_agent": request.headers.get("user-agent", "")[:200]})
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"last_admin_login": now()}})
    await audit(user["user_id"], "admin.login", user["user_id"], {"ip": ip, "remember": body.remember})
    return {"token": raw, "expires_at": exp, "admin": await admin_out(user["user_id"])}


@api.get("/admin/auth/me")
async def admin_me(admin: dict = Depends(get_admin_any)):
    return await admin_out(admin["user_id"])


@api.post("/admin/auth/logout")
async def admin_logout(request: Request, admin: dict = Depends(get_admin_any)):
    token = request.headers.get("Authorization", "")[7:]
    await db.admin_sessions.delete_one({"token_hash": sha256(token)})
    await audit(admin["user_id"], "admin.logout", admin["user_id"])
    return {"ok": True}


class AdminPasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=10, max_length=128)


@api.post("/admin/auth/change-password")
async def admin_change_password(body: AdminPasswordIn, request: Request, admin: dict = Depends(get_admin_any)):
    await rate_limit(f"adminpw:{admin['user_id']}", 10, 900)
    full = await db.users.find_one({"user_id": admin["user_id"]})
    if not check_pw(body.current_password, full.get("password_hash", "")):
        raise HTTPException(400, "Current password is incorrect")
    p = body.new_password
    if not (re.search(r"[a-z]", p) and re.search(r"[A-Z]", p) and re.search(r"\d", p)) or p == body.current_password:
        raise HTTPException(400, "Use at least 10 characters with upper and lower case letters and a number, different from the current password")
    await db.users.update_one({"user_id": admin["user_id"]}, {"$set": {"password_hash": hash_pw(p), "password_changed_at": now(), "must_change_password": False}})
    token = request.headers.get("Authorization", "")[7:]
    await db.admin_sessions.delete_many({"user_id": admin["user_id"], "token_hash": {"$ne": sha256(token)}})
    await audit(admin["user_id"], "admin.password_changed", admin["user_id"])
    return await admin_out(admin["user_id"])


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
    picture: Optional[str] = Field(default=None, max_length=100)


@api.put("/me")
async def update_me(body: ProfileIn, user: dict = Depends(get_user)):
    upd = {k: v for k, v in body.model_dump().items() if v is not None}
    if "phone" in upd:
        raw = upd["phone"].strip()
        digits = re.sub(r"\D", "", raw)[-10:]
        if raw and not re.fullmatch(r"[6-9]\d{9}", digits):
            raise HTTPException(400, "Enter a valid 10-digit mobile number")
        if digits == re.sub(r"\D", "", user.get("phone") or "")[-10:]:
            upd.pop("phone")  # unchanged
        elif user.get("phone_verified"):
            raise HTTPException(400, "Your mobile number is verified. Change it with OTP from your Profile.")
        else:
            upd["phone"] = digits
    if upd.get("upi_id") and not re.fullmatch(r"[\w.\-]{2,}@[a-zA-Z]{2,}", upd["upi_id"]):
        raise HTTPException(400, "Enter a valid UPI ID like name@bank")
    if upd:
        await db.users.update_one({"user_id": user["user_id"]}, {"$set": upd})
    return await db.users.find_one({"user_id": user["user_id"]}, USER_PRIVATE)


@api.post("/me/photo")
async def upload_profile_photo(file: UploadFile = File(...), user: dict = Depends(get_user)):
    """Personal profile photo (managed only from the Profile screen). Stored in private object storage."""
    await rate_limit(f"photo:{user['user_id']}", 20, 3600, "Too many photo uploads. Please try again later.")
    content = await file.read(5 * 1024 * 1024 + 1)
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(413, "Photo too large. Maximum 5 MB allowed.")
    sniffed = sniff_image(content)
    if not sniffed or sniffed[0] == "application/pdf":
        raise HTTPException(400, "Please choose a JPG, PNG or WEBP photo.")
    ctype, ext = sniffed
    file_id = nid("file")
    doc = {"file_id": file_id, "owner_id": user["user_id"], "kind": "user_profile", "content_type": ctype, "size": len(content),
           "sha256": hashlib.sha256(content).hexdigest(), "original_name": (file.filename or "")[:120], "created_at": now(), "deleted": False}
    try:
        res = await run_in_threadpool(put_object, f"{STORAGE_APP}/profile/{user['user_id']}/{uuid.uuid4().hex}.{ext}", content, ctype)
        doc["path"] = res["path"]
    except Exception as e:  # storage outage: keep the photo in the database instead of failing the upload
        logger.warning("profile photo storage failed, using database: %s", e)
        doc["data"] = content
    await db.files.insert_one(doc)
    await db.files.update_many({"owner_id": user["user_id"], "kind": "user_profile", "file_id": {"$ne": file_id}}, {"$set": {"deleted": True, "deleted_at": now()}})
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"picture": file_id}})
    return {"file_id": file_id, "picture": file_id}


async def read_file_bytes(f: dict) -> bytes:
    if f.get("data") is not None:
        return f["data"]
    data, _ = await run_in_threadpool(get_object, f["path"])
    return data


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
    out = {k: s.get(k) for k in ("passenger_cancel_hours", "driver_cancel_hours", "cancellation_reasons", "instant_driver_approval",
                                 "featured_upi_id")}
    out["featured_price"] = s.get("featured_price", FEATURED_DEFAULT_PRICE)
    out["featured_days"] = FEATURED_DAYS
    out["pricing"] = pricing_rules(s)
    return out


# ---------------------------------------------------------------- driver verification & vehicles
DMY = r"^\d{2}-\d{2}-\d{4}$"


def valid_dmy(s: str) -> bool:
    try:
        datetime.strptime(s, "%d-%m-%Y")
        return True
    except ValueError:
        return False


class VerificationIn(BaseModel):
    vehicle_name: str = Field(min_length=2, max_length=80)
    licence_no: str = Field(min_length=8, max_length=20)
    licence_expiry: str = Field(pattern=DMY)
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
MAX_UPLOAD = 10 * 1024 * 1024
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
    if data[:5] == b"%PDF-":
        return "application/pdf", "pdf"
    return None


DOC_META = {
    # kind: (label, required, max files, pdf allowed)
    "licence_front": ("Driving licence (front)", True, 1, True),
    "licence_back": ("Driving licence (back)", True, 1, True),
    "id_proof": ("Aadhaar card", True, 1, True),
    "rc": ("Vehicle registration certificate (RC)", True, 1, True),
    "licence": ("Driving licence", False, 1, True),  # legacy single-sided licence (older accounts)
}
# The personal photo is managed only from the Profile screen (users.picture), never in driver verification.
UPLOAD_KINDS = [k for k in DOC_META if k != "licence"]
REQUIRED_KINDS = [k for k, m in DOC_META.items() if m[1]]
LOCKED_STATUSES = ("under_review", "approved")
FILE_OUT = {"_id": 0, "file_id": 1, "kind": 1, "content_type": 1, "size": 1, "original_name": 1, "created_at": 1}


async def active_files(uid: str) -> list:
    return await db.files.find({"owner_id": uid, "deleted": {"$ne": True}, "kind": {"$in": list(DOC_META)}}, FILE_OUT).sort("created_at", 1).to_list(60)


def missing_kinds(files: list) -> list:
    have = {f["kind"] for f in files}
    if "licence" in have:  # legacy accounts: single licence photo counts for both sides
        have |= {"licence_front", "licence_back"}
    return [k for k in REQUIRED_KINDS if k not in have]


async def sync_photo_map(uid: str):
    """driver_documents.photos keeps the primary file id per kind (used by badges & older screens)."""
    files = await active_files(uid)
    photos: dict = {}
    for f in files:
        photos.setdefault(f["kind"], f["file_id"])
    await db.driver_documents.update_one({"user_id": uid}, {"$set": {"photos": photos, "user_id": uid}}, upsert=True)


async def add_history(uid: str, action: str, by: str, note: str = ""):
    await db.driver_verification_events.insert_one({"event_id": nid("dve"), "user_id": uid, "action": action, "by": by, "note": note, "at": now()})


@api.post("/driver/documents/{kind}")
async def upload_document(kind: str, request: Request, file: UploadFile = File(...), user: dict = Depends(get_user)):
    if kind not in UPLOAD_KINDS:
        raise HTTPException(400, "Unknown document type")
    if user.get("driver_status") in LOCKED_STATUSES:
        raise HTTPException(400, "Documents are locked while your verification is pending or approved")
    await rate_limit(f"upload:{user['user_id']}", 60, 3600, "Too many uploads. Please try again later.")
    label, _, max_files, pdf_ok = DOC_META[kind]
    data = await file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "File is too large. The maximum size is 10 MB.")
    if len(data) < 1024:
        raise HTTPException(400, "This file looks empty or damaged. Please choose another one.")
    sniffed = sniff_image(data)
    if not sniffed:
        raise HTTPException(400, f"{label}: please upload a JPG or PNG{' or PDF' if pdf_ok else ''} file")
    ctype, ext = sniffed
    if ctype == "application/pdf" and not pdf_ok:
        raise HTTPException(400, f"{label} must be a photo (JPG or PNG), not a PDF")
    digest = hashlib.sha256(data).hexdigest()
    dup = await db.files.find_one({"owner_id": user["user_id"], "kind": kind, "sha256": digest, "deleted": {"$ne": True}}, FILE_OUT)
    if dup:
        return {**dup, "duplicate": True}
    existing = await db.files.count_documents({"owner_id": user["user_id"], "kind": kind, "deleted": {"$ne": True}})
    if max_files > 1 and existing >= max_files:
        raise HTTPException(400, f"You can upload up to {max_files} files for {label}. Delete one first.")
    
    fid = nid("file")
    path = f"{STORAGE_APP}/driver-docs/{user['user_id']}/{kind}-{uuid.uuid4().hex}.{ext}"
    
    # Try to use Emergent storage, fallback to MongoDB if it fails
    storage_path = None
    try:
        res = await run_in_threadpool(put_object, path, data, ctype)
        storage_path = res["path"]
    except Exception as e:
        logger.warning(f"Emergent storage failed for {kind}, falling back to MongoDB: {e}")
        # Store data directly in MongoDB as fallback
        storage_path = None
    
    doc = {"file_id": fid, "owner_id": user["user_id"], "path": storage_path, "kind": kind, "content_type": ctype, "size": len(data),
           "sha256": digest, "original_name": (file.filename or "")[:120], "created_at": now()}
    
    # If storage failed, store data in MongoDB
    if storage_path is None:
        doc["data"] = data
    
    await db.files.insert_one(doc)
    if max_files == 1:
        await db.files.update_many({"owner_id": user["user_id"], "kind": kind, "file_id": {"$ne": fid}}, {"$set": {"deleted": True, "deleted_at": now()}})
        if kind in ("licence_front", "licence_back"):
            await db.files.update_many({"owner_id": user["user_id"], "kind": "licence"}, {"$set": {"deleted": True, "deleted_at": now()}})
    await sync_photo_map(user["user_id"])
    return {k: doc[k] for k in ("file_id", "kind", "content_type", "size", "original_name", "created_at")}


@api.delete("/driver/documents/file/{fid}")
async def delete_document(fid: str, user: dict = Depends(get_user)):
    if user.get("driver_status") in LOCKED_STATUSES:
        raise HTTPException(400, "Documents are locked while your verification is pending or approved")
    r = await db.files.update_one({"file_id": fid, "owner_id": user["user_id"], "deleted": {"$ne": True}}, {"$set": {"deleted": True, "deleted_at": now()}})
    if not r.matched_count:
        raise HTTPException(404, "File not found")
    await sync_photo_map(user["user_id"])
    return {"ok": True}


@api.get("/files/{fid}")
async def get_file(fid: str, request: Request, token: Optional[str] = None):
    auth = request.headers.get("Authorization", "")
    tok = auth[7:] if auth.startswith("Bearer ") else token
    if not tok:
        raise HTTPException(401, "Not authenticated")
    user = await user_from_token(tok)
    f = await db.files.find_one({"file_id": fid}, {"_id": 0})
    is_admin = user.get("role") == "admin" and user.get("_admin_session")
    if not f or (f["owner_id"] != user["user_id"] and not is_admin) or (f.get("deleted") and not is_admin):
        raise HTTPException(404, "File not found")
    
    # Check if file is stored in MongoDB (fallback)
    if "data" in f:
        data = f["data"]
        ctype = f.get("content_type") or "application/octet-stream"
    else:
        # Try to get from Emergent storage
        try:
            data, ctype = await run_in_threadpool(get_object, f["path"])
        except Exception as e:
            logger.error(f"Failed to get file {fid} from storage: {e}")
            raise HTTPException(404, "File not found")
    
    if is_admin and f["owner_id"] != user["user_id"]:
        await audit(user["user_id"], "admin.document_view", f["owner_id"], {"file_id": fid, "kind": f.get("kind")})
    ct = f.get("content_type") or ctype
    headers = {"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"}
    if ct == "application/pdf":
        headers["Content-Disposition"] = f'inline; filename="{f.get("kind", "document")}.pdf"'
    else:
        headers["Content-Security-Policy"] = "default-src 'none'; sandbox"
    return Response(content=data, media_type=ct, headers=headers)


@api.get("/driver/profile")
async def driver_profile(user: dict = Depends(get_user)):
    doc = await db.driver_documents.find_one({"user_id": user["user_id"]}, {"_id": 0}) or {}
    if doc:
        doc["licence_no"] = mask(doc.get("licence_no", ""))
        doc["rc_no"] = mask(doc.get("rc_no", ""))
    files = await active_files(user["user_id"])
    vehicles = await db.vehicles.find({"owner_id": user["user_id"], "deleted": {"$ne": True}}, {"_id": 0}).to_list(20)
    kinds = [{"kind": k, "label": DOC_META[k][0], "required": DOC_META[k][1], "max": DOC_META[k][2], "pdf": DOC_META[k][3]} for k in UPLOAD_KINDS]
    return {"status": user.get("driver_status", "not_submitted"), "documents": doc, "vehicles": vehicles, "files": files,
            "kinds": kinds, "missing": missing_kinds(files), "locked": user.get("driver_status") in LOCKED_STATUSES}


@api.post("/driver/verification")
async def submit_verification(body: VerificationIn, user: dict = Depends(get_user)):
    if user.get("driver_status") in LOCKED_STATUSES:
        raise HTTPException(400, "Verification already submitted")
    missing = missing_kinds(await active_files(user["user_id"]))
    if missing:
        raise HTTPException(400, f"Please upload: {', '.join(DOC_META[k][0] for k in missing)}")
    phone = re.sub(r"\D", "", user.get("phone") or "")[-10:]
    if not re.fullmatch(r"[6-9]\d{9}", phone):
        raise HTTPException(400, "Add a valid 10-digit mobile number in Profile → Edit profile first. We use your registered number for verification.")
    if not (re.fullmatch(DMY, body.licence_expiry) and valid_dmy(body.licence_expiry)):
        raise HTTPException(400, "Licence expiry: enter a real date as DD-MM-YYYY")
    if datetime.strptime(body.licence_expiry, "%d-%m-%Y").date() < datetime.now(IST).date():
        raise HTTPException(400, "Your driving licence has expired. Please renew it before applying.")
    prev = user.get("driver_status", "not_submitted")
    settings = await get_settings()
    status = "approved" if settings.get("instant_driver_approval") else "under_review"
    doc = {**body.model_dump(), "licence_no": body.licence_no.upper().replace(" ", ""), "rc_no": body.rc_no.upper().replace(" ", ""),
           "vehicle_name": body.vehicle_name.strip(), "phone": phone,
           "user_id": user["user_id"], "submitted_at": now(), "admin_note": "", "reviewed_at": None}
    await db.driver_documents.update_one({"user_id": user["user_id"]}, {"$set": doc}, upsert=True)
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"driver_status": status}})
    resub = prev in ("rejected", "resubmit")
    await add_history(user["user_id"], "resubmitted" if resub else "submitted", user["user_id"])
    await admin_alert("resubmission" if resub else "verification_submitted",
                      f"{'Documents resubmitted' if resub else 'New driver verification'}: {user.get('name')}", user["user_id"])
    if status == "approved":
        await notify(user["user_id"], "driver_approved", {})
    await audit(user["user_id"], "driver.submit", user["user_id"], {"status": status})
    return {"status": status}


# Maximum passenger seats (driver excluded). SUV/MUV: driver enters the RC-approved seating minus the driver, up to 8.
SEAT_CAPS = {"hatchback": 3, "sedan": 3, "suv": 8, "muv": 8, "other": 3}
MILEAGE_DEFAULTS = {"hatchback": 18, "sedan": 16, "suv": 12, "muv": 13}


def seat_cap(vtype: Optional[str]) -> int:
    return SEAT_CAPS.get(vtype or "other", 3)


class VehicleIn(BaseModel):
    make: str = Field(min_length=2, max_length=40)
    model: str = Field(min_length=1, max_length=40)
    vtype: Literal["hatchback", "sedan", "suv", "muv"] = "sedan"
    color: str = Field(default="", max_length=20)
    reg_no: str = Field(min_length=6, max_length=15)
    seats: int = Field(ge=1, le=8)
    ac: bool = True
    luggage: Literal["small", "medium", "large"] = "medium"
    fuel_type: Literal["petrol", "diesel", "cng", "electric"] = "petrol"
    mileage: Optional[float] = Field(default=None, gt=0, le=60)  # km/l, km/kg (CNG) or km/kWh (EV)


@api.post("/vehicles")
async def add_vehicle(body: VehicleIn, user: dict = Depends(get_user)):
    if body.seats > seat_cap(body.vtype):
        raise HTTPException(400, f"A {body.vtype} can offer at most {seat_cap(body.vtype)} passenger seats (driver not counted)")
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
    pickup_pin: Optional["PinIn"] = None
    drop_pin: Optional["PinIn"] = None


class PinIn(BaseModel):
    lat: float = Field(ge=6, le=37.5)
    lng: float = Field(ge=68, le=97.5)


TripIn.model_rebuild()


async def road_route(pts: list, choice: int = 0) -> Optional[dict]:
    """Road route (OSRM on OpenStreetMap data, with mirror fallback). None if no routing provider answered."""
    res = await geo_router.route_options(pts, alternatives=True)
    if not res["source"].startswith("osrm"):
        return None
    return res["routes"][min(choice, len(res["routes"]) - 1)]


PRICING_DEFAULTS = {"rate_per_km": {"hatchback": 6.0, "sedan": 7.0, "suv": 9.0, "muv": 9.0}, "base_fare": 0, "min_fare": 50}


def pricing_rules(settings: dict) -> dict:
    p = settings.get("pricing") or {}
    return {"rate_per_km": {**PRICING_DEFAULTS["rate_per_km"], **(p.get("rate_per_km") or {})},
            "base_fare": p.get("base_fare", PRICING_DEFAULTS["base_fare"]), "min_fare": p.get("min_fare", PRICING_DEFAULTS["min_fare"]),
            "max_price_factor": settings.get("max_price_factor", 1.5)}


def price_suggestion(km: float, vtype: Optional[str], seats: int, settings: dict) -> dict:
    """Suggested contribution per person (not a fuel cost): distance × vehicle rate ÷ passenger seats + base fare, admin-configurable."""
    r = pricing_rules(settings)
    rate = r["rate_per_km"].get(vtype or "sedan", r["rate_per_km"]["sedan"])
    rec = max(r["min_fare"], math.floor(km * rate / max(1, seats) + r["base_fare"] + 0.5))
    return {"kind": "suggested", "distance_km": km, "vtype": vtype, "seats": seats, "rate_per_km": rate, "base_fare": r["base_fare"],
            "recommended": rec, "max": max(rec, math.floor(rec * r["max_price_factor"] + 0.5))}


@api.get("/pricing/suggest")
async def pricing_suggest(km: float = Query(gt=0, le=5000), vtype: str = "sedan", seats: int = Query(ge=1, le=8)):
    return price_suggestion(km, vtype, seats, await get_settings())


def cost_breakdown(km: float, mileage: float, fuel_price: float, tolls: float, maint: float, seats: int, mode: str, fuel_type: str) -> dict:
    """Fuel = km / mileage × price; total = fuel + tolls; per person = total / passenger seats offered (driver never counted)."""
    fuel_units = km / mileage
    fuel_cost = fuel_units * fuel_price
    maint, mode = 0, "passenger"
    maint_cost = 0
    total = fuel_cost + tolls
    sharers = seats
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
            "pickup_pin": body.pickup_pin.model_dump() if body.pickup_pin else None, "drop_pin": body.drop_pin.model_dump() if body.drop_pin else None,
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
    max_seats = min(vehicle["seats"], seat_cap(vehicle.get("vtype")))
    if body.seats > max_seats:
        raise HTTPException(400, f"This {vehicle.get('vtype') or 'vehicle'} can offer at most {max_seats} passenger seats (driver not counted)")
    if body.origin.loc_id == body.destination.loc_id:
        raise HTTPException(400, "Origin and destination must be different")
    trip = await build_trip(body, user, vehicle)
    if trip["departure_at"] < now():
        raise HTTPException(400, "Departure must be in the future")
    settings = await get_settings()
    sug = price_suggestion(trip["distance_km"], vehicle.get("vtype"), body.seats, settings)
    if body.price > sug["max"]:
        raise HTTPException(400, f"Price is above the allowed maximum of ₹{sug['max']} per person for this ride")
    trip["price_suggestion"] = sug
    trips = [trip]
    if body.return_date and body.return_time:
        rb = body.model_copy(update={"origin": body.destination, "destination": body.origin, "stops": list(reversed(body.stops)),
                                     "pickup_point": body.drop_point, "drop_point": body.pickup_point, "date": body.return_date, "time": body.return_time})
        rt = await build_trip(rb, user, vehicle)
        if rt["departure_at"] <= trip["departure_at"]:
            raise HTTPException(400, "Return must be after the outbound departure")
        rt["price_suggestion"] = price_suggestion(rt["distance_km"], vehicle.get("vtype"), body.seats, settings)
        if body.price > rt["price_suggestion"]["max"]:
            raise HTTPException(400, f"Price is above the allowed maximum of ₹{rt['price_suggestion']['max']} per person for the return ride")
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
        veh = await db.vehicles.find_one({"vehicle_id": trip["vehicle"]["vehicle_id"]}, {"_id": 0, "seats": 1, "vtype": 1}) or {}
        max_seats = min(veh.get("seats", 8), seat_cap(veh.get("vtype") or trip["vehicle"].get("vtype")))
        if body.seats > max_seats:
            raise HTTPException(400, f"This vehicle can offer at most {max_seats} passenger seats")
        upd["seats_total"] = body.seats
        upd["seats_available"] = body.seats - booked
    if "price" in upd and await db.bookings.count_documents({"trip_id": tid, "status": {"$in": ["pending", "confirmed"]}}):
        raise HTTPException(400, "Price cannot change after bookings are made")
    if body.seats is not None or body.price is not None:
        seats = upd.get("seats_total", trip["seats_total"])
        veh = await db.vehicles.find_one({"vehicle_id": trip["vehicle"]["vehicle_id"]}, {"_id": 0, "vtype": 1}) or {}
        sug = price_suggestion(trip["distance_km"], veh.get("vtype") or trip["vehicle"].get("vtype"), seats, await get_settings())
        price = upd.get("price", trip["price"])
        if price > sug["max"]:
            raise HTTPException(400, f"Price is above the allowed maximum of ₹{sug['max']} per person for {seats} seat(s).")
        upd["price_suggestion"] = sug
    await db.trips.update_one({"trip_id": tid}, {"$set": upd})
    async for b in db.bookings.find({"trip_id": tid, "status": {"$in": ["pending", "confirmed"]}}, {"_id": 0}):
        await notify(b["passenger_id"], "trip_updated", {"route": b["route"]}, b["booking_id"])
    return await db.trips.find_one({"trip_id": tid}, TRIP_OUT)


async def enrich_trips(trips: list) -> list:
    ids = list({t["driver_id"] for t in trips})
    drivers = {u["user_id"]: u for u in await db.users.find({"user_id": {"$in": ids}}, PUBLIC_FIELDS).to_list(len(ids) or 1)}
    for d in drivers.values():
        d["has_photo"] = str(d.get("picture") or "").startswith("file_") and d.get("driver_status") == "approved"
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
    trip["driver_reviews"] = await db.reviews.find(
        {"target_id": trip["driver_id"], "role": "driver", "hidden": {"$ne": True}},
        {"_id": 0, "review_id": 1, "reviewer_name": 1, "rating": 1, "comment": 1, "route": 1, "created_at": 1},
    ).sort("created_at", -1).to_list(5)
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
    await admin_alert("booking", f"New booking {b['booking_id']} · {b['route']}", b["booking_id"])
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
    await admin_alert("complaint", f"New {body.type} ticket from {user['name']}", t["ticket_id"])
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
            "monthly": monthly, "growth": growth, "top_drivers": top, "top_routes": routes,
            "passengers_registered": await db.users.count_documents({"role": "user", "driver_status": "not_submitted"}),
            "rejected": await db.users.count_documents({"driver_status": "rejected"}),
            "resubmit": await db.users.count_documents({"driver_status": "resubmit"}),
            "rides_active": await db.trips.count_documents({"status": {"$in": ["scheduled", "started"]}}),
            "rides_completed": await db.trips.count_documents({"status": "completed"}),
            "rides_cancelled": await db.trips.count_documents({"status": "cancelled"}),
            "complaints_open": await db.tickets.count_documents({"status": {"$ne": "resolved"}}),
            "complaints_total": await db.tickets.count_documents({}),
            "new_7d": await db.users.count_documents({"created_at": {"$gt": now() - timedelta(days=7)}}),
            "unread_alerts": await db.admin_notifications.count_documents({"read": False})}


@api.get("/admin/users")
async def admin_users(q: str = "", _: dict = Depends(get_admin)):
    filt = {"$or": [{"name": {"$regex": re.escape(q), "$options": "i"}}, {"email": {"$regex": re.escape(q), "$options": "i"}}, {"phone": {"$regex": re.escape(re.sub(r"\D", "", q) or q)}}, {"phone_e164": {"$regex": re.escape(re.sub(r"\D", "", q) or q)}}]} if q else {}
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
async def admin_drivers(status: str = "under_review", q: str = "", _: dict = Depends(get_admin)):
    filt: dict = {"driver_status": {"$ne": "not_submitted"}} if status == "all" else {"driver_status": status}
    if q:
        rx = {"$regex": re.escape(q.strip()), "$options": "i"}
        filt["$or"] = [{"name": rx}, {"email": rx}, {"phone": rx}, {"user_id": rx}]
    users = await db.users.find(filt, USER_PRIVATE).sort("created_at", -1).to_list(200)
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
    filt = {"$or": [{"name": {"$regex": re.escape(q), "$options": "i"}}, {"email": {"$regex": re.escape(q), "$options": "i"}}, {"phone": {"$regex": re.escape(re.sub(r"\D", "", q) or q)}}, {"phone_e164": {"$regex": re.escape(re.sub(r"\D", "", q) or q)}}]} if q else {}
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
    note: str = Field(default="", max_length=500)


@api.post("/admin/drivers/{uid}/review")
async def admin_review_driver(uid: str, body: DriverReviewIn, admin: dict = Depends(get_admin)):
    doc = await db.driver_documents.find_one({"user_id": uid}, {"_id": 0, "submitted_at": 1})
    target = await db.users.find_one({"user_id": uid}, {"_id": 0, "driver_status": 1})
    if not doc or not doc.get("submitted_at") or not target:
        raise HTTPException(400, "This user has not submitted verification details")
    if target["driver_status"] not in ("under_review", "approved"):
        raise HTTPException(400, "Only pending or approved verifications can be reviewed")
    note = body.note.strip()
    if body.decision != "approved" and len(note) < 5:
        raise HTTPException(400, "Please add a reason (at least 5 characters) so the driver knows what to fix")
    await db.users.update_one({"user_id": uid}, {"$set": {"driver_status": body.decision}})
    await db.driver_documents.update_one({"user_id": uid}, {"$set": {"admin_note": note, "reviewed_at": now(), "reviewed_by": admin["user_id"]}})
    await db.vehicles.update_many({"owner_id": uid}, {"$set": {"verified": body.decision == "approved"}})
    await add_history(uid, body.decision, admin["user_id"], note)
    ntype = {"approved": "driver_approved", "rejected": "driver_rejected", "resubmit": "driver_resubmit"}[body.decision]
    await notify(uid, ntype, {"note": note})
    await notify_driver_status_email(uid, body.decision, note)
    await audit(admin["user_id"], f"driver.{body.decision}", uid, {"note": note})
    return {"ok": True, "status": body.decision}


@api.get("/admin/drivers/{uid}/detail")
async def admin_driver_detail(uid: str, admin: dict = Depends(get_admin)):
    u = await db.users.find_one({"user_id": uid}, USER_PRIVATE)
    if not u:
        raise HTTPException(404, "Driver not found")
    files = await db.files.find({"owner_id": uid, "kind": {"$in": list(DOC_META)}}, {**FILE_OUT, "deleted": 1}).sort("created_at", -1).to_list(100)
    history = await db.driver_verification_events.find({"user_id": uid}, {"_id": 0}).sort("at", -1).to_list(100)
    names = {a["user_id"]: a["name"] for a in await db.users.find({"user_id": {"$in": list({h["by"] for h in history})}}, {"_id": 0, "user_id": 1, "name": 1}).to_list(50)}
    for h in history:
        h["by_name"] = names.get(h["by"], h["by"])
    await audit(admin["user_id"], "admin.document_review_open", uid)
    return {"user": u, "documents": await db.driver_documents.find_one({"user_id": uid}, {"_id": 0}) or {},
            "files": [f for f in files if not f.get("deleted")], "removed_files": [f for f in files if f.get("deleted")][:20],
            "labels": {k: m[0] for k, m in DOC_META.items()}, "missing": missing_kinds([f for f in files if not f.get("deleted")]),
            "history": history, "vehicles": await db.vehicles.find({"owner_id": uid, "deleted": {"$ne": True}}, {"_id": 0}).to_list(10),
            "trips": await db.trips.count_documents({"driver_id": uid}),
            "recent_trips": await db.trips.find({"driver_id": uid}, {"_id": 0, "trip_id": 1, "origin.name": 1, "destination.name": 1, "date": 1, "time": 1, "status": 1, "price": 1}).sort("departure_at", -1).to_list(10)}


@api.get("/admin/passengers/{uid}/detail")
async def admin_passenger_detail(uid: str, admin: dict = Depends(get_admin)):
    u = await db.users.find_one({"user_id": uid}, USER_PRIVATE)
    if not u:
        raise HTTPException(404, "Passenger not found")
    rides = await db.bookings.find({"passenger_id": uid}, {"_id": 0, "active_key": 0}).sort("created_at", -1).to_list(100)
    drivers = {d["user_id"]: d["name"] for d in await db.users.find({"user_id": {"$in": list({r["driver_id"] for r in rides})}}, {"_id": 0, "user_id": 1, "name": 1}).to_list(100)}
    for r in rides:
        r["driver_name"] = drivers.get(r["driver_id"], "")
    tickets = await db.tickets.find({"user_id": uid}, {"_id": 0}).sort("created_at", -1).to_list(50)
    await audit(admin["user_id"], "admin.passenger_view", uid)
    return {"user": u, "rides": rides, "tickets": tickets,
            "stats": {"total": len(rides), "completed": sum(r["status"] == "completed" for r in rides),
                      "cancelled": sum(r["status"] == "cancelled" for r in rides),
                      "spent": sum(r["fare_total"] for r in rides if r["status"] == "completed")}}


@api.get("/admin/rides")
async def admin_rides(status: Literal["active", "completed", "cancelled", "all"] = "active", q: str = "", _: dict = Depends(get_admin)):
    filt: dict = {"status": {"active": {"$in": ["scheduled", "started"]}, "completed": "completed", "cancelled": "cancelled"}[status]} if status != "all" else {}
    if q:
        rx = {"$regex": re.escape(q), "$options": "i"}
        filt["$or"] = [{"origin.name": rx}, {"destination.name": rx}, {"trip_id": rx}]
    trips = await db.trips.find(filt, {"_id": 0, "trip_id": 1, "driver_id": 1, "origin.name": 1, "destination.name": 1, "pickup_point": 1, "drop_point": 1,
                                       "date": 1, "time": 1, "price": 1, "status": 1, "seats_total": 1, "seats_available": 1, "created_at": 1,
                                       "cancel_reason": 1, "vehicle.make": 1, "vehicle.model": 1}).sort("departure_at", -1).to_list(150)
    tids = [t["trip_id"] for t in trips]
    bookings = await db.bookings.find({"trip_id": {"$in": tids}}, {"_id": 0, "booking_id": 1, "trip_id": 1, "passenger_id": 1, "seats": 1, "fare_total": 1, "status": 1, "created_at": 1}).to_list(1000)
    uids = list({t["driver_id"] for t in trips} | {b["passenger_id"] for b in bookings})
    users = {u["user_id"]: u for u in await db.users.find({"user_id": {"$in": uids}}, {"_id": 0, "user_id": 1, "name": 1, "phone": 1}).to_list(len(uids) or 1)}
    for t in trips:
        t["driver"] = users.get(t["driver_id"], {})
        t["bookings"] = [{**b, "passenger": users.get(b["passenger_id"], {})} for b in bookings if b["trip_id"] == t["trip_id"]]
        t["booked_value"] = sum(b["fare_total"] for b in t["bookings"] if b["status"] in ("confirmed", "started", "completed"))
    return trips


@api.get("/admin/notifications")
async def admin_notifications(_: dict = Depends(get_admin)):
    rows = await db.admin_notifications.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return {"items": rows, "unread": await db.admin_notifications.count_documents({"read": False})}


@api.post("/admin/notifications/read")
async def admin_notifications_read(admin: dict = Depends(get_admin)):
    await db.admin_notifications.update_many({"read": False}, {"$set": {"read": True, "read_by": admin["user_id"], "read_at": now()}})
    return {"ok": True}


@api.get("/admin/activity")
async def admin_activity(_: dict = Depends(get_admin)):
    admins = [a["user_id"] for a in await db.users.find({"role": "admin"}, {"_id": 0, "user_id": 1}).to_list(50)]
    names = {a["user_id"]: a["name"] for a in await db.users.find({"role": "admin"}, {"_id": 0, "user_id": 1, "name": 1}).to_list(50)}
    rows = await db.audit_logs.find({"$or": [{"actor": {"$in": admins}}, {"action": {"$regex": "^admin\\."}}]}, {"_id": 0}).sort("created_at", -1).to_list(200)
    for r in rows:
        r["actor_name"] = names.get(r["actor"], r["actor"])
    return rows


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


class PricingIn(BaseModel):
    rate_per_km: Dict[Literal["hatchback", "sedan", "suv", "muv"], float]
    base_fare: int = Field(default=0, ge=0, le=2000)
    min_fare: int = Field(default=50, ge=0, le=2000)

    @field_validator("rate_per_km")
    @classmethod
    def _rates(cls, v):
        if any(not (0.5 <= x <= 100) for x in v.values()):
            raise ValueError("Rate per km must be between 0.5 and 100")
        return v


class SettingsIn(BaseModel):
    instant_driver_approval: Optional[bool] = None
    passenger_cancel_hours: Optional[int] = Field(default=None, ge=0, le=72)
    driver_cancel_hours: Optional[int] = Field(default=None, ge=0, le=72)
    maintenance_per_km: Optional[float] = Field(default=None, ge=0, le=20)
    max_price_factor: Optional[float] = Field(default=None, ge=1, le=3)
    featured_price: Optional[int] = Field(default=None, ge=0, le=100000)
    featured_upi_id: Optional[str] = Field(default=None, max_length=80)
    mileage_defaults: Optional[Dict[Literal["hatchback", "sedan", "suv", "muv"], float]] = None
    pricing: Optional[PricingIn] = None

    @field_validator("mileage_defaults")
    @classmethod
    def _mil(cls, v):
        if v and any(not (3 <= x <= 60) for x in v.values()):
            raise ValueError("Mileage must be between 3 and 60 km per litre")
        return v


@api.get("/admin/settings")
async def admin_get_settings(_: dict = Depends(get_admin)):
    return await get_settings()


@api.put("/admin/settings")
async def admin_put_settings(body: SettingsIn, admin: dict = Depends(get_admin)):
    upd = {k: v for k, v in body.model_dump().items() if v is not None}
    if body.pricing:
        upd["pricing"] = body.pricing.model_dump()
    await db.settings.update_one({"key": "platform"}, {"$set": upd}, upsert=True)
    await audit(admin["user_id"], "settings.update", "platform", upd)
    return await get_settings()


# ---------------------------------------------------------------- featured rides (paid by UPI to the platform, admin approves)
FEATURED_DAYS = 7
FEATURED_DEFAULT_PRICE = 199
FEATURE_OUT = {"_id": 0}


class FeatureIn(BaseModel):
    payment_ref: str = Field(min_length=6, max_length=40, pattern=r"^[A-Za-z0-9\-]+$")


@api.get("/trips/{tid}/feature")
async def my_trip_feature(tid: str, user: dict = Depends(get_user)):
    return await db.featured.find_one({"trip_id": tid, "driver_id": user["user_id"]}, FEATURE_OUT, sort=[("requested_at", -1)])


@api.post("/trips/{tid}/feature")
async def request_feature(tid: str, body: FeatureIn, user: dict = Depends(get_user)):
    trip = await db.trips.find_one({"trip_id": tid, "driver_id": user["user_id"]}, {"_id": 0})
    if not trip:
        raise HTTPException(404, "Trip not found")
    if trip["status"] != "scheduled" or trip["departure_at"].replace(tzinfo=timezone.utc) <= now():
        raise HTTPException(400, "Only upcoming rides can be featured")
    if trip["seats_available"] <= 0:
        raise HTTPException(400, "This ride is full, so it can't be featured")
    s = await get_settings()
    if not s.get("featured_upi_id"):
        raise HTTPException(400, "Featured spots are not open yet. Please try again later.")
    if await db.featured.find_one({"trip_id": tid, "$or": [{"status": "pending"}, {"status": "active", "expires_at": {"$gt": now()}}]}):
        raise HTTPException(409, "This ride already has a featured request")
    doc = {"feature_id": nid("fea"), "trip_id": tid, "driver_id": user["user_id"], "driver_name": user["name"],
           "route": route_label(trip), "date": trip["date"], "time": trip["time"],
           "amount": s.get("featured_price", FEATURED_DEFAULT_PRICE), "days": FEATURED_DAYS,
           "payment_ref": body.payment_ref.upper(), "status": "pending", "admin_note": "",
           "requested_at": now(), "approved_at": None, "expires_at": None}
    await db.featured.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api.get("/featured")
async def featured_rides():
    feats = await db.featured.find({"status": "active", "expires_at": {"$gt": now()}}, {"_id": 0, "trip_id": 1, "expires_at": 1}).to_list(50)
    if not feats:
        return []
    ids = [f["trip_id"] for f in feats]
    out_proj = {k: v for k, v in TRIP_OUT.items()}
    rows = await db.trips.find({"trip_id": {"$in": ids}, "status": "scheduled", "seats_available": {"$gt": 0},
                                "departure_at": {"$gt": now()}}, out_proj).sort("departure_at", 1).to_list(10)
    return await enrich_trips(rows)


@api.get("/admin/featured")
async def admin_featured(status: str = "pending", _: dict = Depends(get_admin)):
    q: dict = {"status": status}
    if status == "active":
        q["expires_at"] = {"$gt": now()}
    elif status == "ended":
        q = {"$or": [{"status": "ended"}, {"status": "active", "expires_at": {"$lte": now()}}]}
    return await db.featured.find(q, FEATURE_OUT).sort("requested_at", -1).to_list(200)


class FeatureReviewIn(BaseModel):
    note: str = Field(default="", max_length=300)


@api.post("/admin/featured/{fid}/{action}")
async def admin_review_feature(fid: str, action: Literal["approve", "reject", "end"], body: FeatureReviewIn, admin: dict = Depends(get_admin)):
    f = await db.featured.find_one({"feature_id": fid}, FEATURE_OUT)
    if not f:
        raise HTTPException(404, "Request not found")
    if action in ("approve", "reject") and f["status"] != "pending":
        raise HTTPException(400, "Only pending requests can be reviewed")
    if action == "end" and f["status"] != "active":
        raise HTTPException(400, "Only active spots can be ended")
    upd = {"admin_note": body.note, "reviewed_by": admin["user_id"]}
    if action == "approve":
        upd.update(status="active", approved_at=now(), expires_at=now() + timedelta(days=FEATURED_DAYS))
    elif action == "reject":
        upd.update(status="rejected")
    else:
        upd.update(status="ended", expires_at=now())
    await db.featured.update_one({"feature_id": fid}, {"$set": upd})
    await audit(admin["user_id"], f"featured.{action}", fid)
    if action != "end":
        await notify(f["driver_id"], f"featured_{'approved' if action == 'approve' else 'rejected'}",
                     {"route": f["route"], "days": FEATURED_DAYS})
    return {"ok": True}


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
        doc["must_change_password"] = True
        await db.users.insert_one(doc)
    # migration: an admin who still uses the bootstrap password from the environment must replace it
    await db.users.update_many({"role": "admin", "must_change_password": {"$exists": False}}, {"$set": {"must_change_password": True}})
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
    u = await db.users.find_one({"user_id": uid}, {"_id": 0, "driver_status": 1, "picture": 1})
    pro = await db.pro_drivers.find_one({"user_id": uid, "status": "approved"}, {"_id": 1})
    fid = (u or {}).get("picture")
    if not str(fid or "").startswith("file_") or not (pro or (u and u.get("driver_status") == "approved")):
        raise HTTPException(404, "No verified photo")
    f = await db.files.find_one({"file_id": fid, "owner_id": uid, "deleted": {"$ne": True}}, {"_id": 0})
    if not f:
        raise HTTPException(404, "No verified photo")
    return Response(content=await read_file_bytes(f), media_type=f.get("content_type") or "image/jpeg",
                    headers={"Cache-Control": "public, max-age=3600", "X-Content-Type-Options": "nosniff"})


async def has_badge_photo(uid: str) -> bool:
    u = await db.users.find_one({"user_id": uid}, {"_id": 0, "picture": 1})
    return str((u or {}).get("picture") or "").startswith("file_")


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
        unread = await db.messages.count_documents({"booking_id": b["booking_id"], "sender_id": {"$nin": [uid, "system"]}, "read_by": {"$ne": uid}})
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
    return {"prices": out, "maintenance_per_km": 0, "max_price_factor": s.get("max_price_factor", 1.5),
            "mileage_defaults": {**MILEAGE_DEFAULTS, **(s.get("mileage_defaults") or {})}, "seat_caps": SEAT_CAPS,
            "live_source": None}  # no official live fuel-price feed is connected; prices are admin-maintained estimates


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
    photos = {**(doc.get("photos") or {})}
    if str(user.get("picture") or "").startswith("file_"):
        photos["profile"] = user["picture"]
    return {"profile": p, "photos": photos}


@api.post("/pro/register")
async def pro_register(body: ProDriverIn, user: dict = Depends(get_user)):
    if not (user.get("phone") and re.fullmatch(r"[6-9]\d{9}", user["phone"])):
        raise HTTPException(400, "Add a valid registered mobile number in your profile first")
    existing = await db.pro_drivers.find_one({"user_id": user["user_id"]}, {"_id": 0, "status": 1})
    if existing and existing["status"] in ("under_review", "approved"):
        raise HTTPException(400, "Local driver profile already submitted")
    doc = await db.driver_documents.find_one({"user_id": user["user_id"]}, {"_id": 0, "photos": 1}) or {}
    photos = {**(doc.get("photos") or {})}
    if str(user.get("picture") or "").startswith("file_"):
        photos["profile"] = user["picture"]
    missing = [k for k in ("profile", "licence") if not photos.get(k) and not (k == "licence" and photos.get("licence_front"))]
    if missing:
        raise HTTPException(400, "Please add your " + " and ".join("profile photo (Profile screen)" if k == "profile" else "licence photo" for k in missing))
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


@app.middleware("http")
async def system_error_alerts(request: Request, call_next):
    try:
        response = await call_next(request)
    except Exception as exc:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        await admin_alert("system_error", f"Server error on {request.method} {request.url.path}", None, {"error": str(exc)[:300]})
        return Response(content='{"detail":"Something went wrong on our side. Please try again."}', status_code=500, media_type="application/json")
    if response.status_code >= 500:
        await admin_alert("system_error", f"{response.status_code} on {request.method} {request.url.path}")
    return response
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
async def startup():
    await ensure_indexes()
    await seed()
    # one-time move: profile photos uploaded in the old driver-verification screen become the Profile photo
    async for d in db.driver_documents.find({"photos.profile": {"$exists": True}}, {"_id": 0, "user_id": 1, "photos.profile": 1}):
        await db.users.update_one({"user_id": d["user_id"], "picture": {"$not": {"$regex": "^file_"}}}, {"$set": {"picture": d["photos"]["profile"]}})
        await db.driver_documents.update_one({"user_id": d["user_id"]}, {"$unset": {"photos.profile": ""}})
    app.state.geo_sync = asyncio.create_task(geo_router.sync_loop())
    try:
        await run_in_threadpool(init_storage)
    except Exception as exc:
        logger.error("object storage init failed: %s", exc)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
