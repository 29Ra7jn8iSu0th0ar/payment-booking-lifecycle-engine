def test_booking_flow(client):

    seed_payload = {
        "event_id": "event1",
        "total_seats": 10,
    }
    seed_response = client.post("/inventory/seed", json=seed_payload)
    assert seed_response.status_code == 200

    payload = {
        "user_id": "user1",
        "event_id": "event1",
        "seat_count": 1,
        "idempotency_key": "abc123",
    }

    response = client.post("/bookings", json=payload)

    assert response.status_code == 200
    booking_id = response.json()["booking_id"]
    assert response.json()["status"] == "PENDING_PAYMENT"

    pay_response = client.post(
        f"/bookings/{booking_id}/pay",
        json={"result": "success"},
    )
    assert pay_response.status_code == 200
    assert pay_response.json()["status"] == "SUCCESS"