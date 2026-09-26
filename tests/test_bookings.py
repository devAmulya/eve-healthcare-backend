from datetime import datetime, timedelta, timezone


def _future_iso(days=1):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def test_create_booking_success(client, auth_headers, seeded_test):
    headers = auth_headers()
    resp = client.post(
        "/bookings/",
        headers=headers,
        json={"test_id": seeded_test.id, "appointment_time": _future_iso()},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "PENDING"
    assert body["amount"] == seeded_test.price  # snapshotted from test price


def test_create_booking_invalid_test_id(client, auth_headers):
    headers = auth_headers()
    resp = client.post(
        "/bookings/",
        headers=headers,
        json={"test_id": "does-not-exist", "appointment_time": _future_iso()},
    )
    assert resp.status_code == 404


def test_create_booking_past_appointment_rejected(client, auth_headers, seeded_test):
    headers = auth_headers()
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    resp = client.post(
        "/bookings/",
        headers=headers,
        json={"test_id": seeded_test.id, "appointment_time": past},
    )
    assert resp.status_code == 400


def test_create_booking_requires_auth(client, seeded_test):
    resp = client.post(
        "/bookings/",
        json={"test_id": seeded_test.id, "appointment_time": _future_iso()},
    )
    assert resp.status_code in (401, 403)


def test_user_cannot_view_another_users_booking(client, auth_headers, seeded_test):
    owner_headers = auth_headers(email="owner@example.com")
    create_resp = client.post(
        "/bookings/",
        headers=owner_headers,
        json={"test_id": seeded_test.id, "appointment_time": _future_iso()},
    )
    booking_id = create_resp.json()["id"]

    intruder_headers = auth_headers(email="intruder@example.com")
    resp = client.get(f"/bookings/{booking_id}", headers=intruder_headers)
    assert resp.status_code == 403


def test_get_nonexistent_booking_returns_404(client, auth_headers):
    headers = auth_headers()
    resp = client.get("/bookings/does-not-exist", headers=headers)
    assert resp.status_code == 404


def test_cancel_pending_booking_success(client, auth_headers, seeded_test):
    headers = auth_headers()
    create_resp = client.post(
        "/bookings/",
        headers=headers,
        json={"test_id": seeded_test.id, "appointment_time": _future_iso()},
    )
    booking_id = create_resp.json()["id"]

    resp = client.delete(f"/bookings/{booking_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "CANCELLED"


def test_cannot_cancel_already_cancelled_booking(client, auth_headers, seeded_test):
    headers = auth_headers()
    create_resp = client.post(
        "/bookings/",
        headers=headers,
        json={"test_id": seeded_test.id, "appointment_time": _future_iso()},
    )
    booking_id = create_resp.json()["id"]
    client.delete(f"/bookings/{booking_id}", headers=headers)

    resp = client.delete(f"/bookings/{booking_id}", headers=headers)
    assert resp.status_code == 409


def test_list_bookings_only_returns_own(client, auth_headers, seeded_test):
    headers_a = auth_headers(email="a_user@example.com")
    headers_b = auth_headers(email="b_user@example.com")

    client.post("/bookings/", headers=headers_a, json={"test_id": seeded_test.id, "appointment_time": _future_iso()})
    client.post("/bookings/", headers=headers_b, json={"test_id": seeded_test.id, "appointment_time": _future_iso()})

    resp = client.get("/bookings/", headers=headers_a)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
