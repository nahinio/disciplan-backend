# Deploy DisciPlan Backend (Render)

Repository: [github.com/nahinio/disciplan-backend](https://github.com/nahinio/disciplan-backend)

## 1. Prerequisites

- [Aiven MySQL](https://aiven.io) database running
- [Cloudinary](https://cloudinary.com) account
- Migrations applied (`python scripts/run_migrations.py`)

## 2. Create Render Web Service

1. Go to [render.com](https://render.com) → **New** → **Web Service**
2. Connect **nahinio/disciplan-backend**
3. Settings:
   - **Runtime:** Python 3
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Health check path:** `/health`

Or use **Blueprint** and upload `render.yaml` from this repo.

## 3. Environment variables

Copy from `.env.example`. Required on Render:

| Variable | Notes |
|----------|--------|
| `APP_ENV` | `production` |
| `DEBUG` | `false` |
| `CORS_ORIGINS` | Your Vercel URL, e.g. `https://disciplan.vercel.app` |
| `DB_HOST` | Aiven host |
| `DB_PORT` | Aiven port |
| `DB_USER` | Aiven user |
| `DB_PASSWORD` | Aiven password |
| `DB_NAME` | Database name |
| `DB_SSL` | `true` |
| `DB_SSL_CA` | Paste full Aiven CA certificate PEM (from Aiven console) |
| `JWT_SECRET` | Long random string |
| `OTP_DEMO_MODE` | `false` for production |
| `CLOUDINARY_*` | Cloud name, API key, secret |

`DB_SSL_CA` replaces local `certs/ca.pem` on Render. Paste the entire certificate including `-----BEGIN CERTIFICATE-----` lines.

## 4. After deploy

- API docs: `https://YOUR-SERVICE.onrender.com/docs`
- OpenAPI: `https://YOUR-SERVICE.onrender.com/openapi.json`
- Health: `https://YOUR-SERVICE.onrender.com/health`

Set the frontend `VITE_API_BASE_URL` to:

```
https://YOUR-SERVICE.onrender.com/api/v1
```

## 5. Free tier note

Render free services sleep after inactivity. First request after sleep can take 30–60 seconds. Ping `/health` before a live demo.

## 6. WebSockets

Chat uses WebSockets at `/api/v1/chat/ws/{group_id}`. Render supports WebSockets on web services. Use `wss://` in production (derived automatically from `VITE_API_BASE_URL`).
