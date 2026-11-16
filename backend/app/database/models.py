from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, Numeric, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""


class Patient(Base):
    __tablename__ = "patients"
    __table_args__ = (
        CheckConstraint("length(trim(full_name)) > 0", name="ck_patients_full_name"),
        CheckConstraint("glucose IS NULL OR glucose >= 0", name="ck_patients_glucose"),
        CheckConstraint(
            "haemoglobin IS NULL OR haemoglobin >= 0",
            name="ck_patients_haemoglobin",
        ),
        CheckConstraint(
            "cholesterol IS NULL OR cholesterol >= 0",
            name="ck_patients_cholesterol",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    glucose: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    haemoglobin: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    cholesterol: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
