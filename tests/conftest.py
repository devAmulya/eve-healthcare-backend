import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models import DiagnosticCentre, DiagnosticTest

TEST_DB_URL = "sqlite:///./test.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def _fresh_db():
    """Recreate all tables before every test so tests don't leak state into each other."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


def _override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db_session():
    session = TestingSessionLocal()
    yield session
    session.close()


@pytest.fixture
def seeded_test(db_session):
    """Creates one centre with one test, returns the test's id and price."""
    centre = DiagnosticCentre(name="Test Diagnostics", location="Test City")
    db_session.add(centre)
    db_session.flush()

    test = DiagnosticTest(centre_id=centre.id, name="CBC", price=299.0)
    db_session.add(test)
    db_session.commit()
    db_session.refresh(test)

    return test


@pytest.fixture
def auth_headers(client):
    """Signs up + logs in a fresh user, returns (headers, user info) for reuse."""

    def _make(email="user@example.com", password="password123"):
        client.post("/auth/signup", json={"email": email, "password": password})
        resp = client.post("/auth/login", json={"email": email, "password": password})
        token = resp.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _make
