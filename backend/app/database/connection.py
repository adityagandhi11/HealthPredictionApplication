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
    """Create tables and apply small, backward-compatible SQLite changes."""
    Base.metadata.create_all(bind=engine)
    if engine.dialect.name != "sqlite":
        return

    inspector = inspect_database(engine)
    if "patients" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("patients")}
    indexes = inspector.get_indexes("patients")
    with engine.begin() as connection:
        if "ai_status" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE patients ADD COLUMN ai_status VARCHAR(20) "
                "NOT NULL DEFAULT 'pending'"
            )
        for index in indexes:
            if (
                index.get("unique")
                and index.get("column_names") == ["email"]
                and index.get("name")
            ):
                index_name = index["name"].replace('"', '""')
                connection.exec_driver_sql(f'DROP INDEX "{index_name}"')
                connection.exec_driver_sql(
                    "CREATE INDEX IF NOT EXISTS ix_patients_email "
                    "ON patients (email)"
                )


def get_db() -> Generator[Session, None, None]:
    """Provide one database session per request and always close it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
