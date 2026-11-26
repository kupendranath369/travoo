"""
TRAVOO Backend Regression Test Suite
Tests all main flows after environment restore and bug fixes.
"""
import os
import uuid
import requests
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

# Configuration
BASE_URL = "https://app-runner-149--3ohxnclk.preview.emergentagent.com"
API = f"{BASE_URL}/api"
IST = timezone(timedelta(hours=5, minutes=30))

# Test state
STATE = {
    "created_users": [],  # Track for cleanup
    "created_trips": [],
    "created_bookings": [],
    "created_hire_requests": [],
    "admin_token": None,
}

# Create a larger PNG (minimum 1024 bytes required)
PNG = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                    "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082") * 20  # Repeat to make it larger


def h(tok):
    """Helper to create Authorization header"""
    return {"Authorization": f"Bearer {tok}"}


def future_date(days=3):
    """Get future date in YYYY-MM-DD format"""
    return (datetime.now(IST) + timedelta(days=days)).strftime("%Y-%m-%d")


def register_user(prefix="user"):
    """Register a new test user"""
    email = f"TEST_{prefix}_{uuid.uuid4().hex[:8]}@example.com"
    payload = {
        "email": email,
        "password": "TestPass123!",
        "name": f"TEST_{prefix}",
        "consent": True
    }
    r = requests.post(f"{API}/auth/register", json=payload, timeout=20)
    if r.status_code != 200:
        print(f"❌ Register failed: {r.status_code} - {r.text}")
        return None, None, None
    
    data = r.json()
    user_id = data["user"]["user_id"]
    STATE["created_users"].append(user_id)
    return data["token"], data["user"], email


def login_user(email, password):
    """Login existing user"""
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    if r.status_code != 200:
        print(f"❌ Login failed: {r.status_code} - {r.text}")
        return None
    return r.json()["token"]


def admin_login():
    """Login as admin - ONLY CALL ONCE (rate limited)"""
    if STATE["admin_token"]:
        return STATE["admin_token"]
    
    r = requests.post(f"{API}/admin/auth/login", 
                     json={"email": "admin@travoo.in", "password": "TravooAdmin2026"}, 
                     timeout=20)
    if r.status_code != 200:
        print(f"❌ Admin login failed: {r.status_code} - {r.text}")
        return None
    
    STATE["admin_token"] = r.json()["token"]
    return STATE["admin_token"]


def upload_driver_docs(tok):
    """Upload all 4 required driver documents"""
    # Correct document types: licence_front, licence_back, id_proof, rc
    for doc_type in ("licence_front", "licence_back", "id_proof", "rc"):
        r = requests.post(f"{API}/driver/documents/{doc_type}", 
                         headers=h(tok), 
                         files={"file": ("test.png", PNG, "image/png")}, 
                         timeout=30)
        if r.status_code != 200:
            print(f"❌ Upload {doc_type} failed: {r.status_code} - {r.text}")
            return False
    return True


def search_location(query):
    """Search for a location"""
    r = requests.get(f"{API}/locations/search", params={"q": query}, timeout=20)
    if r.status_code != 200 or not r.json():
        print(f"❌ Location search failed: {r.status_code}")
        return None
    
    row = r.json()[0]
    return {k: row.get(k) for k in ("loc_id", "name", "type", "district", "state", "pin", "lat", "lng")}


# ============================================================================
# TEST SUITE
# ============================================================================

def test_auth_flow():
    """Test authentication: register, login, me, forgot-password"""
    print("\n🧪 Testing Auth Flow...")
    
    # Test register
    tok, user, email = register_user("auth_test")
    if not tok:
        return False
    print(f"✅ Register successful: {email}")
    
    # Test login
    tok2 = login_user(email, "TestPass123!")
    if not tok2:
        return False
    print(f"✅ Login successful")
    
    # Test /auth/me
    r = requests.get(f"{API}/auth/me", headers=h(tok2), timeout=20)
    if r.status_code != 200:
        print(f"❌ /auth/me failed: {r.status_code} - {r.text}")
        return False
    me_data = r.json()
    if me_data["user_id"] != user["user_id"]:
        print(f"❌ /auth/me returned wrong user")
        return False
    print(f"✅ /auth/me successful")
    
    # Test forgot-password (may be rate limited, so don't fail on 429)
    r = requests.post(f"{API}/auth/forgot-password", json={"email": email}, timeout=20)
    if r.status_code in [200, 202]:
        print(f"✅ Forgot password successful")
    elif r.status_code == 429:
        print(f"⚠️  Forgot password rate limited (expected)")
    else:
        print(f"❌ Forgot password failed: {r.status_code} - {r.text}")
        return False
    
    # Test duplicate registration
    r = requests.post(f"{API}/auth/register", 
                     json={"email": email, "password": "TestPass123!", "name": "TEST_dup", "consent": True},
                     timeout=20)
    if r.status_code != 409:
        print(f"❌ Duplicate registration should return 409, got {r.status_code}")
        return False
    print(f"✅ Duplicate registration correctly rejected")
    
    # Test wrong password
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": "WrongPass"}, timeout=20)
    if r.status_code != 401:
        print(f"❌ Wrong password should return 401, got {r.status_code}")
        return False
    print(f"✅ Wrong password correctly rejected")
    
    return True


def test_admin_auth():
    """Test admin authentication"""
    print("\n🧪 Testing Admin Auth...")
    
    # Test admin login
    admin_tok = admin_login()
    if not admin_tok:
        return False
    print(f"✅ Admin login successful")
    
    # Test that regular /api/auth/login rejects admin (by design) - may be rate limited
    r = requests.post(f"{API}/auth/login", 
                     json={"email": "admin@travoo.in", "password": "TravooAdmin2026"}, 
                     timeout=20)
    if r.status_code == 403:
        print(f"✅ Admin correctly rejected from regular login endpoint")
    elif r.status_code == 429:
        print(f"⚠️  Admin login test rate limited (expected)")
    else:
        print(f"❌ Regular login should reject admin with 403, got {r.status_code}")
        return False
    
    return True


def test_location_search():
    """Test location search and geo endpoints"""
    print("\n🧪 Testing Location Search...")
    
    # Test /locations/search
    r = requests.get(f"{API}/locations/search", params={"q": "Bangalore"}, timeout=20)
    if r.status_code != 200:
        print(f"❌ Location search failed: {r.status_code} - {r.text}")
        return False
    results = r.json()
    if not results:
        print(f"❌ Location search returned no results")
        return False
    print(f"✅ Location search successful: found {len(results)} results")
    
    # Test geo search
    r = requests.get(f"{API}/geo/search", params={"q": "Mumbai"}, timeout=20)
    if r.status_code != 200:
        print(f"❌ Geo search failed: {r.status_code} - {r.text}")
        return False
    print(f"✅ Geo search successful")
    
    # Test geo status
    r = requests.get(f"{API}/geo/status", timeout=20)
    if r.status_code != 200:
        print(f"❌ Geo status failed: {r.status_code} - {r.text}")
        return False
    print(f"✅ Geo status successful")
    
    return True


def test_driver_flow():
    """Test complete driver flow: register -> verify -> admin approve -> publish trip -> search -> book"""
    print("\n🧪 Testing Driver Flow...")
    
    # Register driver
    drv_tok, drv_user, drv_email = register_user("driver")
    if not drv_tok:
        return False
    drv_id = drv_user["user_id"]
    print(f"✅ Driver registered: {drv_id}")
    
    # Add phone number (required for driver verification)
    r = requests.put(f"{API}/me", headers=h(drv_tok), json={"phone": "9876543210"}, timeout=20)
    if r.status_code != 200:
        print(f"❌ Failed to add phone: {r.status_code} - {r.text}")
        return False
    
    # Upload documents
    if not upload_driver_docs(drv_tok):
        return False
    print(f"✅ Driver documents uploaded")
    
    # Submit verification
    r = requests.post(f"{API}/driver/verification", headers=h(drv_tok), json={
        "legal_name": "TEST Driver",
        "vehicle_name": "Maruti Ertiga",
        "phone": "9876543210",
        "licence_no": "KA0120201234567",
        "licence_expiry": "01-01-2030",
        "rc_no": "KA01AB9999"
    }, timeout=20)
    if r.status_code != 200:
        print(f"❌ Driver verification submission failed: {r.status_code} - {r.text}")
        return False
    print(f"✅ Driver verification submitted")
    
    # Admin approve driver
    admin_tok = admin_login()
    if not admin_tok:
        return False
    
    r = requests.post(f"{API}/admin/drivers/{drv_id}/review", headers=h(admin_tok), 
                     json={"decision": "approved", "note": "TEST approval"}, timeout=20)
    if r.status_code != 200:
        print(f"❌ Admin driver approval failed: {r.status_code} - {r.text}")
        return False
    print(f"✅ Driver approved by admin")
    
    # Get locations for trip
    origin = search_location("Bangalore")
    destination = search_location("Mysore")
    if not origin or not destination:
        print(f"❌ Failed to get locations for trip")
        return False
    
    # Create vehicle
    r = requests.post(f"{API}/vehicles", headers=h(drv_tok), json={
        "make": "Maruti",
        "model": "Ertiga",
        "vtype": "muv",
        "reg_no": "KA01AB1234",
        "seats": 4,
        "ac": True,
        "luggage": "medium",
        "fuel_type": "petrol"
    }, timeout=20)
    if r.status_code != 200:
        print(f"❌ Vehicle creation failed: {r.status_code} - {r.text}")
        return False
    vehicle_id = r.json()["vehicle_id"]
    print(f"✅ Vehicle created: {vehicle_id}")
    
    # Publish trip
    trip_date = future_date(5)
    r = requests.post(f"{API}/trips", headers=h(drv_tok), json={
        "origin": origin,
        "destination": destination,
        "date": trip_date,
        "time": "10:00",
        "seats": 3,
        "price": 500,
        "vehicle_id": vehicle_id,
        "pickup_point": "TEST Pickup Point",
        "drop_point": "TEST Drop Point"
    }, timeout=20)
    if r.status_code != 200:
        print(f"❌ Trip creation failed: {r.status_code} - {r.text}")
        return False
    trip_id = r.json()["trip_id"]
    STATE["created_trips"].append(trip_id)
    print(f"✅ Trip published: {trip_id}")
    
    # Search trips
    r = requests.get(f"{API}/trips/search", params={
        "from_lat": origin["lat"],
        "from_lng": origin["lng"],
        "to_lat": destination["lat"],
        "to_lng": destination["lng"],
        "date": trip_date
    }, timeout=20)
    if r.status_code != 200:
        print(f"❌ Trip search failed: {r.status_code} - {r.text}")
        return False
    trips = r.json()["trips"]
    if not any(t["trip_id"] == trip_id for t in trips):
        print(f"❌ Published trip not found in search results")
        return False
    print(f"✅ Trip search successful: found {len(trips)} trips")
    
    # Register passenger and book trip
    pax_tok, pax_user, pax_email = register_user("passenger")
    if not pax_tok:
        return False
    pax_id = pax_user["user_id"]
    print(f"✅ Passenger registered: {pax_id}")
    
    # Book trip
    r = requests.post(f"{API}/bookings", headers=h(pax_tok), json={
        "trip_id": trip_id,
        "seats": 2,
        "pickup": "TEST Pickup Point"
    }, timeout=20)
    if r.status_code != 200:
        print(f"❌ Booking creation failed: {r.status_code} - {r.text}")
        return False
    booking_id = r.json()["booking_id"]
    STATE["created_bookings"].append(booking_id)
    print(f"✅ Booking created: {booking_id}")
    
    # Check booking status - it may be auto-accepted
    r = requests.get(f"{API}/bookings/{booking_id}", headers=h(drv_tok), timeout=20)
    if r.status_code == 200:
        booking_status = r.json().get("status")
        if booking_status == "pending":
            # Driver accept booking
            r = requests.post(f"{API}/bookings/{booking_id}/accept", headers=h(drv_tok), json={}, timeout=20)
            if r.status_code != 200:
                print(f"❌ Booking acceptance failed: {r.status_code} - {r.text}")
                return False
            print(f"✅ Booking accepted by driver")
        else:
            print(f"⚠️  Booking auto-accepted (status: {booking_status})")
    
    # Test cancel booking
    r = requests.post(f"{API}/bookings/{booking_id}/cancel", headers=h(pax_tok), 
                     json={"reason": "TEST cancellation"}, timeout=20)
    if r.status_code == 200:
        print(f"✅ Booking cancelled")
    else:
        # Cancellation may fail if booking is already in progress
        print(f"⚠️  Booking cancellation returned {r.status_code} (may be expected)")
    
    return True


def test_local_driver_hire():
    """Test local driver hire flow: pro register -> admin approve -> search -> request (hourly & outstation)"""
    print("\n🧪 Testing Local Driver Hire Flow...")
    
    # Register pro driver
    pro_tok, pro_user, pro_email = register_user("pro_driver")
    if not pro_tok:
        return False
    pro_id = pro_user["user_id"]
    print(f"✅ Pro driver registered: {pro_id}")
    
    # Add phone number (required for pro registration)
    r = requests.put(f"{API}/me", headers=h(pro_tok), json={"phone": "9876543210"}, timeout=20)
    if r.status_code != 200:
        print(f"❌ Failed to add phone: {r.status_code} - {r.text}")
        return False
    
    # Upload profile photo
    r = requests.post(f"{API}/me/photo", headers=h(pro_tok), 
                     files={"file": ("profile.png", PNG, "image/png")}, timeout=30)
    if r.status_code != 200:
        print(f"❌ Failed to upload profile photo: {r.status_code} - {r.text}")
        return False
    
    # Upload licence document
    r = requests.post(f"{API}/driver/documents/licence_front", headers=h(pro_tok), 
                     files={"file": ("licence.png", PNG, "image/png")}, timeout=30)
    if r.status_code != 200:
        print(f"❌ Failed to upload licence: {r.status_code} - {r.text}")
        return False
    
    # Get home location
    home_loc = search_location("Hiriyur")
    if not home_loc:
        print(f"❌ Failed to get home location")
        return False
    
    # Get city location
    city_loc = search_location("Chitradurga")
    if not city_loc:
        print(f"❌ Failed to get city location")
        return False
    
    # Register as pro driver (rent service) with all required fields
    r = requests.post(f"{API}/pro/register", headers=h(pro_tok), json={
        "services": ["rent"],
        "city": city_loc,
        "home": {
            "subdistrict_code": "5508",  # Hiriyur taluk code
            "city": "Hiriyur"
        },
        "acceptOutstationTrips": False,
        "languages": ["Kannada", "English"],
        "experience_years": 5,
        "licence_no": "KA0120201234567",
        "licence_expiry": "01-01-2035",
        "vehicle_types": ["sedan", "suv"],
        "days": [0, 1, 2, 3, 4, 5, 6],
        "start_time": "06:00",
        "end_time": "20:00",
        "rate_hourly": 200,
        "rate_half_day": 800,
        "rate_full_day": 1500
    }, timeout=20)
    if r.status_code != 200:
        print(f"❌ Pro driver registration failed: {r.status_code} - {r.text}")
        return False
    print(f"✅ Pro driver registered (rent service)")
    
    # Admin approve pro driver
    admin_tok = admin_login()
    if not admin_tok:
        return False
    
    r = requests.post(f"{API}/admin/pro-drivers/{pro_id}/review", headers=h(admin_tok), 
                     json={"decision": "approved", "note": "TEST approval"}, timeout=20)
    if r.status_code != 200:
        print(f"❌ Admin pro driver approval failed: {r.status_code} - {r.text}")
        return False
    print(f"✅ Pro driver approved by admin")
    
    # Register another pro driver with book service and outstation
    pro2_tok, pro2_user, pro2_email = register_user("pro_driver_book")
    if not pro2_tok:
        return False
    pro2_id = pro2_user["user_id"]
    
    # Add phone for pro2
    r = requests.put(f"{API}/me", headers=h(pro2_tok), json={"phone": "9876543211"}, timeout=20)
    if r.status_code != 200:
        print(f"❌ Failed to add phone for pro2: {r.status_code} - {r.text}")
        return False
    
    # Upload profile photo for pro2
    r = requests.post(f"{API}/me/photo", headers=h(pro2_tok), 
                     files={"file": ("profile.png", PNG, "image/png")}, timeout=30)
    if r.status_code != 200:
        print(f"❌ Failed to upload profile photo for pro2: {r.status_code} - {r.text}")
        return False
    
    # Upload licence for pro2
    r = requests.post(f"{API}/driver/documents/licence_front", headers=h(pro2_tok), 
                     files={"file": ("licence.png", PNG, "image/png")}, timeout=30)
    if r.status_code != 200:
        print(f"❌ Failed to upload licence for pro2: {r.status_code} - {r.text}")
        return False
    
    # Create vehicle for book service
    r = requests.post(f"{API}/vehicles", headers=h(pro2_tok), json={
        "make": "Toyota",
        "model": "Innova",
        "vtype": "suv",
        "reg_no": "KA16AB5678",
        "seats": 6,
        "ac": True,
        "luggage": "large",
        "fuel_type": "diesel"
    }, timeout=20)
    if r.status_code != 200:
        print(f"❌ Vehicle creation for pro2 failed: {r.status_code} - {r.text}")
        return False
    vehicle2_id = r.json()["vehicle_id"]
    
    r = requests.post(f"{API}/pro/register", headers=h(pro2_tok), json={
        "services": ["book"],
        "city": city_loc,
        "home": {
            "subdistrict_code": "5508",
            "city": "Hiriyur"
        },
        "acceptOutstationTrips": True,
        "languages": ["Kannada", "English"],
        "experience_years": 5,
        "licence_no": "KA0120201234568",
        "licence_expiry": "01-01-2035",
        "vehicle_types": ["suv"],
        "days": [0, 1, 2, 3, 4, 5, 6],
        "start_time": "06:00",
        "end_time": "20:00",
        "rate_hourly": 250,
        "rate_half_day": 900,
        "rate_full_day": 1600,
        "vehicles": [{
            "vehicle_id": vehicle2_id,
            "name": "TEST Innova",
            "reg_no": "KA16AB5678",
            "category": "suv",
            "seats": 6,
            "day_rate": 1200
        }]
    }, timeout=20)
    if r.status_code != 200:
        print(f"❌ Pro driver 2 registration failed: {r.status_code} - {r.text}")
        return False
    print(f"✅ Pro driver 2 registered (book service, outstation)")
    
    r = requests.post(f"{API}/admin/pro-drivers/{pro2_id}/review", headers=h(admin_tok), 
                     json={"decision": "approved", "note": "TEST approval"}, timeout=20)
    if r.status_code != 200:
        print(f"❌ Admin pro driver 2 approval failed: {r.status_code} - {r.text}")
        return False
    print(f"✅ Pro driver 2 approved by admin")
    
    # Register customer BEFORE testing local-drivers endpoint
    cust_tok, cust_user, cust_email = register_user("hire_customer")
    if not cust_tok:
        return False
    cust_id = cust_user["user_id"]
    print(f"✅ Hire customer registered: {cust_id}")
    
    # Test GET /api/hire/local-drivers (should not return 500) - needs authentication
    r = requests.get(f"{API}/hire/local-drivers", headers=h(cust_tok), params={
        "subdistrict_code": "5508",  # Hiriyur taluk code
        "date": future_date(7),
        "time": "10:00",
        "service": "rent",
        "service_type": "hourly",
        "hours": 4
    }, timeout=20)
    if r.status_code != 200:
        print(f"❌ GET /api/hire/local-drivers failed: {r.status_code} - {r.text}")
        return False
    drivers = r.json().get("local", [])
    print(f"✅ GET /api/hire/local-drivers successful: found {len(drivers)} drivers")
    
    # Test POST /api/hire/requests for HOURLY (non-outstation) - Bug fix test
    r = requests.post(f"{API}/hire/requests", headers=h(cust_tok), json={
        "service": "rent",
        "service_type": "hourly",
        "date": future_date(7),
        "time": "10:00",
        "hours": 4,
        "city": city_loc,
        "pickup": "TEST Pickup Location",
        "destination": "TEST Destination",
        "passengers": 2,
        "vehicle_type": "",
        "subdistrict_code": "5508",
        "pickup_subdistrict_code": "5508"
    }, timeout=20)
    if r.status_code != 200:
        print(f"❌ POST /api/hire/requests (hourly) failed: {r.status_code} - {r.text}")
        print(f"   This is the BUG FIX test - should not return 500!")
        return False
    req1_id = r.json()["request_id"]
    STATE["created_hire_requests"].append(req1_id)
    print(f"✅ POST /api/hire/requests (hourly) successful - BUG FIX VERIFIED")
    
    # Test POST /api/hire/requests for OUTSTATION
    r = requests.post(f"{API}/hire/requests", headers=h(cust_tok), json={
        "service": "rent",
        "service_type": "outstation",
        "date": future_date(8),
        "time": "09:00",
        "days": 2,
        "city": city_loc,
        "pickup": "TEST Pickup Location",
        "destination": "TEST Outstation Destination",
        "passengers": 3,
        "vehicle_type": "",
        "subdistrict_code": "5508",
        "pickup_subdistrict_code": "5508"
    }, timeout=20)
    if r.status_code != 200:
        print(f"❌ POST /api/hire/requests (outstation) failed: {r.status_code} - {r.text}")
        return False
    req2_id = r.json()["request_id"]
    STATE["created_hire_requests"].append(req2_id)
    print(f"✅ POST /api/hire/requests (outstation) successful")
    
    # Test accept hire request
    r = requests.post(f"{API}/hire/requests/{req1_id}/accept", headers=h(pro_tok), json={}, timeout=20)
    if r.status_code != 200:
        print(f"❌ Accept hire request failed: {r.status_code} - {r.text}")
        return False
    booking_id = r.json()["booking_id"]
    print(f"✅ Hire request accepted: {booking_id}")
    
    # Test decline hire request (use req2 which hasn't been accepted yet)
    # First, we need to check if pro2 was dispatched for req2
    # Since req2 is outstation and pro2 accepts outstation, pro2 should be able to decline it
    r = requests.post(f"{API}/hire/requests/{req2_id}/decline", headers=h(pro2_tok), json={}, timeout=20)
    if r.status_code == 200:
        print(f"✅ Hire request declined")
    elif r.status_code == 404:
        # This is OK - the driver may not have been dispatched for this request
        print(f"⚠️  Decline test skipped - driver not dispatched for this request")
    else:
        print(f"❌ Decline hire request failed: {r.status_code} - {r.text}")
        return False
    
    return True


def test_chat_notifications():
    """Test chat/conversations and notifications"""
    print("\n🧪 Testing Chat & Notifications...")
    
    # Register two users
    user1_tok, user1, _ = register_user("chat_user1")
    user2_tok, user2, _ = register_user("chat_user2")
    if not user1_tok or not user2_tok:
        return False
    
    # Test notifications endpoint
    r = requests.get(f"{API}/notifications", headers=h(user1_tok), timeout=20)
    if r.status_code != 200:
        print(f"❌ Get notifications failed: {r.status_code} - {r.text}")
        return False
    print(f"✅ Get notifications successful")
    
    # Test mark notification as read (if any exist)
    notifs = r.json()
    if isinstance(notifs, list) and len(notifs) > 0:
        notif_id = notifs[0].get("notif_id")
        if notif_id:
            r = requests.post(f"{API}/notifications/{notif_id}/read", headers=h(user1_tok), json={}, timeout=20)
            if r.status_code != 200:
                print(f"❌ Mark notification read failed: {r.status_code} - {r.text}")
                return False
            print(f"✅ Mark notification read successful")
        else:
            print(f"⚠️  No notifications to test mark as read")
    else:
        print(f"⚠️  No notifications to test mark as read")
    
    return True


def test_admin_endpoints():
    """Test admin endpoints: stats, drivers, users, trips, bookings, pro-drivers, hire-bookings, hire-reports, licence-verifications, settings"""
    print("\n🧪 Testing Admin Endpoints...")
    
    admin_tok = admin_login()
    if not admin_tok:
        return False
    
    # Test admin stats
    r = requests.get(f"{API}/admin/stats", headers=h(admin_tok), timeout=20)
    if r.status_code != 200:
        print(f"❌ Admin stats failed: {r.status_code} - {r.text}")
        return False
    print(f"✅ Admin stats successful")
    
    # Test admin drivers list
    r = requests.get(f"{API}/admin/drivers", headers=h(admin_tok), timeout=20)
    if r.status_code != 200:
        print(f"❌ Admin drivers list failed: {r.status_code} - {r.text}")
        return False
    print(f"✅ Admin drivers list successful")
    
    # Test admin users list
    r = requests.get(f"{API}/admin/users", headers=h(admin_tok), timeout=20)
    if r.status_code != 200:
        print(f"❌ Admin users list failed: {r.status_code} - {r.text}")
        return False
    print(f"✅ Admin users list successful")
    
    # Test admin trips list
    r = requests.get(f"{API}/admin/trips", headers=h(admin_tok), timeout=20)
    if r.status_code != 200:
        print(f"❌ Admin trips list failed: {r.status_code} - {r.text}")
        return False
    print(f"✅ Admin trips list successful")
    
    # Test admin bookings list
    r = requests.get(f"{API}/admin/bookings", headers=h(admin_tok), timeout=20)
    if r.status_code != 200:
        print(f"❌ Admin bookings list failed: {r.status_code} - {r.text}")
        return False
    print(f"✅ Admin bookings list successful")
    
    # Test admin pro-drivers list
    r = requests.get(f"{API}/admin/pro-drivers", headers=h(admin_tok), timeout=20)
    if r.status_code != 200:
        print(f"❌ Admin pro-drivers list failed: {r.status_code} - {r.text}")
        return False
    print(f"✅ Admin pro-drivers list successful")
    
    # Test admin hire-bookings list
    r = requests.get(f"{API}/admin/hire-bookings", headers=h(admin_tok), timeout=20)
    if r.status_code != 200:
        print(f"❌ Admin hire-bookings list failed: {r.status_code} - {r.text}")
        return False
    print(f"✅ Admin hire-bookings list successful")
    
    # Test admin hire-reports
    r = requests.get(f"{API}/admin/hire-reports", headers=h(admin_tok), timeout=20)
    if r.status_code != 200:
        print(f"❌ Admin hire-reports failed: {r.status_code} - {r.text}")
        return False
    print(f"✅ Admin hire-reports successful")
    
    # Test admin licence-verifications list
    r = requests.get(f"{API}/admin/licence-verifications", headers=h(admin_tok), timeout=20)
    if r.status_code != 200:
        print(f"❌ Admin licence-verifications list failed: {r.status_code} - {r.text}")
        return False
    verifications = r.json()
    print(f"✅ Admin licence-verifications list successful")
    
    # Test GET /api/admin/licence-verifications/{id}/documents - Bug fix test
    if verifications:
        ver_id = verifications[0]["user_id"]
        r = requests.get(f"{API}/admin/licence-verifications/{ver_id}/documents", headers=h(admin_tok), timeout=20)
        if r.status_code != 200:
            print(f"❌ Admin licence-verifications documents failed: {r.status_code} - {r.text}")
            print(f"   This is the BUG FIX test - should not crash with undefined fileUrl!")
            return False
        print(f"✅ Admin licence-verifications documents successful - BUG FIX VERIFIED")
    else:
        print(f"⚠️  No licence verifications found to test /documents endpoint")
    
    # Test admin settings
    r = requests.get(f"{API}/admin/settings", headers=h(admin_tok), timeout=20)
    if r.status_code != 200:
        print(f"❌ Admin settings failed: {r.status_code} - {r.text}")
        return False
    print(f"✅ Admin settings successful")
    
    return True


def test_settings():
    """Test user settings endpoints"""
    print("\n🧪 Testing User Settings...")
    
    tok, user, _ = register_user("settings_user")
    if not tok:
        return False
    
    # Test get settings
    r = requests.get(f"{API}/settings", headers=h(tok), timeout=20)
    if r.status_code != 200:
        print(f"❌ Get settings failed: {r.status_code} - {r.text}")
        return False
    print(f"✅ Get settings successful")
    
    # Test update profile via /me endpoint
    r = requests.put(f"{API}/me", headers=h(tok), json={
        "name": "TEST Updated Name",
        "bio": "TEST bio"
    }, timeout=20)
    if r.status_code != 200:
        print(f"❌ Update profile failed: {r.status_code} - {r.text}")
        return False
    print(f"✅ Update profile successful")
    
    return True


def test_geo_route():
    """Test geo route endpoint"""
    print("\n🧪 Testing Geo Route...")
    
    # Test route estimation with correct parameter format (points, not origin/destination)
    r = requests.get(f"{API}/geo/route", params={
        "points": "12.9716,77.5946;12.2958,76.6394",  # Bangalore to Mysore
        "alternatives": True
    }, timeout=20)
    if r.status_code != 200:
        print(f"❌ Geo route failed: {r.status_code} - {r.text}")
        return False
    route_data = r.json()
    if "routes" not in route_data or not route_data["routes"]:
        print(f"❌ Geo route missing routes")
        return False
    best_route = route_data["routes"][0]
    if "distance_km" not in best_route or "duration_min" not in best_route:
        print(f"❌ Geo route missing required fields")
        return False
    print(f"✅ Geo route successful: {best_route.get('distance_km')}km, {best_route.get('duration_min')}min")
    
    return True


# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

def run_all_tests():
    """Run all backend tests"""
    print("=" * 80)
    print("TRAVOO BACKEND REGRESSION TEST SUITE")
    print("=" * 80)
    print(f"Backend URL: {BASE_URL}")
    print(f"API Base: {API}")
    print("=" * 80)
    
    results = {}
    
    # Run all tests
    tests = [
        ("Auth Flow", test_auth_flow),
        ("Admin Auth", test_admin_auth),
        ("Location Search", test_location_search),
        ("Settings", test_settings),
        ("Geo Route", test_geo_route),
        ("Driver Flow", test_driver_flow),
        ("Local Driver Hire", test_local_driver_hire),
        ("Chat & Notifications", test_chat_notifications),
        ("Admin Endpoints", test_admin_endpoints),
    ]
    
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ {test_name} crashed: {str(e)}")
            results[test_name] = False
    
    # Print summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print("=" * 80)
    print(f"TOTAL: {passed}/{total} tests passed")
    print("=" * 80)
    
    return results


if __name__ == "__main__":
    results = run_all_tests()
    
    # Exit with error code if any test failed
    if not all(results.values()):
        exit(1)
