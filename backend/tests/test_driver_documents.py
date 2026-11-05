"""TRAVOO driver document photos: upload, file access control, verification gating, admin listing/review."""
import io
import os
import uuid

import pytest
import requests

BASE_URL = (os.environ.get("EXPO_BACKEND_URL") or os.environ.get("EXPO_PUBLIC_BACKEND_URL") or "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("EXPO_PUBLIC_BACKEND_URL"):
                BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")
API = f"{BASE_URL}/api"
KINDS = ["profile", "licence", "rc", "vehicle"]
S = {}
# 1x1 PNG
PNG = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                    "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082")


def h(t):
    return {"Authorization": f"Bearer {t}"}


def login(e, p):
    r = requests.post(f"{API}/auth/login", json={"email": e, "password": p}, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["token"]


def register(prefix):
    email = f"test_{prefix}_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": "Passw0rd!x", "name": f"TEST_{prefix}", "consent": True}, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["token"], r.json()["user"]


def upload(tok, kind, data=PNG, ctype="image/png", name="a.png"):
    return requests.post(f"{API}/driver/documents/{kind}", headers=h(tok), files={"file": (name, io.BytesIO(data), ctype)}, timeout=120)


VERIF = {"legal_name": "TEST Driver Doc", "vehicle_name": "Maruti Swift", "phone": "9876543210",
         "licence_no": "KA0120230001234", "licence_expiry": "01-01-2030", "rc_no": "KA01AB9999"}


@pytest.fixture(scope="module", autouse=True)
def setup():
    S["admin"] = login("admin@travoo.in", "TravooAdmin@2026")
    S["tok"], S["user"] = register("docs")
    S["other"], _ = register("other")
    S["empty"], S["empty_user"] = register("empty")
    yield


# --- upload validation
def test_unknown_kind_rejected():
    r = upload(S["tok"], "passport")
    assert r.status_code == 400 and "Unknown" in r.json()["detail"]


def test_non_image_rejected():
    r = upload(S["tok"], "profile", b"hello", "text/plain", "a.txt")
    assert r.status_code == 400 and ("image" in r.json()["detail"].lower() or "photo" in r.json()["detail"].lower())


def test_too_large_rejected():
    r = upload(S["tok"], "profile", b"\x00" * (8 * 1024 * 1024 + 10), "image/jpeg", "big.jpg")
    assert r.status_code == 413, r.text


def test_upload_requires_auth():
    r = requests.post(f"{API}/driver/documents/profile", files={"file": ("a.png", io.BytesIO(PNG), "image/png")}, timeout=30)
    assert r.status_code == 401


# --- verification gating
def test_verification_requires_photos():
    upload_r = upload(S["tok"], "profile")
    assert upload_r.status_code == 200, upload_r.text
    S["fid_profile"] = upload_r.json()["file_id"]
    r = requests.post(f"{API}/driver/verification", headers=h(S["tok"]), json=VERIF, timeout=20)
    assert r.status_code == 400 and "Please upload" in r.json()["detail"] and "licence" in r.json()["detail"]


def test_verification_requires_vehicle_name():
    body = {k: v for k, v in VERIF.items() if k != "vehicle_name"}
    r = requests.post(f"{API}/driver/verification", headers=h(S["tok"]), json=body, timeout=20)
    assert r.status_code == 422


def test_upload_all_kinds():
    for k in KINDS[1:]:
        r = upload(S["tok"], k)
        assert r.status_code == 200, r.text
        assert r.json()["kind"] == k and r.json()["file_id"]
        S[f"fid_{k}"] = r.json()["file_id"]
    prof = requests.get(f"{API}/driver/profile", headers=h(S["tok"]), timeout=20).json()
    assert set(prof["documents"]["photos"].keys()) == set(KINDS)


# --- file access control
def test_file_owner_bearer():
    r = requests.get(f"{API}/files/{S['fid_profile']}", headers=h(S["tok"]), timeout=60)
    assert r.status_code == 200 and r.content == PNG and r.headers["content-type"].startswith("image/png")


def test_file_owner_query_token():
    r = requests.get(f"{API}/files/{S['fid_licence']}?token={S['tok']}", timeout=60)
    assert r.status_code == 200 and len(r.content) == len(PNG)


def test_file_admin():
    r = requests.get(f"{API}/files/{S['fid_rc']}", headers=h(S["admin"]), timeout=60)
    assert r.status_code == 200


def test_file_other_user_404():
    r = requests.get(f"{API}/files/{S['fid_rc']}", headers=h(S["other"]), timeout=30)
    assert r.status_code == 404


def test_file_no_token_401():
    assert requests.get(f"{API}/files/{S['fid_rc']}", timeout=30).status_code == 401


def test_file_bad_token_401():
    assert requests.get(f"{API}/files/{S['fid_rc']}?token=bogus", timeout=30).status_code == 401


# --- submit + lock
def test_submit_verification_under_review():
    r = requests.post(f"{API}/driver/verification", headers=h(S["tok"]), json=VERIF, timeout=20)
    assert r.status_code == 200, r.text
    assert r.json()["status"] in ("under_review", "approved")
    S["status"] = r.json()["status"]


def test_upload_locked_after_submit():
    r = upload(S["tok"], "profile")
    assert r.status_code == 400 and "locked" in r.json()["detail"].lower()


def test_admin_drivers_lists_documents():
    if S.get("status") != "under_review":
        pytest.skip("instant approval on")
    r = requests.get(f"{API}/admin/drivers?status=under_review", headers=h(S["admin"]), timeout=30)
    assert r.status_code == 200
    me = [u for u in r.json() if u["user_id"] == S["user"]["user_id"]]
    assert me, "submitted driver missing from admin list"
    d = me[0]["documents"]
    assert d["vehicle_name"] == "Maruti Swift"
    assert d["photos"]["profile"] == S["fid_profile"] and all(d["photos"].get(k) for k in KINDS)
    assert "_id" not in me[0] and "password_hash" not in me[0]


def test_admin_review_no_docs_400():
    r = requests.post(f"{API}/admin/drivers/{S['empty_user']['user_id']}/review", headers=h(S["admin"]), json={"decision": "approved"}, timeout=20)
    assert r.status_code == 400


def test_admin_approve():
    r = requests.post(f"{API}/admin/drivers/{S['user']['user_id']}/review", headers=h(S["admin"]), json={"decision": "approved", "note": "TEST ok"}, timeout=20)
    assert r.status_code == 200
    prof = requests.get(f"{API}/driver/profile", headers=h(S["tok"]), timeout=20).json()
    assert prof["status"] == "approved"


def test_partial_upload_then_admin_review_should_fail():
    """A user who uploaded 1 photo but never submitted must not be reviewable."""
    tok, u = register("partial")
    assert upload(tok, "profile").status_code == 200
    r = requests.post(f"{API}/admin/drivers/{u['user_id']}/review", headers=h(S["admin"]), json={"decision": "approved"}, timeout=20)
    assert r.status_code == 400, f"partial-upload user was approved: {r.status_code}"
