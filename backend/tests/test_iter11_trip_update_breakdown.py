"""Iteration 11 retest: PUT /api/trips/{tid} recomputes cost_breakdown on seats/price change and enforces price cap.
Requires /tmp/ui10.json from ui_setup_iter10.py (approved TEST driver + sedan). Run with -p no:xdist."""
import json
import os

import pytest
import requests

from test_travoo_api import API, h
from test_iter10_capacity_pricing_photo import trip_body

S = {}


@pytest.fixture(scope="module", autouse=True)
def driver():
    if not os.path.exists("/tmp/ui10.json"):
        pytest.skip("run ui_setup_iter10.py first")
    cfg = json.load(open("/tmp/ui10.json"))
    r = requests.post(f"{API}/auth/login", json={"email": cfg["drv_email"], "password": cfg["pw"]})
    if r.status_code != 200:
        pytest.skip("driver login failed")
    S["tok"], S["vid"] = r.json()["token"], cfg["vid"]
    S["fac"] = requests.get(f"{API}/fuel-prices").json()["max_price_factor"]
    yield
    for t in S.get("trips", []):
        requests.post(f"{API}/trips/{t}/cancel", headers=h(S["tok"]), json={"reason": "TEST cleanup"})


def get_trip(tid):
    return requests.get(f"{API}/trips/{tid}", headers=h(S["tok"])).json()


class TestTripUpdateBreakdown:
    # create trip with breakdown
    def test_create(self):
        r = requests.post(f"{API}/trips", headers=h(S["tok"]), json=trip_body(S["vid"], 3, price=100, days=9))
        assert r.status_code == 200, r.text
        t = r.json()
        S.setdefault("trips", []).append(t["trip_id"])
        S["tid"], S["cb"] = t["trip_id"], t["cost_breakdown"]
        assert S["cb"]["sharers"] == 3

    # price above cap -> 400, not persisted
    def test_price_20000_rejected(self):
        r = requests.put(f"{API}/trips/{S['tid']}", headers=h(S["tok"]), json={"price": 20000})
        assert r.status_code == 400 and "limit" in r.text, r.text
        assert get_trip(S["tid"])["price"] == 100

    # price just above cap / at cap
    def test_price_cap_boundary(self):
        cap = round(S["cb"]["recommended"] * S["fac"])
        assert requests.put(f"{API}/trips/{S['tid']}", headers=h(S["tok"]), json={"price": cap + 1}).status_code == 400
        r = requests.put(f"{API}/trips/{S['tid']}", headers=h(S["tok"]), json={"price": cap})
        assert r.status_code == 200, r.text
        assert get_trip(S["tid"])["price"] == cap

    # seats 3 -> 1 recomputes breakdown
    def test_seats_to_one(self):
        r = requests.put(f"{API}/trips/{S['tid']}", headers=h(S["tok"]), json={"seats": 1})
        assert r.status_code == 200, r.text
        t = get_trip(S["tid"])
        cb = t["cost_breakdown"]
        assert t["seats_total"] == 1 and t["seats_available"] == 1
        assert cb["sharers"] == 1
        assert cb["recommended"] == max(50, round(cb["total"] / 1))
        assert cb["total"] == S["cb"]["total"]

    # seats up (1 -> 3) with high price -> 400 since recommended drops
    def test_seats_up_with_high_price(self):
        cap1 = round(max(50, round(S["cb"]["total"])) * S["fac"])
        assert requests.put(f"{API}/trips/{S['tid']}", headers=h(S["tok"]), json={"price": cap1}).status_code == 200
        r = requests.put(f"{API}/trips/{S['tid']}", headers=h(S["tok"]), json={"seats": 3})
        if round(S["cb"]["recommended"] * S["fac"]) < cap1:
            assert r.status_code == 400 and "limit" in r.text, r.text
            assert get_trip(S["tid"])["seats_total"] == 1

    # seats + price together
    def test_seats_and_price_together(self):
        r = requests.put(f"{API}/trips/{S['tid']}", headers=h(S["tok"]), json={"seats": 2, "price": 100})
        assert r.status_code == 200, r.text
        t = get_trip(S["tid"])
        assert t["seats_total"] == 2 and t["price"] == 100
        assert t["cost_breakdown"]["sharers"] == 2
        assert t["cost_breakdown"]["recommended"] == max(50, round(t["cost_breakdown"]["total"] / 2))

    # seats above vehicle cap still rejected
    def test_seats_above_cap(self):
        r = requests.put(f"{API}/trips/{S['tid']}", headers=h(S["tok"]), json={"seats": 4})
        assert r.status_code == 400 and "at most" in r.text, r.text
        assert get_trip(S["tid"])["seats_total"] == 2

    # non-price/seat update keeps breakdown
    def test_other_field_update(self):
        r = requests.put(f"{API}/trips/{S['tid']}", headers=h(S["tok"]), json={"pickup_point": "TEST new pickup"})
        assert r.status_code == 200, r.text
        t = get_trip(S["tid"])
        assert t["pickup_point"] == "TEST new pickup" and t["cost_breakdown"]["sharers"] == 2
