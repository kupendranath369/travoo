# Iter39: all-India PIN code import + LGD hierarchy regression (public endpoints, no login)
import os
import pytest
import requests

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or os.environ.get("EXPO_PUBLIC_BACKEND_URL")).rstrip("/")
S = requests.Session()


# PIN lookup across states/UTs incl. islands and NE
@pytest.mark.parametrize("pin,state", [
    ("110011", "Delhi"), ("673001", "Kerala"), ("560001", "Karnataka"),
    ("794001", "Meghalaya"), ("744101", "Andaman"), ("190001", "Jammu"), ("682555", "Lakshadweep"),
])
def test_pincode_lookup(pin, state):
    r = S.get(f"{BASE_URL}/api/geo/pincode/{pin}", timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["pin"] == pin
    assert state.lower() in d["state"].lower()
    assert len(d["offices"]) >= 1
    assert "_id" not in d and "geo" not in d
    assert d["lat"] is not None
    assert any(l["type"] == "post_office" for l in d["locations"])


def test_pincode_invalid():
    assert S.get(f"{BASE_URL}/api/geo/pincode/012345", timeout=15).status_code == 400
    assert S.get(f"{BASE_URL}/api/geo/pincode/abc", timeout=15).status_code == 400


def test_pincode_not_found():
    r = S.get(f"{BASE_URL}/api/geo/pincode/999999", timeout=30)
    assert r.status_code == 404


# search by 6-digit PIN returns post offices
@pytest.mark.parametrize("pin", ["673571", "110011", "744101"])
def test_search_by_pin(pin):
    r = S.get(f"{BASE_URL}/api/geo/search", params={"q": pin}, timeout=30)
    assert r.status_code == 200
    rows = r.json()["results"]
    assert rows, "no results"
    assert all(x.get("pin") == pin for x in rows)
    assert any(x["type"] == "post_office" for x in rows)


def test_search_by_pin_prefix():
    r = S.get(f"{BASE_URL}/api/geo/search", params={"q": "6735"}, timeout=30)
    assert r.status_code == 200
    rows = r.json()["results"]
    assert rows and all(x["pin"].startswith("6735") for x in rows)


def test_search_name_kunnamangalam():
    r = S.get(f"{BASE_URL}/api/geo/search", params={"q": "Kunnamangalam"}, timeout=40)
    assert r.status_code == 200
    rows = r.json()["results"]
    assert any("kunnamangalam" in x["name"].lower() for x in rows)


def test_lgd_states_districts_subdistricts():
    st = S.get(f"{BASE_URL}/api/lgd/states", timeout=15).json()
    assert len(st) == 36
    kerala = next(s for s in st if s["name"].lower() == "kerala")
    ds = S.get(f"{BASE_URL}/api/lgd/districts", params={"state_code": kerala["code"]}, timeout=15).json()
    assert len(ds) == 14
    kkd = next(d for d in ds if "kozhikode" in d["name"].lower())
    sds = S.get(f"{BASE_URL}/api/lgd/subdistricts", params={"district_code": kkd["code"]}, timeout=15).json()
    assert len(sds) >= 3
    assert all(x["district_code"] == kkd["code"] for x in sds)
    vs = S.get(f"{BASE_URL}/api/lgd/villages", params={"subdistrict_code": sds[0]["code"]}, timeout=15).json()
    assert len(vs) >= 1


def test_lgd_subdistrict_search():
    r = S.get(f"{BASE_URL}/api/lgd/subdistricts/search", params={"q": "Koz"}, timeout=15)
    assert r.status_code == 200
    assert any("koz" in x["name"].lower() for x in r.json())
