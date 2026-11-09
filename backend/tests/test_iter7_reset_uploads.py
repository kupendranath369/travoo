"""Iteration 7: password reset emails (forgot/reset) + driver document uploads + AI extract."""
import io
import os
import time
import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
import requests
from PIL import Image, ImageDraw, ImageFont
from pymongo import MongoClient

BASE_URL = (os.environ.get("EXPO_BACKEND_URL") or os.environ.get("EXPO_PUBLIC_BACKEND_URL") or "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("EXPO_PUBLIC_BACKEND_URL"):
                BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")
API = f"{BASE_URL}/api"

ENV = {}
with open("/app/backend/.env") as f:
    for line in f:
        if "=" in line:
            k, v = line.strip().split("=", 1)
            ENV[k] = v.strip().strip('"')
JWT_SECRET = ENV["JWT_SECRET"]
db = MongoClient(ENV["MONGO_URL"])[ENV["DB_NAME"]]
S = {}


def h(t):
    return {"Authorization": f"Bearer {t}"}


def font(size):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def doc_image(kind, fmt="JPEG"):
    """Realistic-looking document card with text/edges (not blank)."""
    img = Image.new("RGB", (900, 560), (235, 240, 250))
    d = ImageDraw.Draw(img)
    d.rectangle([10, 10, 890, 550], outline=(20, 60, 140), width=6)
    d.rectangle([10, 10, 890, 90], fill=(20, 80, 170))
    if kind == "licence":
        d.text((30, 30), "INDIAN UNION DRIVING LICENCE - KARNATAKA", fill="white", font=font(30))
        lines = ["DL No: KA0120200001234", "Name: RAHUL KUMAR SHARMA", "DOB: 15-08-1990",
                 "Valid Till (NT): 14-08-2040", "Address: 12 MG Road, Bengaluru"]
        d.rectangle([680, 120, 860, 340], fill=(180, 150, 120), outline="black", width=3)
        d.ellipse([725, 150, 815, 240], fill=(120, 90, 60))
    elif kind == "rc":
        d.text((30, 30), "CERTIFICATE OF REGISTRATION", fill="white", font=font(32))
        lines = ["Regn No: KA01AB1234", "Owner: RAHUL KUMAR SHARMA", "Maker: MARUTI SUZUKI",
                 "Model: DZIRE VXI", "Fuel: PETROL   Colour: WHITE"]
    elif kind == "vehicle":
        d.text((30, 30), "VEHICLE PHOTO", fill="white", font=font(32))
        d.rectangle([150, 260, 750, 420], fill=(200, 30, 30))
        d.polygon([(260, 260), (340, 170), (560, 170), (640, 260)], fill=(170, 20, 20))
        d.ellipse([220, 380, 320, 480], fill="black")
        d.ellipse([580, 380, 680, 480], fill="black")
        lines = []
    else:
        d.text((30, 30), "PROFILE PHOTO", fill="white", font=font(32))
        d.ellipse([350, 130, 550, 330], fill=(210, 170, 130))
        d.rectangle([300, 340, 600, 540], fill=(40, 70, 160))
        lines = []
    for i, ln in enumerate(lines):
        d.text((40, 130 + i * 70), ln, fill=(10, 10, 10), font=font(30))
    buf = io.BytesIO()
    img.save(buf, fmt)
    return buf.getvalue()


def register(prefix="TEST_iter7"):
    email = f"{prefix}_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": "Pass@12345", "name": "TEST Iter7", "consent": True}, timeout=20)
    assert r.status_code == 200, r.text
    d = r.json()
    return email, d["token"], d["user"]["user_id"]


def mint_reset(uid, ph=None, exp_delta=timedelta(hours=1), purpose="reset"):
    if ph is None:
        ph = db.users.find_one({"user_id": uid})["password_hash"][-12:]
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": uid, "purpose": purpose, "ph": ph, "exp": now + exp_delta, "iat": now}, JWT_SECRET, algorithm="HS256")


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    ids = S.get("created_uids", [])
    if ids:
        db.users.delete_many({"user_id": {"$in": ids}})
        db.driver_documents.delete_many({"user_id": {"$in": ids}})
        db.files.delete_many({"owner_id": {"$in": ids}})


# ---------- forgot-password
class TestForgotPassword:
    def test_forgot_existing_user_generic_no_token(self):
        r = requests.post(f"{API}/auth/forgot-password", json={"email": "delivered@resend.dev"}, timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "reset_token" not in d and "token" not in d
        assert d["message"] == "If the email exists, a reset link will be sent"
        time.sleep(1)
        log = open("/var/log/supervisor/backend.err.log").read()[-20000:]
        assert "Password reset email sent to delivered@resend.dev" in log, "send log line missing"

    def test_forgot_unknown_email_same_message(self):
        r = requests.post(f"{API}/auth/forgot-password", json={"email": f"TEST_nouser_{uuid.uuid4().hex[:6]}@example.com"}, timeout=30)
        assert r.status_code == 200
        assert r.json() == {"message": "If the email exists, a reset link will be sent"}

    def test_forgot_invalid_email_422(self):
        r = requests.post(f"{API}/auth/forgot-password", json={"email": "not-an-email"}, timeout=20)
        assert r.status_code == 422


# ---------- reset-password
class TestResetPassword:
    def test_login_token_rejected(self):
        email, tok, uid = register()
        S.setdefault("created_uids", []).append(uid)
        S["reset_user"] = (email, tok, uid)
        r = requests.post(f"{API}/auth/reset-password", json={"token": tok, "new_password": "NewPass@123"}, timeout=20)
        assert r.status_code == 400

    def test_garbage_and_expired_and_wrong_ph_rejected(self):
        _, _, uid = S["reset_user"]
        for t in ("garbage", mint_reset(uid, exp_delta=timedelta(seconds=-10)), mint_reset(uid, ph="xxxxxxxxxxxx")):
            r = requests.post(f"{API}/auth/reset-password", json={"token": t, "new_password": "NewPass@123"}, timeout=20)
            assert r.status_code == 400, r.text

    def test_short_password_422(self):
        _, _, uid = S["reset_user"]
        r = requests.post(f"{API}/auth/reset-password", json={"token": mint_reset(uid), "new_password": "short"}, timeout=20)
        assert r.status_code == 422

    def test_reset_token_cannot_auth_me(self):
        _, _, uid = S["reset_user"]
        r = requests.get(f"{API}/auth/me", headers=h(mint_reset(uid)), timeout=20)
        assert r.status_code == 401

    def test_valid_reset_then_single_use(self):
        email, _, uid = S["reset_user"]
        t = mint_reset(uid)
        r = requests.post(f"{API}/auth/reset-password", json={"token": t, "new_password": "NewPass@123"}, timeout=20)
        assert r.status_code == 200, r.text
        assert "reset" in r.json()["message"].lower()
        assert requests.post(f"{API}/auth/login", json={"email": email, "password": "Pass@12345"}, timeout=20).status_code == 401
        lr = requests.post(f"{API}/auth/login", json={"email": email, "password": "NewPass@123"}, timeout=20)
        assert lr.status_code == 200
        r2 = requests.post(f"{API}/auth/reset-password", json={"token": t, "new_password": "Another@123"}, timeout=20)
        assert r2.status_code == 400, "token reused"


# ---------- driver uploads + verification + AI extract
class TestDriverUploads:
    def test_setup_driver(self):
        email, tok, uid = register("TEST_iter7drv")
        S.setdefault("created_uids", []).append(uid)
        S["drv"] = tok

    def test_ai_extract_400_without_photos(self):
        r = requests.post(f"{API}/driver/ai-extract", headers=h(S["drv"]), timeout=30)
        assert r.status_code == 400
        assert "licence" in r.json()["detail"] and "rc" in r.json()["detail"]

    def test_verification_400_missing_photos(self):
        body = {"legal_name": "Rahul Kumar Sharma", "vehicle_name": "Maruti Dzire", "phone": "9876543210",
                "licence_no": "KA0120200001234", "licence_expiry": "14-08-2040", "rc_no": "KA01AB1234"}
        S["vbody"] = body
        r = requests.post(f"{API}/driver/verification", json=body, headers=h(S["drv"]), timeout=20)
        assert r.status_code == 400 and "upload" in r.json()["detail"].lower()

    def test_reject_non_image(self):
        r = requests.post(f"{API}/driver/documents/licence", headers=h(S["drv"]),
                          files={"file": ("x.jpg", b"hello not an image" * 10, "image/jpeg")}, timeout=30)
        assert r.status_code == 400

    def test_unknown_kind(self):
        r = requests.post(f"{API}/driver/documents/passport", headers=h(S["drv"]),
                          files={"file": ("x.jpg", doc_image("profile"), "image/jpeg")}, timeout=30)
        assert r.status_code == 400

    def test_upload_all_four(self):
        for k, fmt, mime in (("profile", "JPEG", "image/jpeg"), ("licence", "JPEG", "image/jpeg"),
                             ("rc", "PNG", "image/png"), ("vehicle", "JPEG", "image/jpeg")):
            r = requests.post(f"{API}/driver/documents/{k}", headers=h(S["drv"]),
                              files={"file": (f"{k}.{fmt.lower()}", doc_image(k, fmt), mime)}, timeout=60)
            assert r.status_code == 200, f"{k}: {r.text}"
            assert r.json()["kind"] == k and r.json()["file_id"].startswith("file")
        p = requests.get(f"{API}/driver/profile", headers=h(S["drv"]), timeout=20).json()
        photos = p["documents"]["photos"]
        assert set(photos) == {"profile", "licence", "rc", "vehicle"}
        S["photos"] = photos
        f = requests.get(f"{API}/files/{photos['licence']}", headers=h(S["drv"]), timeout=30)
        assert f.status_code == 200 and f.headers["content-type"].startswith("image/jpeg")

    def test_ai_extract_reads_fields(self):
        t0 = time.time()
        r = requests.post(f"{API}/driver/ai-extract", headers=h(S["drv"]), timeout=120)
        print("AI extract", round(time.time() - t0, 1), "s", r.status_code, r.text)
        assert r.status_code == 200, r.text
        d = r.json()
        assert set(d) == {"legal_name", "licence_no", "licence_expiry", "rc_no", "vehicle_name"}
        assert d["licence_no"] == "KA0120200001234"
        assert d["rc_no"] == "KA01AB1234"
        assert "RAHUL" in d["legal_name"].upper()

    def test_submit_verification(self):
        r = requests.post(f"{API}/driver/verification", json=S["vbody"], headers=h(S["drv"]), timeout=20)
        assert r.status_code == 200, r.text
        assert r.json()["status"] in ("under_review", "approved")
        p = requests.get(f"{API}/driver/profile", headers=h(S["drv"]), timeout=20).json()
        assert p["status"] == r.json()["status"]
        assert p["documents"]["photos"] == S["photos"]

    def test_upload_locked_after_submit(self):
        r = requests.post(f"{API}/driver/documents/profile", headers=h(S["drv"]),
                          files={"file": ("p.jpg", doc_image("profile"), "image/jpeg")}, timeout=30)
        assert r.status_code == 400
