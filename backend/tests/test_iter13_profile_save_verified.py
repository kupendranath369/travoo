"""Iteration 13: Profile 'Edit profile' save sends the full form {name, phone, upi_id, bio}; check verified/empty phone cases."""
import random
import requests
from test_travoo_api import API, h
from test_iter10_capacity_pricing_photo import reg
from test_iter13_retest_fixes import _db


def test_verified_user_saves_profile_with_same_phone():
    tok, uid, _ = reg("Ver13")
    ph = f"98{random.randint(10000000, 99999999)}"
    assert requests.put(f"{API}/me", headers=h(tok), json={"phone": ph}).status_code == 200
    _db().users.update_one({"user_id": uid}, {"$set": {"phone_verified": True, "phone_e164": "91" + ph}})
    # exactly what app/profile.tsx sends: unchanged phone + edited name
    r = requests.put(f"{API}/me", headers=h(tok), json={"name": "TEST_Ver13 New", "phone": ph, "upi_id": "", "bio": ""})
    print("verified same-phone save:", r.status_code, r.text[:150])
    _db().users.update_one({"user_id": uid}, {"$unset": {"phone_e164": ""}, "$set": {"phone_verified": False}})
    assert r.status_code == 200, r.text


def test_unverified_user_save_with_empty_phone():
    tok, uid, _ = reg("Emp13")
    r = requests.put(f"{API}/me", headers=h(tok), json={"name": "TEST_Emp13 New", "phone": "", "upi_id": "", "bio": ""})
    print("empty phone save:", r.status_code, r.text[:150])
    assert r.status_code == 200, r.text
