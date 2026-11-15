import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.connection import get_db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/api/health")
def health_check(db: Session = Depends(get_db)) -> dict[str, str]:
    """Report healthy only when the application can reach its database."""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as error:
        logger.exception("Health check could not reach the database")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable.",
        ) from error
    return {"status": "ok"}
