# Payment & Booking Lifecycle Engine

A FastAPI backend that models end-to-end booking and payment lifecycles for:
- Event seat bookings (multi-seat-type inventory + waitlist)
- Restaurant table slot bookings
- Payment order creation and signature verification via Razorpay

This project is designed to demonstrate clean domain modeling, idempotent booking behavior, state transitions, and transactional inventory handling.

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
- Event inventory management with concurrency-safe seat deduction
- Event waitlist queue with automatic promotion when seats are released
- Restaurant table slot lifecycle (`AVAILABLE -> HELD -> BOOKED`)
- Razorpay order creation and payment signature verification
- API + simple HTML pages for event/table/waitlist status

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
Create a `.env` (or set shell env vars):

```env
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/district_engine
RAZORPAY_KEY_ID=rzp_test_xxxxx
RAZORPAY_KEY_SECRET=xxxxxxxx
```

## Local Setup
1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Start PostgreSQL (Docker option):
```bash
docker compose up -d db
```

3. Run the API:
```bash
python -m uvicorn src.main:app --reload
```

4. Open:
- Swagger UI: `http://127.0.0.1:8000/docs`
- Landing page: `http://127.0.0.1:8000/`

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

### 3) Event waitlist flow
- `POST /events/{event_id}/waitlist`
- `GET /events/waitlist/{waitlist_id}/page`
- `POST /events/waitlist/{waitlist_id}/initiate`

### 4) Restaurant table booking flow
- `POST /restaurants/tables`
- `GET /restaurants/tables`
- `POST /restaurants/tables/{slot_id}/book`
- `POST /restaurants/bookings/{booking_id}/verify`

## Run Tests
```bash
pytest -q
```

## Notes
- `venv/` is intentionally ignored and should not be committed.
- Use Razorpay test credentials in development.
- Tables are created at startup via SQLAlchemy metadata (`Base.metadata.create_all`).

## Resume-Friendly Summary
Built a transaction-oriented booking engine with explicit domain state transitions, idempotent booking APIs, inventory locking patterns, waitlist promotion logic, and Razorpay payment verification on FastAPI + PostgreSQL.
