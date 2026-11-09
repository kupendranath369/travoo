# TRAVOO API reference

Base URL: `$EXPO_PUBLIC_BACKEND_URL/api`. Auth: `Authorization: Bearer <token>` from `POST /api/auth/login`, `/register` or `/session` (Google). Admin routes need an admin user. Errors return `{"detail": "..."}` with 4xx/5xx status. Interactive docs: `/docs` (FastAPI Swagger) when the backend is running.

| Method | Path | Source |
|---|---|---|
| POST | `/api/auth/register` | server.py |
| POST | `/api/auth/login` | server.py |
| POST | `/api/auth/session` | server.py |
| GET | `/api/auth/me` | server.py |
| POST | `/api/auth/logout` | server.py |
| PUT | `/api/me` | server.py |
| GET | `/api/users/{uid}` | server.py |
| GET | `/api/geo/states` | server.py |
| GET | `/api/routes/popular` | server.py |
| GET | `/api/settings` | server.py |
| POST | `/api/driver/documents/{kind}` | server.py |
| GET | `/api/files/{fid}` | server.py |
| GET | `/api/driver/profile` | server.py |
| POST | `/api/driver/verification` | server.py |
| POST | `/api/vehicles` | server.py |
| DELETE | `/api/vehicles/{vid}` | server.py |
| POST | `/api/trips` | server.py |
| PUT | `/api/trips/{tid}` | server.py |
| GET | `/api/trips/search` | server.py |
| GET | `/api/trips/mine` | server.py |
| GET | `/api/trips/{tid}` | server.py |
| POST | `/api/trips/{tid}/cancel` | server.py |
| POST | `/api/trips/{tid}/start` | server.py |
| POST | `/api/trips/{tid}/complete` | server.py |
| POST | `/api/bookings` | server.py |
| GET | `/api/bookings/mine` | server.py |
| GET | `/api/bookings/{bid}` | server.py |
| POST | `/api/bookings/{bid}/accept` | server.py |
| POST | `/api/bookings/{bid}/reject` | server.py |
| POST | `/api/bookings/{bid}/cancel` | server.py |
| POST | `/api/bookings/{bid}/settle` | server.py |
| GET | `/api/earnings` | server.py |
| POST | `/api/reviews` | server.py |
| GET | `/api/bookings/{bid}/messages` | server.py |
| POST | `/api/bookings/{bid}/messages` | server.py |
| GET | `/api/notifications` | server.py |
| POST | `/api/notifications/read` | server.py |
| POST | `/api/tickets` | server.py |
| GET | `/api/tickets/mine` | server.py |
| GET | `/api/admin/stats` | server.py |
| GET | `/api/admin/users` | server.py |
| POST | `/api/admin/users/{uid}/suspend` | server.py |
| GET | `/api/admin/drivers` | server.py |
| POST | `/api/admin/drivers/{uid}/review` | server.py |
| GET | `/api/admin/trips` | server.py |
| GET | `/api/admin/bookings` | server.py |
| GET | `/api/admin/vehicles` | server.py |
| GET | `/api/admin/tickets` | server.py |
| POST | `/api/admin/tickets/{tid}/resolve` | server.py |
| GET | `/api/admin/reviews` | server.py |
| DELETE | `/api/admin/reviews/{rid}` | server.py |
| POST | `/api/admin/routes` | server.py |
| DELETE | `/api/admin/routes/{rid}` | server.py |
| GET | `/api/admin/settings` | server.py |
| PUT | `/api/admin/settings` | server.py |
| GET | `/api/public/photo/{uid}` | server.py |
| GET | `/api/users/{uid}/profile` | server.py |
| GET | `/api/conversations` | server.py |
| POST | `/api/searches` | server.py |
| GET | `/api/searches` | server.py |
| DELETE | `/api/searches` | server.py |
| POST | `/api/locations/missing` | server.py |
| GET | `/api/admin/locations/missing` | server.py |
| POST | `/api/admin/locations/missing/{rid}` | server.py |
| GET | `/api/fuel-prices` | server.py |
| POST | `/api/admin/fuel-prices` | server.py |
| GET | `/api/pro/me` | server.py |
| POST | `/api/pro/register` | server.py |
| GET | `/api/hire/drivers` | server.py |
| POST | `/api/hire/bookings` | server.py |
| GET | `/api/hire/bookings` | server.py |
| GET | `/api/hire/bookings/{bid}` | server.py |
| POST | `/api/hire/bookings/{bid}/{action}` | server.py |
| GET | `/api/admin/pro-drivers` | server.py |
| POST | `/api/admin/pro-drivers/{uid}/review` | server.py |
| GET | `/api/geo/search` | geo.py |
| GET | `/api/locations/search` | geo.py |
| GET | `/api/locations/osm` | geo.py |
| GET | `/api/geo/pincode/{pin}` | geo.py |
| GET | `/api/geo/reverse` | geo.py |
| GET | `/api/locations/reverse` | geo.py |
| GET | `/api/geo/place/{loc_id}` | geo.py |
| GET | `/api/geo/route` | geo.py |
| GET | `/api/route/estimate` | geo.py |
| GET | `/api/geo/nearby` | geo.py |
| GET | `/api/geo/status` | geo.py |
| POST | `/api/admin/geo/sync` | geo.py |
| GET | `/api/admin/geo/report` | geo.py |

## Key endpoints

- `GET /api/geo/search?q=&lat=&lng=&limit=`: autocomplete across villages, towns, PIN codes, districts, states, streets, stations, bus stops and landmarks. Returns `{results: Loc[], sources, attribution}`.
- `GET /api/geo/place/{loc_id}`: resolves a selected result and fills in district, taluk and PIN.
- `GET /api/geo/reverse?lat=&lng=&exact=true`: reverse geocoding. With `exact=true` it keeps the pinned coordinates.
- `GET /api/geo/pincode/{pin}`: India Post offices for a PIN plus its approximate centre.
- `GET /api/geo/route?points=lat,lng;lat,lng[;...]`: up to 3 road routes, each with `distance_km`, `duration_min`, `via`, `toll_km`, `toll_estimate` and `geometry` (`[[lat,lng],...]`).
- `GET /api/geo/nearby?lat=&lng=&radius_m=`: bus stops, bus stands, railway stations and airports nearby.
- `GET /api/geo/status`: last map sync, record counts and provider health.
- `POST /api/admin/geo/sync` starts a background sync. `GET /api/admin/geo/report` shows sync stats, searches with no results and flagged coordinates.
- `GET /api/trips/search?from_lat&from_lng&to_lat&to_lng&date&seats&radius_km`: direct and along-route matches. Along-route matches include `match: {type: "along_route", pickup_km, pickup_eta}`.
- `POST /api/trips`: publish a trip. Takes `origin`, `destination`, `stops`, `date`, `time`, `seats`, `price`, `vehicle_id`, `fuel_price`, `mileage`, `tolls` and `route_choice`.
- `POST /api/bookings` books a trip. Then `POST /api/bookings/{id}/accept|reject|cancel|settle`.
- `GET|POST /api/bookings/{id}/messages`: in-app chat.
- `GET /api/hire/drivers` and `POST /api/hire/bookings` book a professional driver. Then `POST /api/hire/bookings/{id}/{action}`.
