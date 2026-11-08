"""TRAVOO iteration 4: route estimate, cost-sharing cap + return trip, recent searches, missing places, fuel prices,
Hire-a-Driver flow (pro register/approve/search/book/mask/accept/start/complete/review), chat conversations/read ticks/system msgs,
public verified photo."""
import io
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from PIL import Image

from test_travoo_api import API, h, login, register, loc, future, upload_docs, IST

JPEG = io.BytesIO()
Image.new("RGB", (8, 8), (20, 120, 200)).save(JPEG, "JPEG")
JPEG = JPEG.getvalue()
S = {}


def next_weekday_date(days_ahead=3):
    d = datetime.now(IST) + timedelta(days=days_ahead)
    return d.strftime("%Y-%m-%d"), d.weekday()


@pytest.fixture(scope="module")
def admin():
    return login("admin@travoo.in", "TravooAdmin@2026")


@pytest.fixture(scope="module")
def carpool_driver(admin):
    tok, user, _ = register("drv4")
    upload_docs(tok)
    r = requests.post(f"{API}/driver/verification", headers=h(tok), json={
        "legal_name": "TEST Driver4", "vehicle_name": "Maruti Ertiga", "phone": "9876543210", "licence_no": "KA0120201234567",
        "licence_expiry": "01-01-2030", "rc_no": "KA01AB9999"})
    assert r.status_code == 200, r.text
    if r.json()["status"] != "approved":
        r = requests.post(f"{API}/admin/drivers/{user['user_id']}/review", headers=h(admin), json={"decision": "approved"})
        assert r.status_code == 200, r.text
    v = requests.post(f"{API}/vehicles", headers=h(tok), json={"make": "Maruti", "model": "Ertiga", "vtype": "muv",
                                                               "reg_no": f"KA01T{uuid.uuid4().hex[:4].upper()}", "seats": 6, "ac": True, "mileage": 15})
    assert v.status_code == 200, v.text
    v = v.json()
    return tok, user, v["vehicle_id"]


# ---- Route estimate
class TestRouteEstimate:
    def test_estimate_blr_chennai(self):
        r = requests.get(f"{API}/route/estimate", params={"points": "12.9716,77.5946;13.0827,80.2707"}, timeout=40)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["source"] in ("osrm", "estimate") and 250 < d["distance_km"] < 450, d
        S["route_source"] = d["source"]

    def test_estimate_invalid(self):
        assert requests.get(f"{API}/route/estimate", params={"points": "abc"}).status_code == 400
        assert requests.get(f"{API}/route/estimate", params={"points": "12.9,77.5"}).status_code == 400


# ---- Cost sharing, price cap, return trip
class TestCostSharing:
    def body(self, veh, price, **kw):
        return {"origin": loc("Bengaluru"), "destination": loc("Chennai"), "pickup_point": "TEST Silk Board",
                "drop_point": "TEST Koyambedu", "date": future(5), "time": "09:00", "seats": 3, "price": price,
                "vehicle_id": veh, "instant_booking": False, "fuel_price": 102, "mileage": 15, "tolls": 400,
                "maintenance_per_km": 2, "share_mode": "equal", **kw}

    def test_price_cap_and_breakdown(self, carpool_driver):
        tok, _, veh = carpool_driver
        r = requests.post(f"{API}/trips", headers=h(tok), json=self.body(veh, 600), timeout=60)
        assert r.status_code == 200, r.text
        t = r.json()
        cb = t["cost_breakdown"]
        km = t["distance_km"]
        exp_total = round(km / 15 * 102 + 400 + km * 2)
        assert abs(cb["total"] - exp_total) <= 1 and cb["sharers"] == 4
        assert cb["recommended"] == max(50, round(cb["total"] / 4))
        cap = round(cb["recommended"] * 1.5)
        S["cap"], S["trip_ok"] = cap, t["trip_id"]
        r2 = requests.post(f"{API}/trips", headers=h(tok), json=self.body(veh, cap + 1), timeout=60)
        assert r2.status_code == 400 and "limit" in r2.text, r2.text
        r3 = requests.post(f"{API}/trips", headers=h(tok), json=self.body(veh, cap, date=future(6)), timeout=60)
        assert r3.status_code == 200, r3.text
        S["trip_cap"] = r3.json()["trip_id"]

    def test_return_trip(self, carpool_driver):
        tok, _, veh = carpool_driver
        r = requests.post(f"{API}/trips", headers=h(tok), json=self.body(veh, 500, date=future(8), return_date=future(9), return_time="17:00"), timeout=60)
        assert r.status_code == 200, r.text
        tid = r.json()["trip_id"]
        mine = requests.get(f"{API}/trips/mine", headers=h(tok)).json()
        mine = mine if isinstance(mine, list) else mine.get("items", mine.get("trips", []))
        ret = [x for x in mine if x.get("return_of") == tid]
        assert len(ret) == 1, mine
        rt = ret[0]
        assert rt["origin"]["name"] == r.json()["destination"]["name"] and rt["date"] == future(9) and rt["time"] == "17:00"
        assert rt.get("cost_breakdown")
        # return before outbound -> 400
        r2 = requests.post(f"{API}/trips", headers=h(tok), json=self.body(veh, 500, date=future(10), return_date=future(9), return_time="09:00"), timeout=60)
        assert r2.status_code == 400

    def test_price_cap_bypass_without_fuel_price(self, carpool_driver):
        """Observation: cap only enforced when fuel_price sent."""
        tok, _, veh = carpool_driver
        b = self.body(veh, 5000, date=future(11))
        b.pop("fuel_price")
        r = requests.post(f"{API}/trips", headers=h(tok), json=b, timeout=60)
        S["bypass_status"] = r.status_code
        print("cap bypass without fuel_price ->", r.status_code)


# ---- Recent searches
class TestSearches:
    def test_upsert_max10_clear(self):
        tok, _, _ = register("srch")
        o, d = loc("Bengaluru"), loc("Chennai")
        for _ in range(2):
            assert requests.post(f"{API}/searches", headers=h(tok), json={"kind": "intercity", "origin": o, "destination": d, "date": future(2)}).status_code == 200
        rows = requests.get(f"{API}/searches", headers=h(tok)).json()
        assert len(rows) == 1 and rows[0]["origin"]["name"] == o["name"]
        for i in range(12):
            requests.post(f"{API}/searches", headers=h(tok), json={"kind": "hire", "origin": o, "service": f"svc{i}"})
        assert len(requests.get(f"{API}/searches", headers=h(tok)).json()) == 10
        assert requests.delete(f"{API}/searches", headers=h(tok)).status_code == 200
        assert requests.get(f"{API}/searches", headers=h(tok)).json() == []


# ---- Missing places
class TestMissingPlace:
    def test_submit_approve_search(self, admin):
        tok, _, _ = register("plc")
        name = f"TESTPlace{uuid.uuid4().hex[:6]}"
        r = requests.post(f"{API}/locations/missing", headers=h(tok), json={"name": name, "ltype": "village", "district": "Mandya",
                                                                          "state": "Karnataka", "pin": "571401", "lat": 12.52, "lng": 76.9})
        assert r.status_code == 200, r.text
        rid = r.json()["request_id"]
        assert r.json()["status"] == "pending"
        assert requests.get(f"{API}/locations/search", params={"q": name}).json() == []
        assert requests.get(f"{API}/admin/locations/missing", headers=h(tok)).status_code == 403
        lst = requests.get(f"{API}/admin/locations/missing", headers=h(admin)).json()
        assert any(x["request_id"] == rid for x in lst)
        assert requests.post(f"{API}/admin/locations/missing/{rid}", headers=h(admin), json={"decision": "approved"}).status_code == 200
        res = requests.get(f"{API}/locations/search", params={"q": name}).json()
        assert any(x["name"] == name for x in res), res
        assert requests.post(f"{API}/admin/locations/missing/{rid}", headers=h(admin), json={"decision": "approved"}).status_code == 404

    def test_validation(self):
        tok, _, _ = register("plc2")
        r = requests.post(f"{API}/locations/missing", headers=h(tok), json={"name": "X", "district": "M", "state": "K", "lat": 1, "lng": 1})
        assert r.status_code == 422


# ---- Fuel prices
class TestFuel:
    def test_admin_set_and_public_get(self, admin):
        st = "TEST_State"
        assert requests.post(f"{API}/admin/fuel-prices", headers=h(admin), json={"state": st, "fuel_type": "diesel", "price": 91.5}).status_code == 200
        d = requests.get(f"{API}/fuel-prices", params={"state": st}).json()
        assert d["prices"]["diesel"]["price"] == 91.5 and d["max_price_factor"] == 1.5
        print("default fuel prices:", requests.get(f"{API}/fuel-prices").json()["prices"])
        tok, _, _ = register("fuel")
        assert requests.post(f"{API}/admin/fuel-prices", headers=h(tok), json={"fuel_type": "diesel", "price": 1}).status_code == 403


# ---- Hire a driver + chat
class TestHire:
    def test_pro_register_and_approve(self, admin):
        tok, user, _ = register("pro")
        city = loc("Bengaluru")
        date, wd = next_weekday_date(3)
        body = {"city": city, "languages": ["Kannada", "English"], "experience_years": 6, "licence_no": "KA0120191234567",
                "licence_expiry": "01-01-2031", "vehicle_types": ["sedan", "suv"], "days": [wd], "start_time": "06:00",
                "end_time": "22:00", "bio": "TEST experienced professional driver in Bengaluru", "rate_hourly": 200,
                "rate_half_day": 700, "rate_full_day": 1300, "rate_one_way": 600}
        r = requests.post(f"{API}/pro/register", headers=h(tok), json=body)
        assert r.status_code == 400 and "mobile" in r.text
        assert requests.put(f"{API}/me", headers=h(tok), json={"phone": "9812345678"}).status_code == 200
        r = requests.post(f"{API}/pro/register", headers=h(tok), json=body)
        assert r.status_code == 400 and "upload" in r.text.lower()
        for k in ("profile", "licence"):
            u = requests.post(f"{API}/driver/documents/{k}", headers=h(tok), files={"file": ("a.jpg", JPEG, "image/jpeg")}, timeout=120)
            assert u.status_code == 200, u.text
        # photo not public before approval
        assert requests.get(f"{API}/public/photo/{user['user_id']}").status_code == 404
        r = requests.post(f"{API}/pro/register", headers=h(tok), json=body)
        assert r.status_code == 200 and r.json()["status"] == "under_review", r.text
        pend = requests.get(f"{API}/admin/pro-drivers", headers=h(admin)).json()
        assert any(p["user_id"] == user["user_id"] for p in pend)
        r = requests.post(f"{API}/admin/pro-drivers/{user['user_id']}/review", headers=h(admin), json={"decision": "approved"})
        assert r.status_code == 200
        p = requests.get(f"{API}/public/photo/{user['user_id']}")
        assert p.status_code == 200 and p.headers["content-type"].startswith("image/")
        S.update(pro_tok=tok, pro_uid=user["user_id"], city=city, date=date)

    def test_search_and_book_masked(self):
        ctok, cust, _ = register("cust")
        requests.put(f"{API}/me", headers=h(ctok), json={"phone": "9898989898"})
        c = S["city"]
        res = requests.get(f"{API}/hire/drivers", headers=h(ctok), params={"lat": c["lat"], "lng": c["lng"], "date": S["date"],
                                                                         "service": "half_day"}).json()
        mine = [x for x in res if x["user_id"] == S["pro_uid"]]
        assert mine and mine[0]["estimate"] == 700 and mine[0]["user"]["has_photo"] is True
        assert "licence_no" not in mine[0]
        b = {"driver_id": S["pro_uid"], "service_type": "half_day", "date": S["date"], "time": "10:00", "hours": 4, "city": c,
             "pickup": "TEST Indiranagar", "destination": "TEST Airport", "vehicle_type": "sedan", "vehicle_desc": "TEST Honda City"}
        r = requests.post(f"{API}/hire/bookings", headers=h(ctok), json=b)
        assert r.status_code == 200, r.text
        hb = r.json()
        assert hb["booking_id"].startswith("HIR-") and hb["status"] == "pending" and hb["service_fee"] == 700
        assert requests.post(f"{API}/hire/bookings", headers=h(ctok), json=b).status_code == 409
        g = requests.get(f"{API}/hire/bookings/{hb['booking_id']}", headers=h(ctok)).json()
        assert g["driver"]["phone_masked"] is True and "9812345678" not in g["driver"]["phone"]
        S.update(cust_tok=ctok, cust_uid=cust["user_id"], hid=hb["booking_id"])

    def test_chat_before_accept_and_unread(self):
        hid = S["hid"]
        m = requests.post(f"{API}/bookings/{hid}/messages", headers=h(S["cust_tok"]), json={"text": "TEST hello driver"})
        assert m.status_code == 200, m.text
        conv = requests.get(f"{API}/conversations", headers=h(S["pro_tok"])).json()
        item = [x for x in conv["items"] if x["booking_id"] == hid][0]
        assert item["kind"] == "hire" and item["unread"] >= 1
        msgs = requests.get(f"{API}/bookings/{hid}/messages", headers=h(S["cust_tok"])).json()
        mine = [x for x in msgs if x["sender_id"] == S["cust_uid"]]
        assert mine[0]["status"] == "delivered"
        requests.get(f"{API}/bookings/{hid}/messages", headers=h(S["pro_tok"]))  # driver reads
        msgs = requests.get(f"{API}/bookings/{hid}/messages", headers=h(S["cust_tok"])).json()
        assert [x for x in msgs if x["sender_id"] == S["cust_uid"]][0]["status"] == "read"
        conv = requests.get(f"{API}/conversations", headers=h(S["pro_tok"])).json()
        assert [x for x in conv["items"] if x["booking_id"] == hid][0]["unread"] == 0
        out_tok, _, _ = register("outsider")
        assert requests.get(f"{API}/bookings/{hid}/messages", headers=h(out_tok)).status_code == 404
        assert requests.get(f"{API}/hire/bookings/{hid}", headers=h(out_tok)).status_code == 404

    def test_accept_unmask_start_complete_review(self):
        hid = S["hid"]
        assert requests.post(f"{API}/hire/bookings/{hid}/accept", headers=h(S["cust_tok"]), json={}).status_code == 403
        r = requests.post(f"{API}/hire/bookings/{hid}/accept", headers=h(S["pro_tok"]), json={})
        assert r.status_code == 200, r.text
        g = requests.get(f"{API}/hire/bookings/{hid}", headers=h(S["cust_tok"])).json()
        assert g["status"] == "confirmed" and g["driver"]["phone"] == "9812345678" and g["driver"]["phone_masked"] is False
        gd = requests.get(f"{API}/hire/bookings/{hid}", headers=h(S["pro_tok"])).json()
        assert gd["customer"]["phone"] == "9898989898" and gd["is_driver"] is True
        msgs = requests.get(f"{API}/bookings/{hid}/messages", headers=h(S["cust_tok"])).json()
        sys_types = [m.get("sys_type") for m in msgs if m["sender_id"] == "system"]
        assert "hire_request" in sys_types and "hire_confirmed" in sys_types, sys_types
        assert requests.post(f"{API}/hire/bookings/{hid}/start", headers=h(S["pro_tok"]), json={}).status_code == 200
        assert requests.post(f"{API}/hire/bookings/{hid}/complete", headers=h(S["pro_tok"]), json={}).status_code == 200
        assert requests.post(f"{API}/hire/bookings/{hid}/complete", headers=h(S["pro_tok"]), json={}).status_code == 400
        r = requests.post(f"{API}/reviews", headers=h(S["cust_tok"]), json={"booking_id": hid, "target_id": S["pro_uid"], "rating": 5, "comment": "TEST great"})
        assert r.status_code == 200, r.text
        prof = requests.get(f"{API}/users/{S['pro_uid']}/profile", headers=h(S["cust_tok"])).json()
        assert prof["verified"] and prof["user"]["has_photo"] and prof["completed_journeys"] >= 1 and prof["user"].get("bio")
        assert any(rv["booking_id"] == hid for rv in prof["reviews"])

    def test_cancel_system_message(self):
        c = S["city"]
        b = {"driver_id": S["pro_uid"], "service_type": "hourly", "date": future(4), "time": "10:00", "hours": 2, "city": c,
             "pickup": "TEST MG Road", "vehicle_type": "sedan", "vehicle_desc": "TEST Swift"}
        r = requests.post(f"{API}/hire/bookings", headers=h(S["cust_tok"]), json=b)
        assert r.status_code == 200, r.text
        hid = r.json()["booking_id"]
        assert requests.post(f"{API}/hire/bookings/{hid}/cancel", headers=h(S["cust_tok"]), json={"reason": "TEST"}).status_code == 200
        msgs = requests.get(f"{API}/bookings/{hid}/messages", headers=h(S["pro_tok"])).json()
        assert any(m.get("sys_type") == "hire_cancelled" for m in msgs)


# ---- Public photo + has_photo in ride search
class TestPublicPhoto:
    def test_photo_404_for_unapproved(self):
        _, u, _ = register("nophoto")
        assert requests.get(f"{API}/public/photo/{u['user_id']}").status_code == 404
        assert requests.get(f"{API}/public/photo/nonexistent_uid").status_code == 404

    def test_search_has_photo(self, carpool_driver):
        o, d = loc("Bengaluru"), loc("Chennai")
        r = requests.get(f"{API}/trips/search", params={"date": future(5), "from_lat": o["lat"], "from_lng": o["lng"], "to_lat": d["lat"], "to_lng": d["lng"]})
        assert r.status_code == 200, r.text
        rows = r.json()["trips"]
        print("search rows", len(rows))
        assert rows and all("has_photo" in x["driver"] for x in rows)


# ---- Carpool conversations + system message after accept (regression for chat)
class TestCarpoolChat:
    def test_carpool_conv_sys_msg(self, carpool_driver):
        tok, _, veh = carpool_driver
        b = TestCostSharing().body(veh, 500, date=future(12))
        b["instant_booking"] = False
        t = requests.post(f"{API}/trips", headers=h(tok), json=b, timeout=60)
        assert t.status_code == 200, t.text
        ptok, _, _ = register("cpass")
        bk = requests.post(f"{API}/bookings", headers=h(ptok), json={"trip_id": t.json()["trip_id"], "seats": 1})
        assert bk.status_code == 200, bk.text
        bid = bk.json()["booking_id"]
        assert requests.post(f"{API}/bookings/{bid}/accept", headers=h(tok), json={}).status_code == 200
        conv = requests.get(f"{API}/conversations", headers=h(ptok)).json()
        it = [x for x in conv["items"] if x["booking_id"] == bid]
        assert it and it[0]["kind"] == "carpool" and it[0]["unread"] >= 1 and conv["unread"] >= 1
        msgs = requests.get(f"{API}/bookings/{bid}/messages", headers=h(ptok)).json()
        assert any(m["sender_id"] == "system" and m.get("sys_type") == "booking_confirmed" for m in msgs), msgs
        assert requests.post(f"{API}/bookings/{bid}/cancel", headers=h(ptok), json={}).status_code == 200
        msgs = requests.get(f"{API}/bookings/{bid}/messages", headers=h(tok)).json()
        print("sys types after cancel:", [m.get("sys_type") for m in msgs])
