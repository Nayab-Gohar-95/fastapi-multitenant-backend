# Multi-Tenant LLM SaaS Backend

A production-ready, async FastAPI backend implementing multi-tenant architecture, JWT authentication, RBAC, and an LLM messaging system. Built for SaaS and AI platform engineering roles.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        FastAPI App                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ /tenants │  │  /auth   │  │ /messages│  │  /admin  │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  │
│       │              │              │              │         │
│  ┌────▼──────────────▼──────────────▼──────────────▼─────┐ │
│  │              Dependency Injection Layer                 │ │
│  │   get_db  │  get_current_user  │  get_current_admin    │ │
│  └─────────────────────┬───────────────────────────────── ┘ │
│                         │                                    │
│  ┌──────────────────────▼──────────────────────────────── ┐ │
│  │                  Service Layer                          │ │
│  │  TenantService │ UserService │ MessageService │ LLM    │ │
│  └──────────────────────┬────────────────────────────────┘  │
│                          │                                   │
│  ┌───────────────────────▼───────────────────────────────┐  │
│  │        Async SQLAlchemy + asyncpg → PostgreSQL        │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

**Key design decisions:**

- **Async-first**: Every route, service, and DB call is `async/await`. Zero blocking calls.
- **Tenant isolation at query level**: Every DB query includes `tenant_id` in the WHERE clause. This is not optional and cannot be bypassed by client-supplied values.
- **JWT embeds tenant_id + role**: Stateless auth — most requests require zero extra DB lookups for authorisation.
- **Service layer abstraction**: Routes never write SQL. Services never return HTTP responses. Clean separation.
- **LLM pluggability**: `LLMService` wraps the provider. Swap OpenAI for Anthropic/Ollama in one place.

---

## Project Structure

```
llm-saas-backend/
├── main.py                          # FastAPI app factory, lifespan, CORS
├── create_tables.py                 # One-shot table creation script
├── requirements.txt
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── alembic.ini
├── alembic/
│   ├── env.py                       # Async Alembic migration environment
│   └── versions/                    # Auto-generated migration files
└── app/
    ├── __init__.py
    ├── dependencies.py              # get_current_user / get_current_admin
    ├── core/
    │   ├── config.py                # Settings via pydantic-settings + .env
    │   ├── security.py              # bcrypt hashing, JWT mint/verify
    │   └── logging.py               # Structured JSON logging (structlog)
    ├── db/
    │   ├── base.py                  # DeclarativeBase + TimestampMixin
    │   └── session.py               # AsyncEngine, session factory, get_db()
    ├── models/
    │   ├── __init__.py              # Re-exports Base + all models
    │   ├── tenant.py                # Tenant ORM model
    │   ├── user.py                  # User ORM model + UserRole enum
    │   └── message.py               # Message ORM model
    ├── schemas/
    │   ├── tenant.py                # TenantCreate, TenantRead
    │   ├── user.py                  # UserRegister, UserCreate, TokenResponse
    │   └── message.py               # MessageCreate, MessageRead
    ├── services/
    │   ├── tenant_service.py        # Tenant CRUD
    │   ├── user_service.py          # Registration, auth, user listing
    │   ├── message_service.py       # LLM call + message persistence
    │   └── llm_service.py           # LLM abstraction (mock + OpenAI)
    └── api/
        └── routes/
            ├── tenants.py           # POST /create-tenant, GET /tenants/{id}/users
            ├── auth.py              # POST /register, POST /login, GET /me
            ├── messages.py          # POST /messages, GET /messages
            └── admin.py             # POST /admin/users
```

---

## Database Schema

```sql
tenants
  id          VARCHAR(36) PK
  name        VARCHAR(255) UNIQUE NOT NULL
  created_at  TIMESTAMPTZ DEFAULT now()
  updated_at  TIMESTAMPTZ DEFAULT now()

users
  id               VARCHAR(36) PK
  email            VARCHAR(320) UNIQUE NOT NULL
  hashed_password  VARCHAR(255) NOT NULL
  role             VARCHAR(20) NOT NULL  -- 'admin' | 'user'
  tenant_id        VARCHAR(36) FK → tenants.id ON DELETE CASCADE
  created_at       TIMESTAMPTZ DEFAULT now()
  updated_at       TIMESTAMPTZ DEFAULT now()

messages
  id          VARCHAR(36) PK
  content     TEXT NOT NULL
  response    TEXT NOT NULL
  user_id     VARCHAR(36) FK → users.id ON DELETE CASCADE
  tenant_id   VARCHAR(36) FK → tenants.id ON DELETE CASCADE  ← denormalised for fast queries
  created_at  TIMESTAMPTZ DEFAULT now()
  updated_at  TIMESTAMPTZ DEFAULT now()
```

---

## API Reference

| Method | Endpoint | Auth | Role | Description |
|--------|----------|------|------|-------------|
| GET | `/health` | None | — | Liveness check |
| POST | `/create-tenant` | None | — | Create a new tenant |
| POST | `/register` | None | — | Register a user in an existing tenant |
| POST | `/login` | None | — | Get JWT access token |
| GET | `/me` | JWT | any | Get current user profile |
| POST | `/messages` | JWT | user/admin | Send prompt to LLM |
| GET | `/messages` | JWT | user/admin | List tenant messages (paginated) |
| POST | `/admin/users` | JWT | admin | Create user in tenant |
| GET | `/tenants/{id}/users` | JWT | admin | List users in tenant |

---

## Setup & Running

### Option A — Local Development

**1. Prerequisites**
- Python 3.12+
- PostgreSQL 15+ running locally
- (Optional) Redis

**2. Create virtual environment**
```bash
python -m venv .venv
source .venv/bin/activate       # Linux / macOS
.venv\Scripts\activate          # Windows PowerShell
```

**3. Install dependencies**
```bash
pip install -r requirements.txt
```

**4. Configure environment**
```bash
cp .env.example .env
# Edit .env — at minimum set:
#   SECRET_KEY=<random 32+ char string>
#   DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/llm_saas_db
```

Generate a secure secret key:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

**5. Create PostgreSQL database**
```bash
psql -U postgres -c "CREATE DATABASE llm_saas_db;"
```

**6a. Create tables (quick)**
```bash
python create_tables.py
```

**6b. OR use Alembic migrations (recommended)**
```bash
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

**7. Start the server**
```bash
uvicorn main:app --reload --port 8000
```

Visit: http://localhost:8000/docs

---

### Option B — Docker Compose

```bash
cp .env.example .env
# Edit SECRET_KEY at minimum

docker compose up --build
```

API available at http://localhost:8000/docs

---

## Example API Calls

### 1. Create a tenant

**curl:**
```bash
curl -X POST http://localhost:8000/create-tenant \
  -H "Content-Type: application/json" \
  -d '{"name": "Acme Corp"}'
```

**PowerShell:**
```powershell
Invoke-RestMethod -Method POST -Uri "http://localhost:8000/create-tenant" `
  -ContentType "application/json" `
  -Body '{"name": "Acme Corp"}'
```

**Response:**
```json
{
  "id": "3f7c1234-...",
  "name": "Acme Corp",
  "created_at": "2025-01-15T10:30:00Z"
}
```

---

### 2. Register a user

```bash
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "alice@acme.com",
    "password": "s3cur3P@ssw0rd",
    "tenant_id": "3f7c1234-..."
  }'
```

---

### 3. Login

```bash
curl -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"email": "alice@acme.com", "password": "s3cur3P@ssw0rd"}'
```

**Response:**
```json
{
  "access_token": "eyJhbGci...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": { "id": "...", "email": "alice@acme.com", "role": "user", ... }
}
```

---

### 4. Send a message (authenticated)

```bash
export TOKEN="eyJhbGci..."

curl -X POST http://localhost:8000/messages \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"content": "What are the benefits of async Python?"}'
```

**PowerShell:**
```powershell
$token = "eyJhbGci..."
$headers = @{ Authorization = "Bearer $token"; "Content-Type" = "application/json" }
Invoke-RestMethod -Method POST -Uri "http://localhost:8000/messages" `
  -Headers $headers -Body '{"content": "What is async Python?"}'
```

---

### 5. List messages (paginated)

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/messages?skip=0&limit=20"
```

---

### 6. Create admin user (admin token required)

```bash
curl -X POST http://localhost:8000/admin/users \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"email": "bob@acme.com", "password": "adminP@ss!", "role": "admin"}'
```

---

### 7. List tenant users (admin only)

```bash
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  "http://localhost:8000/tenants/{tenant_id}/users"
```

---

## Postman Collection

Import into Postman using Environment Variables:
- `base_url`: `http://localhost:8000`
- `token`: *(set after login)*
- `tenant_id`: *(set after create-tenant)*

---

## Extending the System

### Redis Caching

```python
# services/cache_service.py
import redis.asyncio as redis
from app.core.config import settings

redis_client = redis.from_url(settings.REDIS_URL)

async def get_cached(key: str) -> str | None:
    return await redis_client.get(key)

async def set_cached(key: str, value: str, ttl: int = 300) -> None:
    await redis_client.set(key, value, ex=ttl)
```

Cache message responses by prompt hash to reduce LLM API costs.

### Background Tasks (FastAPI + asyncio)

```python
from fastapi import BackgroundTasks

@router.post("/messages")
async def send_message(body: MessageCreate, background_tasks: BackgroundTasks, ...):
    message = await MessageService.create_message(...)
    background_tasks.add_task(send_slack_notification, message.id)  # fire-and-forget
    return MessageRead.model_validate(message)
```

For heavy async jobs, use **Celery + Redis** or **ARQ**.

### Rate Limiting

```python
# Using slowapi (ASGI-compatible)
pip install slowapi

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/messages")
@limiter.limit("10/minute")
async def send_message(request: Request, ...):
    ...
```

For per-tenant rate limits, key on `tenant_id` from the JWT.

### Vector DB Integration (RAG)

```python
# services/vector_service.py — using pgvector or Pinecone
import pinecone

async def store_embedding(text: str, message_id: str, tenant_id: str):
    embedding = await openai_embed(text)
    index.upsert([(message_id, embedding, {"tenant_id": tenant_id})])

async def search_similar(query: str, tenant_id: str, top_k: int = 5):
    embedding = await openai_embed(query)
    # Metadata filter enforces tenant isolation in the vector store
    return index.query(vector=embedding, filter={"tenant_id": tenant_id}, top_k=top_k)
```

---

## Scalability Recommendations

1. **Read replicas**: Route `SELECT` queries to read replicas using SQLAlchemy's `execution_options(sync_dialect_options={"postgresql_readonly": True})`.
2. **Connection pooling**: Use PgBouncer in transaction mode between app and PostgreSQL.
3. **Horizontal scaling**: The app is stateless — run multiple container instances behind a load balancer.
4. **Async task queue**: Move LLM calls to an ARQ/Celery worker queue so HTTP requests return immediately.
5. **Multi-region**: Tenant data can be sharded to region-specific databases for data residency compliance.
6. **Observability**: Integrate OpenTelemetry traces → Jaeger/Tempo; metrics → Prometheus/Grafana.

---

## Security Hardening Checklist

- [x] bcrypt with work factor 12
- [x] JWT signed with HS256 (upgrade to RS256 for microservices)
- [x] tenant_id enforced at DB query level
- [x] hashed_password never returned in any response
- [x] Non-root Docker user
- [x] CORS configured via environment
- [ ] Add `python-slowapi` rate limiting
- [ ] Rotate `SECRET_KEY` with dual-token acceptance window
- [ ] Enable PostgreSQL row-level security (RLS) as defence-in-depth
- [ ] Add request ID middleware for log correlation
- [ ] TLS termination at load balancer / nginx
