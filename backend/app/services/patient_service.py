from sqlalchemy.orm import Session

from app.database.models import Patient
from app.schemas.patient import PatientCreate, PatientUpdate
from app.services.ai_service import (
    AIConfigurationError,
    AIServiceError,
    generate_health_remarks,
)


def create_patient(db: Session, patient_data: PatientCreate) -> Patient:
    patient = Patient(**patient_data.model_dump())
    db.add(patient)
    db.commit()
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
    should_regenerate = bool(
        {"date_of_birth", "glucose", "haemoglobin", "cholesterol"} & changed_fields.keys()
    )
    for field_name, value in changed_fields.items():
        setattr(patient, field_name, value)
    if should_regenerate:
        patient.remarks = None
        patient.ai_status = "pending"
    db.commit()
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
