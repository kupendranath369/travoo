"""Iteration 6 smoke: boot/health, admin login, register/login, forgot-password regression."""
import os
import uuid

import pytest
import requests

BASE_URL = (os.environ.get("EXPO_BACKEND_URL") or os.environ.get("EXPO_PUBLIC_BACKEND_URL") or "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as fh:
        for line in fh:
            if line.startswith("EXPO_PUBLIC_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")
API = f"{BASE_URL}/api"
ADMIN_PW = os.environ.get("ADMIN_PASSWORD")


# Boot / settings
def test_settings_public():
    r = requests.get(f"{API}/settings", timeout=20)
    assert r.status_code == 200 and isinstance(r.json(), dict)


# Admin login
def test_admin_login():
    if not ADMIN_PW:
        pytest.skip("ADMIN_PASSWORD env not set")
    r = requests.post(f"{API}/auth/login", json={"email": "admin@travoo.in", "password": ADMIN_PW}, timeout=20)
    assert r.status_code == 200
    d = r.json()
    assert d["user"]["role"] == "admin" and d["token"]
    assert "password_hash" not in d["user"] and "_id" not in d["user"]


def test_wrong_password_401():
    r = requests.post(f"{API}/auth/login", json={"email": "admin@travoo.in", "password": "nope-nope"}, timeout=20)
    assert r.status_code == 401


# Register -> login -> me
def test_register_login_me():
    email = f"test_i6_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": "Passw0rd!x", "name": "TEST i6", "consent": True}, timeout=20)
    assert r.status_code == 200
    tok = requests.post(f"{API}/auth/login", json={"email": email, "password": "Passw0rd!x"}, timeout=20).json()["token"]
    me = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {tok}"}, timeout=20).json()
    assert me["email"] == email and me["driver_status"] == "not_submitted"


# Forgot password: unknown email must be 200 (no enumeration)
def test_forgot_password_unknown_email():
    r = requests.post(f"{API}/auth/forgot-password", json={"email": f"nobody_{uuid.uuid4().hex[:6]}@example.com"}, timeout=20)
    assert r.status_code == 200


# Forgot password: existing email -> currently 500 ('body' shadowed); must not leak reset_token
def test_forgot_password_existing_email():
    email = f"test_i6fp_{uuid.uuid4().hex[:8]}@example.com"
    requests.post(f"{API}/auth/register", json={"email": email, "password": "Passw0rd!x", "name": "TEST fp", "consent": True}, timeout=20)
    r = requests.post(f"{API}/auth/forgot-password", json={"email": email}, timeout=20)
    assert r.status_code == 200, f"forgot-password 500 for existing email: {r.text[:120]}"
    assert "reset_token" not in r.json(), "reset token leaked in API response"
