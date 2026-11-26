# Iteration 38: Book a Car price estimate (/api/hire/book-estimate)
import os
import pytest
import requests

BASE = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://app-runner-149--3ohxnclk.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"
RATES = {"hatchback": 11, "sedan": 13, "suv": 17, "muv": 16}


@pytest.fixture(scope="module")
def tok():
    # cache token in /tmp so xdist workers don't each log in (login is limited to 10/email/15 min)
    cache = "/tmp/iter38_tok"
    if os.path.exists(cache):
        t = open(cache).read().strip()
        if requests.get(f"{API}/hire/book-estimate", params={"km": 1}, headers={"Authorization": f"Bearer {t}"}).status_code == 200:
            return t
    r = requests.post(f"{API}/auth/login", json={"email": "passenger@travoo.in", "password": "Passenger@2026"})
    if r.status_code != 200:
        pytest.skip("login failed")
    open(cache, "w").write(r.json()["token"])
    return r.json()["token"]


def get(tok, **p):
    return requests.get(f"{API}/hire/book-estimate", params=p, headers={"Authorization": f"Bearer {tok}"} if tok else {})


def expect(km, st, days):
    d = max(1, days)
    if st == "one_way":
        b, d = km, 1
    elif st == "round_trip":
        b = 2 * km
    else:
        b = max(2 * km, 250 * d)
    out = {}
    for c, r in RATES.items():
        low = max(400, round(b * r + 300 * d, -1))
        out[c] = (int(low), int(round(low * 1.2, -1)))
    return out, round(b), d


def test_no_auth_401():
    assert get(None, km=100).status_code == 401


@pytest.mark.parametrize("km,st,days", [(270, "one_way", 3), (270, "round_trip", 2), (270, "multi_day", 3), (50, "outstation", 4),
                                        (5, "one_way", 1), (100.5, "round_trip", 1), (5000, "multi_day", 30)])
def test_formula(tok, km, st, days):
    r = get(tok, km=km, service_type=st, days=days)
    assert r.status_code == 200, r.text
    d = r.json()
    exp, bill, dd = expect(km, st, days)
    assert d["days"] == dd and d["billable_km"] == bill and d["distance_km"] == round(km)
    assert d["driver_allowance"] == 300 * dd
    got = {e["vehicle_type"]: (e["low"], e["high"]) for e in d["estimates"]}
    assert got == exp
    assert {e["vehicle_type"]: e["rate_per_km"] for e in d["estimates"]} == RATES


def test_one_way_cheapest(tok):
    ow = get(tok, km=270, service_type="one_way").json()["estimates"]
    rt = get(tok, km=270, service_type="round_trip", days=1).json()["estimates"]
    md = get(tok, km=270, service_type="multi_day", days=3).json()["estimates"]
    for a, b, c in zip(ow, rt, md):
        assert a["low"] < b["low"] <= c["low"]


@pytest.mark.parametrize("p", [{"km": 0}, {"km": -5}, {"km": 5001}, {"km": 100, "service_type": "bad"}, {"km": 100, "days": 0},
                               {"km": 100, "days": 31}, {"km": "abc"}, {}])
def test_validation_422(tok, p):
    assert get(tok, **p).status_code == 422
