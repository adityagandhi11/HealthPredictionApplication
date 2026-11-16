from collections.abc import Generator
from datetime import date, timedelta
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.connection import get_db
from app.database.models import Base
from app.main import app
from app.services.ai_service import AIConfigurationError, AIServiceError


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    previous_overrides = app.dependency_overrides.copy()

    def override_get_db() -> Generator[Session, None, None]:
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    def no_ai_configured(_: object) -> str:
        raise AIConfigurationError("AI not configured for this test.")

    monkeypatch.setattr("app.main.init_db", lambda: None)
    monkeypatch.setattr(
        "app.services.patient_service.generate_health_remarks",
        no_ai_configured,
    )
    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def patient_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "full_name": "Alex Patient",
        "date_of_birth": "12/04/1990",
        "email": "alex@example.com",
        "glucose": 95.5,
        "haemoglobin": 14.2,
        "cholesterol": 180,
    }
    payload.update(overrides)
    return payload


def test_health_and_complete_patient_crud(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"status": "ok"}

    created = client.post("/api/patients", json=patient_payload())
    assert created.status_code == 201
    patient_id = created.json()["id"]
    assert created.json()["date_of_birth"] == "1990-04-12"
    assert created.json()["ai_status"] == "pending"

    listed = client.get("/api/patients")
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert client.get(f"/api/patients/{patient_id}").json()["email"] == "alex@example.com"

    updated = client.put(
        f"/api/patients/{patient_id}",
        json={"email": "gokul@infocare.com"},
    )
    assert updated.status_code == 200
    assert updated.json()["email"] == "gokul@infocare.com"
    assert updated.json()["ai_status"] == "pending"

    assert client.delete(f"/api/patients/{patient_id}").status_code == 204
    assert client.get("/api/patients").json() == []
    assert client.get(f"/api/patients/{patient_id}").status_code == 404


def test_validates_email_dates_and_reports_multiple_errors(client: TestClient) -> None:
    invalid_email = client.post(
        "/api/patients",
        json=patient_payload(email="hunter@gmail"),
    )
    assert invalid_email.status_code == 422
    assert "email" in invalid_email.json()["detail"][0]["field"]

    impossible_date = client.post(
        "/api/patients",
        json=patient_payload(date_of_birth="31.11.2001"),
    )
    assert impossible_date.status_code == 422
    assert "date_of_birth" in impossible_date.json()["detail"][0]["field"]

    future_and_email = client.post(
        "/api/patients",
        json=patient_payload(
            date_of_birth=(date.today() + timedelta(days=1)).strftime("%d.%m.%Y"),
            email="not-an-email",
        ),
    )
    assert future_and_email.status_code == 422
    errors = future_and_email.json()["detail"]
    assert {error["field"] for error in errors} >= {"date_of_birth", "email"}
    assert any("future" in error["message"].lower() for error in errors)


@pytest.mark.parametrize("value", ["not-a-number", -1, "NaN", "Infinity"])
def test_rejects_invalid_lab_values(client: TestClient, value: object) -> None:
    response = client.post("/api/patients", json=patient_payload(glucose=value))

    assert response.status_code == 422
    assert any(error["field"] == "glucose" for error in response.json()["detail"])


def test_duplicate_name_and_email_pair_is_rejected(client: TestClient) -> None:
    first = client.post("/api/patients", json=patient_payload())
    duplicate = client.post(
        "/api/patients",
        json=patient_payload(full_name="  alex patient ", email=" ALEX@example.com "),
    )

    assert first.status_code == 201
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "duplicate_patient"
    assert "already exists" in duplicate.json()["detail"]["message"]
    assert len(client.get("/api/patients").json()) == 1


def test_duplicate_name_email_pair_is_rejected_on_update(client: TestClient) -> None:
    first = client.post("/api/patients", json=patient_payload())
    second = client.post(
        "/api/patients",
        json=patient_payload(full_name="Another Patient", email="another@example.com"),
    )

    conflict = client.put(
        f"/api/patients/{second.json()['id']}",
        json={"full_name": first.json()["full_name"], "email": first.json()["email"]},
    )

    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "duplicate_patient"
    assert client.get(f"/api/patients/{second.json()['id']}").json()["full_name"] == "Another Patient"


def test_missing_patient_responses(client: TestClient) -> None:
    assert client.get("/api/patients/999").status_code == 404
    assert client.put("/api/patients/999", json={"email": "new@example.com"}).status_code == 404
    assert client.delete("/api/patients/999").status_code == 404
    assert client.post("/api/patients/999/remarks").status_code == 404


def test_ai_success_is_saved_and_ai_failure_does_not_block_crud(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.patient_service.generate_health_remarks",
        lambda _: "Informational summary; discuss results with a clinician.",
    )
    generated = client.post("/api/patients", json=patient_payload())
    assert generated.status_code == 201
    assert generated.json()["ai_status"] == "generated"
    assert "clinician" in generated.json()["remarks"]

    def unavailable(_: object) -> str:
        raise AIServiceError("The AI service timed out.")

    monkeypatch.setattr(
        "app.services.patient_service.generate_health_remarks",
        unavailable,
    )
    failed = client.post(
        "/api/patients",
        json=patient_payload(
            full_name="Another Patient",
            email="another@example.com",
        ),
    )
    assert failed.status_code == 201
    assert failed.json()["ai_status"] == "failed"
    assert failed.json()["remarks"] is None

    retry = client.post(f"/api/patients/{failed.json()['id']}/remarks")
    assert retry.status_code == 503
    assert retry.json()["detail"]["code"] == "ai_service_error"


def test_assessment_dataset_and_crud_operations(client: TestClient) -> None:
    assessment_cases = [
        ("Robyn Pears", "28.01.1960", "robyn@gmail.com", 232, 13.5, 180),
        ("John Hunter", "10.12.1990", "hunter@gmail", 94, 15, 200),
        ("Darryl Tim", "12.11.1993", "timd@smh.com.au", 240, 18.6, 326),
        ("Peter Larry", "31.11.2001", "Larry@hotmail.com", 88, 11.5, 165),
        ("Sam Kerr", "09.12.2006", "sam@news.com.au", 198, 8.9, 192),
        ("Robyn Pears", "28.01.1960", "robyn@gmail.com", 232, 13.5, 180),
        ("Madison XI", "12.09.1998", "madison@hotmail.com", 85, 7.6, 163),
        ("Kris Wu", "19.10.2030", "Kris.wu.gmail.com", 79, 16.5, 197),
        ("Tenille Singh", "30.11.1991", "Tenille@yahoo.com", 101, 15, 310),
        ("Prem Kumar", "28.04.1990", "prem@telstra.com", 155, 12.5, 265),
    ]
    results = []
    for name, dob, email, glucose, haemoglobin, cholesterol in assessment_cases:
        response = client.post(
            "/api/patients",
            json=patient_payload(
                full_name=name,
                date_of_birth=dob,
                email=email,
                glucose=glucose,
                haemoglobin=haemoglobin,
                cholesterol=cholesterol,
            ),
        )
        results.append(response)

    assert [index + 1 for index, result in enumerate(results) if result.status_code == 201] == [
        1, 3, 5, 7, 9, 10
    ]
    assert results[5].status_code == 409
    assert len(client.get("/api/patients").json()) == 6

    first_id = results[0].json()["id"]
    updated = client.put(
        f"/api/patients/{first_id}",
        json={"email": "gokul@infocare.com"},
    )
    assert updated.status_code == 200
    assert client.get(f"/api/patients/{first_id}").json()["email"] == "gokul@infocare.com"

    delete_id = results[2].json()["id"]
    assert client.delete(f"/api/patients/{delete_id}").status_code == 204
    patients = client.get("/api/patients").json()
    assert len(patients) == 5
    assert delete_id not in {patient["id"] for patient in patients}


def test_groq_response_and_provider_error_handling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.database.models import Patient
    from app.services import ai_service

    patient = Patient(
        full_name="Private Patient",
        date_of_birth=date(1990, 4, 12),
        email="private@example.com",
        glucose=95,
        haemoglobin=14,
        cholesterol=180,
    )
    monkeypatch.setattr(ai_service, "GROQ_API_KEY", "test-key")
    monkeypatch.setattr(ai_service, "GROQ_MODEL", "test-model")
    captured: dict[str, Any] = {}

    def successful_request(url: str, **kwargs: Any) -> httpx.Response:
        captured.update(kwargs)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Cautious note."}}]},
        )

    monkeypatch.setattr(ai_service.httpx, "post", successful_request)
    assert ai_service.generate_health_remarks(patient) == "Cautious note."
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert "Private Patient" not in captured["json"]["messages"][1]["content"]
    assert "private@example.com" not in captured["json"]["messages"][1]["content"]

    def unauthorized(_: str, **__: Any) -> httpx.Response:
        return httpx.Response(401)

    monkeypatch.setattr(ai_service.httpx, "post", unauthorized)
    with pytest.raises(AIServiceError, match="rejected its credentials"):
        ai_service.generate_health_remarks(patient)

    def rate_limited(_: str, **__: Any) -> httpx.Response:
        return httpx.Response(429)

    monkeypatch.setattr(ai_service.httpx, "post", rate_limited)
    with pytest.raises(AIServiceError, match="rate limit"):
        ai_service.generate_health_remarks(patient)

    def invalid_response(_: str, **__: Any) -> httpx.Response:
        return httpx.Response(200, content=b"not-json")

    monkeypatch.setattr(ai_service.httpx, "post", invalid_response)
    with pytest.raises(AIServiceError, match="invalid response"):
        ai_service.generate_health_remarks(patient)
