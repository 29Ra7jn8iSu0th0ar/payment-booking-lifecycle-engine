## District Integrity Engine (Mock Payment Flow)

This is a minimal mock payment flow for seat booking.

### Run

1. Start Postgres (Docker):
   `docker compose up -d db`

2. Install deps:
   `pip install -r requirements.txt`

3. Run API:
   `python -m uvicorn src.main:app --reload`

Open `http://127.0.0.1:8000/docs`

### Flow

1. Seed inventory:
   `POST /inventory/seed`

   Example body:
   ```json
   { "event_id": "1", "total_seats": 10 }
   ```

2. Create booking:
   `POST /bookings`

   Example body:
   ```json
   {
     "user_id": "Rajni",
     "event_id": "1",
     "seat_count": 1,
     "idempotency_key": "011"
   }
   ```

3. Pay:
   `POST /bookings/{booking_id}/pay`

   Example body:
   ```json
   { "result": "success" }
   ```