from datetime import date, datetime
from datetime import datetime as datetime_class
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.utils.validators import validate_full_name


def parse_patient_date(value: object) -> object:
    if not isinstance(value, str):
        return value
    cleaned_value = value.strip()
    for date_format in ("%d/%m/%Y", "%d.%m.%Y"):
        try:
            return datetime_class.strptime(cleaned_value, date_format).date()
        except ValueError:
            pass
    return cleaned_value


def validate_not_future(value: date) -> date:
    if value > date.today():
        raise ValueError("Date of birth cannot be in the future.")
    return value


class PatientCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=150)
    date_of_birth: date
    email: EmailStr
    glucose: Decimal | None = Field(default=None, ge=0, allow_inf_nan=False)
    haemoglobin: Decimal | None = Field(default=None, ge=0, allow_inf_nan=False)
    cholesterol: Decimal | None = Field(default=None, ge=0, allow_inf_nan=False)

    @field_validator("date_of_birth", mode="before")
    @classmethod
    def parse_supported_date_formats(cls, value: object) -> object:
        return parse_patient_date(value)

    @field_validator("date_of_birth")
    @classmethod
    def date_of_birth_must_not_be_future(cls, value: date) -> date:
        return validate_not_future(value)

    @field_validator("email", mode="before")
    @classmethod
    def trim_email(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("full_name")
    @classmethod
    def full_name_must_not_be_blank(cls, value: str) -> str:
        return validate_full_name(value)


class PatientUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=150)
    date_of_birth: date | None = None
    email: EmailStr | None = None
    glucose: Decimal | None = Field(default=None, ge=0, allow_inf_nan=False)
    haemoglobin: Decimal | None = Field(default=None, ge=0, allow_inf_nan=False)
    cholesterol: Decimal | None = Field(default=None, ge=0, allow_inf_nan=False)

    @field_validator("date_of_birth", mode="before")
    @classmethod
    def parse_supported_date_formats(cls, value: object) -> object:
        return parse_patient_date(value)

    @field_validator("date_of_birth")
    @classmethod
    def date_of_birth_must_not_be_future(cls, value: date | None) -> date | None:
        return validate_not_future(value) if value is not None else None

    @field_validator("email", mode="before")
    @classmethod
    def trim_email(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("full_name")
    @classmethod
    def full_name_must_not_be_blank(cls, value: str | None) -> str | None:
        return validate_full_name(value) if value is not None else None

    @model_validator(mode="after")
    def require_update_fields(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided.")
        for field_name in ("full_name", "date_of_birth", "email"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null.")
        return self


class PatientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    date_of_birth: date
    email: EmailStr
    glucose: Decimal | None
    haemoglobin: Decimal | None
    cholesterol: Decimal | None
    remarks: str | None
    ai_status: str
    created_at: datetime
    updated_at: datetime
