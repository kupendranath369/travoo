# TRAVOO database (MongoDB)

Indexes are created automatically at startup by `ensure_indexes()` in `backend/server.py` (the `INDEXES` dict) and `GEO_INDEXES` in `backend/geo.py`. Seed data (states/UTs, curated places, popular routes, demo users and trips) is inserted by `seed()` and is idempotent.

Every document uses a string id (for example `user_id` or `trip_id`). Mongo `_id` is never exposed by the API.

| Collection | Key fields | Indexes |
|---|---|---|
| `users` | user_id, email, password_hash, name, phone, role (user/admin), driver_status, is_pro, languages, bio, rating_avg, suspended | email unique, user_id unique |
| `user_sessions` | session_token, user_id, expires_at | token unique |
| `vehicles` | vehicle_id, owner_id, name, vtype, plate, seats | vehicle_id unique |
| `trips` | trip_id, driver_id, origin/destination/stops (`{name, lat, lng, geo}`), date, time, departure_at, distance_km, duration_min, seats, seats_available, price, cost_breakdown, status, route_line (GeoJSON LineString), route_via, toll_estimate | trip_id unique, origin.geo 2dsphere, route_line 2dsphere, status+date |
| `bookings` | booking_id, trip_id, passenger_id, seats, status (pending/confirmed/rejected/cancelled/completed), active_key, settlement | booking_id unique, sparse unique active_key (prevents duplicate bookings) |
| `earnings_ledger` | booking_id, driver_id, type, amount (append-only) | booking_id+type unique |
| `reviews` | booking_id, reviewer_id, target_id, rating, text, hidden | unique per booking/reviewer/target |
| `messages` | booking_id, sender_id, text, created_at, read_at | booking_id+created_at |
| `notifications` | user_id, title, body, read, created_at | user_id+created_at |
| `tickets` | ticket_id, user_id, kind, text, status | ticket_id unique |
| `files` | file_id, owner_id, kind, path (object storage), content_type | file_id unique, owner_id |
| `pro_drivers` | user_id, city (geo), areas, languages, rates, availability, status | user_id unique, city.geo 2dsphere |
| `hires` | booking_id, driver_id, customer_id, date, hours, status | booking_id unique, driver_id+date |
| `searches` | user_id, key, from, to (recent searches) | user_id+key unique |
| `locations` | loc_id, name, type, district, sub_district, state, pin, lat, lng, geo, aliases, search_terms, source (travoo/community/openstreetmap/india_post), osm_id, synced_at, stale, needs_review | loc_id unique, geo 2dsphere, search_terms, osm_id, source+synced_at, state+district |
| `pincodes` | pin, district, state, offices[], lat, lng, geo, synced_at | pin unique, geo 2dsphere |
| `geo_cache` | key, data, expires_at | key unique, TTL on expires_at |
| `geo_meta` | key="sync", last_success_at, last_stats, last_errors | — |
| `geo_misses` | q, count, last_at (searches with no results) | q unique |
| `missing_locations` | request_id, name, lat, lng, state, status | request_id unique |
| `contact_access` | viewer_id, owner_id, booking_id (log of phone-number reveals) | unique triple |
| `fuel_prices` | state, fuel_type, price | state+fuel_type unique |
| `popular_routes` | route_id, from, to | route_id unique |
| `settings` | instant approval mode, cancellation hours, max price factor, etc. | — |
| `audit_logs` | admin actions | created_at |

**Security rules.** Access control lives in the API, not in the database. Every protected route uses the `get_user` / `get_admin` dependencies. Driver documents are only readable by their owner or an admin. Phone numbers are masked until a booking is confirmed. Keep MongoDB on a private network with authentication turned on.
