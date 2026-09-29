# ♻️ Kabadiwala Connect

Kabadiwala Connect is a digital platform that connects informal scrap and e-waste collectors (kabadiwalas) with authorized recyclers through verified digital lots, transparent prices, and a traceable handover process. Built for Smart India Hackathon 2026, Problem Statement PS 26229.

Live Demo: https://sih-tawny-sigma-38.vercel.app/

---

## 📑 Table of Contents

- About
- How It Works
- Real-World Use Cases
- Features
- Tech Stack
- File Tree
- Getting Started
- Usage
- Authentication
- Rate Limiting
- API Reference
- Error Handling
- Testing
- Deployment
- License

---

## 🧾 About

**Tagline: From scrap to verified sale, in one traceable flow.**

Kabadiwala Connect is a mobile-first, offline-capable platform that lets collectors register scrap as digital lots, get an instant value estimate, compare offers from nearby authorized recyclers, schedule pickups, and complete a verified handover with a digital receipt. Recyclers get a dashboard to manage incoming lots, offers, and payments. Admins verify recyclers, manage the price feed, and resolve disputes.

The platform is designed for collectors, authorized recyclers, and administrators. It supports English, Hindi, and Marathi, and adds AI features such as scrap identification from a photo, price prediction, abnormal price detection, and a voice assistant.

---

## ⚙️ How It Works

```
Collector -> Digital Lot -> Recycler Match -> Pickup -> Handover -> Payment -> Processing
```

Request lifecycle:

```
Client Request
    |
    v
Rate Limiter -> Auth Middleware -> Validator -> Router -> Service -> Database
    |
    v
JSON Response (success or structured error)
```

- Collection: The collector captures a photo, selects or confirms the material, enters an approximate weight, and creates a lot with a unique ID and QR code.
- Estimation: The value is calculated from the weight and the current price feed for the material and city.
- Matching: Authorized recyclers are ranked by distance, offer price, availability, and rating.
- Pickup and Handover: The recycler confirms the pickup. At handover, GPS, timestamp, and photo are recorded and verified.
- Payment: Cash, UPI reference, or bank transfer is recorded, and a digital receipt is generated.
- Traceability: Every step is stored as a lot event, so the full timeline (Collection, Pickup, Handover, Recycler, Processing) is visible.
- Offline-first: Lots created without internet are stored in a local queue and synced automatically when the connection returns.

---

## 💼 Real-World Use Cases

- Informal Collectors: A kabadiwala checks live prices, records a lot on a low-end phone, and sells to a verified recycler at a fair rate.
- Authorized Recyclers: A recycling unit receives verified lots, sets material-wise offers, and confirms handovers with QR scanning.
- Municipal and Regulatory Bodies: Admins track verified handover rates, recycler authorization, and environmental impact.
- Communities and NGOs: Aggregated, non-personal data supports community recycling drives and awareness.

---

## ✨ Features

Core features:

- Collector registration and profile
- Marathi, Hindi, and English support
- Photo-based scrap entry with client-side compression
- Material categorization and approximate weight entry
- Digital lot creation with QR and unique lot ID
- Instant scrap value estimation
- Current price board and historical price trends
- Nearby authorized recycler search and recycler matching
- Recycler price comparison and pickup availability
- Digital handover record with GPS, timestamp, and photo verification
- Recycler confirmation
- Cash and digital payment recording
- Earnings ledger and transaction history
- Safety guidance
- Offline-first functionality with automatic data synchronization
- Recycler dashboard and admin dashboard

AI features:

- AI scrap identification
- AI price estimation
- AI recycler recommendation
- AI price prediction
- Fraud and abnormal price detection
- Scrap condition detection
- Mixed-scrap detection
- AI voice assistant (Hindi and Marathi)
- AI safety assistant
- Best-sale recommendation
- Duplicate lot detection
- Recycler reliability prediction
- Earnings prediction
- Personalized price alerts

Additional features:

- QR-based lot tracking and complete traceability timeline
- Recycler verification badge
- Recycler rating and feedback
- Dispute and complaint system
- Digital payment receipt and digital handover certificate
- Pending payment tracker
- Offline transaction queue and automatic sync
- Low-data mode and compressed image upload
- Audio tutorials and pictorial safety instructions
- Emergency and safety button
- Transaction analytics and environmental impact dashboard
- Validated recycler history
- Collector achievement and reward system
- Referral system
- Multi-language voice and audio navigation
- Public community recycling map

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React, Vite, TypeScript, Tailwind CSS |
| App Type | Progressive Web App (installable, offline-capable) |
| Offline Storage | IndexedDB (Dexie), Workbox |
| Backend | Python, FastAPI |
| Validation | Pydantic |
| ORM | SQLAlchemy, Alembic |
| Database | PostgreSQL (SQLite for local development) |
| Auth | JWT with role-based access (collector, recycler, admin) |
| Maps | Leaflet, OpenStreetMap |
| Charts | Recharts |
| i18n | react-i18next (English, Hindi, Marathi) |
| Voice | Web Speech API |
| AI | Vision model or zero-shot CLIP, scikit-learn, rule-based fallbacks |
| QR | qrcode, html5-qrcode |
| Deployment | Vercel (frontend), Docker |

---

## 📂 File Tree

```
kabadiwala-connect/
├── frontend/
│   ├── src/
│   │   ├── pages/          # Landing, auth, collector, recycler, admin
│   │   ├── components/     # Shared UI components
│   │   ├── offline/        # IndexedDB, sync queue
│   │   ├── i18n/           # en, hi, mr translation files
│   │   └── hooks/          # Voice, GPS, sync helpers
│   └── vite.config.ts
├── backend/
│   ├── app/
│   │   ├── routers/        # Route handlers
│   │   ├── models/         # SQLAlchemy models
│   │   ├── schemas/        # Pydantic schemas
│   │   ├── services/       # Business logic
│   │   ├── ai/             # AI endpoints and fallbacks
│   │   └── core/           # Auth, config, rate limiting
│   ├── alembic/
│   ├── seed.py
│   └── tests/
├── reference/
│   └── prototype.html
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## 🏁 Getting Started

```
git clone https://github.com/your-username/kabadiwala-connect.git
cd kabadiwala-connect
cp .env.example .env
```

Backend:

```
cd backend
pip install -r requirements.txt
alembic upgrade head
python seed.py
uvicorn app.main:app --reload
```

Frontend:

```
cd frontend
npm install
npm run dev
```

The backend runs on http://localhost:8000 and the frontend on http://localhost:5173.

Or run everything with Docker:

```
docker-compose up --build
```

---

## 💡 Usage

Try the live demo: https://sih-tawny-sigma-38.vercel.app/

On the login page, click one of the demo user cards to enter a dashboard directly:

- Collector demo: create lots, see prices, get matched with recyclers
- Recycler demo: receive lots, set offers, confirm handovers
- Admin demo: verify recyclers, manage prices, resolve disputes

Make your first request:

```
# Get current prices (public endpoint)
curl https://your-api-url/api/v1/prices

# Create a lot (authenticated)
curl -X POST https://your-api-url/api/v1/lots \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: 7c9e6679-7425-40de-944b-e07fc1f90ae7" \
  -d '{"material": "PCB", "weight_kg": 10, "lat": 17.385, "lng": 78.486}'
```

Voice example: tap the microphone and ask "PCB ka bhav kya hai?" to hear the current PCB price.

---

## 🔑 Authentication

```
Authorization: Bearer <YOUR_TOKEN>
```

Collectors log in with phone and OTP. Recyclers and admins log in with email and password. Roles are enforced on both the frontend and backend.

Get a token:

```
POST /api/v1/auth/login
Content-Type: application/json

{ "email": "user@example.com", "password": "your_password" }
```

Response:

```
{ "accessToken": "eyJ...", "refreshToken": "eyJ...", "expiresIn": 3600 }
```

Demo login (only when DEMO_MODE=true):

```
POST /api/v1/auth/demo-login
Content-Type: application/json

{ "role": "collector" }
```

---

## 🚦 Rate Limiting

| Tier | Limit |
|---|---|
| Public endpoints | 60 req / minute per IP |
| Authenticated users | 300 req / minute |
| Demo accounts | 30 req / minute |

Response headers on every request:

```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 55
X-RateLimit-Reset: 1714000000
```

---

## 📚 API Reference

Auth

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| POST | /api/v1/auth/register | Register collector or recycler | No |
| POST | /api/v1/auth/login | Log in | No |
| POST | /api/v1/auth/demo-login | Log in as a demo user | No |

Lots

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| GET | /api/v1/lots | List own lots | Yes |
| POST | /api/v1/lots | Create a digital lot | Yes |
| GET | /api/v1/lots/:id | Get lot with timeline | Yes |
| GET | /api/v1/verify/:lotId | Public lot verification | No |

Prices and Recyclers

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| GET | /api/v1/prices | Current price board | No |
| GET | /api/v1/prices/history | Historical prices | No |
| GET | /api/v1/recyclers/nearby | Nearby authorized recyclers | Yes |
| POST | /api/v1/pickups | Schedule a pickup | Yes |

Handover and Payments

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| POST | /api/v1/handovers | Record and verify a handover | Yes |
| POST | /api/v1/transactions | Record a payment | Yes |
| GET | /api/v1/transactions | Transaction history | Yes |
| GET | /api/v1/receipts/:id | Download a receipt | Yes |

Sync

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| POST | /api/v1/sync | Push queued offline actions | Yes |

AI

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| POST | /ai/identify | Identify scrap from a photo | Yes |
| POST | /ai/estimate-price | Estimate scrap value | Yes |
| POST | /ai/recommend-recycler | Rank recyclers | Yes |
| POST | /ai/predict-price | Forecast price movement | Yes |
| POST | /ai/detect-abnormal-price | Flag unusual quotes | Yes |
| POST | /ai/condition | Estimate scrap condition | Yes |
| POST | /ai/mixed-scrap | Detect multiple materials | Yes |

Admin

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| GET | /api/v1/admin/recyclers/pending | Verification queue | Admin |
| POST | /api/v1/admin/recyclers/:id/approve | Approve a recycler | Admin |
| POST | /api/v1/admin/prices | Manage the price feed | Admin |
| POST | /api/v1/admin/reset-demo | Reset demo data | Admin |

---

## ⚠️ Error Handling

All errors follow a consistent format:

```
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "The requested lot does not exist.",
    "status": 404
  }
}
```

| Code | HTTP | Description |
|---|---|---|
| UNAUTHORIZED | 401 | Missing or invalid token |
| FORBIDDEN | 403 | Insufficient permissions |
| RESOURCE_NOT_FOUND | 404 | Resource does not exist |
| VALIDATION_ERROR | 422 | Invalid request body or params |
| DUPLICATE_REQUEST | 409 | Idempotency key already used |
| RATE_LIMIT_EXCEEDED | 429 | Too many requests |
| INTERNAL_ERROR | 500 | Unexpected server error |

---

## 🧪 Testing

```
# Backend
cd backend
pytest

# Frontend
cd frontend
npm run test

# End-to-end
npx playwright test
```

---

## 🚢 Deployment

Live frontend: https://sih-tawny-sigma-38.vercel.app/

Frontend build:

```
cd frontend
npm run build
npm run preview
```

Docker:

```
docker build -t kabadiwala-connect .
docker run -p 8000:8000 --env-file .env kabadiwala-connect
```

Set the frontend environment variable to point to your backend API:

```
VITE_API_URL=https://your-backend-url
```

Environment files containing secrets must not be committed to Git.

---

## 📄 License

Add the project's actual license here once one has been selected.
