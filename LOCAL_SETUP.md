# Run Travoo on your own computer

## 1. Install
- Python 3.11, Node.js 20+ (Node 24 used here), Yarn 1 (`npm i -g yarn`)
- MongoDB: either
  - **Local:** MongoDB Community Server 7+ (https://www.mongodb.com/try/download/community). It runs at `mongodb://localhost:27017`.
  - **Atlas (cloud, free):** create a free cluster at https://cloud.mongodb.com → Database Access: add a user → Network Access: allow your IP → Connect → Drivers → copy the URI, e.g. `mongodb+srv://USER:PASSWORD@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority`
- Expo Go app on your phone (Play Store / App Store), on the same Wi-Fi as your computer.

## 2. Backend (FastAPI, port 8001)
```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/
cp .env.example .env               # then edit .env: MONGO_URL, JWT_SECRET
bash scripts/load_india_data.sh    # one time: all states, districts, taluks, villages, PIN codes (~10 min)
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```
Check: open http://localhost:8001/api/geo/pincode/673001

## 3. Frontend (Expo, port 8081)
```bash
cd frontend
cp .env.example .env               # set EXPO_PUBLIC_BACKEND_URL=http://<your computer's Wi-Fi IP>:8001
yarn install
npx expo start
```
- Phone: scan the QR code in the terminal with Expo Go (Android) or the Camera app (iPhone).
- Browser: press `w`.
- Use your computer's Wi-Fi IP (Windows `ipconfig`, Mac/Linux `ifconfig` / `ip a`), not `localhost`, so the phone can reach the backend. Allow port 8001 in your firewall.

## 4. Logins
- Admin portal: `/admin/login` → value of ADMIN_EMAIL / ADMIN_PASSWORD in backend/.env (created on first start).
- Riders / drivers: register in the app.

## Notes
- Emails (password reset, notices) and push notifications use Emergent-managed keys (EMERGENT_EMAIL_KEY, EMERGENT_PUSH_KEY) that only work on Emergent. Locally, leave them empty: email/password sign-up and login still work, but password-reset emails and push notifications won't be sent.
- Never commit `.env` files.
