"""Iteration 26: retest of iter25 fixes - suspended online block, resubmission keeps home geo, flagged docs re-upload,
hire start 2h guard, migration keeps 'rejected' commercial_status.
Run: cd /app/backend/tests && pytest test_iter26_retest_fixes.py -c /dev/null -p no:xdist -v"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests

from test_travoo_api import API, h
import test_iter25_local_driver_redesign as b25

S: dict = {}
UIDS = b25.UIDS  # shared list; cleaned by our own fixture below
db = b25.db
MIG_UID = "user_TEST_mig26"


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    for uid in list(UIDS):
        for c, f in (("pro_drivers", "user_id"), ("driver_documents", "user_id"), ("vehicles", "owner_id"), ("files", "owner_id"),
                     ("hire_requests", "passenger_id"), ("hire_dispatches", "driver_id"), ("hires", "driver_id"), ("hires", "passenger_id"),
                     ("notifications", "user_id"), ("users", "user_id")):
            db[c].delete_many({f: uid})
    db.pro_drivers.delete_many({"user_id": MIG_UID})
    db.vehicles.delete_many({"owner_id": MIG_UID})


# Setup: admin login + passenger
class TestSetup:
    def test_setup(self):
        r = requests.post(f"{API}/admin/auth/login", json={"email": "admin@travoo.in", "password": "TravooAdmin2026x"})
        assert r.status_code == 200, r.text
        b25.S["adm"] = S["adm"] = r.json()["token"]
        S["pax"], S["pax_id"] = b25.new_user("Pax26")


# Suspended driver cannot go online
class TestSuspend:
    def test_suspended_online_400(self):
        tok, uid = b25.make_driver("Sus26")
        r = requests.post(f"{API}/admin/pro-drivers/{uid}/suspend", headers=h(S["adm"]), json={"suspended": True, "note": "TEST"})
        assert r.status_code == 200
        r = requests.put(f"{API}/pro/settings", headers=h(tok), json={"availability_status": "available"})
        assert r.status_code == 400 and "suspended" in r.json()["detail"].lower(), r.text
        assert db.pro_drivers.find_one({"user_id": uid})["available"] is False
        # offline still allowed; reactivate -> online allowed
        assert requests.put(f"{API}/pro/settings", headers=h(tok), json={"availability_status": "offline"}).status_code == 200
        requests.post(f"{API}/admin/pro-drivers/{uid}/suspend", headers=h(S["adm"]), json={"suspended": False, "note": "TEST"})
        assert requests.put(f"{API}/pro/settings", headers=h(tok), json={"availability_status": "available"}).status_code == 200


# Resubmission keeps home geo + flagged docs must be re-uploaded
class TestResubmit:
    def test_resubmit_keeps_geo_and_requires_flagged(self):
        tok, uid = b25.make_driver("Res26", online=False)
        before = db.pro_drivers.find_one({"user_id": uid})["home"]
        assert before.get("geo") and before.get("loc_id")
        r = b25.adm_review(uid, "resubmit", note="TEST blurry back", items=["licence_back"])
        assert r.status_code == 200, r.text
        body = b25.reg_body()
        body["home"]["place"] = None
        # not re-uploaded -> 400
        r = requests.post(f"{API}/pro/register", headers=h(tok), json=body)
        assert r.status_code == 400 and r.json()["detail"] == "Please upload a new photo for: Driving licence (back)", r.text
        assert b25.upload(tok, "licence_back").status_code == 200  # flagged -> allowed
        r = requests.post(f"{API}/pro/register", headers=h(tok), json=body)
        assert r.status_code == 200 and r.json()["status"] == "under_review", r.text
        after = db.pro_drivers.find_one({"user_id": uid})["home"]
        assert after["geo"] == before["geo"] and after["loc_id"] == before["loc_id"], (before, after)
        assert after.get("place_name") == before.get("place_name")

    def test_local_only_docs_locked_when_approved(self):
        """Local-only (no carpool) approved driver should not be able to replace a verified document."""
        tok, uid = b25.make_driver("Lock26", online=False)
        r = b25.upload(tok, "licence_front")
        assert r.status_code == 400, f"approved local-only driver replaced licence_front: {r.status_code}"

    def test_different_taluk_drops_geo(self):
        tok, uid = b25.make_driver("Res26b", online=False)
        assert b25.adm_review(uid, "resubmit", note="TEST move", items=[]).status_code == 200
        body = b25.reg_body(sub=b25.HOLALKERE)
        body["home"]["place"] = None
        r = requests.post(f"{API}/pro/register", headers=h(tok), json=body)
        assert r.status_code == 200, r.text
        home = db.pro_drivers.find_one({"user_id": uid})["home"]
        assert home["subdistrict_code"] == b25.HOLALKERE and not home.get("geo")


# Hire start guard
class TestStartGuard:
    def test_start_guard(self):
        dtok, duid = b25.make_driver("Gd26")
        r = requests.post(f"{API}/hire/requests", headers=h(S["pax"]), json=b25.req_body(time="18:00"))
        assert r.status_code == 200, r.text
        a = requests.post(f"{API}/hire/requests/{r.json()['request_id']}/accept", headers=h(dtok))
        assert a.status_code == 200, a.text
        bid = a.json()["booking_id"]
        u = f"{API}/hire/bookings/{bid}"
        r = requests.post(f"{u}/start", headers=h(dtok), json={})
        assert r.status_code == 400 and "2 hours" in r.json()["detail"]
        db.hires.update_one({"booking_id": bid}, {"$set": {"starts_at": datetime.now(timezone.utc) + timedelta(hours=2, minutes=10)}})
        assert requests.post(f"{u}/start", headers=h(dtok), json={}).status_code == 400
        db.hires.update_one({"booking_id": bid}, {"$set": {"starts_at": datetime.now(timezone.utc) + timedelta(hours=1, minutes=50)}})
        assert requests.post(f"{u}/start", headers=h(dtok), json={}).status_code == 200
        assert db.hires.find_one({"booking_id": bid})["status"] == "started"
        assert requests.post(f"{u}/complete", headers=h(dtok), json={}).status_code == 200


# Migration does not override 'rejected' commercial_status (calls the server function directly)
class TestMigration:
    def test_migration_keeps_rejected(self):
        import asyncio, importlib, sys
        sys.path.insert(0, "/app/backend")
        db.vehicles.insert_one({"vehicle_id": "veh_TEST_mig26", "owner_id": MIG_UID, "reg_no": "KA01MG2601", "make": "TEST", "vtype": "sedan",
                                "seats": 3, "commercial_status": "rejected", "deleted": False})
        db.vehicles.insert_one({"vehicle_id": "veh_TEST_mig26b", "owner_id": MIG_UID, "reg_no": "KA01MG2602", "make": "TEST", "vtype": "sedan",
                                "seats": 3, "commercial_status": "none", "deleted": False})
        db.pro_drivers.insert_one({"user_id": MIG_UID, "name": "TEST_mig26", "status": "approved",
                                   "vehicles": [{"name": "TEST", "reg_no": "KA 01 MG 2601", "category": "sedan", "seats": 3, "day_rate": 1},
                                                {"name": "TEST", "reg_no": "KA01MG2602", "category": "sedan", "seats": 3, "day_rate": 1}]})
        server = importlib.import_module("server")
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(server.migrate_local_drivers())
        finally:
            loop.close()
        assert db.vehicles.find_one({"vehicle_id": "veh_TEST_mig26"})["commercial_status"] == "rejected"
        assert db.vehicles.find_one({"vehicle_id": "veh_TEST_mig26b"})["commercial_status"] == "approved"
        p = db.pro_drivers.find_one({"user_id": MIG_UID})
        assert p["vehicles_migrated"] is True and set(p["vehicle_ids"]) == {"veh_TEST_mig26", "veh_TEST_mig26b"}
