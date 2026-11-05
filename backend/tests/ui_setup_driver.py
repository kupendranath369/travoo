"""Helper: create approved TEST driver + vehicle and print creds (for UI tests)."""
import uuid
import requests
from test_travoo_api import API, h, login

adm = login("admin@travoo.in", "TravooAdmin@2026")
email = f"test_uidrv_{uuid.uuid4().hex[:6]}@example.com"
r = requests.post(f"{API}/auth/register", json={"email": email, "password": "Passw0rd!x", "name": "TEST UiDriver", "consent": True}).json()
tok, uid = r["token"], r["user"]["user_id"]
requests.put(f"{API}/me", headers=h(tok), json={"upi_id": "test.drv@okaxis"})
print(requests.post(f"{API}/driver/verification", headers=h(tok), json={"legal_name": "TEST UiDriver", "phone": "9876511111",
      "licence_no": "KA0120209999999", "licence_expiry": "01-01-2032", "rc_no": "KA05UI0001"}).json())
print(requests.post(f"{API}/admin/drivers/{uid}/review", headers=h(adm), json={"decision": "approved"}).json())
print(requests.post(f"{API}/vehicles", headers=h(tok), json={"make": "Honda", "model": "City", "vtype": "sedan", "reg_no": "KA05UI0001", "seats": 4}).json()["vehicle_id"])
pt = login("passenger@travoo.in", "Passenger@2026")
print("restore passenger lang", requests.put(f"{API}/me", headers=h(pt), json={"language": "en"}).status_code)
print("EMAIL", email, "UID", uid)
