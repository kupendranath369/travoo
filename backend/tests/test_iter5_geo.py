# Iteration 5: India-wide map/location database (geo search, PIN, reverse, place, route, nearby, sync) + along-route trip matching
import os
import time
from datetime import datetime, timedelta, timezone

import pytest
import requests

BASE_URL = os.environ.get("EXPO_BACKEND_URL", os.environ.get("EXPO_PUBLIC_BACKEND_URL")).rstrip("/")
API = f"{BASE_URL}/api"
IST = timezone(timedelta(hours=5, minutes=30))
S = {}


def in_india(x):
    return 6 <= x["lat"] <= 37.5 and 68 <= x["lng"] <= 97.5


def login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["token"]


def h(t):
    return {"Authorization": f"Bearer {t}"}


def gsearch(q, **kw):
    r = requests.get(f"{API}/geo/search", params={"q": q, **kw}, timeout=40)
    assert r.status_code == 200, r.text
    return r.json()


# ---- Geo search (cities, villages, streets, stations, PINs)
class TestGeoSearch:
    @pytest.mark.parametrize("q,expect", [("Bengaluru", "bengaluru"), ("Chandigarh", "chandigarh"), ("Mawlynnong", "mawlynnong"),
                                          ("Hampi", "hampi"), ("Bastar", "bastar"), ("MG Road Bengaluru", "mg road"),
                                          ("Dharavi", "dharavi")])
    def test_text_queries(self, q, expect):
        d = gsearch(q)
        assert d["results"], f"no results for {q}"
        assert "sources" in d and d["attribution"]
        names = [(x["name"] + " " + (x.get("address") or "")).lower() for x in d["results"]]
        assert any(expect in n for n in names), f"{q}: {names[:5]}"
        assert all(in_india(x) for x in d["results"]), q
        S.setdefault("hits", {})[q] = d["results"]
        time.sleep(1)

    @pytest.mark.parametrize("pin", ["560034", "793110"])
    def test_pin_queries(self, pin):
        d = gsearch(pin)
        assert "india_post" in d["sources"], d["sources"]
        assert any(x.get("pin") == pin for x in d["results"]), d["results"][:3]
        assert all(in_india(x) for x in d["results"])
        S.setdefault("pins", {})[pin] = d["results"]


# ---- Place enrichment
class TestPlace:
    def test_osm_place_district(self):
        r = requests.get(f"{API}/geo/place/osm_n3178190161", timeout=30)
        if r.status_code == 404:
            pytest.skip("osm_n3178190161 not cached in DB yet")
        assert r.status_code == 200, r.text
        d = r.json()
        assert "east khasi hills" in (d.get("district") or "").lower(), d

    def test_pin_post_office_place(self):
        offices = [x for x in S.get("pins", {}).get("560034", []) if x["type"] == "post_office"]
        if not offices:
            pytest.skip("no post office rows")
        r = requests.get(f"{API}/geo/place/{offices[0]['loc_id']}", timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["pin"] == "560034" and in_india(r.json())

    def test_place_404(self):
        assert requests.get(f"{API}/geo/place/osm_n0_nope", timeout=15).status_code == 404


# ---- PIN directory
class TestPincode:
    def test_pin_ok(self):
        r = requests.get(f"{API}/geo/pincode/560034", timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["offices"] and d["state"].lower() == "karnataka" and d["locations"]
        assert "_id" not in d and "geo" not in d

    def test_pin_invalid(self):
        assert requests.get(f"{API}/geo/pincode/000000", timeout=15).status_code == 400


# ---- Reverse geocoding
class TestReverse:
    def test_exact(self):
        r = requests.get(f"{API}/geo/reverse", params={"lat": 25.2019, "lng": 91.9155, "exact": "true"}, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["loc_id"].startswith("pin_") and abs(d["lat"] - 25.2019) < 1e-5 and abs(d["lng"] - 91.9155) < 1e-5
        assert d["name"]

    def test_outside(self):
        assert requests.get(f"{API}/geo/reverse", params={"lat": 51.5, "lng": -0.12}, timeout=15).status_code == 400


# ---- Routing
class TestRoute:
    def test_blr_chennai(self):
        r = requests.get(f"{API}/geo/route", params={"points": "12.9716,77.5946;13.0827,80.2707"}, timeout=40)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["source"].startswith("osrm"), d["source"]
        assert 1 <= len(d["routes"]) <= 3
        r0 = d["routes"][0]
        assert 280 <= r0["distance_km"] <= 400 and r0["duration_min"] > 200
        assert isinstance(r0["via"], list) and r0["toll_estimate"] >= 0 and len(r0["geometry"]) > 10

    def test_rural(self):
        r = requests.get(f"{API}/geo/route", params={"points": "25.2019,91.9155;25.5788,91.8933"}, timeout=40)
        assert r.status_code == 200, r.text
        assert r.json()["routes"][0]["distance_km"] > 30

    def test_with_stop(self):
        r = requests.get(f"{API}/geo/route", params={"points": "12.9716,77.5946;12.9165,79.1325;13.0827,80.2707"}, timeout=40)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["source"].startswith("osrm") and len(d["routes"]) == 1

    def test_invalid_points(self):
        assert requests.get(f"{API}/geo/route", params={"points": "abc"}, timeout=15).status_code == 400
        assert requests.get(f"{API}/geo/route", params={"points": "51.5,-0.1;12.9,77.5"}, timeout=15).status_code == 400


# ---- Nearby pickup points
class TestNearby:
    def test_nearby(self):
        t = time.time()
        r = requests.get(f"{API}/geo/nearby", params={"lat": 12.9716, "lng": 77.5946}, timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        print("nearby source", d["source"], len(d["results"]), round(time.time() - t, 1), "s")
        assert d["results"] and all("distance_m" in x for x in d["results"])


# ---- Status / admin sync / report
class TestSync:
    def test_status(self):
        d = requests.get(f"{API}/geo/status", timeout=20).json()
        assert "counts" in d and "providers" in d and d["counts"]["locations"] > 0

    def test_admin_only(self):
        tok = login("passenger@travoo.in", "Passenger@2026")
        assert requests.post(f"{API}/admin/geo/sync", headers=h(tok), timeout=20).status_code in (401, 403)
        assert requests.get(f"{API}/admin/geo/report", timeout=20).status_code in (401, 403)

    def test_admin_sync_and_report(self):
        tok = login("admin@travoo.in", "TravooAdmin@2026")
        r = requests.post(f"{API}/admin/geo/sync", headers=h(tok), timeout=180)
        assert r.status_code == 200, r.text
        assert r.json()["status"] in ("started", "running"), r.json()
        print("sync:", r.json())
        rep = requests.get(f"{API}/admin/geo/report", headers=h(tok), timeout=30)
        assert rep.status_code == 200 and "misses" in rep.json() and "last_stats" in rep.json()
        assert requests.get(f"{API}/geo/status", timeout=20).json()["last_success_at"]


# ---- Legacy endpoints
class TestLegacy:
    def test_legacy(self):
        r = requests.get(f"{API}/locations/search", params={"q": "beng"}, timeout=30)
        assert r.status_code == 200 and isinstance(r.json(), list) and r.json()
        r = requests.get(f"{API}/locations/osm", params={"q": "Hampi"}, timeout=30)
        assert r.status_code == 200 and isinstance(r.json(), list)
        r = requests.get(f"{API}/locations/reverse", params={"lat": 12.9716, "lng": 77.5946}, timeout=30)
        assert r.status_code == 200 and r.json()["name"]
        r = requests.get(f"{API}/route/estimate", params={"points": "12.9716,77.5946;13.0827,80.2707"}, timeout=30)
        assert r.status_code == 200 and r.json()["source"] == "osrm"


# ---- Trip publish stores route + along-route matching
class TestAlongRoute:
    @pytest.fixture(scope="class")
    def drv(self):
        tok = login("driver@travoo.in", "Driver@2026")
        veh = requests.get(f"{API}/driver/profile", headers=h(tok), timeout=20).json()["vehicles"][0]
        date = (datetime.now(IST) + timedelta(days=9)).strftime("%Y-%m-%d")
        body = {"origin": {"loc_id": "TEST_blr", "name": "Bengaluru", "type": "city", "state": "Karnataka", "lat": 12.9716, "lng": 77.5946},
                "destination": {"loc_id": "TEST_maa", "name": "Chennai", "type": "city", "state": "Tamil Nadu", "lat": 13.0827, "lng": 80.2707},
                "pickup_point": "TEST Majestic", "drop_point": "TEST Koyambedu", "date": date, "time": "06:00", "seats": 2, "price": 400,
                "vehicle_id": veh["vehicle_id"], "fuel_price": 102, "mileage": 15, "tolls": 300, "notes": "TEST_ along-route"}
        r = requests.post(f"{API}/trips", headers=h(tok), json=body, timeout=60)
        assert r.status_code == 200, r.text
        tid = r.json()["trip_id"]
        yield tok, tid, date
        requests.post(f"{API}/trips/{tid}/cancel", headers=h(tok), json={"reason": "TEST cleanup"}, timeout=20)

    def test_trip_has_route(self, drv):
        tok, tid, _ = drv
        t = requests.get(f"{API}/trips/{tid}", headers=h(tok), timeout=20).json()
        assert t["route_source"] == "osrm" and isinstance(t["route"], list) and len(t["route"]) > 10
        assert t.get("route_via") is not None and "toll_estimate" in t and "route_line" not in t

    def test_along_route_vellore(self, drv):
        _, tid, date = drv
        r = requests.get(f"{API}/trips/search", params={"from_lat": 12.9165, "from_lng": 79.1325, "to_lat": 13.0827, "to_lng": 80.2707,
                                                     "date": date}, timeout=30)
        assert r.status_code == 200, r.text
        m = [t for t in r.json()["trips"] if t["trip_id"] == tid]
        assert m and m[0]["match"]["type"] == "along_route", r.json()["trips"][:1]
        assert "route_line" not in m[0]

    def test_reverse_not_matched(self, drv):
        _, tid, date = drv
        r = requests.get(f"{API}/trips/search", params={"from_lat": 13.0827, "from_lng": 80.2707, "to_lat": 12.9165, "to_lng": 79.1325,
                                                     "date": date}, timeout=30)
        assert not [t for t in r.json()["trips"] if t["trip_id"] == tid]

    def test_direct(self, drv):
        _, tid, date = drv
        r = requests.get(f"{API}/trips/search", params={"from_lat": 12.97, "from_lng": 77.59, "to_lat": 13.08, "to_lng": 80.27, "date": date}, timeout=30)
        m = [t for t in r.json()["trips"] if t["trip_id"] == tid]
        assert m and m[0]["match"]["type"] == "direct"

    def test_with_stop_publish(self, drv):
        tok, _, date = drv
        veh = requests.get(f"{API}/driver/profile", headers=h(tok), timeout=20).json()["vehicles"][0]
        body = {"origin": {"loc_id": "TEST_blr2", "name": "Bengaluru", "lat": 12.9716, "lng": 77.5946},
                "destination": {"loc_id": "TEST_maa2", "name": "Chennai", "lat": 13.0827, "lng": 80.2707},
                "stops": [{"loc_id": "TEST_vel", "name": "Vellore", "lat": 12.9165, "lng": 79.1325}],
                "pickup_point": "TEST A", "drop_point": "TEST B", "date": date, "time": "07:00", "seats": 2, "price": 400,
                "vehicle_id": veh["vehicle_id"], "fuel_price": 102, "mileage": 15, "tolls": 300}
        r = requests.post(f"{API}/trips", headers=h(tok), json=body, timeout=60)
        assert r.status_code == 200, r.text
        tid = r.json()["trip_id"]
        try:
            t = requests.get(f"{API}/trips/{tid}", headers=h(tok), timeout=20).json()
            assert t["route_source"] == "osrm" and t["route"]
        finally:
            requests.post(f"{API}/trips/{tid}/cancel", headers=h(tok), json={"reason": "TEST cleanup"}, timeout=20)

    def test_demo_search(self):
        r = requests.get(f"{API}/trips/search", params={"from_lat": 12.9716, "from_lng": 77.5946, "to_lat": 13.0827, "to_lng": 80.2707}, timeout=30)
        assert r.status_code == 200 and r.json()["trips"], "no seeded BLR->Chennai trips"


# ---- Known issues found in iteration 5 (expected to pass once fixed by main agent)
class TestKnownIssues:
    @pytest.mark.parametrize("alias,city", [("Bangalore", "Bengaluru"), ("Bombay", "Mumbai"), ("Mysore", "Mysuru")])
    def test_alias_ranks_curated_city_top3(self, alias, city):
        names = [x["name"] for x in gsearch(alias)["results"][:3]]
        assert city in names, f"{alias}: top3={names}"

    def test_degenerate_route_line_no_500(self):
        tok = login("driver@travoo.in", "Driver@2026")
        veh = requests.get(f"{API}/driver/profile", headers=h(tok), timeout=20).json()["vehicles"][0]
        date = (datetime.now(IST) + timedelta(days=12)).strftime("%Y-%m-%d")
        p = {"lat": 12.9716, "lng": 77.5946}
        body = {"origin": {"loc_id": "TEST_same_a", "name": "TEST A", **p}, "destination": {"loc_id": "TEST_same_b", "name": "TEST B", **p},
                "pickup_point": "TEST p", "drop_point": "TEST d", "date": date, "time": "09:00", "seats": 1, "price": 50,
                "vehicle_id": veh["vehicle_id"], "fuel_price": 102, "mileage": 15}
        r = requests.post(f"{API}/trips", headers=h(tok), json=body, timeout=60)
        if r.status_code == 200:
            requests.post(f"{API}/trips/{r.json()['trip_id']}/cancel", headers=h(tok), json={"reason": "TEST cleanup"}, timeout=20)
        assert r.status_code in (200, 400), f"{r.status_code} {r.text[:200]}"
