from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.connection import get_db
from app.database.models import Base
from app.main import app


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db() -> Generator[Session, None, None]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def patient_payload(email: str = "alex@example.com") -> dict[str, object]:
    return {
        "full_name": "Alex Patient",
        "date_of_birth": "1990-04-12",
        "email": email,
        "glucose": 95.5,
    }


def test_health_check(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_patient_crud(client: TestClient) -> None:
    created = client.post("/api/patients", json=patient_payload())
    assert created.status_code == 201
    patient_id = created.json()["id"]
    assert created.json()["full_name"] == "Alex Patient"

    listed = client.get("/api/patients")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    fetched = client.get(f"/api/patients/{patient_id}")
    assert fetched.status_code == 200
    assert fetched.json()["email"] == "alex@example.com"

    updated = client.put(
        f"/api/patients/{patient_id}",
        json={"remarks": "Follow-up required"},
    )
    assert updated.status_code == 200
    assert updated.json()["remarks"] == "Follow-up required"

    deleted = client.delete(f"/api/patients/{patient_id}")
    assert deleted.status_code == 204
    assert client.get(f"/api/patients/{patient_id}").status_code == 404


def test_patient_validation_and_duplicate_email(client: TestClient) -> None:
    invalid = client.post("/api/patients", json=patient_payload("not-an-email"))
    assert invalid.status_code == 422

    assert client.post("/api/patients", json=patient_payload()).status_code == 201
    duplicate = client.post("/api/patients", json=patient_payload())
    assert duplicate.status_code == 409
