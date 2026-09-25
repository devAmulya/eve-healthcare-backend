def test_signup_success(client):
    resp = client.post("/auth/signup", json={"email": "new@example.com", "password": "password123"})
    assert resp.status_code == 201
    assert resp.json()["email"] == "new@example.com"
    assert "hashed_password" not in resp.json()


def test_signup_duplicate_email_rejected(client):
    client.post("/auth/signup", json={"email": "dupe@example.com", "password": "password123"})
    resp = client.post("/auth/signup", json={"email": "dupe@example.com", "password": "password123"})
    assert resp.status_code == 409


def test_signup_short_password_rejected(client):
    resp = client.post("/auth/signup", json={"email": "short@example.com", "password": "abc"})
    assert resp.status_code == 422


def test_login_success(client):
    client.post("/auth/signup", json={"email": "ok@example.com", "password": "password123"})
    resp = client.post("/auth/login", json={"email": "ok@example.com", "password": "password123"})
    assert resp.status_code == 200
    assert resp.json()["token_type"] == "bearer"
    assert len(resp.json()["access_token"]) > 20


def test_login_wrong_password(client):
    client.post("/auth/signup", json={"email": "ok2@example.com", "password": "password123"})
    resp = client.post("/auth/login", json={"email": "ok2@example.com", "password": "wrongpass"})
    assert resp.status_code == 401


def test_login_nonexistent_user(client):
    resp = client.post("/auth/login", json={"email": "ghost@example.com", "password": "password123"})
    assert resp.status_code == 401


def test_protected_route_requires_token(client):
    resp = client.get("/bookings/")
    assert resp.status_code in (401, 403)  # HTTPBearer returns 403 with no header at all


def test_protected_route_rejects_garbage_token(client):
    resp = client.get("/bookings/", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401
