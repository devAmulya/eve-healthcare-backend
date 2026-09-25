from datetime import datetime, timedelta, timezone


def _create_booking(client, headers, test_id):
    appt = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    resp = client.post("/bookings/", headers=headers, json={"test_id": test_id, "appointment_time": appt})
    return resp.json()["id"]


def test_payment_success_confirms_booking(client, auth_headers, seeded_test):
    headers = auth_headers()
    booking_id = _create_booking(client, headers, seeded_test.id)

    resp = client.post(
        "/payments/", headers=headers, json={"booking_id": booking_id, "force_result": "SUCCESS"}
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "SUCCESS"

    booking = client.get(f"/bookings/{booking_id}", headers=headers).json()
    assert booking["status"] == "CONFIRMED"


def test_payment_failure_fails_booking(client, auth_headers, seeded_test):
    headers = auth_headers()
    booking_id = _create_booking(client, headers, seeded_test.id)

    resp = client.post("/payments/", headers=headers, json={"booking_id": booking_id, "force_result": "FAILED"})
    assert resp.status_code == 201
    assert resp.json()["status"] == "FAILED"

    booking = client.get(f"/bookings/{booking_id}", headers=headers).json()
    assert booking["status"] == "FAILED"


def test_cannot_pay_for_someone_elses_booking(client, auth_headers, seeded_test):
    owner_headers = auth_headers(email="owner2@example.com")
    booking_id = _create_booking(client, owner_headers, seeded_test.id)

    intruder_headers = auth_headers(email="intruder2@example.com")
    resp = client.post(
        "/payments/", headers=intruder_headers, json={"booking_id": booking_id, "force_result": "SUCCESS"}
    )
    assert resp.status_code == 403


def test_cannot_pay_for_nonexistent_booking(client, auth_headers):
    headers = auth_headers()
    resp = client.post("/payments/", headers=headers, json={"booking_id": "ghost", "force_result": "SUCCESS"})
    assert resp.status_code == 404


def test_cannot_pay_twice_for_same_booking(client, auth_headers, seeded_test):
    headers = auth_headers()
    booking_id = _create_booking(client, headers, seeded_test.id)

    first = client.post("/payments/", headers=headers, json={"booking_id": booking_id, "force_result": "SUCCESS"})
    assert first.status_code == 201

    second = client.post("/payments/", headers=headers, json={"booking_id": booking_id, "force_result": "SUCCESS"})
    assert second.status_code == 409


def test_cannot_pay_for_cancelled_booking(client, auth_headers, seeded_test):
    headers = auth_headers()
    booking_id = _create_booking(client, headers, seeded_test.id)
    client.delete(f"/bookings/{booking_id}", headers=headers)

    resp = client.post("/payments/", headers=headers, json={"booking_id": booking_id, "force_result": "SUCCESS"})
    assert resp.status_code == 409
