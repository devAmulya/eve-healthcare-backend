# EVE Healthcare — Diagnostic Bookings API

A backend service for booking diagnostic tests and simulating their payment,
built for the EVE Healthcare SDE Intern backend assignment.

**Stack:** FastAPI, SQLAlchemy 2.0, PostgreSQL (SQLite for tests), JWT auth, pytest.

---

## Running it

### Option A — Docker Compose (recommended, matches submission requirements)

```bash
cp .env.example .env
# edit .env and set a real JWT_SECRET_KEY, e.g.:
#   python -c "import secrets; print(secrets.token_hex(32))"

docker compose up --build
```

The API is then live at `http://localhost:8000`. Interactive docs (Swagger UI,
generated automatically by FastAPI) are at `http://localhost:8000/docs`.

To seed a couple of sample diagnostic centres/tests so there's something to
book against:

```bash
docker compose exec api python seed.py
```

### Option B — Run locally without Docker

Needs Python 3.11+. This path uses SQLite instead of Postgres, so there's
nothing else to install.

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate

pip install -r requirements.txt

# Point at a local SQLite file instead of Postgres
export DATABASE_URL="sqlite:///./dev.db"      # PowerShell: $env:DATABASE_URL="sqlite:///./dev.db"
export JWT_SECRET_KEY="dev-secret"             # PowerShell: $env:JWT_SECRET_KEY="dev-secret"

python seed.py
uvicorn app.main:app --reload
```

### Running tests

```bash
pip install -r requirements.txt   # includes pytest + httpx
pytest -v
```

Tests run against an isolated SQLite database (`tests/conftest.py`) that is
wiped and recreated before every test function, so they're fully independent
of whatever `DATABASE_URL` is set to and never touch Postgres.

---

## API endpoints

All request/response bodies are JSON. Full interactive docs with schemas and
a "try it out" console are auto-generated at `/docs` once the server is
running.

### Auth

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/signup` | — | Create a user. `{email, password}` (password ≥ 8 chars) |
| POST | `/auth/login` | — | Returns a JWT. `{email, password}` → `{access_token, token_type}` |

```bash
curl -X POST http://localhost:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email": "patient@example.com", "password": "hunter22222"}'

curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "patient@example.com", "password": "hunter22222"}'
# → {"access_token": "eyJ...", "token_type": "bearer"}
```

All endpoints below require `Authorization: Bearer <access_token>` unless noted.

### Centres & tests (public, read-only)

| Method | Path | Description |
|---|---|---|
| GET | `/centres/` | List all diagnostic centres with their tests |
| GET | `/centres/{id}` | Get one centre with its tests |

```bash
curl http://localhost:8000/centres/
```

### Bookings (auth required, owner-only)

| Method | Path | Description |
|---|---|---|
| POST | `/bookings/` | Create a booking. `{test_id, appointment_time}` → `PENDING` booking |
| GET | `/bookings/` | List the current user's bookings |
| GET | `/bookings/{id}` | Get one booking (403 if it isn't yours) |
| DELETE | `/bookings/{id}` | Cancel a booking — only allowed while it's `PENDING` |

```bash
curl -X POST http://localhost:8000/bookings/ \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"test_id": "<test-id-from-/centres/>", "appointment_time": "2026-10-15T09:00:00Z"}'
```

Booking states: `PENDING → CONFIRMED` (payment success), `PENDING → FAILED`
(payment failure), `PENDING → CANCELLED` (user cancels). There is no
transition out of `CONFIRMED`, `FAILED`, or `CANCELLED` — they're terminal.

### Payments

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/payments/` | Yes | Simulate an immediate payment attempt for a `PENDING` booking you own |
| POST | `/payments/webhook/` | No* | Simulates an async status push from a payment provider |

\* Real payment providers sign their webhook requests rather than requiring a
user JWT — see [Assumptions](#assumptions) below.

```bash
# Synchronous simulated payment (randomly succeeds ~80% of the time,
# or force a result for testing):
curl -X POST http://localhost:8000/payments/ \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"booking_id": "<id>", "force_result": "SUCCESS"}'

# Async webhook delivery:
curl -X POST http://localhost:8000/payments/webhook/ \
  -H "Content-Type: application/json" \
  -d '{"event_id": "evt-123", "booking_id": "<id>", "status": "SUCCESS"}'
```

---

## Database schema

```
User            id, email (unique), hashed_password, created_at
DiagnosticCentre  id, name, location
DiagnosticTest    id, centre_id → Centre, name, price
Booking           id, user_id → User, test_id → Test, centre_id → Centre,
                   appointment_time, amount, status, created_at, updated_at
Payment           id, booking_id → Booking (unique), amount, status,
                   provider_event_id (unique), created_at
```

Two design choices worth calling out:

- **`Booking.amount` is snapshotted from `DiagnosticTest.price` at booking
  time**, not re-read from the test later. If a centre changes its price,
  existing bookings shouldn't silently change value.
- **`Payment.booking_id` is unique**, so a booking can have at most one
  settled payment. Combined with a unique constraint on
  `Payment.provider_event_id`, this is what makes webhook idempotency a cheap
  database-level guarantee instead of an application-level "check then act"
  race condition.

## Webhook idempotency design

This was the edge case the assignment weighted most heavily, so it gets its
own section. `POST /payments/webhook/` handles three distinct replay
scenarios, all covered in `tests/test_webhook_idempotency.py`:

1. **Same `event_id` delivered more than once** — caught by a unique DB
   constraint on `provider_event_id`. The second delivery is detected and
   returns `200 {"status": "already_processed"}` without touching the
   booking again.
2. **A different `event_id` arrives for a booking that's already settled**
   (e.g. a provider retry that generates a new event id) — caught by the
   unique constraint on `Payment.booking_id`. Also a no-op.
3. **A late webhook arrives after the user already cancelled the booking** —
   explicitly checked before writing anything, so a stale success event can't
   resurrect a cancelled booking into `CONFIRMED`.

The insert is wrapped in a try/except around `IntegrityError`, so even two
webhook deliveries hitting the check at the exact same instant (a genuine
race, not just sequential duplicates) still can't both win — the database
constraint is the actual source of truth, not an in-memory check.

## Assumptions

- **No real payment gateway** — `/payments/` simulates an outcome in-process
  (random with a forceable override for testing), and `/payments/webhook/`
  simulates the provider push. In production these would be two ends of a
  real integration (e.g. Razorpay/Stripe), and the webhook would carry a
  provider signature to verify instead of being open.
- **`/payments/webhook/` has no auth** on purpose — this mirrors how real
  payment providers call webhooks (they don't have your users' JWTs; they'd
  sign the payload with a shared secret instead). Signature verification is
  called out as a "would add" item below rather than faked here.
- **Table creation uses `Base.metadata.create_all()`** at startup rather than
  Alembic migrations, to keep the assignment's scope manageable in the time
  given. Alembic is in `requirements.txt` and wiring it up is the first thing
  listed below.
- **A user can only have one PENDING→paid attempt at a time per booking** —
  once a booking leaves `PENDING`, no further payment can be initiated
  against it. Re-booking is a new `Booking` row, not a retried payment on the
  same one.
- **Diagnostic centres/tests are read-only via the API** in this submission
  (seeded via `seed.py`). Admin write endpoints for managing centres/tests
  weren't in the assignment's required scope, so they were left out in favor
  of spending the time on the booking/payment state machine and its edge
  cases.

## What I'd improve with more time

- Wire up **Alembic** migrations instead of `create_all()`, so schema changes
  are versioned and reviewable.
- **Webhook signature verification** (HMAC against a shared secret) instead
  of an open endpoint, plus a small retry-with-backoff queue (Celery/RQ) so a
  failed downstream side-effect from a webhook doesn't silently drop it.
- **Pagination** on `GET /bookings/` and `GET /centres/` — trivial for a demo
  dataset, not trivial once either table has real volume.
- **Rate limiting** on `/auth/login` specifically, to blunt credential
  stuffing — this is the one place in the API where its absence is a real
  gap rather than just a nice-to-have.
- **Structured (JSON) logging** with a request ID threaded through, instead
  of relying on default uvicorn access logs, to make production debugging
  and webhook-replay auditing tractable.
- **Admin endpoints** for managing centres/tests, with a separate role/scope
  on the JWT rather than reusing the patient-facing user model.
