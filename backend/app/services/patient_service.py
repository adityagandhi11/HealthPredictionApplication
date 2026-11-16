from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.models import Patient
from app.schemas.patient import PatientCreate, PatientUpdate
from app.services.ai_service import (
    AIConfigurationError,
    AIServiceError,
    generate_health_remarks,
)


class DuplicatePatientError(Exception):
    """Raised when a patient with the same name and email already exists."""


def _is_duplicate_pair_error(error: IntegrityError) -> bool:
    return "duplicate_patient" in str(error.orig)


def _ensure_patient_pair_is_unique(
    db: Session,
    full_name: str,
    email: str,
    *,
    exclude_patient_id: int | None = None,
) -> None:
    statement = select(Patient.id).where(
        func.lower(func.trim(Patient.full_name)) == full_name.strip().lower(),
        func.lower(func.trim(Patient.email)) == email.strip().lower(),
    )
    if exclude_patient_id is not None:
        statement = statement.where(Patient.id != exclude_patient_id)
    if db.scalar(statement) is not None:
        raise DuplicatePatientError(
            "A patient with this name and email address already exists."
        )


def create_patient(db: Session, patient_data: PatientCreate) -> Patient:
    _ensure_patient_pair_is_unique(
        db,
        patient_data.full_name,
        str(patient_data.email),
    )
    patient = Patient(**patient_data.model_dump())
    db.add(patient)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        if _is_duplicate_pair_error(error):
            raise DuplicatePatientError(
                "A patient with this name and email address already exists."
            ) from error
        raise
    db.refresh(patient)
    generate_patient_remarks(db, patient)
    return patient


def list_patients(db: Session) -> list[Patient]:
    return list(db.query(Patient).order_by(Patient.id).all())


def get_patient(db: Session, patient_id: int) -> Patient | None:
    return db.get(Patient, patient_id)


def update_patient(
    db: Session,
    patient_id: int,
    updates: PatientUpdate,
) -> Patient | None:
    patient = db.get(Patient, patient_id)
    if patient is None:
        return None

    changed_fields = updates.model_dump(exclude_unset=True)
    new_full_name = changed_fields.get("full_name", patient.full_name)
    new_email = changed_fields.get("email", patient.email)
    _ensure_patient_pair_is_unique(
        db,
        new_full_name,
        str(new_email),
        exclude_patient_id=patient.id,
    )
    should_regenerate = bool(
        {"date_of_birth", "glucose", "haemoglobin", "cholesterol"} & changed_fields.keys()
    )
    for field_name, value in changed_fields.items():
        setattr(patient, field_name, value)
    if should_regenerate:
        patient.remarks = None
        patient.ai_status = "pending"
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        if _is_duplicate_pair_error(error):
            raise DuplicatePatientError(
                "A patient with this name and email address already exists."
            ) from error
        raise
    if should_regenerate:
        generate_patient_remarks(db, patient)
    else:
        db.refresh(patient)
    return patient


def retry_patient_remarks(db: Session, patient: Patient) -> Patient:
    patient.remarks = None
    patient.ai_status = "pending"
    db.commit()
    generate_patient_remarks(db, patient, propagate_error=True)
    return patient


def generate_patient_remarks(
    db: Session,
    patient: Patient,
    *,
    propagate_error: bool = False,
) -> None:
    try:
        patient.remarks = generate_health_remarks(patient)
        patient.ai_status = "generated"
    except AIConfigurationError:
        patient.ai_status = "pending"
        if propagate_error:
            db.commit()
            raise
    except AIServiceError:
        patient.ai_status = "failed"
        if propagate_error:
            db.commit()
            raise
    db.commit()
    db.refresh(patient)


def delete_patient(db: Session, patient_id: int) -> bool:
    patient = db.get(Patient, patient_id)
    if patient is None:
        return False
    db.delete(patient)
    db.commit()
    return True
