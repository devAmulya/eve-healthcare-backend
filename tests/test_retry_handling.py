from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.models import Payment


def _create_booking(client, headers, test_id):
    appt = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    resp = client.post("/bookings/", headers=headers, json={"test_id": test_id, "appointment_time": appt})
    return resp.json()["id"]


def _flaky_commit(fail_times):
    """
    Returns a replacement for Session.commit that raises OperationalError
    the first `fail_times` calls, then delegates to the real commit.
    Tracks call count on the returned function itself for assertions.
    """
    original_commit = Session.commit
    state = {"calls": 0}

    def _commit(self, *args, **kwargs):
        state["calls"] += 1
        if state["calls"] <= fail_times:
            raise OperationalError("COMMIT", {}, Exception("simulated transient connection drop"))
        return original_commit(self, *args, **kwargs)

    _commit.state = state
    return _commit


def test_webhook_recovers_from_transient_db_error_within_retry_budget(
    client, auth_headers, seeded_test, db_session, monkeypatch
):
    """Fails twice, succeeds on the 3rd attempt - within our stop_after_attempt(3) budget."""
    headers = auth_headers()
    booking_id = _create_booking(client, headers, seeded_test.id)

    flaky = _flaky_commit(fail_times=2)
    monkeypatch.setattr(Session, "commit", flaky)

    resp = client.post(
        "/payments/webhook/",
        json={"event_id": "evt-transient-1", "booking_id": booking_id, "status": "SUCCESS"},
    )

    assert resp.status_code == 200
    assert resp.json()["status"] == "processed"
    assert resp.json()["booking_status"] == "CONFIRMED"
    assert flaky.state["calls"] == 3  # 2 failures + 1 success

    # Exactly one Payment row - the retried unit rebuilt it cleanly each time,
    # it didn't leave partial/duplicate state behind.
    payments = db_session.query(Payment).filter(Payment.booking_id == booking_id).all()
    assert len(payments) == 1


def test_webhook_returns_503_when_retries_exhausted(client, auth_headers, seeded_test, db_session, monkeypatch):
    """Fails all 3 attempts - retry budget exhausted, should surface as 503, not 500 or a silent 200."""
    headers = auth_headers()
    booking_id = _create_booking(client, headers, seeded_test.id)

    flaky = _flaky_commit(fail_times=99)  # never succeeds within the retry budget
    monkeypatch.setattr(Session, "commit", flaky)

    resp = client.post(
        "/payments/webhook/",
        json={"event_id": "evt-transient-2", "booking_id": booking_id, "status": "SUCCESS"},
    )

    assert resp.status_code == 503
    assert flaky.state["calls"] == 3  # stop_after_attempt(3), no more

    # Nothing should have been left half-committed.
    payments = db_session.query(Payment).filter(Payment.booking_id == booking_id).all()
    assert len(payments) == 0


def test_payment_initiation_recovers_from_transient_db_error(client, auth_headers, seeded_test, monkeypatch):
    headers = auth_headers()
    booking_id = _create_booking(client, headers, seeded_test.id)

    flaky = _flaky_commit(fail_times=1)
    monkeypatch.setattr(Session, "commit", flaky)

    resp = client.post(
        "/payments/", headers=headers, json={"booking_id": booking_id, "force_result": "SUCCESS"}
    )

    assert resp.status_code == 201
    assert resp.json()["status"] == "SUCCESS"
    assert flaky.state["calls"] == 2
