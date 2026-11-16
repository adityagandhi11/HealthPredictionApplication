from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy import inspect as inspect_database
from sqlalchemy.orm import Session, sessionmaker

from app.config import DATABASE_URL
from app.database.models import Base

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    """Create tables and add backward-compatible SQLite schema protections."""
    Base.metadata.create_all(bind=engine)
    if engine.dialect.name != "sqlite":
        return

    inspector = inspect_database(engine)
    if "patients" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("patients")}
    with engine.begin() as connection:
        if "ai_status" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE patients ADD COLUMN ai_status VARCHAR(20) "
                "NOT NULL DEFAULT 'pending'"
            )

        indexes = connection.exec_driver_sql(
            "SELECT name, sql FROM sqlite_master "
            "WHERE type = 'index' AND tbl_name = 'patients' AND sql IS NOT NULL"
        ).mappings().all()
        for index in indexes:
            normalized_sql = index["sql"].lower().replace('"', "").replace(" ", "")
            if (
                "createuniqueindex" in normalized_sql
                and normalized_sql.endswith("(email)")
            ):
                index_name = index["name"].replace('"', '""')
                connection.exec_driver_sql(f'DROP INDEX "{index_name}"')
                connection.exec_driver_sql(
                    "CREATE INDEX IF NOT EXISTS ix_patients_email "
                    "ON patients (email)"
                )

        legacy_index = connection.exec_driver_sql(
            "SELECT 1 FROM sqlite_master WHERE type = 'index' "
            "AND name = 'uq_patients_name_email_normalized'"
        ).first()
        if legacy_index is not None:
            connection.exec_driver_sql(
                "DROP INDEX uq_patients_name_email_normalized"
            )

        connection.exec_driver_sql(
            """
            CREATE TRIGGER IF NOT EXISTS trg_patients_prevent_duplicate_insert
            BEFORE INSERT ON patients
            WHEN EXISTS (
                SELECT 1 FROM patients
                WHERE lower(trim(full_name)) = lower(trim(NEW.full_name))
                  AND lower(trim(email)) = lower(trim(NEW.email))
            )
            BEGIN
                SELECT RAISE(ABORT, 'duplicate_patient');
            END
            """
        )
        connection.exec_driver_sql(
            """
            CREATE TRIGGER IF NOT EXISTS trg_patients_prevent_duplicate_update
            BEFORE UPDATE OF full_name, email ON patients
            WHEN (
                lower(trim(NEW.full_name)) != lower(trim(OLD.full_name))
                OR lower(trim(NEW.email)) != lower(trim(OLD.email))
            )
            AND EXISTS (
                SELECT 1 FROM patients
                WHERE id != OLD.id
                  AND lower(trim(full_name)) = lower(trim(NEW.full_name))
                  AND lower(trim(email)) = lower(trim(NEW.email))
            )
            BEGIN
                SELECT RAISE(ABORT, 'duplicate_patient');
            END
            """
        )


def get_db() -> Generator[Session, None, None]:
    """Provide one database session per request and always close it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
