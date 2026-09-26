def test_signup_allows_up_to_limit(client):
    for i in range(5):
        resp = client.post("/auth/signup", json={"email": f"user{i}@example.com", "password": "password123"})
        assert resp.status_code == 201, f"request {i} should have succeeded"


def test_signup_blocks_after_limit_exceeded(client):
    for i in range(5):
        client.post("/auth/signup", json={"email": f"limit{i}@example.com", "password": "password123"})

    resp = client.post("/auth/signup", json={"email": "onemore@example.com", "password": "password123"})
    assert resp.status_code == 429


def test_login_blocks_after_limit_exceeded(client):
    client.post("/auth/signup", json={"email": "bruteforce@example.com", "password": "password123"})

    for _ in range(10):
        client.post("/auth/login", json={"email": "bruteforce@example.com", "password": "wrongpassword"})

    # The 11th attempt should be rate-limited regardless of whether the
    # credentials are even correct this time. That's the point.
    resp = client.post("/auth/login", json={"email": "bruteforce@example.com", "password": "password123"})
    assert resp.status_code == 429
