# Payment & Booking Lifecycle Engine

A FastAPI backend that models end-to-end booking and payment lifecycles for:
- Event seat bookings (multi-seat-type inventory + waitlist)
- Restaurant table slot bookings
- Payment order creation and signature verification via Razorpay

This project is designed to demonstrate clean domain modeling, idempotent booking behavior, state transitions, and transactional inventory handling.

## Live Demo
- API Base URL: `https://<your-railway-or-render-domain>`
- Swagger UI: `https://<your-railway-or-render-domain>/docs`
- Health Check: `https://<your-railway-or-render-domain>/health`

## Tech Stack
- Python
- FastAPI
- SQLAlchemy 2.x
- PostgreSQL
- Razorpay SDK
- Pytest
- Jinja2 templates

## Core Features
- Booking state machine for base booking flow (`INITIATED -> PENDING_PAYMENT -> SUCCESS/FAILED/...`)
- Idempotent booking creation with conflict checks
- Webhook idempotency ledger (`payment_webhook_events`) to dedupe repeated gateway callbacks
- Transactional outbox (`outbox_events`) for reliable post-payment event dispatch
- Graceful degradation queue for event booking requests when DB is temporarily unavailable
- Event inventory management with concurrency-safe seat deduction
- Event waitlist queue with automatic promotion when seats are released
- Restaurant table slot lifecycle (`AVAILABLE -> HELD -> BOOKED`)
- Razorpay order creation and payment signature verification
- API + simple HTML pages for event/table/waitlist status

## Project Status
### What works
- Event creation and seat-type inventory management
- Event booking with Razorpay order generation
- Payment signature verification with idempotency protection
- Waitlist join and auto-promotion after seat release/cancellation
- Restaurant table slot booking and payment verification
- Outbox persistence for reliable downstream publishing
- Graceful degradation queue for temporary DB outages

### What is in progress
- End-to-end webhook simulator and replay tooling
- Background worker for automatic outbox publishing
- Improved observability (structured logs and error dashboards)

### Next planned features
- Auth + role-based access (admin/operator/user)
- Rate limiting and abuse protection on booking/payment endpoints
- CI pipeline with lint, tests, and security scan gates
- Public Postman collection with one-click environment setup

## Project Structure
```text
src/
  api/
    routes/routes.py
    schemas/schemas.py
  application/
    booking_service.py
  domain/
    entities.py
    exceptions.py
    state_machine.py
  infrastructure/
    db/
      models.py
      session.py
    repositories/
      booking_repository.py
      seat_repository.py
  templates/
  main.py
tests/
  unit/
  integration/
```

## Prerequisites
- Python 3.10+
- PostgreSQL 15+ (or Docker)
- Razorpay test keys (for payment endpoints)

## Environment Variables
Create a `.env` from `.env.example` (or set shell env vars):
```bash
cp .env.example .env
```

```env
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/district_engine
RAZORPAY_KEY_ID=rzp_test_xxxxx
RAZORPAY_KEY_SECRET=xxxxxxxx
```

If your local PostgreSQL runs on port `5433` (common on Windows installs), use:
```env
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5433/district_engine
```

## Local Setup
1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Activate virtual environment (PowerShell):
```powershell
.\venv\Scripts\Activate.ps1
```

3. Start PostgreSQL (Docker option):
```bash
docker compose up -d db
```

4. Run the API:
```bash
python -m uvicorn src.main:app --reload
```

5. Open:
- Swagger UI: `http://127.0.0.1:8000/docs`
- Landing page: `http://127.0.0.1:8000/`

## Startup Troubleshooting
- If you get `connection refused` on `localhost:5432`, PostgreSQL is not ready yet.
- The app now retries DB connection at startup (defaults: `30` retries, `1.5s` delay).
- You can tune retries with:
```env
DB_CONNECT_MAX_RETRIES=30
DB_CONNECT_RETRY_DELAY=1.5
```

## Key API Flows
### 1) Legacy seat inventory booking flow
- `POST /inventory/seed`
- `POST /bookings`
- `POST /bookings/{booking_id}/pay`

### 2) Event booking + payment flow
- `POST /events`
- `GET /events`
- `POST /events/{event_id}/book`
- `POST /events/bookings/{booking_id}/verify`
- `POST /events/bookings/{booking_id}/cancel`
- `GET /degraded/events/bookings`
- `POST /degraded/events/bookings/{request_id}/retry`

### 3) Event waitlist flow
- `POST /events/{event_id}/waitlist`
- `GET /events/waitlist/{waitlist_id}/page`
- `POST /events/waitlist/{waitlist_id}/initiate`

### 4) Restaurant table booking flow
- `POST /restaurants/tables`
- `GET /restaurants/tables`
- `POST /restaurants/tables/{slot_id}/book`
- `POST /restaurants/bookings/{booking_id}/verify`

### 5) Outbox operations
- `GET /outbox/events`
- `POST /outbox/events/{event_id}/mark-published`

## API Examples (Recruiter Quick Test)
Set base URL first:

```bash
BASE_URL="http://127.0.0.1:8000"
# For deployed app:
# BASE_URL="https://<your-railway-or-render-domain>"
```

### 1) Health check
Request:
```bash
curl -s "$BASE_URL/health"
```
Sample response:
```json
{
  "message": "District Integrity Engine is running"
}
```

### 2) Create an event
Request:
```bash
curl -s -X POST "$BASE_URL/events" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "AI Summit 2026",
    "type": "conference",
    "date_time": "2026-08-20T18:00:00",
    "location": "Bangalore",
    "seat_types": [
      {"seat_type": "VIP", "price": 2500, "total_seats": 50},
      {"seat_type": "Regular", "price": 1200, "total_seats": 200}
    ]
  }'
```
Sample response:
```json
{
  "id": "e9a9e2f7-3c49-4f86-a17e-2ce1f1cfa6d7",
  "title": "AI Summit 2026",
  "type": "conference",
  "date_time": "2026-08-20T18:00:00",
  "location": "Bangalore",
  "seat_types": [
    {"seat_type": "VIP", "price": 2500, "total_seats": 50, "available_seats": 50},
    {"seat_type": "Regular", "price": 1200, "total_seats": 200, "available_seats": 200}
  ]
}
```

### 3) Book seats for an event
Request:
```bash
curl -s -X POST "$BASE_URL/events/<EVENT_ID>/book" \
  -H "Content-Type: application/json" \
  -d '{
    "seat_type": "VIP",
    "seat_count": 2
  }'
```
Sample response:
```json
{
  "booking_id": "0f4ff95f-77cb-4f8f-b17d-c7d42ed28040",
  "status": "PENDING",
  "order_id": "order_Q1x2y3z4abc",
  "amount": 500000,
  "currency": "INR",
  "key_id": "rzp_test_xxxxx"
}
```

### 4) Verify event booking payment
Request:
```bash
curl -s -X POST "$BASE_URL/events/bookings/<BOOKING_ID>/verify" \
  -H "Content-Type: application/json" \
  -d '{
    "razorpay_order_id": "order_Q1x2y3z4abc",
    "razorpay_payment_id": "pay_Q1x2y3z4abc",
    "razorpay_signature": "generated_signature"
  }'
```
Sample response:
```json
{
  "booking_id": "0f4ff95f-77cb-4f8f-b17d-c7d42ed28040",
  "status": "SUCCESS",
  "order_id": null,
  "amount": null,
  "currency": null,
  "key_id": null
}
```

## Reliability Design
- Webhook Idempotency:
  Payment webhook calls are tracked in `payment_webhook_events` with unique `(provider, payment_id)`.
  Repeated callbacks for the same payment id become safe no-op responses instead of double writes.
- Transactional Outbox:
  Booking state update and outbox insert happen in the same DB transaction.
  If process crashes before external dispatch, pending outbox rows remain in DB and can be replayed later.
- Graceful Degradation:
  If DB connection/timeout errors happen during event booking, request is queued in memory and retried via API.
  This prevents user-facing 500 crashes during short DB outages.

## Edge Cases Checklist
- Duplicate webhook delivery from gateway for same `payment_id`.
- Same `payment_id` accidentally reused for a different booking id.
- Webhook with valid signature but mismatched `order_id` for booking.
- Payment verified once, then replayed again (should remain idempotent).
- Payment verification fails after seat hold (inventory must be restored).
- Cancellation after success (inventory + waitlist promotion consistency).
- Outbox duplicate emits during retries (dedupe via unique `dedupe_key`).
- App crash between state change and external publish (pending outbox should remain).
- Temporary DB outage while creating event booking (request should move to degraded queue).
- Degraded queue full (`503`) during prolonged outage.
- Deferred booking retried after inventory changed (business validation can reject).
- Race on same seat type bookings (row-level lock required).
- Startup with stale schema in existing DB (run migrations or recreate DB for new constraints/tables).

## Run Tests
```bash
pytest -q
```

## Deployment (Railway)
1. Push this project to GitHub.
2. Create a new project on Railway and select `Deploy from GitHub repo`.
3. Add a PostgreSQL service in the same Railway project.
4. In app service `Variables`, set:
```env
DATABASE_URL=${{Postgres.DATABASE_URL}}
RAZORPAY_KEY_ID=rzp_test_xxxxx
RAZORPAY_KEY_SECRET=xxxxxxxx
DB_CONNECT_MAX_RETRIES=60
DB_CONNECT_RETRY_DELAY=1.5
```
5. Railway will use `railway.toml` and run:
```bash
python -m uvicorn src.main:app --host 0.0.0.0 --port $PORT
```
6. Open the generated Railway domain and verify:
- `/health`
- `/`
- `/docs`
7. Update the `Live Demo` section at the top of this README with your final deployed URL.

## Notes
- `venv/` is intentionally ignored and should not be committed.
- Use Razorpay test credentials in development.
- Tables are created at startup via SQLAlchemy metadata (`Base.metadata.create_all`).

## Resume-Friendly Summary
Built a transaction-oriented booking engine with explicit domain state transitions, idempotent booking APIs, inventory locking patterns, waitlist promotion logic, and Razorpay payment verification on FastAPI + PostgreSQL.
