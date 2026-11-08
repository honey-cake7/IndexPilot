import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from threading import Lock
from typing import Literal

import psycopg
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException

from indexpilot.api.body_limit import BodyLimitMiddleware
from indexpilot.api.candidates import router as candidate_router
from indexpilot.api.dependencies import get_engine
from indexpilot.api.evaluations import router as evaluation_router
from indexpilot.api.plans import router as plan_router
from indexpilot.api.schema import router as schema_router
from indexpilot.api.workloads import router as workload_router
from indexpilot.config import Settings
from indexpilot.db.capabilities import Capabilities, inspect_capabilities
from indexpilot.db.connections import require_demo_identity, target_connection
from indexpilot.errors import DomainError
from indexpilot.local import LocalConnectionError

logger = logging.getLogger("indexpilot")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)


class Status(BaseModel):
    status: Literal["ok"] = "ok"


class ConnectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target: Literal["demo"] = "demo"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Liveness must work even before credentials/database setup is available.
        app.state.metadata_engine = None
        yield
        if app.state.metadata_engine is not None:
            app.state.metadata_engine.dispose()

    app = FastAPI(title="IndexPilot", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.metadata_lock = Lock()
    app.add_middleware(BodyLimitMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    def failure(request: Request, code: str, message: str, status: int):
        return JSONResponse(
            status_code=status,
            content={
                "error": {
                    "code": code,
                    "message": message,
                    "request_id": request.state.request_id,
                }
            },
        )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request.state.request_id = uuid.uuid4().hex
        started = time.monotonic()
        try:
            response = await call_next(request)
        except Exception as error:
            # Never log raw database exceptions, request bodies, DSNs or SQL parameters.
            logger.error(
                json.dumps(
                    {
                        "event": "request_failed",
                        "type": type(error).__name__,
                        "request_id": request.state.request_id,
                    }
                )
            )
            response = failure(request, "internal_error", "Unexpected application failure.", 500)
        response.headers["X-Request-ID"] = request.state.request_id
        logger.info(
            json.dumps(
                {
                    "event": "request",
                    "method": request.method,
                    "status": response.status_code,
                    "duration_ms": round((time.monotonic() - started) * 1000, 2),
                    "request_id": request.state.request_id,
                }
            )
        )
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid(request: Request, error: RequestValidationError):
        return failure(
            request, "invalid_request", "Input does not match the supported schema.", 422
        )

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException):
        return failure(
            request, "http_error", "Resource or method not available.", error.status_code
        )

    @app.exception_handler(LocalConnectionError)
    async def connection_error(request: Request, error: LocalConnectionError):
        return failure(request, error.code, str(error), 503)

    @app.exception_handler(DomainError)
    async def domain_error(request: Request, error: DomainError):
        return failure(request, error.code, error.message, error.status)

    @app.exception_handler(psycopg.Error)
    async def database_error(request: Request, error: psycopg.Error):
        if error.sqlstate == "42501":
            return failure(
                request, "insufficient_privilege", "Required database privilege missing.", 403
            )
        if error.sqlstate == "57014":
            return failure(
                request, "statement_timeout", "Database statement exceeded its limit.", 504
            )
        return failure(request, "database_error", "Database operation failed.", 503)

    @app.exception_handler(SQLAlchemyError)
    async def metadata_error(request: Request, error: SQLAlchemyError):
        return failure(request, "metadata_unavailable", "Metadata database is not ready.", 503)

    @app.get("/health/live", response_model=Status)
    def live():
        return Status()

    @app.get("/health/ready", response_model=Status)
    def ready(request: Request):
        with get_engine(request).connect() as connection:
            revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
            if revision != "0006":
                raise LocalConnectionError("metadata_migration_required")
        with target_connection(settings) as connection:
            require_demo_identity(connection)
            connection.execute("SELECT 1")
        return Status()

    @app.post("/api/v1/connections/validate", response_model=Capabilities)
    def validate_connection(body: ConnectionRequest):
        with target_connection(settings) as connection:
            require_demo_identity(connection)
            return inspect_capabilities(connection)

    @app.get("/api/v1/connections/demo", response_model=Capabilities)
    def demo_capabilities():
        return validate_connection(ConnectionRequest())

    app.include_router(workload_router)
    app.include_router(schema_router)
    app.include_router(plan_router)
    app.include_router(candidate_router)
    app.include_router(evaluation_router)
    return app


app = create_app()
