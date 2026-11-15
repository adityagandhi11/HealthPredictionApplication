from datetime import date, datetime
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.utils.validators import validate_full_name


class PatientCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=150)
    date_of_birth: date
    email: EmailStr
    glucose: Decimal | None = Field(default=None, ge=0, max_digits=8, decimal_places=2)
    haemoglobin: Decimal | None = Field(default=None, ge=0, max_digits=8, decimal_places=2)
    cholesterol: Decimal | None = Field(default=None, ge=0, max_digits=8, decimal_places=2)

    @field_validator("full_name")
    @classmethod
    def full_name_must_not_be_blank(cls, value: str) -> str:
        return validate_full_name(value)


class PatientUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=150)
    date_of_birth: date | None = None
    email: EmailStr | None = None
    glucose: Decimal | None = Field(default=None, ge=0, max_digits=8, decimal_places=2)
    haemoglobin: Decimal | None = Field(default=None, ge=0, max_digits=8, decimal_places=2)
    cholesterol: Decimal | None = Field(default=None, ge=0, max_digits=8, decimal_places=2)
    remarks: str | None = None

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
    created_at: datetime
    updated_at: datetime
