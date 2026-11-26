# Iter35: password reset email delivery via Emergent managed email (forgot/reset password)
import os
import re
import subprocess
import time
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", os.environ.get("REACT_APP_BACKEND_URL", "")).rstrip("/")
if not BASE_URL:
    for line in open("/app/frontend/.env"):
        if line.startswith("EXPO_PUBLIC_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")

MONGO = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
DB = MONGO[os.environ.get("DB_NAME", "travoo")]
DELIVERED = "delivered@resend.dev"
UNKNOWN = f"test_unknown_{uuid.uuid4().hex[:8]}@example.com"
RATE = f"test_rate_{uuid.uuid4().hex[:8]}@example.com"
STATE = {"created_user_id": None}


def clear_forgot_limits():
    # filtered delete: only forgot-password limiter keys (ip + our test emails)
    DB.rate_limits.delete_many({"key": {"$regex": r"^forgot:(ip:|email:(delivered@resend\.dev|test_|admin@travoo\.in))"}})


@pytest.fixture(scope="module", autouse=True)
def setup_module_data():
    clear_forgot_limits()
    if not DB.users.find_one({"email": DELIVERED}):
        r = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": DELIVERED, "password": "TestPass123", "name": "TEST_Delivered", "consent": True})
        assert r.status_code == 200, r.text
        STATE["created_user_id"] = r.json()["user"]["user_id"]
    yield
    clear_forgot_limits()
    uid = STATE["created_user_id"]
    if uid:
        DB.password_resets.delete_many({"user_id": uid})
        DB.audit_logs.delete_many({"actor": uid}) if "audit_logs" in DB.list_collection_names() else None
        DB.users.delete_one({"user_id": uid})


# Existing deliverable user -> 200 accepted + password_resets doc accepted + log line
def test_forgot_existing_user_sends_email():
    r = requests.post(f"{BASE_URL}/api/auth/forgot-password", json={"email": DELIVERED})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "accepted"
    uid = DB.users.find_one({"email": DELIVERED})["user_id"]
    rec = DB.password_resets.find_one({"user_id": uid}, sort=[("created_at", -1)])
    assert rec["provider_status"] == "accepted"
    assert rec.get("provider_email_id")
    STATE["email_id"] = rec["provider_email_id"]
    time.sleep(1)
    logs = subprocess.run("tail -n 300 /var/log/supervisor/backend.*.log", shell=True, capture_output=True, text=True).stdout
    assert f"Email accepted id={rec['provider_email_id']}" in logs


# Unknown email -> same generic response (no enumeration)
def test_forgot_unknown_email_generic():
    r = requests.post(f"{BASE_URL}/api/auth/forgot-password", json={"email": UNKNOWN})
    assert r.status_code == 200
    known = requests.post  # noqa
    assert r.json()["status"] == "accepted"
    assert "If an account exists" in r.json()["message"]


# Invalid token rejected
def test_reset_invalid_token():
    r = requests.post(f"{BASE_URL}/api/auth/reset-password", json={"token": "x" * 40, "new_password": "NewPass1234"})
    assert r.status_code == 400
    assert "invalid" in r.json()["detail"].lower()


# Email HTML only has https links (no travoo:// scheme)
def test_reset_email_html_https_only():
    import sys
    sys.path.insert(0, "/app/backend")
    from server import reset_email_html
    from email_service import _assert_safe_email
    html = reset_email_html("Tester", "https://example.com/reset-password?token=abc", "travoo://reset-password?token=abc")
    hrefs = re.findall(r'href="([^"]+)"', html)
    assert hrefs and all(h.startswith("https://") for h in hrefs)
    assert "travoo://" not in html
    _assert_safe_email("Reset Your Travoo Password", html)


# Rate limit: 4th request for same email -> 429 (unknown email, no sends)
def test_rate_limit_fourth_request():
    codes = [requests.post(f"{BASE_URL}/api/auth/forgot-password", json={"email": RATE}).status_code for _ in range(4)]
    assert codes[:3] == [200, 200, 200], codes
    assert codes[3] == 429, codes


# Undeliverable address -> 502 friendly
def test_forgot_undeliverable_admin():
    clear_forgot_limits()
    r = requests.post(f"{BASE_URL}/api/auth/forgot-password", json={"email": "admin@travoo.in", "portal": "admin"})
    print("admin status", r.status_code, r.text)
    assert r.status_code == 502, r.text
    assert "couldn't send" in r.json()["detail"]
