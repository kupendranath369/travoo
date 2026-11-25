"""Iteration 25: Local Driver redesign - 3-step register, shared vehicles, admin review/suspend, settings/availability,
matching (online/scheduled/outstation/reach/book/suspend/clash), requests + atomic accept, trip status + live location, earnings.
Run: cd /app/backend/tests && pytest test_iter25_local_driver_redesign.py -c /dev/null -p no:xdist -v"""
import uuid
from datetime import datetime, timedelta

import pytest
import requests

from test_travoo_api import API, h
from test_iter8_admin_docs_reset import real_image
import test_iter15_lgd_local_hire as t

HIRIYUR, HOLALKERE = "5508", "5506"
HIRI_GEO = {"lat": 13.944, "lng": 76.617}
D = t.future_date(6)
S: dict = {}
UIDS: list = []
db = t._db()


def iso(d, hm):
    return f"{d}T{hm}:00+05:30"


def place(name="TEST Hiriyur", geo=HIRI_GEO):
    return {"loc_id": f"TEST_{uuid.uuid4().hex[:6]}", "name": name, "type": "town", "district": "Chitradurga", "state": "Karnataka", **geo}


def new_user(name, phone=True):
    tok, uid, _ = t.reg(name)
    UIDS.append(uid)
    if phone:
        r = requests.put(f"{API}/me", headers=h(tok), json={"phone": f"98{uuid.uuid4().int % 10**8:08d}"})
        assert r.status_code == 200, r.text
    return tok, uid


def upload(tok, kind, seed=None):
    return requests.post(f"{API}/driver/documents/{kind}", headers=h(tok),
                         files={"file": (f"{kind}.jpg", real_image(seed or uuid.uuid4().int % 900 + 1), "image/jpeg")}, timeout=120)


def docs(tok):
    for k in ("licence_front", "licence_back", "id_proof"):
        r = upload(tok, k)
        assert r.status_code == 200, r.text


def reg_body(sub=HIRIYUR, geo=HIRI_GEO, **kw):
    b = {"home": {"subdistrict_code": sub, "city": "TEST Town", "place": place(geo=geo)}, "languages": ["Kannada", "English"],
         "licence_no": "KA0120201234567", "licence_expiry": "01-01-2035", "services": ["rent"], "vehicle_ids": []}
    b.update(kw)
    return b


def add_vehicle(tok, vtype="sedan", seats=3, commercial=True, **kw):
    b = {"make": "Maruti", "model": "Dzire", "vtype": vtype, "seats": seats, "reg_no": f"KA{uuid.uuid4().int % 10**8:08d}", "name": "TEST car"}
    if commercial:
        rc = upload(tok, "vehicle_rc")
        assert rc.status_code == 200, rc.text
        b.update(rc_file_id=rc.json()["file_id"], permit_no="TESTPERMIT1", insurance_expiry="01-01-2034")
    b.update(kw)
    return requests.post(f"{API}/vehicles", headers=h(tok), json=b)


def adm_review(uid, decision="approved", note="TEST", items=None):
    return requests.post(f"{API}/admin/pro-drivers/{uid}/review", headers=h(S["adm"]), json={"decision": decision, "note": note, "items": items or []})


def make_driver(name, approve=True, online=True, **kw):
    tok, uid = new_user(name)
    docs(tok)
    r = requests.post(f"{API}/pro/register", headers=h(tok), json=reg_body(**kw))
    assert r.status_code == 200, r.text
    if approve:
        assert adm_review(uid).status_code == 200
        if online:
            r = requests.put(f"{API}/pro/settings", headers=h(tok), json={"availability_status": "available"})
            assert r.status_code == 200, r.text
    return tok, uid


def match(tok=None, **kw):
    p = {"subdistrict_code": HIRIYUR, "date": D, "time": "10:00", "hours": 2, "lat": HIRI_GEO["lat"], "lng": HIRI_GEO["lng"]}
    p.update(kw)
    r = requests.get(f"{API}/hire/local-drivers", headers=h(tok or S["pax"]), params=p)
    assert r.status_code == 200, r.text[:300]
    return {x["user_id"] for x in r.json()["local"]}


def req_body(**kw):
    b = {"service": "rent", "service_type": "hourly", "date": D, "time": "10:00", "hours": 2, "city": place("TEST pickup"),
         "pickup": "TEST bus stand", "destination": "TEST temple", "passengers": 1, "subdistrict_code": HIRIYUR}
    b.update(kw)
    return b


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    for uid in UIDS:
        for c, f in (("pro_drivers", "user_id"), ("driver_documents", "user_id"), ("vehicles", "owner_id"), ("files", "owner_id"),
                     ("hire_requests", "passenger_id"), ("hire_dispatches", "driver_id"), ("hires", "driver_id"), ("hires", "passenger_id"),
                     ("notifications", "user_id"), ("users", "user_id")):
            db[c].delete_many({f: uid})


class TestSetup:
    def test_setup(self):
        r = requests.post(f"{API}/admin/auth/login", json={"email": "admin@travoo.in", "password": "TravooAdmin2026x"})
        assert r.status_code == 200, r.text
        S["adm"] = r.json()["token"]
        S["pax"], S["pax_id"] = new_user("Pax25")
        S["pax2"], S["pax2_id"] = new_user("Pax25b")


class TestRegister:
    def test_requires_phone(self):
        tok, _ = new_user("NoPhone25", phone=False)
        r = requests.post(f"{API}/pro/register", headers=h(tok), json=reg_body())
        assert r.status_code == 400 and "mobile" in r.json()["detail"].lower()

    def test_requires_docs(self):
        tok, _ = new_user("NoDocs25")
        upload(tok, "licence_front")
        r = requests.post(f"{API}/pro/register", headers=h(tok), json=reg_body())
        assert r.status_code == 400 and "Please upload" in r.json()["detail"]

    def test_rent_only_no_vehicle(self):
        tok, uid = new_user("Rent25")
        docs(tok)
        r = requests.post(f"{API}/pro/register", headers=h(tok), json=reg_body())
        assert r.status_code == 200 and r.json()["status"] == "under_review", r.text
        me = requests.get(f"{API}/pro/me", headers=h(tok)).json()
        assert me["profile"]["status"] == "under_review" and me["profile"]["services"] == ["rent"]
        assert me["profile"]["online"] is False and me["missing"] == [] and [k["kind"] for k in me["kinds"]] == ["licence_front", "licence_back", "id_proof"]
        for k in ("files", "docs_locked", "licence_on_file", "vehicles", "book_ready", "personal"):
            assert k in me
        assert me["profile"]["home"]["subdistrict_code"] == HIRIYUR and me["profile"]["home"]["geo"]["lat"] == HIRI_GEO["lat"]
        # cannot go online while pending
        r = requests.put(f"{API}/pro/settings", headers=h(tok), json={"availability_status": "available"})
        assert r.status_code == 400
        S["rent"] = (tok, uid)

    def test_book_needs_ready_vehicle(self):
        tok, uid = new_user("Book25")
        docs(tok)
        bad = add_vehicle(tok, commercial=False)
        assert bad.status_code == 200, bad.text
        r = requests.post(f"{API}/pro/register", headers=h(tok), json=reg_body(services=["book"], vehicle_ids=[bad.json()["vehicle_id"]]))
        assert r.status_code == 400 and "RC" in r.json()["detail"]
        r = requests.post(f"{API}/pro/register", headers=h(tok), json=reg_body(services=["book"], vehicle_ids=[]))
        assert r.status_code == 400
        past = add_vehicle(tok, insurance_expiry="01-01-2020")
        r = requests.post(f"{API}/pro/register", headers=h(tok), json=reg_body(services=["book"], vehicle_ids=[past.json()["vehicle_id"]]))
        assert r.status_code == 400 and "insurance" in r.json()["detail"].lower()
        good = add_vehicle(tok)
        vid = good.json()["vehicle_id"]
        r = requests.post(f"{API}/pro/register", headers=h(tok), json=reg_body(services=["rent", "book"], vehicle_ids=[vid]))
        assert r.status_code == 200, r.text
        v = db.vehicles.find_one({"vehicle_id": vid})
        assert v["commercial_status"] == "pending"
        S["book"] = (tok, uid, vid)

    def test_carpool_approved_reuse(self):
        tok, uid = new_user("Carpool25")
        db.users.update_one({"user_id": uid}, {"$set": {"driver_status": "approved"}})
        db.driver_documents.update_one({"user_id": uid}, {"$set": {"user_id": uid, "licence_no": "KA0920190001234", "licence_expiry": "01-01-2036"}}, upsert=True)
        docs(tok)  # allowed because local kinds are missing
        assert upload(tok, "licence_front").status_code == 400  # no longer missing -> locked
        assert upload(tok, "vehicle_rc").status_code == 200  # always allowed
        me = requests.get(f"{API}/pro/me", headers=h(tok)).json()
        assert me["licence_on_file"] is True and me["docs_locked"] is True
        b = reg_body()
        b.pop("licence_no"); b.pop("licence_expiry")
        r = requests.post(f"{API}/pro/register", headers=h(tok), json=b)
        assert r.status_code == 200, r.text
        p = db.pro_drivers.find_one({"user_id": uid})
        assert p["licence_no"] == "KA0920190001234" and p["licence_expiry"] == "01-01-2036"
        S["cp"] = (tok, uid)


class TestVehicles:
    def test_dup_and_caps(self):
        tok = S["rent"][0]
        r = add_vehicle(tok, commercial=False, reg_no="KA01TEST25")
        assert r.status_code == 200
        assert add_vehicle(tok, commercial=False, reg_no="ka01 test25").status_code == 409
        assert add_vehicle(tok, commercial=False, seats=4).status_code == 400
        assert add_vehicle(tok, commercial=False, vtype="hatchback", seats=4).status_code == 400
        assert add_vehicle(tok, commercial=False, vtype="suv", seats=8).status_code == 200
        assert add_vehicle(tok, commercial=False, vtype="muv", seats=9).status_code in (400, 422)
        vid = r.json()["vehicle_id"]
        assert requests.post(f"{API}/vehicles/{vid}/commercial", headers=h(tok)).status_code == 400

    def test_edit_resets_approval(self):
        tok, uid, vid = S["book"]
        r = requests.post(f"{API}/admin/vehicles/{vid}/commercial", headers=h(S["adm"]), json={"decision": "approved"})
        assert r.status_code == 200
        v = db.vehicles.find_one({"vehicle_id": vid}, {"_id": 0})
        body = {k: v[k] for k in ("make", "model", "vtype", "reg_no", "seats", "name", "rc_file_id", "permit_no", "insurance_expiry")}
        r = requests.put(f"{API}/vehicles/{vid}", headers=h(tok), json={**body, "name": "TEST renamed"})
        assert r.status_code == 200 and r.json()["commercial_status"] == "approved"  # non-critical change keeps approval
        r = requests.put(f"{API}/vehicles/{vid}", headers=h(tok), json={**body, "permit_no": "TESTPERMIT2"})
        assert r.json()["commercial_status"] == "pending"
        assert requests.post(f"{API}/admin/vehicles/{vid}/commercial", headers=h(S["adm"]), json={"decision": "approved"}).status_code == 200


class TestAdmin:
    def test_review_note_required(self):
        uid = S["cp"][1]
        assert adm_review(uid, "resubmit", note="").status_code == 400
        assert adm_review(uid, "resubmit", note="TEST blurry licence", items=["licence_front"]).status_code == 200
        me = requests.get(f"{API}/pro/me", headers=h(S["cp"][0])).json()
        assert me["profile"]["status"] == "resubmit" and me["profile"]["resubmit_items"] == ["licence_front"]
        assert me["profile"]["admin_note"] == "TEST blurry licence"

    def test_flagged_upload_and_reregister(self):
        tok, uid = S["cp"]
        assert upload(tok, "licence_front").status_code == 200  # flagged -> unlocked
        assert upload(tok, "id_proof").status_code == 400  # not flagged
        b = reg_body(); b.pop("licence_no"); b.pop("licence_expiry")
        r = requests.post(f"{API}/pro/register", headers=h(tok), json=b)
        assert r.status_code == 200 and r.json()["status"] == "under_review"
        assert db.pro_drivers.find_one({"user_id": uid})["resubmit_items"] == []
        assert adm_review(uid).status_code == 200

    def test_list_filters_and_audit(self):
        for st in ("under_review", "approved", "resubmit", "rejected", "suspended", "all"):
            r = requests.get(f"{API}/admin/pro-drivers", headers=h(S["adm"]), params={"status": st})
            assert r.status_code == 200, st
        rows = requests.get(f"{API}/admin/pro-drivers", headers=h(S["adm"]), params={"status": "all"}).json()
        mine = next(x for x in rows if x["user_id"] == S["book"][1])
        for k in ("shared_vehicles", "availability", "completed_trips", "earnings_total", "carpool_status"):
            assert k in mine, k
        log = requests.get(f"{API}/admin/audit-log", headers=h(S["adm"]), params={"prefix": "pro."}).json()
        assert any(e.get("action") == "pro.resubmit" for e in log)


class TestSettings:
    def test_approve_book_and_settings(self):
        tok, uid, vid = S["book"]
        assert adm_review(uid).status_code == 200
        r = requests.put(f"{API}/pro/settings", headers=h(tok), json={"services": ["rent", "book"], "acceptOutstationTrips": True, "availability_status": "available"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["profile"]["online"] and d["profile"]["acceptOutstationTrips"] and d["book_ready"]

    def test_book_without_vehicle_400(self):
        tok, uid = S["cp"]
        assert requests.put(f"{API}/pro/settings", headers=h(tok), json={"services": ["book"]}).status_code == 400

    def test_availability_validation(self):
        tok = S["cp"][0]
        bad = [[{"from": iso(D, "12:00"), "to": iso(D, "10:00")}],
               [{"from": iso(D, "08:00"), "to": iso(D, "12:00")}, {"from": iso(D, "11:00"), "to": iso(D, "14:00")}],
               [{"from": iso(D, "08:00"), "to": iso(t.future_date(25), "08:00")}]]
        for b in bad:
            assert requests.put(f"{API}/pro/settings", headers=h(tok), json={"availability": b}).status_code == 400, b
        r = requests.put(f"{API}/pro/settings", headers=h(tok), json={"availability": [{"from": iso(D, "08:00"), "to": iso(D, "14:00")}]})
        assert r.status_code == 200 and len(r.json()["profile"]["availability"]) == 1
        aid = r.json()["profile"]["availability"][0]["id"]
        r = requests.put(f"{API}/pro/settings", headers=h(tok), json={"availability": [{"id": aid, "from": iso(D, "07:00"), "to": iso(D, "14:00")}]})
        assert r.json()["profile"]["availability"][0]["id"] == aid


class TestMatching:
    def test_setup_drivers(self):
        S["on"] = make_driver("On25")
        S["off"] = make_driver("Off25", online=False)
        S["sched"] = make_driver("Sch25", online=False)
        r = requests.put(f"{API}/pro/settings", headers=h(S["sched"][0]), json={"availability": [{"from": iso(D, "08:00"), "to": iso(D, "14:00")}]})
        assert r.status_code == 200
        S["far"] = make_driver("Far25", geo={"lat": 28.61, "lng": 77.21})
        S["susp"] = make_driver("Sus25")
        r = requests.post(f"{API}/admin/pro-drivers/{S['susp'][1]}/suspend", headers=h(S["adm"]), json={"suspended": True, "note": "TEST"})
        assert r.status_code == 200
        assert db.pro_drivers.find_one({"user_id": S["susp"][1]})["availability_status"] == "offline"

    def test_suspended_cannot_go_online(self):
        r = requests.put(f"{API}/pro/settings", headers=h(S["susp"][0]), json={"availability_status": "available"})
        assert r.status_code == 400, f"suspended driver was allowed to go Online: {r.status_code}"

    def test_online_offline_scheduled(self):
        m = match()
        assert S["on"][1] in m
        assert S["off"][1] not in m
        assert S["sched"][1] in m
        assert S["sched"][1] not in match(time="13:00", hours=3)  # overruns scheduled period

    def test_far_and_suspended_excluded(self):
        m = match()
        assert S["far"][1] not in m and S["susp"][1] not in m
        lst = requests.get(f"{API}/admin/pro-drivers", headers=h(S["adm"]), params={"status": "suspended"}).json()
        assert any(x["user_id"] == S["susp"][1] for x in lst)

    def test_outstation_pref(self):
        m = match(pickup_subdistrict_code=HOLALKERE)
        assert S["on"][1] not in m  # outstation OFF
        assert S["book"][1] in m  # outstation ON
        assert S["on"][1] in match()

    def test_book_requires_vehicle(self):
        m = match(service="book", service_type="one_way", vehicle_type="sedan", passengers=3)
        assert S["book"][1] in m and S["on"][1] not in m
        assert S["book"][1] not in match(service="book", service_type="one_way", vehicle_type="sedan", passengers=4)

    def test_offline_keeps_confirmed_and_clash(self):
        # pax requests rent; on + book + cp drivers notified; first accept wins, second 409
        r = requests.post(f"{API}/hire/requests", headers=h(S["pax"]), json=req_body())
        assert r.status_code == 200, r.text
        rid = r.json()["request_id"]
        inbox = requests.get(f"{API}/hire/requests", headers=h(S["on"][0])).json()["inbox"]
        mine = next(x for x in inbox if x["request_id"] == rid)
        assert mine["dispatch"]["estimate"] > 0 and mine["dispatch"]["km_to_pickup"] is not None
        a = requests.post(f"{API}/hire/requests/{rid}/accept", headers=h(S["on"][0]))
        assert a.status_code == 200, a.text
        b = requests.post(f"{API}/hire/requests/{rid}/accept", headers=h(S["book"][0]))
        assert b.status_code == 409
        S["bid"] = a.json()["booking_id"]
        # going offline keeps the booking
        assert requests.put(f"{API}/pro/settings", headers=h(S["on"][0]), json={"availability_status": "offline"}).status_code == 200
        assert db.hires.find_one({"booking_id": S["bid"]})["status"] == "confirmed"
        requests.put(f"{API}/pro/settings", headers=h(S["on"][0]), json={"availability_status": "available"})
        assert S["on"][1] not in match(time="11:00")  # clash with confirmed hire
        assert S["on"][1] in match(time="15:00")


class TestRoundTrip:
    def test_round_trip_validation_and_storage(self):
        base = dict(service="book", service_type="round_trip", vehicle_type="sedan", time="16:00")
        assert requests.post(f"{API}/hire/requests", headers=h(S["pax2"]), json=req_body(**base)).status_code == 400
        assert requests.post(f"{API}/hire/requests", headers=h(S["pax2"]), json=req_body(**base, return_date=D, return_time="15:00")).status_code == 400
        r = requests.post(f"{API}/hire/requests", headers=h(S["pax2"]), json=req_body(**base, return_date=D, return_time="20:00"))
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["return_date"] == D and d["return_time"] == "20:00" and d["hours"] >= 4
        inbox = requests.get(f"{API}/hire/requests", headers=h(S["book"][0])).json()["inbox"]
        disp = next(x for x in inbox if x["request_id"] == d["request_id"])["dispatch"]
        assert disp["vehicle"] and disp["vehicle"]["vehicle_id"] == S["book"][2]
        a = requests.post(f"{API}/hire/requests/{d['request_id']}/accept", headers=h(S["book"][0]))
        assert a.status_code == 200, a.text
        hb = db.hires.find_one({"booking_id": a.json()["booking_id"]})
        assert hb["return_date"] == D and hb["return_time"] == "20:00" and hb["vehicle"]["vehicle_id"] == S["book"][2]


class TestTrip:
    def test_trip_flow_and_location(self):
        bid, dtok, ptok = S["bid"], S["on"][0], S["pax"]
        u = f"{API}/hire/bookings/{bid}"
        g = requests.get(u, headers=h(ptok)).json()
        assert g["driver"]["phone_masked"] is False and "*" not in (g["driver"]["phone"] or "")
        assert requests.post(f"{u}/arrived", headers=h(dtok), json={}).status_code == 400
        pre = requests.post(f"{u}/location", headers=h(dtok), json={"lat": 13.9, "lng": 76.6})
        assert pre.status_code == 400, f"pre-arriving location: {pre.status_code} {pre.text[:200]}"
        assert requests.post(f"{u}/arriving", headers=h(ptok), json={}).status_code == 403
        assert requests.post(f"{u}/arriving", headers=h(dtok), json={}).status_code == 200
        post = requests.post(f"{u}/location", headers=h(dtok), json={"lat": 13.9, "lng": 76.6})
        assert post.status_code == 200, f"location POST shadowed by /hire/bookings/{{bid}}/{{action}}: {post.status_code} {post.text[:200]}"
        assert requests.post(f"{u}/location", headers=h(ptok), json={"lat": 13.9, "lng": 76.6}).status_code == 400
        loc = requests.get(f"{u}/location", headers=h(ptok))
        assert loc.status_code == 200 and loc.json()["lat"] == 13.9
        assert requests.get(f"{u}/location", headers=h(dtok)).status_code == 404
        assert requests.get(f"{u}/location", headers=h(S["pax2"])).status_code == 404
        assert "driver_location" not in requests.get(u, headers=h(ptok)).json()
        assert all("driver_location" not in x for x in requests.get(f"{API}/hire/bookings", headers=h(ptok)).json())
        assert requests.post(f"{u}/arrived", headers=h(dtok), json={}).status_code == 200
        assert requests.post(f"{u}/start", headers=h(dtok), json={}).status_code == 200
        assert requests.post(f"{u}/complete", headers=h(dtok), json={}).status_code == 200
        assert requests.get(f"{u}/location", headers=h(ptok)).json() is None
        assert "driver_location" not in db.hires.find_one({"booking_id": bid})

    def test_earnings_summary(self):
        d = requests.get(f"{API}/driver/earnings-summary", headers=h(S["on"][0])).json()
        assert d["commission_pct"] >= 0
        rent = d["totals"]["rent"]["all"]
        assert rent["trips"] == 1 and rent["gross"] > 0 and d["totals"]["book"]["all"]["trips"] == 0
        assert d["totals"]["all"]["all"]["trips"] == 1 and len(d["items"]) == 1
        for per in ("today", "week", "month"):
            assert per in d["totals"]["carpool"]


class TestMe:
    def test_dob_gender(self):
        tok = S["pax"]
        r = requests.put(f"{API}/me", headers=h(tok), json={"dob": "15-08-1990", "gender": "female"})
        assert r.status_code == 200
        assert requests.put(f"{API}/me", headers=h(tok), json={"gender": "x"}).status_code == 422
        assert requests.put(f"{API}/me", headers=h(tok), json={"dob": "1990-08-15"}).status_code == 422
