# Iteration 8: driver documents (new kinds), verification submit, file ACL, admin portal auth/RBAC, admin APIs, forgot/reset password
import os, io, uuid, time, hashlib, secrets
from datetime import datetime, timedelta, timezone
import pytest, requests
from PIL import Image, ImageDraw
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv('/app/frontend/.env')
load_dotenv('/app/backend/.env')
BASE_URL = (os.environ.get('EXPO_BACKEND_URL') or os.environ.get('EXPO_PUBLIC_BACKEND_URL')).rstrip('/')
API = f"{BASE_URL}/api"
ADMIN_EMAIL, ADMIN_PW = "admin@travoo.in", "TravooAdmin2026"
mdb = MongoClient(os.environ['MONGO_URL'])[os.environ['DB_NAME']]
CREATED_UIDS = []


def real_image(seed, fmt="JPEG", size=(640, 420)):
    img = Image.new("RGB", size, (240, 240, 230))
    d = ImageDraw.Draw(img)
    for i in range(0, size[0], 37):
        d.line([(i, 0), (size[0] - i, size[1])], fill=((i * 7 + seed * 31) % 255, (i * 3) % 255, (seed * 50) % 255), width=3)
    d.rectangle([40, 40, 300, 200], outline=(10, 20, 200), width=5)
    d.ellipse([350, 100, 600, 380], fill=(200, 60 + seed % 150, 40))
    d.text((60, 90), f"TRAVOO DOC {seed} {uuid.uuid4().hex[:8]}", fill=(0, 0, 0))
    b = io.BytesIO(); img.save(b, fmt); return b.getvalue()


def real_pdf(seed):
    b = io.BytesIO(); Image.open(io.BytesIO(real_image(seed))).save(b, "PDF"); return b.getvalue()


def register(prefix="TEST_drv"):
    email = f"{prefix.lower()}_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": "Passw0rd123", "name": f"{prefix} User", "consent": True})
    assert r.status_code == 200, r.text
    d = r.json(); CREATED_UIDS.append(d["user"]["user_id"])
    return {"email": email, "token": d["token"], "uid": d["user"]["user_id"], "h": {"Authorization": f"Bearer {d['token']}"}}


def up(u, kind, data, name="a.jpg", mime="image/jpeg"):
    return requests.post(f"{API}/driver/documents/{kind}", headers=u["h"], files={"file": (name, data, mime)}, timeout=120)


@pytest.fixture(scope="module")
def admin():
    r = requests.post(f"{API}/admin/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW, "remember": False})
    assert r.status_code == 200, r.text
    tok = r.json()["token"]; assert tok.startswith("adm_")
    yield {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    for uid in CREATED_UIDS:
        for c, k in [("users", "user_id"), ("driver_documents", "user_id"), ("notifications", "user_id"), ("driver_verification_events", "user_id"), ("password_resets", "user_id")]:
            mdb[c].delete_many({k: uid})
        mdb.files.delete_many({"owner_id": uid})
        mdb.admin_notifications.delete_many({"ref": uid})


@pytest.fixture(scope="module")
def driver():
    return register()


# ---- admin auth / RBAC
class TestAdminAuth:
    def test_wrong_password_401(self):
        r = requests.post(f"{API}/admin/auth/login", json={"email": ADMIN_EMAIL, "password": "wrong-pass"})
        assert r.status_code == 401

    def test_me(self, admin):
        r = requests.get(f"{API}/admin/auth/me", headers=admin)
        assert r.status_code == 200 and r.json()["email"] == ADMIN_EMAIL and r.json()["must_change_password"] is False

    def test_lockout_non_existing(self):
        email = f"lockout-test-{uuid.uuid4().hex[:6]}@example.com"
        codes = [requests.post(f"{API}/admin/auth/login", json={"email": email, "password": "x"}).status_code for _ in range(6)]
        assert codes[:5] == [401] * 5 and codes[5] == 429, codes

    def test_normal_login_rejects_admin(self):
        r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW})
        assert r.status_code == 403

    def test_user_token_on_admin_403(self, driver):
        assert requests.get(f"{API}/admin/stats", headers=driver["h"]).status_code == 403
        assert requests.get(f"{API}/admin/auth/me", headers=driver["h"]).status_code == 403

    def test_change_password_wrong_current(self, admin):
        r = requests.post(f"{API}/admin/auth/change-password", headers=admin, json={"current_password": "nope", "new_password": "NewPassw0rd99"})
        assert r.status_code == 400

    def test_change_password_weak(self, admin):
        r = requests.post(f"{API}/admin/auth/change-password", headers=admin, json={"current_password": ADMIN_PW, "new_password": "alllowercase1"})
        assert r.status_code == 400


# ---- admin read APIs
class TestAdminAPIs:
    def test_stats_fields(self, admin):
        r = requests.get(f"{API}/admin/stats", headers=admin); assert r.status_code == 200
        d = r.json()
        for k in ["passengers_registered", "rejected", "resubmit", "rides_active", "rides_completed", "rides_cancelled", "complaints_open", "new_7d", "unread_alerts"]:
            assert k in d, f"missing {k}: {list(d)}"

    def test_drivers_all_and_search(self, admin):
        r = requests.get(f"{API}/admin/drivers", headers=admin, params={"status": "all", "q": "driver@travoo"})
        assert r.status_code == 200
        assert any(x.get("email") == "driver@travoo.in" for x in r.json()), r.text[:300]

    @pytest.mark.parametrize("st", ["active", "completed", "cancelled"])
    def test_rides(self, admin, st):
        r = requests.get(f"{API}/admin/rides", headers=admin, params={"status": st}); assert r.status_code == 200
        exp = {"active": ("scheduled", "started"), "completed": ("completed",), "cancelled": ("cancelled",)}[st]
        assert all(t["status"] in exp for t in r.json())

    def test_notifications_activity(self, admin):
        r = requests.get(f"{API}/admin/notifications", headers=admin); assert r.status_code == 200
        assert "items" in r.json() and "unread" in r.json()
        a = requests.get(f"{API}/admin/activity", headers=admin); assert a.status_code == 200
        assert any(x["action"] == "admin.login" for x in a.json())

    def test_passenger_detail(self, admin):
        p = register("TEST_pax")
        r = requests.get(f"{API}/admin/passengers/{p['uid']}/detail", headers=admin)
        assert r.status_code == 200 and r.json()["user"]["user_id"] == p["uid"] and r.json()["stats"]["total"] == 0


# ---- driver documents + verification + admin review (sequential flow)
class TestDriverDocs:
    def test_validation(self, driver):
        assert up(driver, "profile", real_pdf(1), "a.pdf", "application/pdf").status_code == 400
        assert up(driver, "vehicle", real_pdf(2), "a.pdf", "application/pdf").status_code == 400
        assert up(driver, "rc", os.urandom(5000), "a.jpg").status_code == 400
        assert up(driver, "rc", b"\xff\xd8\xff" + os.urandom(11 * 1024 * 1024)).status_code == 413
        assert up(driver, "bogus", real_image(3)).status_code == 400

    def test_submit_missing_lists_docs(self, driver):
        r = requests.post(f"{API}/driver/verification", headers=driver["h"], json=VER)
        assert r.status_code == 400 and "Please upload" in r.json()["detail"]

    def test_upload_all_kinds_dup_max_delete(self, driver):
        for i, k in enumerate(["profile", "licence_front", "licence_back", "id_proof", "insurance"]):
            r = up(driver, k, real_image(10 + i)); assert r.status_code == 200, f"{k}: {r.text}"
        r = up(driver, "rc", real_pdf(20), "rc.pdf", "application/pdf"); assert r.status_code == 200 and r.json()["content_type"] == "application/pdf"
        png = real_image(30, "PNG")
        r1 = up(driver, "vehicle", png, "v.png", "image/png"); assert r1.status_code == 200
        r2 = up(driver, "vehicle", png, "v.png", "image/png"); assert r2.json().get("duplicate") is True and r2.json()["file_id"] == r1.json()["file_id"]
        for i in range(3):
            assert up(driver, "vehicle", real_image(40 + i)).status_code == 200
        assert up(driver, "vehicle", real_image(50)).status_code == 400  # 5th vehicle photo
        others = [up(driver, "other", real_image(60 + i)).json()["file_id"] for i in range(3)]
        assert up(driver, "other", real_image(70)).status_code == 400
        assert requests.delete(f"{API}/driver/documents/file/{others[0]}", headers=driver["h"]).status_code == 200
        assert requests.delete(f"{API}/driver/documents/file/{others[0]}", headers=driver["h"]).status_code == 404
        p = requests.get(f"{API}/driver/profile", headers=driver["h"]).json()
        assert p["missing"] == [] and p["locked"] is False and len(p["kinds"]) == 8
        assert sum(f["kind"] == "vehicle" for f in p["files"]) == 4 and sum(f["kind"] == "other" for f in p["files"]) == 2
        assert mdb.files.count_documents({"owner_id": driver["uid"], "kind": "vehicle", "deleted": {"$ne": True}}) == 4

    def test_file_acl(self, driver, admin):
        fid = requests.get(f"{API}/driver/profile", headers=driver["h"]).json()["files"][0]["file_id"]
        assert requests.get(f"{API}/files/{fid}", headers=driver["h"]).status_code == 200
        assert requests.get(f"{API}/files/{fid}").status_code == 401
        other = register("TEST_other")
        assert requests.get(f"{API}/files/{fid}", headers=other["h"]).status_code == 404
        r = requests.get(f"{API}/files/{fid}", headers=admin); assert r.status_code == 200 and len(r.content) > 1024

    def test_submit_under_review_and_lock(self, driver, admin):
        r = requests.post(f"{API}/driver/verification", headers=driver["h"], json=VER)
        assert r.status_code == 200 and r.json()["status"] == "under_review", r.text
        assert up(driver, "other", real_image(80)).status_code == 400
        assert requests.get(f"{API}/driver/profile", headers=driver["h"]).json()["locked"] is True
        n = requests.get(f"{API}/admin/notifications", headers=admin).json()["items"]
        assert any(x["ref"] == driver["uid"] and x["kind"] == "verification_submitted" for x in n)

    def test_review_reject_requires_note_then_resubmit_then_approve(self, driver, admin):
        u = f"{API}/admin/drivers/{driver['uid']}/review"
        assert requests.post(u, headers=admin, json={"decision": "rejected", "note": "bad"}).status_code == 400
        assert requests.post(u, headers=driver["h"], json={"decision": "approved", "note": ""}).status_code == 403
        r = requests.post(u, headers=admin, json={"decision": "resubmit", "note": "Licence back is blurry"}); assert r.status_code == 200
        assert requests.get(f"{API}/driver/profile", headers=driver["h"]).json()["status"] == "resubmit"
        nots = requests.get(f"{API}/notifications", headers=driver["h"]).json()
        items = nots.get("items", nots) if isinstance(nots, dict) else nots
        assert any(x.get("type") == "driver_resubmit" for x in items), str(nots)[:300]
        assert up(driver, "licence_back", real_image(90)).status_code == 200
        assert requests.post(f"{API}/driver/verification", headers=driver["h"], json=VER).json()["status"] == "under_review"
        assert requests.post(u, headers=admin, json={"decision": "approved", "note": ""}).json()["status"] == "approved"
        d = requests.get(f"{API}/admin/drivers/{driver['uid']}/detail", headers=admin).json()
        acts = [h["action"] for h in d["history"]]
        assert {"submitted", "resubmit", "resubmitted", "approved"} <= set(acts), acts
        a = requests.get(f"{API}/admin/activity", headers=admin).json()
        assert any(x["action"] == "driver.resubmit" and x.get("target") == driver["uid"] for x in a) or any(x["action"] == "driver.resubmit" for x in a)


VER = {"legal_name": "TEST Driver Name", "vehicle_name": "Maruti Swift", "phone": "9876543210", "licence_no": "KA0120201234567",
       "licence_expiry": "01-01-2035", "rc_no": "KA01AB1234"}


# ---- forgot / reset password
class TestPasswordReset:
    def test_forgot_503_then_rate_limit(self):
        email = f"test_fp_{uuid.uuid4().hex[:6]}@example.com"
        codes = [requests.post(f"{API}/auth/forgot-password", json={"email": email}) for _ in range(4)]
        assert [c.status_code for c in codes[:3]] == [503] * 3, [c.text for c in codes]
        assert "not configured" in codes[0].json()["detail"]
        assert codes[3].status_code == 429

    def test_reset_random_token_400(self):
        assert requests.post(f"{API}/auth/reset-password", json={"token": secrets.token_urlsafe(32), "new_password": "NewPassw0rd1"}).status_code == 400

    def test_reset_flow_via_db_token(self):
        u = register("TEST_reset")
        raw, raw_exp = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        n = datetime.now(timezone.utc)
        base = {"user_id": u["uid"], "created_at": n, "used_at": None, "provider_status": "accepted"}
        mdb.password_resets.insert_one({**base, "request_id": "rst_test_" + uuid.uuid4().hex[:6], "token_hash": hashlib.sha256(raw.encode()).hexdigest(), "expires_at": n + timedelta(minutes=30)})
        mdb.password_resets.insert_one({**base, "request_id": "rst_test_" + uuid.uuid4().hex[:6], "token_hash": hashlib.sha256(raw_exp.encode()).hexdigest(), "expires_at": n - timedelta(minutes=1)})
        time.sleep(1.2)
        assert requests.post(f"{API}/auth/reset-password", json={"token": raw_exp, "new_password": "NewPassw0rd1"}).status_code == 400
        r = requests.post(f"{API}/auth/reset-password", json={"token": raw, "new_password": "NewPassw0rd1"}); assert r.status_code == 200, r.text
        assert requests.post(f"{API}/auth/reset-password", json={"token": raw, "new_password": "NewPassw0rd2"}).status_code == 400
        assert requests.post(f"{API}/auth/login", json={"email": u["email"], "password": "Passw0rd123"}).status_code == 401
        assert requests.post(f"{API}/auth/login", json={"email": u["email"], "password": "NewPassw0rd1"}).status_code == 200
        assert requests.get(f"{API}/auth/me", headers=u["h"]).status_code == 401


# ---- logout last (invalidates module admin session)
class TestZLogout:
    def test_logout_invalidates(self, admin):
        assert requests.post(f"{API}/admin/auth/logout", headers=admin).status_code == 200
        assert requests.get(f"{API}/admin/stats", headers=admin).status_code == 401
