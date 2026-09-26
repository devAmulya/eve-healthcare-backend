import uuid


def test_root_path_redirects_to_docs(client):
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code in (302, 307)
    assert resp.headers["location"] == "/docs"


def test_response_has_request_id_header(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert "X-Request-ID" in resp.headers
    # Should be a real UUID, not a placeholder
    uuid.UUID(resp.headers["X-Request-ID"])


def test_each_request_gets_a_distinct_request_id(client):
    resp1 = client.get("/health")
    resp2 = client.get("/health")
    assert resp1.headers["X-Request-ID"] != resp2.headers["X-Request-ID"]
