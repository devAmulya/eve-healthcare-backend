from datetime import datetime, timedelta, timezone

from app.models import Payment


def _create_booking(client, headers, test_id):
    appt = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    resp = client.post("/bookings/", headers=headers, json={"test_id": test_id, "appointment_time": appt})
    return resp.json()["id"]


def test_webhook_confirms_pending_booking(client, auth_headers, seeded_test):
    headers = auth_headers()
    booking_id = _create_booking(client, headers, seeded_test.id)

    resp = client.post(
        "/payments/webhook/",
        json={"event_id": "evt-001", "booking_id": booking_id, "status": "SUCCESS"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "processed"
    assert resp.json()["booking_status"] == "CONFIRMED"


def test_duplicate_webhook_event_is_idempotent(client, auth_headers, seeded_test, db_session):
    """
    This is the core requirement from the assignment: the same event_id
    delivered twice must not create a second Payment row or re-run the
    booking status transition.
    """
    headers = auth_headers()
    booking_id = _create_booking(client, headers, seeded_test.id)

    payload = {"event_id": "evt-duplicate-001", "booking_id": booking_id, "status": "SUCCESS"}

    first = client.post("/payments/webhook/", json=payload)
    assert first.status_code == 200
    assert first.json()["status"] == "processed"

    second = client.post("/payments/webhook/", json=payload)
    assert second.status_code == 200
    assert second.json()["status"] == "already_processed"

    third = client.post("/payments/webhook/", json=payload)
    assert third.status_code == 200
    assert third.json()["status"] == "already_processed"

    payments = db_session.query(Payment).filter(Payment.booking_id == booking_id).all()
    assert len(payments) == 1

    booking = client.get(f"/bookings/{booking_id}", headers=headers).json()
    assert booking["status"] == "CONFIRMED"


def test_webhook_with_different_event_id_but_already_settled_booking_is_noop(
    client, auth_headers, seeded_test, db_session
):
    """
    A provider retry sometimes arrives with a *new* event_id for a booking
    that's already been settled by an earlier event. The unique constraint
    on Payment.booking_id (not just provider_event_id) is what catches this.
    """
    headers = auth_headers()
    booking_id = _create_booking(client, headers, seeded_test.id)

    client.post("/payments/webhook/", json={"event_id": "evt-A", "booking_id": booking_id, "status": "SUCCESS"})
    resp = client.post("/payments/webhook/", json={"event_id": "evt-B", "booking_id": booking_id, "status": "FAILED"})

    assert resp.status_code == 200
    assert resp.json()["status"] == "already_processed"
    # Status must still reflect the FIRST event, not be flipped by the second.
    assert resp.json()["booking_status"] == "CONFIRMED"

    payments = db_session.query(Payment).filter(Payment.booking_id == booking_id).all()
    assert len(payments) == 1


def test_webhook_for_nonexistent_booking_returns_404(client):
    resp = client.post(
        "/payments/webhook/",
        json={"event_id": "evt-ghost", "booking_id": "does-not-exist", "status": "SUCCESS"},
    )
    assert resp.status_code == 404


def test_late_webhook_does_not_resurrect_cancelled_booking(client, auth_headers, seeded_test, db_session):
    headers = auth_headers()
    booking_id = _create_booking(client, headers, seeded_test.id)
    client.delete(f"/bookings/{booking_id}", headers=headers)

    resp = client.post(
        "/payments/webhook/",
        json={"event_id": "evt-late", "booking_id": booking_id, "status": "SUCCESS"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored_booking_cancelled"
    assert resp.json()["booking_status"] == "CANCELLED"

    payments = db_session.query(Payment).filter(Payment.booking_id == booking_id).all()
    assert len(payments) == 0

    booking = client.get(f"/bookings/{booking_id}", headers=headers).json()
    assert booking["status"] == "CANCELLED"


def test_webhook_failed_status_marks_booking_failed(client, auth_headers, seeded_test):
    headers = auth_headers()
    booking_id = _create_booking(client, headers, seeded_test.id)

    resp = client.post(
        "/payments/webhook/",
        json={"event_id": "evt-fail-1", "booking_id": booking_id, "status": "FAILED"},
    )
    assert resp.status_code == 200
    assert resp.json()["booking_status"] == "FAILED"
