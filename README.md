# HSA Platform

A Health Savings Account simulation: create accounts, deposit funds, issue a virtual debit card, and process card purchases that are approved only for qualified medical expenses. Purchases are safe under concurrency: two simultaneous charges can never overdraw an account.

**Stack:** React + TypeScript (Vite) · FastAPI (Python) · PostgreSQL 16 · Docker Compose

- [architecture.md](architecture.md): architecture, request flow, data model, concurrency handling, tradeoffs
- [ai-usage.md](ai-usage.md): how AI was used and how its output was verified

## Quick start (Docker)

Requires Docker Desktop (or Docker Engine with Compose).

```bash
docker compose up --build
```

Then open **http://localhost:3000**.

| Service | URL |
| --- | --- |
| Web UI | http://localhost:3000 |
| API | http://localhost:8000/api |
| Interactive API docs | http://localhost:8000/docs |
| Postgres | `localhost:55432` (user `hsa`, password `hsa`) |

Migrations run automatically when the backend starts. To reset all data: `docker compose down -v`. All ports are bound to `127.0.0.1` only, since this local simulation has no authentication.

If a port is already in use on your machine, override it when starting:

```bash
HSA_WEB_PORT=3001 HSA_API_PORT=8001 HSA_DB_PORT=55433 docker compose up --build
```

(PowerShell: `$env:HSA_WEB_PORT=3001; docker compose up --build`)

## Reviewer walkthrough (about 2 minutes)

1. **Create an account:** enter a name and email, pick self-only or family coverage.
2. **Deposit funds:** deposit `100`. The contribution meter shows progress toward the 2026 IRS limit.
3. **Issue a card:** click *Issue virtual card*.
4. **Simulate purchases:**
   - *Pharmacy* or *Hospital* → **approved**, balance goes down.
   - *Restaurant* or *Electronics* → **declined**: not a qualified medical expense.
   - An amount above the balance → **declined**: insufficient funds.
   - *Freeze card*, then purchase → **declined**: card is frozen.
   - *Retry last request* re-sends the same idempotency key and returns the original result without charging again.
5. **Concurrency test:** with a $100.00 balance, click *Send both at once* ($80 and $50). One is approved, the other declined, and the balance ends at $20 or $50, never negative.
6. **History:** the *Authorizations* tab lists every attempt with its decline reason; the *Ledger* tab shows every balance change.

## Running tests

The tests run against a real Postgres database because the behavior under test is Postgres row locking.

**Easiest: inside the running backend container** (no local Python needed). With the stack up:

```bash
docker compose exec -e TEST_DATABASE_URL=postgresql+psycopg://hsa:hsa@db:5432/hsa_test backend pytest
```

**Or locally** (requires Python 3.11+):

```bash
docker compose up -d db          # Postgres on localhost:55432, creates hsa and hsa_test
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest
```

28 tests, including the concurrency suite in `tests/test_concurrency.py`. The suite uses the separate `hsa_test` database (set by `TEST_DATABASE_URL`) and never touches app data.

## Local development without Docker for the app

Requires Python 3.11+ and Node 20+.

```bash
docker compose up -d db

# Terminal 1: API on :8000
cd backend
source .venv/bin/activate
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# Terminal 2: UI on :5173 (proxies /api to :8000)
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Set `DATABASE_URL` to use a different Postgres (default `postgresql+psycopg://hsa:hsa@localhost:55432/hsa`).

## API

All amounts are **integer cents**.

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/accounts` | Create account `{holder_name, email, coverage_type}` |
| `GET` | `/api/accounts` | List accounts |
| `GET` | `/api/accounts/{id}` | Account with card, balance, contributions this year, annual limit |
| `POST` | `/api/accounts/{id}/deposits` | Deposit `{amount_cents}` (422 if over the annual limit) |
| `POST` | `/api/accounts/{id}/card` | Issue the account's virtual card (409 if one exists) |
| `PATCH` | `/api/cards/{id}` | Freeze or unfreeze `{status: "active" \| "frozen"}` |
| `POST` | `/api/transactions` | Authorize a purchase `{card_id, merchant_name, merchant_category, amount_cents, idempotency_key}`. 201 with `approved`/`declined` + reason; 200 with the original result if the key was already used for the same purchase; 409 if it was used for a different one |
| `GET` | `/api/accounts/{id}/transactions` | Authorization history, newest first |
| `GET` | `/api/accounts/{id}/ledger` | Balance-change history, newest first |
| `GET` | `/api/merchant-categories` | Categories and whether each is a qualified medical expense |

Example:

```bash
curl -X POST localhost:8000/api/transactions -H 'Content-Type: application/json' -d '{
  "card_id": "<card id>", "merchant_name": "CVS", "merchant_category": "pharmacy",
  "amount_cents": 2500, "idempotency_key": "order-123"
}'
```

## Project layout

```
backend/
  app/
    main.py            HTTP routes
    schemas.py         request/response validation
    domain.py          merchant categories, IRS limits, enums
    models.py          tables and database constraints
    services/          business logic (accounts, cards, transactions)
  alembic/             database migrations
  tests/               API tests and concurrency tests
frontend/
  src/
    api.ts             typed API client
    money.ts           dollars ↔ cents without floating-point errors
    labels.ts          display text for decline reasons
    components/        one component per flow
db/init.sql            creates the test database
docker-compose.yml
```
