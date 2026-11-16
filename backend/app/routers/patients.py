from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import Patient
from app.schemas.patient import PatientCreate, PatientRead, PatientUpdate
from app.services.ai_service import AIConfigurationError, AIServiceError
from app.services.patient_service import (
    DuplicatePatientError,
    create_patient,
    delete_patient,
    get_patient,
    list_patients,
    retry_patient_remarks,
    update_patient,
)

router = APIRouter(prefix="/api/patients", tags=["patients"])


@router.post("", response_model=PatientRead, status_code=status.HTTP_201_CREATED)
def create_patient_endpoint(
    patient: PatientCreate,
    db: Session = Depends(get_db),
) -> Patient:
    try:
        return create_patient(db, patient)
    except DuplicatePatientError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "duplicate_patient", "message": str(error)},
        ) from error


@router.get("", response_model=list[PatientRead])
def list_patients_endpoint(db: Session = Depends(get_db)) -> list[Patient]:
    return list_patients(db)


@router.get("/{patient_id}", response_model=PatientRead)
def get_patient_endpoint(patient_id: int, db: Session = Depends(get_db)) -> Patient:
    patient = get_patient(db, patient_id)
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found.")
    return patient


@router.put("/{patient_id}", response_model=PatientRead)
def update_patient_endpoint(
    patient_id: int,
    updates: PatientUpdate,
    db: Session = Depends(get_db),
) -> Patient:
    try:
        patient = update_patient(db, patient_id, updates)
    except DuplicatePatientError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "duplicate_patient", "message": str(error)},
        ) from error
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found.")
    return patient


@router.post("/{patient_id}/remarks", response_model=PatientRead)
def retry_patient_remarks_endpoint(
    patient_id: int,
    db: Session = Depends(get_db),
) -> Patient:
    patient = get_patient(db, patient_id)
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found.")
    try:
        return retry_patient_remarks(db, patient)
    except AIConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "ai_not_configured", "message": str(error)},
        ) from error
    except AIServiceError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "ai_service_error", "message": str(error)},
        ) from error


@router.delete("/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_patient_endpoint(patient_id: int, db: Session = Depends(get_db)) -> Response:
    if not delete_patient(db, patient_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
