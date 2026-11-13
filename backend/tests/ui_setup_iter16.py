"""UI setup iter16: runs ui_setup_iter15 (pax + approved Hiriyur driver) then creates open / cancelled / expired requests for the pax.
Writes /tmp/ui16.json. Cleanup: python cleanup_iter15.py"""
import json
import runpy
import sys
import uuid
from datetime import datetime, timedelta, timezone

import requests
sys.path.insert(0, "/app/backend/tests")
runpy.run_path("/app/backend/tests/ui_setup_iter15.py")
from test_travoo_api import API, h  # noqa: E402
import test_iter15_lgd_local_hire as t  # noqa: E402

u = json.load(open("/tmp/ui15.json"))
pax = u["pax"][2]
t.S["city"] = t.loc("Hiriyur")
open_r = requests.post(f"{API}/hire/requests", headers=h(pax), json=t.req_body(date=t.future_date(3), time="10:00", hours=2, pickup="TEST UI Bus Stand")).json()
canc = requests.post(f"{API}/hire/requests", headers=h(pax), json=t.req_body(date=t.future_date(3), time="15:00", hours=2)).json()
assert requests.post(f"{API}/hire/requests/{canc['request_id']}/cancel", headers=h(pax)).status_code == 200
st = datetime.now(timezone.utc) - timedelta(hours=1)
rid = "LHR-TEST" + uuid.uuid4().hex[:4].upper()
t._db().hire_requests.insert_one({**{k: v for k, v in canc.items() if k not in ("_id", "notified")}, "request_id": rid, "status": "open",
                                  "starts_at": st, "created_at": st - timedelta(hours=2), "date": st.strftime("%Y-%m-%d"), "time": "08:00"})
u["requests"] = {"open": open_r["request_id"], "cancelled": canc["request_id"], "expired": rid}
json.dump(u, open("/tmp/ui16.json", "w"))
print(u["pax"][0], u["drv"][0], u["requests"])
