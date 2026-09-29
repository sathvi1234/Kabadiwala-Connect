# Kabadiwala Connect

SIH 2026, problem statement 26229. Collectors record scrap lots, see live prices, and hand material to authorized recyclers with GPS, time, photo, and QR verification. Recyclers and admins have separate logins.

The visual reference is `reference/prototype.html`. The working app is the React client in `frontend/` and the FastAPI service in `backend/`.

## Run locally (Windows)

Requirements: Python 3.12+ and Node 20+.

```powershell
copy .env.example .env
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe seed.py
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The public landing page is `/`. Log in at `/login`, or use a demo card. The API is http://localhost:8000 (interactive docs at `/docs`).

`DEMO_MODE=true` (the default in development) enables `POST /api/auth/demo-login`. Demo accounts are flagged `is_demo`, cannot change a password or delete price rows, and an admin can restore seeded lots with Reset demo. Set `DEMO_NIGHTLY_RESET=true` only if a 03:00 reset should run.

SQLite is the default database (`backend/kabadiwala.db`). In development the API also creates tables and seeds on startup if the database is empty.

### Demo accounts

Password for every seeded account: `Demo@123`

| Role | Phone | Notes |
| --- | --- | --- |
| Admin | 9999999999 | Approves recyclers, prices, disputes |
| Collector | 9000000001 | Ramesh Kumar, Hindi, Hyderabad |
| Collector | 9000000002 | Savita Pawar, Marathi, Pune |
| Collector | 9000000003 | Imran Shaikh, referred by Ramesh |
| Recycler | 9000000011 | GreenCycle Recycling, approved |
| Recycler | 9000000012 | EcoLoop Recyclers, approved |
| Recycler | 9000000013 | Metro Scrap Hub, approved, busy |
| Recycler | 9000000014 | Pending Scrap Co, waiting for admin |

Registration OTP in development is `123456` and is also returned as `dev_otp`. There is no SMS provider. Outside `ENV=development` the code is random and only logged, not returned.

## Docker

```powershell
docker compose up --build
```

- API: http://localhost:8000
- Web: http://localhost:8080
- Postgres: localhost:5432 (`kabadi` / `kabadi` / `kabadiwala`)

Set `DATABASE_URL=postgresql+psycopg://kabadi:kabadi@localhost:5432/kabadiwala` in `.env` if you want the local API to use that database instead of SQLite.

## Tests

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
cd ..\frontend
npm test
npm run test:e2e
```

Backend tests cover role guards, collector and recycler registration, lot creation, price estimation, sync idempotency, handover GPS/weight flags, partial payment, PDF receipt, and the public verification page. Frontend unit tests check translation key parity and the offline queue helpers. Playwright covers register, create a lot while offline, and sync. The API must be reachable at `http://127.0.0.1:8000` (the Playwright config starts it).

## Demo script

1. Log in as Ramesh (`9000000001` / `Demo@123`). Switch language to Hindi. The choice is saved on the user.
2. Open Prices. Filter Hyderabad, switch 7d / 30d / 90d / 1y, and run the forecast.
3. Open Digital Lots. Add a photo (it is compressed to WebP), confirm or change the suggested material, enter weight in kg or g, capture GPS, and create the lot. The QR is the lot id `LOT-YYYYMMDD-xxxx`.
4. Open the lot. Compare recycler offers. The best net payout is highlighted. Schedule a pickup with GreenCycle.
5. Log out. Log in as GreenCycle (`9000000011`). Set availability, accept the pickup, scan or open the lot, confirm the weight, then record a partial cash payment and the rest by UPI reference.
6. Back as the collector, download the receipt PDF and the handover certificate. Rate the recycler.
7. Turn on airplane mode, create another lot, then go online and press Sync now. The same idempotency key cannot create a duplicate.
8. Log in as admin. Approve Pending Scrap Co, edit a price, resolve the seeded copper dispute, and open the audit log and sync monitor.
9. Open http://localhost:5173/verify/LOT-... and http://localhost:5173/community. Those pages do not show collector phone numbers or names.

## What is real, and what falls back

| Feature | With a key | Without a key |
| --- | --- | --- |
| `POST /ai/identify`, `/ai/condition` | `VISION_API_KEY` plus an OpenAI-compatible vision chat URL | Pillow colour and texture heuristic |
| Voice intent if keywords miss | `LLM_API_KEY` | Keyword and regex matcher for Hindi, Marathi, English, and Hinglish |
| Price forecast and earnings forecast | scikit-learn linear regression with day-of-year seasonality | Average fallback when history is too short |
| Abnormal quotes | z-score and IQR on history and peer offers | Same, always local |
| Payments | Records Cash, UPI reference, or bank reference | No payment gateway |
| Push | In-app notifications, plus the browser Notification API while the app is open | No VAPID/web-push server |
| Maps | Leaflet and OpenStreetMap tiles | Low-data mode hides tiles and shows a list |

Uploaded files go to `backend/uploads` through `app/storage.py`. Swap that module for S3 by keeping the same `save_upload` / `absolute_path` shape.

## Emission factors

Diverted weight is summed from lots in `handed_over`, `processing`, or `completed`. CO₂ avoided is `weight_kg × material.co2_factor`. Factors live on the `materials` table and are cited here:

| Material | kg CO₂e avoided per kg | Source |
| --- | --- | --- |
| Aluminium | 9.0 | International Aluminium Institute, primary versus recycled aluminium |
| Copper | 4.0 | International Copper Association, energy savings of recycled copper |
| Metal | 1.8 | US EPA WARM, steel cans / mixed metals, approximate |
| Plastic | 1.5 | US EPA WARM, mixed plastics recycling versus landfill, approximate |
| Paper/Cardboard | 0.9 | US EPA WARM, corrugated containers, approximate |
| Cable | 2.0 | Copper-content share of the ICA copper factor, for mixed cable |
| Battery | 1.2 | International Lead Association, lead-acid recycling, illustrative |
| PCB | 2.5 | Illustrative WEEE factor informed by UNU Global E-waste Monitor |
| LCD | 1.5 | Illustrative flat-panel WEEE factor |
| CRT | 0.8 | Illustrative intact-CRT handling factor |

WEEE rows are order-of-magnitude factors for the demo, not a national inventory.

## Roles

- Collectors register with phone OTP, language, area, materials, optional ID, and an optional referral code.
- Recyclers upload a licence and stay `pending` until an admin approves or rejects them. Pending accounts can log in but cannot publish offers or appear in search.
- Admins manage users, the price feed, disputes, the audit log, and sync.

Sensitive actions (verification, payments, disputes, price changes, user updates) are written to `audit_logs`.

## Offline

The collector can create a lot with no network. The lot, compressed photo, cached price list, and recycler list sit in IndexedDB (Dexie). Coming online, or pressing Sync now, posts each item with its client UUID. The server returns the original lot if that key was already used. Price edits from a client are ignored (server wins). Lot drafts that are still `open` accept the client update (client wins). The badge shows Synced, Pending N, or Failed.

The service worker (Workbox via `vite-plugin-pwa`) caches the app shell. Translations are bundled and also selected from `localStorage` key `kabadi_lang`.
