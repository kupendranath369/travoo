# TRAVOO — India's Intercity Carpooling & Driver Booking Platform

TRAVOO connects drivers who have empty seats on intercity trips with passengers going the same way, and lets customers **hire a professional local driver** by the hour or day. Payments are made **directly between users in cash or UPI**. There is deliberately **no payment gateway**.

---

## 1. Features

| Area | Highlights |
|---|---|
| **Carpooling** | Publish trips with intermediate stops, return journeys, instant or request booking, seat locking, cancellations, start/complete trip, settlement (cash/UPI declared by driver) |
| **Hire a Driver (TRAVOO DRIVER)** | Professional driver registration (areas, languages, licence, rates), admin approval, search by city/date/service, request → accept → start → complete, reviews |
| **Cost-sharing calculator** | Road distance (OSRM), fuel price per state, mileage, toll estimate, maintenance/km, equal or per-passenger split, price cap enforced on the server |
| **Maps & locations (India-wide)** | Autocomplete across villages, towns, PIN codes, districts, states, streets, stations, bus stops and landmarks; drop-a-pin picker; route map with alternatives; nearby stops/stations; along-route passenger matching; daily map-data sync |
| **Trust & safety** | Driver verification with document photos (private storage), verified badges, phone numbers revealed only after a booking is confirmed, report/SOS info, ratings and reviews |
| **Chat** | Per-booking in-app chat with unread counts and read receipts (3 s polling) |
| **Languages** | English + 22 scheduled Indian languages (AI-translated, RTL for Urdu/Kashmiri/Sindhi) |
| **Admin (in-app)** | Stats, users, driver approvals, pro drivers, trips, bookings, complaints, reviews, popular routes, fuel prices, missing places, map-database health and sync |
| **Auth** | Email + password (JWT) and Google sign-in (Emergent-managed) |

## 2. Technology stack

- **Frontend:** Expo SDK 58, React Native, TypeScript, expo-router (file-based routing), react-native-webview + Leaflet for maps, expo-location, expo-image-picker.
- **Backend:** Python 3.11, FastAPI, Motor/PyMongo, bcrypt, PyJWT, httpx.
- **Database:** MongoDB (2dsphere geo indexes, TTL caches).
- **Open data services:** OpenStreetMap (Photon, Nominatim, Overpass), India Post PIN API, OSRM routing.

## 3. Repository layout

```
travoo-app/
├── backend/                 FastAPI service
│   ├── server.py            Auth, users, trips, bookings, chat, hire-a-driver, admin, uploads, seeding, indexes
│   ├── geo.py               India location search, geocoding, PIN codes, routing, nearby stops, map sync
│   ├── seed_data.py         36 states/UTs + curated places + popular routes
│   ├── scripts/translate.py AI translation of UI strings into 22 Indian languages
│   ├── tests/               pytest API test suites
│   ├── requirements.txt
│   └── .env.example
├── frontend/                Expo / React Native app
│   ├── app/                 Screens (expo-router): (tabs)/, trip/, booking/, chat/, hire/, user/, admin.tsx, …
│   ├── src/components/      Reusable UI: LocationField, MapPicker, OsmMap, RideCard, Calendar, DocPhotos, Logo, …
│   ├── src/i18n/            i18n provider + 23 locale JSON files
│   ├── src/api.ts           API client  · src/auth.tsx  auth context · src/theme.ts  design tokens
│   ├── assets/              Official TRAVOO logo, icons, splash, fonts
│   ├── app.json  package.json  yarn.lock
│   └── .env.example
├── docs/                    API.md, DATABASE.md, DEPLOYMENT.md
├── memory/PRD.md            Product requirements & change log
├── test_reports/            Automated test reports
├── .env.example  .gitignore  CONTRIBUTING.md  LICENSE
```

## 4. Architecture

**Frontend.** expo-router file-based navigation with a 5-tab layout (Home, Search, Offer, Bookings, Profile) plus stack screens. All server calls go through `src/api.ts`, which prefixes `EXPO_PUBLIC_BACKEND_URL` + `/api` and sends the JWT as a Bearer token. Colours come from `src/theme.ts`. Maps are rendered by `OsmMap` (Leaflet + OSM tiles in a WebView on native, an iframe on web).

**Backend.** A single FastAPI app (`server.py`) with an `/api` router, plus the geo router (`geo.py`). On startup it creates all MongoDB indexes, seeds states/places/demo data and starts the daily map-sync task. All routes are prefixed with `/api`.

**Database.** MongoDB collections: `users`, `user_sessions`, `vehicles`, `trips`, `bookings`, `earnings_ledger`, `reviews`, `messages`, `notifications`, `tickets`, `files`, `pro_drivers`, `hires`, `searches`, `locations`, `pincodes`, `geo_cache`, `geo_meta`, `geo_misses`, `missing_locations`, `contact_access`, `fuel_prices`, `popular_routes`, `settings`, `audit_logs`. See [docs/DATABASE.md](docs/DATABASE.md).

## 5. Requirements

- Node.js 20+ and Yarn 1.x (the frontend uses `yarn`)
- Python 3.11+
- MongoDB 6+ (local or Atlas)
- Expo Go app (phone) or Android Studio / Xcode for native builds

## 6. Environment variables

Copy the examples and fill in real values. **Never commit real `.env` files.**

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

| Variable | Where | Purpose |
|---|---|---|
| `MONGO_URL` | backend | MongoDB connection string |
| `DB_NAME` | backend | Database name |
| `JWT_SECRET` | backend | Long random string used to sign login tokens |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | backend | Admin account created on first start |
| `EMERGENT_LLM_KEY` | backend | Emergent key — used for document/photo storage and the translation script |
| `INTEGRATION_PROXY_URL` | backend (optional) | Override for the Emergent storage endpoint |
| `EXPO_PUBLIC_BACKEND_URL` | frontend | Public URL of the backend (without `/api`), e.g. `http://192.168.1.10:8001` |

## 7. Firebase, Google Maps & authentication

- **Firebase:** TRAVOO does **not** currently use Firebase. No Firebase config or rules are required. (Push notifications are stored in-app only.)
- **Google Maps:** TRAVOO does **not** use the Google Maps SDK or an API key. Maps use **OpenStreetMap** (Leaflet tiles) and open geocoding/routing services. The "Open in Maps" button simply opens a Google Maps URL, which needs no key.
- **Email/password auth:** built in (bcrypt + JWT). It works anywhere once `JWT_SECRET` is set.
- **Google sign-in:** uses Emergent-managed auth (`https://auth.emergentagent.com` in `frontend/src/auth.tsx`, verified in `POST /api/auth/session`). Outside Emergent, replace it with your own Google OAuth client, or hide the Google button.

## 8. Local development

```bash
# 1) Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt   # see note on emergentintegrations below
uvicorn server:app --host 0.0.0.0 --port 8001 --reload

# 2) Frontend (new terminal)
cd frontend
yarn install
yarn start            # press w for web, or scan the QR code with Expo Go
```

> `requirements.txt` includes `emergentintegrations`, which is installed from Emergent's package index:
> `pip install emergentintegrations --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/`
> It is only needed by `scripts/translate.py`. You can remove that line if you don't regenerate translations.

> `frontend/package.json` has a `preinstall` guard script from the Emergent template. If it blocks installs on your machine, remove the `preinstall` line.

**Demo accounts** are created by the seeder (driver/passenger demo users). The admin account comes from `ADMIN_EMAIL` / `ADMIN_PASSWORD`. **Change all demo passwords before going to production.**

## 9. Testing

```bash
cd backend
export EXPO_PUBLIC_BACKEND_URL=http://localhost:8001
export ADMIN_PASSWORD=<your admin password>
pytest -q                    # API suites in backend/tests
cd ../frontend && yarn lint  # ESLint
npx tsc --noEmit             # type check
```

## 10. Build & deployment

- **Inside Emergent:** use **Publish → Deploy**, then generate iOS/Android builds.
- **Self-hosted:** run the backend behind HTTPS (Docker, Render, Railway, a VM, etc.) with MongoDB Atlas. Build the app with EAS (`eas build -p android|ios`) under your own Expo account, after changing `bundleIdentifier`/`package` in `app.json`.

Full guide: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## 11. Dependencies on Emergent services

| Feature | Emergent dependency | Independent replacement |
|---|---|---|
| Driver document & profile photos | Emergent Object Storage (`EMERGENT_LLM_KEY`) | S3 / Cloudinary / GCS — update `put_object`/`get_object` in `server.py` |
| Google sign-in | Emergent-managed auth | Your own Google OAuth client |
| Re-generating translations | `emergentintegrations` + Emergent LLM key | Any LLM API (the existing JSON files already work offline) |
| Hosting & builds | Emergent deploy/build | Any host + EAS Build |

Everything else (carpooling, bookings, chat, hire-a-driver, admin, maps, PIN search, routing, email/password login) runs without Emergent.

## 12. Map data & attribution

Map data © OpenStreetMap contributors (ODbL). PIN codes © India Post. Routing by OSRM. Respect each provider's usage policy: Nominatim allows at most 1 request/s and no autocomplete use, and is rate-limited in `geo.py`. For production traffic, use a commercial or self-hosted tile, geocoding and routing provider. Also check that the map's borders follow Survey of India rules before launch.

## 13. Troubleshooting

| Problem | Fix |
|---|---|
| App shows network errors | `EXPO_PUBLIC_BACKEND_URL` must be reachable from the phone (use your LAN IP, not `localhost`) |
| `KeyError: 'JWT_SECRET'` | Create `backend/.env` from the example |
| Photo uploads fail | `EMERGENT_LLM_KEY` is missing, or replace the storage provider (section 11) |
| Location search slow or empty | Public OSM services are rate-limited or down; results are cached and fall back automatically. Check Admin → Map database |
| Google login fails outside Emergent | Expected. See section 7 |
| Metro cache issues | `yarn start --clear` |

## 14. License

Proprietary — all rights reserved. See [LICENSE](LICENSE).
