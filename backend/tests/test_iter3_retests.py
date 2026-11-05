"""TRAVOO iteration 3 retests: admin review gating (Bug 1), upload content sniffing + file headers (Bug 2), superseded files."""
import io
import os
import uuid

import pytest
import requests
from PIL import Image

BASE_URL = (os.environ.get("EXPO_BACKEND_URL") or os.environ.get("EXPO_PUBLIC_BACKEND_URL") or "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("EXPO_PUBLIC_BACKEND_URL"):
                BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")
API = f"{BASE_URL}/api"
KINDS = ["profile", "licence", "rc", "vehicle"]
VERIF = {"legal_name": "TEST Iter3 Driver", "vehicle_name": "Maruti Swift", "phone": "9876543210",
         "licence_no": "KA0120230001234", "licence_expiry": "01-01-2030", "rc_no": "KA01AB9999"}


def img(fmt):
    b = io.BytesIO()
    Image.new("RGB", (4, 4), (200, 30, 30)).save(b, fmt)
    return b.getvalue()


JPEG, PNG, WEBP = img("JPEG"), img("PNG"), img("WEBP")
SVG = b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"><script>alert(document.cookie)</script></svg>'
TEXT = b"hello this is not an image at all"


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


def review(admin, uid, decision):
    return requests.post(f"{API}/admin/drivers/{uid}/review", headers=h(admin), json={"decision": decision, "note": "TEST"}, timeout=20)


def status(tok):
    return requests.get(f"{API}/driver/profile", headers=h(tok), timeout=20).json()


@pytest.fixture(scope="module")
def admin():
    return login("admin@travoo.in", "TravooAdmin@2026")


# --- Bug 1: admin review gating
class TestReviewGating:
    def test_photos_only_user_cannot_be_reviewed(self, admin):
        tok, user = register("photosonly")
        for k in KINDS:
            assert upload(tok, k).status_code == 200
        for d in ("approved", "rejected", "resubmit"):
            r = review(admin, user["user_id"], d)
            assert r.status_code == 400, f"{d}: {r.status_code} {r.text}"
        assert status(tok)["status"] == "not_submitted"

    def test_not_submitted_no_docs_400(self, admin):
        _, user = register("nodocs")
        r = review(admin, user["user_id"], "approved")
        assert r.status_code == 400

    def test_unknown_user_400(self, admin):
        r = review(admin, "user_doesnotexist123", "approved")
        assert r.status_code in (400, 404)

    def test_full_lifecycle(self, admin):
        tok, user = register("lifecycle")
        uid = user["user_id"]
        for k in KINDS:
            assert upload(tok, k).status_code == 200
        r = requests.post(f"{API}/driver/verification", headers=h(tok), json=VERIF, timeout=20)
        assert r.status_code == 200 and r.json()["status"] == "under_review", r.text
        # under_review -> rejected works
        assert review(admin, uid, "rejected").status_code == 200
        assert status(tok)["status"] == "rejected"
        # rejected cannot be reviewed again
        r = review(admin, uid, "approved")
        assert r.status_code == 400, r.text
        assert status(tok)["status"] == "rejected"
        # driver re-uploads + resubmits -> under_review -> resubmit works
        assert upload(tok, "licence", JPEG, "image/jpeg", "l.jpg").status_code == 200
        r = requests.post(f"{API}/driver/verification", headers=h(tok), json=VERIF, timeout=20)
        assert r.status_code == 200 and r.json()["status"] == "under_review", r.text
        assert review(admin, uid, "resubmit").status_code == 200
        r = review(admin, uid, "approved")
        assert r.status_code == 400, "resubmit status must not be reviewable"
        # resubmit -> driver submits again -> approve
        r = requests.post(f"{API}/driver/verification", headers=h(tok), json=VERIF, timeout=20)
        assert r.status_code == 200, r.text
        assert review(admin, uid, "approved").status_code == 200
        assert status(tok)["status"] == "approved"


# --- Bug 2: content sniffing + response headers
class TestUploadSniffing:
    @pytest.fixture(scope="class")
    def tok(self):
        return register("sniff")[0]

    @pytest.mark.parametrize("data,ctype,name", [
        (SVG, "image/jpeg", "x.jpg"), (SVG, "image/svg+xml", "x.svg"), (TEXT, "image/jpeg", "t.jpg"),
        (b"<html><script>alert(1)</script></html>", "image/png", "p.png"), (b"", "image/jpeg", "e.jpg"),
    ])
    def test_non_images_rejected(self, tok, data, ctype, name):
        r = upload(tok, "profile", data, ctype, name)
        assert r.status_code == 400, f"{name}/{ctype}: {r.status_code} {r.text}"

    @pytest.mark.parametrize("data,ctype,expect", [
        (JPEG, "image/jpeg", "image/jpeg"), (PNG, "image/png", "image/png"), (WEBP, "image/webp", "image/webp"),
        (PNG, "image/jpeg", "image/png"),  # mislabelled real image -> stored with sniffed type
    ])
    def test_real_images_accepted_with_headers(self, tok, data, ctype, expect):
        r = upload(tok, "vehicle", data, ctype, "v.bin")
        assert r.status_code == 200, r.text
        fid = r.json()["file_id"]
        g = requests.get(f"{API}/files/{fid}", headers=h(tok), timeout=60)
        assert g.status_code == 200
        assert g.headers.get("Content-Type", "").startswith(expect)
        assert g.headers.get("X-Content-Type-Options") == "nosniff"
        csp = g.headers.get("Content-Security-Policy", "")
        assert "sandbox" in csp and "default-src 'none'" in csp
        assert g.content == data


# --- Re-upload supersedes old file
class TestSupersede:
    def test_reupload_old_file_404(self):
        tok, _ = register("supersede")
        old = upload(tok, "rc", PNG).json()["file_id"]
        assert requests.get(f"{API}/files/{old}", headers=h(tok), timeout=60).status_code == 200
        new = upload(tok, "rc", JPEG, "image/jpeg").json()["file_id"]
        assert new != old
        assert requests.get(f"{API}/files/{old}", headers=h(tok), timeout=60).status_code == 404
        assert requests.get(f"{API}/files/{new}", headers=h(tok), timeout=60).status_code == 200
        assert status(tok)["documents"]["photos"]["rc"] == new
        # other kinds untouched
        prof = upload(tok, "profile", PNG).json()["file_id"]
        assert requests.get(f"{API}/files/{new}", headers=h(tok), timeout=60).status_code == 200
        assert requests.get(f"{API}/files/{prof}", headers=h(tok), timeout=60).status_code == 200
