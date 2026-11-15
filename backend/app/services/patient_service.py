from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.models import Patient
from app.schemas.patient import PatientCreate, PatientUpdate


class DuplicatePatientEmailError(Exception):
    """Raised when a patient email conflicts with an existing record."""


def create_patient(db: Session, patient_data: PatientCreate) -> Patient:
    patient = Patient(**patient_data.model_dump())
    db.add(patient)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise DuplicatePatientEmailError("A patient with this email already exists.") from error
    db.refresh(patient)
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

    for field_name, value in updates.model_dump(exclude_unset=True).items():
        setattr(patient, field_name, value)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise DuplicatePatientEmailError("A patient with this email already exists.") from error
    db.refresh(patient)
    return patient


def delete_patient(db: Session, patient_id: int) -> bool:
    patient = db.get(Patient, patient_id)
    if patient is None:
        return False
    db.delete(patient)
    db.commit()
    return True
