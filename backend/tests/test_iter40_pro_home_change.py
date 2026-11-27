# Iteration 40: PUT /api/pro/home - verified driver changes home location anytime (no approval, no limit)
import os
import uuid
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", os.environ.get("REACT_APP_BACKEND_URL", "")).rstrip("/")
if not BASE_URL:
    for line in open("/app/frontend/.env"):
        if line.startswith("EXPO_PUBLIC_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")

mdb = MongoClient("mongodb://localhost:27017")["travoo"]
DRIVER = ("test.driver@example.com", "Test@12345")
RIDER = ("test.rider@example.com", "Test@12345")
KOZHIKODE, THAMARASSERY = "5640", "5938"


def login(email, pw):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pw})
    if r.status_code != 200:
        pytest.skip(f"login failed {email}: {r.status_code} {r.text}")
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module")
def driver():
    h = login(*DRIVER)
    uid = mdb.users.find_one({"email": DRIVER[0]})["user_id"]
    orig = mdb.pro_drivers.find_one({"user_id": uid}, {"_id": 0, "home": 1, "service_taluk_codes": 1})
    yield h, uid
    # restore original home + service taluks
    requests.put(f"{BASE_URL}/api/pro/home", headers=h, json={"subdistrict_code": orig["home"]["subdistrict_code"], "city": orig["home"].get("city", "")})
    mdb.pro_drivers.update_one({"user_id": uid}, {"$set": {"home": orig["home"], "service_taluk_codes": orig["service_taluk_codes"]}})


# Verified driver: change applies immediately, side effects recorded
def test_change_home_approved(driver):
    h, uid = driver
    mdb.pro_drivers.update_one({"user_id": uid}, {"$set": {"service_taluk_codes": [KOZHIKODE, "9999X"]}})
    before_hist = len(mdb.pro_drivers.find_one({"user_id": uid}).get("home_history") or [])
    before_notif = mdb.admin_notifications.count_documents({"kind": "driver_home_changed", "ref": uid})
    r = requests.put(f"{BASE_URL}/api/pro/home", headers=h, json={
        "subdistrict_code": THAMARASSERY, "city": "TEST_Thamarassery",
        "place": {"loc_id": "TEST_loc", "name": "TEST_Thamarassery town", "lat": 11.41, "lng": 75.93}})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["subdistrict_code"] == THAMARASSERY and d["district_name"] == "Kozhikode"
    assert d["place_name"] == "TEST_Thamarassery town" and d["geo"]["lat"] == 11.41
    p = mdb.pro_drivers.find_one({"user_id": uid})
    assert p["home"]["subdistrict_code"] == THAMARASSERY
    assert p["service_taluk_codes"][0] == THAMARASSERY
    assert KOZHIKODE not in p["service_taluk_codes"]
    assert "9999X" in p["service_taluk_codes"]  # other service taluks kept
    assert len(p["home_history"]) == min(before_hist + 1, 20)
    assert p["home_history"][-1]["to"]["subdistrict_name"] == "Thamarassery"
    assert mdb.admin_notifications.count_documents({"kind": "driver_home_changed", "ref": uid}) == before_notif + 1


# No limit: repeat changes allowed
def test_repeat_changes(driver):
    h, uid = driver
    for code in (KOZHIKODE, THAMARASSERY, KOZHIKODE):
        r = requests.put(f"{BASE_URL}/api/pro/home", headers=h, json={"subdistrict_code": code})
        assert r.status_code == 200, r.text
        assert r.json()["subdistrict_code"] == code
    p = mdb.pro_drivers.find_one({"user_id": uid})
    assert p["home"]["subdistrict_code"] == KOZHIKODE and p["service_taluk_codes"][0] == KOZHIKODE
    assert THAMARASSERY not in p["service_taluk_codes"]
    me = requests.get(f"{BASE_URL}/api/pro/dashboard", headers=h)
    assert me.status_code == 200


def test_unknown_taluk(driver):
    h, _ = driver
    r = requests.put(f"{BASE_URL}/api/pro/home", headers=h, json={"subdistrict_code": "000000"})
    assert r.status_code == 400


def test_no_auth():
    r = requests.put(f"{BASE_URL}/api/pro/home", json={"subdistrict_code": KOZHIKODE})
    assert r.status_code in (401, 403)


def test_rider_without_profile_404():
    h = login(*RIDER)
    r = requests.put(f"{BASE_URL}/api/pro/home", headers=h, json={"subdistrict_code": KOZHIKODE})
    assert r.status_code == 404, r.text


# Not-yet-approved driver with a home cannot change
@pytest.fixture(scope="module")
def pending_driver():
    email = f"test_pending_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{BASE_URL}/api/auth/register", json={"email": email, "password": "Test@12345", "name": "TEST_Pending", "consent": True})
    assert r.status_code == 200, r.text
    uid = r.json()["user"]["user_id"]
    home = {"subdistrict_code": KOZHIKODE, "subdistrict_name": "Kozhikode", "district_name": "Kozhikode", "state_name": "Kerala"}
    mdb.pro_drivers.insert_one({"user_id": uid, "name": "TEST_Pending", "status": "pending", "home": home, "service_taluk_codes": [KOZHIKODE]})
    yield {"Authorization": f"Bearer {r.json()['token']}"}, uid
    mdb.pro_drivers.delete_one({"user_id": uid})
    mdb.users.delete_one({"user_id": uid})
    mdb.admin_notifications.delete_many({"ref": uid})
    mdb.audit_logs.delete_many({"actor": uid})


def test_pending_cannot_change(pending_driver):
    h, uid = pending_driver
    r = requests.put(f"{BASE_URL}/api/pro/home", headers=h, json={"subdistrict_code": THAMARASSERY})
    assert r.status_code == 400
    assert r.json()["detail"] == "You can change your home location after Travoo verifies your profile"
    assert mdb.pro_drivers.find_one({"user_id": uid})["home"]["subdistrict_code"] == KOZHIKODE


def test_pending_without_home_can_set(pending_driver):
    h, uid = pending_driver
    mdb.pro_drivers.update_one({"user_id": uid}, {"$unset": {"home": ""}})
    r = requests.put(f"{BASE_URL}/api/pro/home", headers=h, json={"subdistrict_code": THAMARASSERY})
    assert r.status_code == 200, r.text
    assert mdb.pro_drivers.find_one({"user_id": uid})["home"]["subdistrict_code"] == THAMARASSERY
