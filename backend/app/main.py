from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.config import CORS_ORIGINS
from app.database.connection import init_db
from app.routers import health, patients

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


app = FastAPI(
    title="Health Prediction API",
    description="Backend foundation for the Health Prediction Application.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    _: Request,
    error: RequestValidationError,
) -> JSONResponse:
    details = [
        {
            "field": ".".join(str(part) for part in item["loc"] if part != "body"),
            "message": item["msg"],
            "type": item["type"],
        }
        for item in error.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": details})


@app.exception_handler(SQLAlchemyError)
async def database_exception_handler(_: Request, error: SQLAlchemyError) -> JSONResponse:
    logging.getLogger(__name__).error(
        "Database operation failed: %s",
        type(error).__name__,
    )
    return JSONResponse(
        status_code=503,
        content={"detail": {"code": "database_unavailable", "message": "Database is unavailable."}},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health.router)
app.include_router(patients.router)
