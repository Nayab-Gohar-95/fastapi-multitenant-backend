# Multi-Tenant LLM SaaS Backend

A production-ready backend for multi-tenant AI/LLM applications built with FastAPI, PostgreSQL, async SQLAlchemy, JWT authentication, role-based access control, MLflow experiment tracking, and real-time LLM streaming via Server-Sent Events.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | FastAPI (async) |
| Database | PostgreSQL 16 + async SQLAlchemy 2.0 |
| DB Driver | asyncpg |
| Migrations | Alembic |
| Auth | JWT (python-jose) + bcrypt |
| LLM | Mock (default) / OpenAI-compatible |
| Experiment Tracking | MLflow |
| Streaming | Server-Sent Events (SSE) via StreamingResponse |
| Config | pydantic-settings + .env |
| Logging | structlog (JSON in prod, console in dev) |
| Containerisation | Docker + Docker Compose |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      FastAPI App                        │
│                                                         │
│  Routes → Dependencies → Services → DB (async)          │
│                                                         │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │  JWT Auth   │  │  LLM Service │  │ MLflow Track  │  │
│  │  RBAC       │  │  + Streaming │  │ per inference │  │
│  │  Tenant ISO │  │  + Mock mode │  │ latency/tokens│  │
│  └─────────────┘  └──────────────┘  └───────────────┘  │
└─────────────────────────────────────────────────────────┘
              │                    │
     PostgreSQL (async)       MLflow (local ./mlruns)
     Multi-tenant schema      or remote tracking server
```

### Multi-Tenant Isolation

Every database table carries a `tenant_id` column. Every query filters by `tenant_id` derived from the JWT — not from user input. A user from Tenant A cannot access Tenant B's data even if they know the IDs.

```
tenants  ──< users  ──< messages
              │               │
         tenant_id       tenant_id  (denormalised for zero-JOIN queries)
```

### Request Flow

```
Request
  → OAuth2 Bearer token extracted
  → JWT decoded (no DB round-trip)
  → User + tenant_id loaded from DB (validates token still valid)
  → Service layer executes with tenant_id enforced
  → MLflow tracks every LLM inference
  → Response returned
```

---

## Project Structure

```
llm-saas-backend/
├── main.py                        ← App factory, lifespan, CORS, error handlers
├── create_tables.py               ← One-shot table creation (dev only)
├── requirements.txt
├── .env                           ← Your secrets (never commit)
├── .env.example                   ← Template
├── Dockerfile                     ← Multi-stage production image
├── docker-compose.yml             ← App + PostgreSQL
├── .dockerignore
│
├── alembic/                       ← Database migrations
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│
└── app/
    ├── dependencies.py            ← get_current_user, get_current_admin
    │
    ├── core/
    │   ├── config.py              ← pydantic-settings, reads .env
    │   ├── security.py            ← bcrypt hashing, JWT mint/verify
    │   └── logging.py             ← structlog setup
    │
    ├── db/
    │   ├── base.py                ← DeclarativeBase, TimestampMixin
    │   └── session.py             ← Async engine, get_db() dependency
    │
    ├── models/
    │   ├── tenant.py              ← Tenant ORM
    │   ├── user.py                ← User ORM + UserRole enum
    │   └── message.py             ← Message ORM (denormalised tenant_id)
    │
    ├── schemas/
    │   ├── tenant.py              ← Pydantic request/response models
    │   ├── user.py                ← Pydantic request/response models
    │   └── message.py             ← Pydantic request/response models
    │
    ├── services/
    │   ├── llm_service.py         ← LLM abstraction: generate() + generate_stream()
    │   ├── mlflow_service.py      ← MLflow experiment tracking per inference
    │   ├── message_service.py     ← Message persistence + LLM orchestration
    │   ├── tenant_service.py      ← Tenant CRUD
    │   └── user_service.py        ← Registration, auth, user management
    │
    └── api/routes/
        ├── auth.py                ← POST /register, POST /login, GET /me
        ├── tenants.py             ← POST /create-tenant, GET /tenants/{id}/users
        ├── messages.py            ← POST /messages, GET /messages/stream, GET /messages
        └── admin.py               ← POST /admin/users
```

---

## API Endpoints

### Public (no auth required)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/create-tenant` | Onboard a new tenant/company |
| POST | `/register` | Register a new user in an existing tenant |
| POST | `/login` | Authenticate, receive JWT token |
| GET | `/health` | Health check |

### Authenticated (JWT required)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/me` | Get current user profile |
| POST | `/messages` | Send prompt to LLM, store response, track in MLflow |
| GET | `/messages/stream` | Stream LLM response token-by-token via SSE |
| GET | `/messages` | Paginated message history (tenant-scoped) |

### Admin only (admin JWT required)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/admin/users` | Create user within your tenant |
| GET | `/tenants/{id}/users` | List all users in a tenant |

---

## Key Features

### 1. JWT Authentication
Tokens embed `user_id`, `tenant_id`, and `role`. Every protected endpoint decodes the token and verifies the user still exists in the DB — revoked/deleted users are rejected immediately.

### 2. Role-Based Access Control
Two roles: `admin` and `user`. Admin endpoints return 403 to regular users. Admins can only manage their own tenant — cross-tenant admin access is blocked even if the tenant ID is known.

### 3. Multi-Tenant Data Isolation
`tenant_id` is enforced at the query level in every service method — never derived from user-supplied request data. The JWT is the source of truth.

### 4. LLM Streaming (SSE)
`GET /messages/stream?content=...` streams the LLM response token by token using FastAPI's `StreamingResponse` with `text/event-stream` media type. Each chunk is formatted as a standard SSE message (`data: <token>\n\n`). The stream ends with `data: [DONE]\n\n`.

```bash
# Test streaming with curl
curl -N -H "Authorization: Bearer <your_token>" \
  "http://localhost:8000/messages/stream?content=What+is+FastAPI"
```

### 5. MLflow Experiment Tracking
Every LLM inference (both `/messages` and `/messages/stream`) is automatically logged to MLflow with:
- **Parameters**: model name, prompt length, tenant_id, user_id, environment
- **Metrics**: latency_ms, response_length, approx_tokens_in, approx_tokens_out
- **Tags**: tenant_id, source

```bash
# View MLflow dashboard
mlflow ui --port 5001
# Open: http://localhost:5001
```

### 6. LLM Provider Abstraction
Set `OPENAI_API_KEY` in `.env` to switch from mock to real OpenAI. No code changes required. The service layer supports any OpenAI-compatible endpoint (Azure OpenAI, Ollama, Together AI).

---

## Local Setup

### Prerequisites
- Python 3.12 or 3.13
- PostgreSQL 15 or 16

### Steps

```bash
# 1. Clone / extract project
cd llm-saas-backend

# 2. Create virtual environment
python -m venv .venv

# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
# Edit .env — set SECRET_KEY and DATABASE_URL with your postgres password

# 5. Create database
psql -U postgres -c "CREATE DATABASE llm_saas_db;"

# 6. Create tables
python create_tables.py

# 7. Start server
uvicorn main:app --reload --port 8000

# 8. Open Swagger UI
# http://localhost:8000/docs

# 9. (Optional) Start MLflow dashboard in a second terminal
mlflow ui --port 5001
# http://localhost:5001
```

### .env Configuration

```env
APP_NAME=LLM SaaS Backend
APP_ENV=development
DEBUG=true

SECRET_KEY=your-random-32-char-string-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

DATABASE_URL=postgresql+asyncpg://postgres:YOUR_PASSWORD@localhost:5432/llm_saas_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=YOUR_PASSWORD
POSTGRES_DB=llm_saas_db

# Leave blank for mock LLM mode (no OpenAI account needed)
OPENAI_API_KEY=
LLM_MODEL=gpt-4o-mini
LLM_MAX_TOKENS=1024
LLM_TEMPERATURE=0.7

ALLOWED_ORIGINS=["http://localhost:3000","http://localhost:8000"]
```

Generate a secure SECRET_KEY:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## Docker Setup

```bash
# Build and start everything (app + postgres)
docker compose up --build

# View logs
docker compose logs -f api

# Stop
docker compose down

# Stop and delete database volume
docker compose down -v
```

---

## Testing the API (Quick Start)

### 1. Create a tenant
```bash
curl -X POST http://localhost:8000/create-tenant \
  -H "Content-Type: application/json" \
  -d '{"name": "Acme Corp"}'
# → copy the "id" field
```

### 2. Register a user
```bash
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{"email": "alice@acme.com", "password": "password123", "tenant_id": "PASTE-ID-HERE"}'
```

### 3. Login
```bash
curl -X POST http://localhost:8000/login \
  -d "username=alice@acme.com&password=password123"
# → copy the "access_token" field
```

### 4. Send a message (full response + MLflow tracking)
```bash
curl -X POST http://localhost:8000/messages \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"content": "What is multi-tenant architecture?"}'
```

### 5. Stream a response (SSE)
```bash
curl -N http://localhost:8000/messages/stream?content=What+is+LangChain \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## Database Migrations (Alembic)

```bash
# Generate migration after model changes
alembic revision --autogenerate -m "describe_change"

# Apply migrations
alembic upgrade head

# Roll back one migration
alembic downgrade -1
```

---

## Extending the Project

| Feature | Where to add |
|---------|-------------|
| LangChain integration | Replace `llm_service.py` generate methods with LangChain chains |
| Vector search (pgvector) | Add `pgvector` to models, embed messages in `message_service.py` |
| WebSocket chat | Add `app/api/routes/ws.py` with FastAPI WebSocket endpoint |
| Rate limiting | Add `slowapi` middleware in `main.py` |
| Redis caching | Add `aioredis` and cache LLM responses in `llm_service.py` |
| Celery background tasks | Add `celery` + Redis for async LLM jobs |
| Stripe billing | Add `stripe` SDK, tenant billing model, webhook endpoint |
| AWS deployment | Dockerize → push to ECR → deploy on ECS or EC2 |
