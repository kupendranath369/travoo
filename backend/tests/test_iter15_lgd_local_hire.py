"""Iteration 15: LGD admin locations, taluk identification, hire-driver home taluk, exact-taluk matching,
broadcast hire requests, accept/decline/cancel. Run: pytest tests/test_iter15_lgd_local_hire.py -c /dev/null -p no:xdist -v"""
import uuid
from datetime import datetime, timedelta

import pytest
import requests
from pymongo import MongoClient

from test_travoo_api import API, h
from test_iter8_admin_docs_reset import real_image
from test_iter10_capacity_pricing_photo import admin_token, loc, reg

S = {"drivers": {}, "requests": []}
HIRIYUR, HOLALKERE, GAJWEL = "5508", "5506", "4483"


def _db():
    env = dict(l.strip().split("=", 1) for l in open("/app/backend/.env") if "=" in l)
    return MongoClient(env["MONGO_URL"].strip('"'))[env["DB_NAME"].strip('"')]


def future_date(days=4):
    return (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")


def pro_body(city, sub, **kw):
    b = {"city": city, "home": {"subdistrict_code": sub, "city": "TEST Town"}, "languages": ["Kannada", "English"],
         "experience_years": 5, "licence_no": "KA0120201234567", "licence_expiry": "01-01-2035", "vehicle_types": ["sedan", "suv"],
         "days": [0, 1, 2, 3, 4, 5, 6], "start_time": "06:00", "end_time": "20:00", "bio": "TEST experienced local driver for hire",
         "rate_hourly": 200, "rate_half_day": 800, "rate_full_day": 1500}
    b.update(kw)
    return b


def make_driver(key, sub, approve=True, **kw):
    tok, uid, _ = reg(f"Hire{key}")
    assert requests.put(f"{API}/me", headers=h(tok), json={"phone": f"98{uuid.uuid4().int % 10**8:08d}"}).status_code == 200
    assert requests.post(f"{API}/me/photo", headers=h(tok), files={"file": ("p.jpg", real_image(uuid.uuid4().int % 900), "image/jpeg")}, timeout=120).status_code == 200
    r = requests.post(f"{API}/driver/documents/licence_front", headers=h(tok), files={"file": ("l.jpg", real_image(uuid.uuid4().int % 900 + 1), "image/jpeg")}, timeout=120)
    assert r.status_code == 200, r.text
    r = requests.post(f"{API}/pro/register", headers=h(tok), json=pro_body(S["city"], sub, **kw))
    assert r.status_code == 200, r.text
    if approve:
        r = requests.post(f"{API}/admin/pro-drivers/{uid}/review", headers=h(S["adm"]), json={"decision": "approved", "note": "TEST"})
        assert r.status_code == 200, r.text
    S["drivers"][key] = (tok, uid)
    return tok, uid


# ---- LGD reference data
class TestLGD:
    def test_states(self):
        d = requests.get(f"{API}/lgd/states").json()
        lab = {s["name"]: s["sub_label"] for s in d}
        assert len(d) == 36
        assert lab["Karnataka"] == "Taluk" and lab["Telangana"] == "Mandal" and lab["Uttar Pradesh"] == "Tehsil" and lab["Maharashtra"] == "Taluka"

    def test_districts_subdistricts_villages(self):
        d = requests.get(f"{API}/lgd/districts", params={"state_code": "29"}).json()
        assert len(d) == 31 and any(x["code"] == "533" and x["name"] == "Chitradurga" for x in d)
        sd = requests.get(f"{API}/lgd/subdistricts", params={"district_code": "533"}).json()
        assert any(x["code"] == HIRIYUR and x["name"] == "Hiriyur" for x in sd)
        v = requests.get(f"{API}/lgd/villages", params={"subdistrict_code": HIRIYUR, "q": "Hi"}).json()
        assert v and all(x["name"].lower().startswith("hi") or "hi" in x["name"].lower() for x in v)
        S["village"] = v[0]["code"]

    def test_search_and_status(self):
        r = requests.get(f"{API}/lgd/subdistricts/search", params={"q": "Hiriyur"}).json()
        assert r[0]["code"] == HIRIYUR and r[0]["district_name"] == "Chitradurga"
        c = requests.get(f"{API}/lgd/status").json()["counts"]
        assert c == {"states": 36, "districts": 790, "subdistricts": 7112, "villages": 677660}


# ---- pickup taluk identification
class TestIdentify:
    @pytest.mark.parametrize("place,taluk,state", [("Hiriyur", "Hiriyur", "Karnataka"), ("Gajwel", "Gajwel", "Telangana"),
                                                    ("Baramati", "Baramati", "Maharashtra"), ("Sitapur", "Sitapur", "Uttar Pradesh"),
                                                    ("Pushkar", "Ajmer", "Rajasthan")])
    def test_identify(self, place, taluk, state):
        res = requests.get(f"{API}/geo/search", params={"q": place}, timeout=60).json()["results"]
        assert res, place
        r = requests.get(f"{API}/hire/identify-taluk", params={"loc_id": res[0]["loc_id"], "pickup": place}, timeout=60)
        assert r.status_code == 200, r.text
        sd = r.json().get("subdistrict") or {}
        print(place, "->", sd.get("name"), sd.get("district_name"), sd.get("state_name"), r.json().get("method"), r.json().get("confidence"))
        assert sd.get("state_name") == state, r.json()
        if place != "Pushkar":
            assert sd.get("name", "").lower().startswith(taluk.lower()[:5]), r.json()

    def test_identify_unknown_loc_404(self):
        assert requests.get(f"{API}/hire/identify-taluk", params={"loc_id": "nope_x"}).status_code == 404


# ---- driver registration with home taluk
class TestProRegister:
    def test_setup(self):
        S["adm"] = admin_token()
        assert S["adm"]
        S["city"] = loc("Hiriyur")
        S["pax"], S["pax_id"], _ = reg("HirePax")

    def test_invalid_home(self):
        tok, uid, _ = reg("HireBad")
        requests.put(f"{API}/me", headers=h(tok), json={"phone": f"97{uuid.uuid4().int % 10**8:08d}"})
        requests.post(f"{API}/me/photo", headers=h(tok), files={"file": ("p.jpg", real_image(11), "image/jpeg")}, timeout=120)
        requests.post(f"{API}/driver/documents/licence_front", headers=h(tok), files={"file": ("l.jpg", real_image(12), "image/jpeg")}, timeout=120)
        S["bad"] = (tok, uid)
        r = requests.post(f"{API}/pro/register", headers=h(tok), json=pro_body(S["city"], "999999"))
        assert r.status_code == 400, r.text
        b = pro_body(S["city"], HIRIYUR)
        b["home"]["village_code"] = "1"  # not in Hiriyur
        r = requests.post(f"{API}/pro/register", headers=h(tok), json=b)
        assert r.status_code == 400, r.text
        b = pro_body(S["city"], HIRIYUR)
        b.pop("home")
        assert requests.post(f"{API}/pro/register", headers=h(tok), json=b).status_code == 422

    def test_register_drivers(self):
        make_driver("A", HIRIYUR, home={"subdistrict_code": HIRIYUR, "city": "Hiriyur", "village_code": S.get("village")})
        make_driver("B", HIRIYUR)
        make_driver("C", HIRIYUR)
        make_driver("D", HOLALKERE)
        make_driver("E", GAJWEL)
        p = requests.get(f"{API}/pro/me", headers=h(S["drivers"]["A"][0])).json()["profile"]
        hm = p["home"]
        assert p["status"] == "approved" and hm["subdistrict_code"] == HIRIYUR and hm["subdistrict_name"] == "Hiriyur"
        assert hm["district_name"] == "Chitradurga" and hm["state_name"] == "Karnataka" and hm["village_code"] == S.get("village") and hm["village_name"]

    def test_put_home_rejected_when_set(self):
        r = requests.put(f"{API}/pro/home", headers=h(S["drivers"]["A"][0]), json={"subdistrict_code": GAJWEL, "city": "X Town"})
        assert r.status_code == 400, r.text

    def test_unavailable(self):
        r = requests.put(f"{API}/pro/availability", headers=h(S["drivers"]["C"][0]), json={"available": False})
        assert r.status_code == 200 and r.json()["available"] is False and r.json()["home"]["subdistrict_code"] == HIRIYUR


def local(params, tok=None):
    r = requests.get(f"{API}/hire/local-drivers", headers=h(tok or S["pax"]), params=params)
    assert r.status_code == 200, r.text
    return r.json()


# ---- matching
class TestMatching:
    def test_local_only_hiriyur(self):
        d = local({"subdistrict_code": HIRIYUR, "date": future_date(), "time": "10:00", "hours": 4})
        ids = {x["user_id"] for x in d["local"]}
        A, B, C, D, E = (S["drivers"][k][1] for k in "ABCDE")
        assert A in ids and B in ids and C not in ids and D not in ids and E not in ids
        assert all(x["home"]["subdistrict_code"] == HIRIYUR for x in d["local"]) and d["nearby"] is None

    def test_nearby_group(self):
        d = local({"subdistrict_code": HIRIYUR, "date": future_date(), "time": "10:00", "hours": 4, "nearby": "true"})
        near = {x["user_id"] for x in d["nearby"]}
        assert S["drivers"]["D"][1] in near and S["drivers"]["E"][1] not in near and S["drivers"]["A"][1] not in near
        assert all(x["home"]["district_code"] == "533" and x["home"]["subdistrict_code"] != HIRIYUR for x in d["nearby"])

    def test_time_outside_window(self):
        d = local({"subdistrict_code": HIRIYUR, "date": future_date(), "time": "21:30", "hours": 2})
        assert not ({S["drivers"]["A"][1], S["drivers"]["B"][1]} & {x["user_id"] for x in d["local"]})

    def test_vehicle_filter(self):
        d = local({"subdistrict_code": HIRIYUR, "date": future_date(), "time": "10:00", "hours": 4, "vehicle_type": "luxury"})
        assert S["drivers"]["A"][1] not in {x["user_id"] for x in d["local"]}


def req_body(**kw):
    b = {"service_type": "hourly", "date": future_date(), "time": "10:00", "hours": 4, "city": S["city"], "pickup": "Hiriyur Bus Stand",
         "destination": "Bengaluru", "passengers": 2, "vehicle_type": "sedan", "vehicle_desc": "TEST Swift Dzire", "subdistrict_code": HIRIYUR}
    b.update(kw)
    return b


# ---- broadcast + accept flow
class TestRequests:
    def test_broadcast_local(self):
        expected = {x["user_id"] for x in local({"subdistrict_code": HIRIYUR, "date": future_date(), "time": "10:00", "hours": 4, "vehicle_type": "sedan"})["local"]}
        r = requests.post(f"{API}/hire/requests", headers=h(S["pax"]), json=req_body())
        assert r.status_code == 200, r.text
        d = r.json()
        S["rid"] = d["request_id"]
        S["requests"].append(d["request_id"])
        assert d["request_id"].startswith("LHR-") and d["notified"] == len(expected) and d["pickup_taluk"]["code"] == HIRIYUR
        disp = list(_db().hire_dispatches.find({"request_id": S["rid"]}, {"_id": 0}))
        assert {x["driver_id"] for x in disp} == expected and len(disp) == len(expected) and all(x["group"] == "local" for x in disp)
        for k in "AB":
            n = list(_db().notifications.find({"user_id": S["drivers"][k][1], "type": "local_hire_request", "ref": S["rid"]}, {"_id": 0}))
            assert len(n) == 1, n
            print("notif", n[0])
        for k in "CDE":
            assert _db().notifications.count_documents({"user_id": S["drivers"][k][1], "ref": S["rid"]}) == 0

    def test_duplicate_409(self):
        assert requests.post(f"{API}/hire/requests", headers=h(S["pax"]), json=req_body()).status_code == 409

    def test_no_drivers_404(self):
        r = requests.post(f"{API}/hire/requests", headers=h(S["pax"]), json=req_body(time="22:00", subdistrict_code=HOLALKERE, vehicle_type="luxury"))
        assert r.status_code == 404, r.text

    def test_lists_seen_delivery(self):
        A = S["drivers"]["A"][0]
        inbox = requests.get(f"{API}/hire/requests", headers=h(A)).json()["inbox"]
        assert any(x["request_id"] == S["rid"] for x in inbox)
        mine = requests.get(f"{API}/hire/requests", headers=h(S["pax"])).json()["mine"]
        assert any(x["request_id"] == S["rid"] for x in mine)
        assert requests.get(f"{API}/hire/requests/{S['rid']}", headers=h(A)).status_code == 200
        d = requests.get(f"{API}/hire/requests/{S['rid']}", headers=h(S["pax"])).json()["delivery"]
        assert d["seen"] >= 1 and d["notified"] >= 2
        assert requests.get(f"{API}/hire/requests/{S['rid']}", headers=h(S["drivers"]["E"][0])).status_code == 404

    def test_non_dispatched_accept_404(self):
        assert requests.post(f"{API}/hire/requests/{S['rid']}/accept", headers=h(S["drivers"]["D"][0])).status_code == 404
        assert requests.post(f"{API}/hire/requests/{S['rid']}/cancel", headers=h(S["drivers"]["A"][0])).status_code == 403

    def test_accept_flow(self):
        r = requests.post(f"{API}/hire/requests/{S['rid']}/accept", headers=h(S["drivers"]["A"][0]))
        assert r.status_code == 200 and r.json()["booking_id"].startswith("HIR-"), r.text
        S["bid"] = r.json()["booking_id"]
        hire = _db().hires.find_one({"booking_id": S["bid"]})
        assert hire["status"] == "confirmed" and hire["driver_id"] == S["drivers"]["A"][1]
        assert _db().notifications.count_documents({"user_id": S["pax_id"], "type": "hire_confirmed", "ref": S["bid"]}) == 1
        assert _db().notifications.count_documents({"user_id": S["drivers"]["B"][1], "type": "local_hire_closed", "ref": S["rid"]}) == 1
        assert requests.post(f"{API}/hire/requests/{S['rid']}/accept", headers=h(S["drivers"]["B"][0])).status_code == 409
        assert requests.post(f"{API}/hire/requests/{S['rid']}/accept", headers=h(S["drivers"]["A"][0])).status_code == 409
        assert requests.post(f"{API}/hire/requests/{S['rid']}/cancel", headers=h(S["pax"])).status_code == 400

    def test_conflict_excluded(self):
        d = local({"subdistrict_code": HIRIYUR, "date": future_date(), "time": "11:00", "hours": 2})
        ids = {x["user_id"] for x in d["local"]}
        assert S["drivers"]["A"][1] not in ids and S["drivers"]["B"][1] in ids

    def test_nearby_broadcast_decline_cancel(self):
        r = requests.post(f"{API}/hire/requests", headers=h(S["pax"]), json=req_body(time="15:00", include_nearby=True))
        assert r.status_code == 200, r.text
        rid = r.json()["request_id"]
        S["requests"].append(rid)
        groups = {x["driver_id"]: x["group"] for x in _db().hire_dispatches.find({"request_id": rid})}
        assert groups.get(S["drivers"]["D"][1]) == "nearby" and groups.get(S["drivers"]["B"][1]) == "local" and S["drivers"]["E"][1] not in groups
        assert requests.post(f"{API}/hire/requests/{rid}/decline", headers=h(S["drivers"]["D"][0])).status_code == 200
        assert requests.post(f"{API}/hire/requests/{rid}/decline", headers=h(S["drivers"]["D"][0])).status_code == 409
        d = requests.get(f"{API}/hire/requests/{rid}", headers=h(S["pax"])).json()["delivery"]
        assert d["declined"] == 1
        assert requests.post(f"{API}/hire/requests/{rid}/cancel", headers=h(S["pax"])).status_code == 200
        assert requests.post(f"{API}/hire/requests/{rid}/accept", headers=h(S["drivers"]["B"][0])).status_code == 409


# ---- regression
class TestRegression:
    def test_hire_drivers_legacy(self):
        c = S["city"]
        r = requests.get(f"{API}/hire/drivers", headers=h(S["pax"]), params={"lat": c["lat"], "lng": c["lng"], "date": future_date()})
        assert r.status_code == 200, r.text

    def test_carpool_search_and_login(self):
        assert requests.get(f"{API}/locations/search", params={"q": "Bengaluru"}).status_code == 200
        assert requests.get(f"{API}/auth/me", headers=h(S["pax"])).status_code == 200
