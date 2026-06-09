# DisciPlan Backend

FastAPI + **raw SQL** + **Aiven MySQL** + **Cloudinary** file storage.

No ORM. All queries are parameterized raw SQL in `app/repositories/`.

## Architecture

```
app/
├── main.py              # FastAPI entry
├── config.py            # Aiven + Cloudinary + JWT settings
├── db/
│   ├── pool.py          # asyncmy connection pool (Aiven SSL)
│   └── session.py       # transaction helpers
├── repositories/        # RAW SQL queries only
├── services/            # business logic
├── routers/             # HTTP endpoints
└── utils/
    ├── security.py      # JWT, bcrypt, OTP
    └── cloudinary.py    # file upload (binaries off-DB)
sql/
├── 001_schema.sql       # ultra-normalized schema (50+ tables)
├── 002_seed.sql         # lookup tables only (roles, enums, tiers)
├── 003_views.sql        # optimized views for complex queries
└── 004_seed_academic.sql # intentionally empty — use admin console for courses
```

## Deploy (Render)

See [DEPLOY.md](./DEPLOY.md) for production deployment to Render.

Repository: [github.com/nahinio/disciplan-backend](https://github.com/nahinio/disciplan-backend)

## Setup

### 1. Aiven MySQL

1. Create a free **Aiven for MySQL** service at [aiven.io](https://aiven.io/free-tier)
2. Copy connection details (host, port, user, password, database)
3. Download the **CA certificate** from Aiven console → save as `certs/ca.pem`

### 2. Cloudinary

1. Create a free account at [cloudinary.com](https://cloudinary.com)
2. Copy Cloud Name, API Key, API Secret

### 3. Environment

```bash
cd DisciPlan-backend
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
copy .env.example .env          # then fill in your values
```

### 4. Run migrations

```bash
python scripts/run_migrations.py
```

### 5. Bootstrap accounts (optional)

No demo users are seeded automatically. Create your first admin:

```bash
set BOOTSTRAP_ADMIN_EMAIL=you@uiu.ac.bd
set BOOTSTRAP_ADMIN_PASSWORD=your-secure-password
set BOOTSTRAP_ADMIN_NAME=Your Name
python scripts/seed_admin.py
```

Add faculty to the roster (pending signup) or create a faculty account — see `BOOTSTRAP_FACULTY_*` in `.env.example`.

### 6. Remove legacy demo data (existing databases)

If you previously applied old seeds with demo courses (`CSE 1115`, etc.) or test accounts:

```bash
python scripts/purge_demo_data.py --confirm
```

### 7. Start API

```bash
uvicorn app.main:app --reload --port 8000
```

- API docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

## API Modules (Phase 1 — implemented)

| Module | Prefix | Description |
|--------|--------|-------------|
| Auth | `/api/v1/auth` | OTP, register, login, refresh |
| Users | `/api/v1/users` | Profile (`/me`) |
| Notifications | `/api/v1/notifications` | Poll-based bell icon |
| Chat | `/api/v1/chat` | DB-backed groups + messages |
| Files | `/api/v1/files` | Cloudinary upload + MySQL metadata |
| Health | `/health` | DB connectivity check |

## Notification + Chat Flow (no WebSocket)

```
Message sent → INSERT chat_messages
            → INSERT notifications (all group members except sender)
Frontend polls GET /notifications/unread-count  (every ~8s)
User clicks notification → navigates to chat page
Frontend polls GET /chat/groups/{id}/messages?after_id=X  (every ~3s)
```

## Database Design Highlights

- **50+ tables**, 3NF/BCNF normalized
- All enums in **lookup tables** (roles, statuses, types)
- **Junction tables** for all M:N relationships
- **Files**: metadata in MySQL, binaries on Cloudinary
- **Views** for complex reads: unread counts, last message per group, leaderboards
- **Indexes** on every FK and hot query column

## Evaluation SQL Showcase

See `sql/003_views.sql` and `app/repositories/` for:

- Multi-table INSERT (notify all group members on new message)
- Keyset pagination (`id > after_id` — no OFFSET)
- Window functions (`RANK()` leaderboard view)
- Aggregate subqueries (unread message counts per group)
- EXISTS checks for read receipts

## Next phases

- Courses, sections, enrollments
- Section hub (announcements, doubts, exams, grades)
- Blogs, forum, practice
- Teams, admin console
- Frontend API integration (replace localStorage)
