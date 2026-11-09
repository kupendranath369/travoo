# Deploying TRAVOO

## Option A — Emergent (current setup)
Click **Publish → Deploy** in Emergent. Then generate the iOS/Android builds from the same panel. Secrets are managed in Emergent and are not stored in this repository.

## Option B — Self-hosted

### 1. Database
Create a MongoDB Atlas cluster (or a self-managed MongoDB 6+). Turn on authentication and restrict access by IP. Put the connection string in `MONGO_URL`.

### 2. Backend
```bash
cd backend
pip install -r requirements.txt      # remove emergentintegrations if you don't use the translation script
uvicorn server:app --host 0.0.0.0 --port 8001 --workers 1
```
- Run it behind HTTPS (Nginx, Caddy, or the platform's load balancer). Route `/api/*` to port 8001.
- Use **1 worker**, or run the daily geo-sync task in a single process only.
- Required env: `MONGO_URL`, `DB_NAME`, `JWT_SECRET`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, plus `EMERGENT_LLM_KEY` for photo storage (or replace the storage provider).

Minimal Dockerfile:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY backend/ .
RUN pip install --no-cache-dir -r requirements.txt
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001"]
```

### 3. Mobile app
1. In `frontend/app.json`, change `ios.bundleIdentifier` and `android.package` to your own ids (e.g. `in.travoo.app`).
2. Set `EXPO_PUBLIC_BACKEND_URL` to the public HTTPS backend URL.
3. Run `npm i -g eas-cli && eas login && eas build:configure`, then `eas build -p android` and `eas build -p ios`.
4. Web build: `npx expo export -p web`, then host the `dist/` folder on any static host.

### 4. Before production
- Change the demo account passwords, or remove the demo seeding in `seed()`.
- Use a commercial or self-hosted map tile, geocoding and routing provider. The public OSM services have strict usage limits.
- Replace Emergent-managed Google login and object storage if you are leaving Emergent (see README section 11).
- Review the legal drafts in `frontend/src/legal.ts` with a lawyer.
