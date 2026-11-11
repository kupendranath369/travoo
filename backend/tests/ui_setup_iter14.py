"""UI setup iter14: TEST email user with no phone (for profile edit save)."""
import json, sys
sys.path.insert(0, "/app/backend/tests")
from test_iter10_capacity_pricing_photo import reg  # noqa: E402
tok, uid, email = reg("UiNoPh14")
json.dump({"email": email, "pw": "Passw0rd!x", "uid": uid}, open("/tmp/ui14.json", "w"))
print(email)
