from datetime import datetime, timedelta, timezone

from app.database import Base
from app.models import DiagnosticCentre, DiagnosticTest


def _future_iso(days=1):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def test_bookings_pagination_defaults(client, auth_headers, seeded_test):
    headers = auth_headers()
    for _ in range(3):
        client.post("/bookings/", headers=headers, json={"test_id": seeded_test.id, "appointment_time": _future_iso()})

    resp = client.get("/bookings/", headers=headers)
    body = resp.json()
    assert body["total"] == 3
    assert body["skip"] == 0
    assert body["limit"] == 20
    assert len(body["items"]) == 3


def test_bookings_pagination_limit_and_skip(client, auth_headers, seeded_test):
    headers = auth_headers()
    for _ in range(5):
        client.post("/bookings/", headers=headers, json={"test_id": seeded_test.id, "appointment_time": _future_iso()})

    page1 = client.get("/bookings/?skip=0&limit=2", headers=headers).json()
    page2 = client.get("/bookings/?skip=2&limit=2", headers=headers).json()

    assert page1["total"] == 5
    assert len(page1["items"]) == 2
    assert len(page2["items"]) == 2
    # No overlap between pages
    ids_page1 = {b["id"] for b in page1["items"]}
    ids_page2 = {b["id"] for b in page2["items"]}
    assert ids_page1.isdisjoint(ids_page2)


def test_bookings_pagination_limit_capped_at_100(client, auth_headers):
    resp = client.get("/bookings/?limit=500", headers=auth_headers())
    assert resp.status_code == 422  # exceeds le=100


def test_bookings_pagination_negative_skip_rejected(client, auth_headers):
    resp = client.get("/bookings/?skip=-1", headers=auth_headers())
    assert resp.status_code == 422


def test_centres_pagination(client, db_session):
    for i in range(3):
        centre = DiagnosticCentre(name=f"Centre {i}", location="Delhi")
        db_session.add(centre)
    db_session.commit()

    resp = client.get("/centres/?skip=0&limit=2")
    body = resp.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
