"""UI setup iter15: TEST passenger + approved Hiriyur hire driver (+ an unregistered user with phone/photo/licence for /hire/register)."""
import json
import sys
import uuid

import requests
sys.path.insert(0, "/app/backend/tests")
from test_travoo_api import API, h  # noqa: E402
from test_iter8_admin_docs_reset import real_image  # noqa: E402
import test_iter15_lgd_local_hire as t  # noqa: E402

t.S["adm"] = t.admin_token()
t.S["city"] = t.loc("Hiriyur")
pax_tok, pax_id, pax_email = t.reg("UiPax15")
drv_tok, drv_id = t.make_driver("UiDrv", t.HIRIYUR)
drv_email = requests.get(f"{API}/auth/me", headers=h(drv_tok)).json()
drv_email = (drv_email.get("user") or drv_email)["email"]
new_tok, new_id, new_email = t.reg("UiNew15")
requests.put(f"{API}/me", headers=h(new_tok), json={"phone": f"96{uuid.uuid4().int % 10**8:08d}"})
json.dump({"pax": [pax_email, pax_id, pax_tok], "drv": [drv_email, drv_id, drv_tok], "new": [new_email, new_id, new_tok],
           "pw": "Passw0rd!x"}, open("/tmp/ui15.json", "w"))
print(pax_email, drv_email, new_email)
