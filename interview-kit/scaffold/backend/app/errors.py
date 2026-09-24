# Domain errors + one JSON error envelope for every failure:
#   {"error": {"code": "...", "message": "...", "request_id": "...", "details": [...]}}
# Services raise AppError subclasses and never import HTTP types; this module
# is the only place that maps errors to status codes.

import logging

import psycopg
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.observability import request_id_var

log = logging.getLogger(__name__)


class AppError(Exception):
    status_code = 500
    code = "internal_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(AppError):
    status_code, code = 404, "not_found"


class ConflictError(AppError):
    status_code, code = 409, "conflict"


class PayloadTooLargeError(AppError):
    status_code, code = 413, "payload_too_large"


class UnavailableError(AppError):
    status_code, code = 503, "unavailable"


def error_response(status: int, code: str, message: str, details: list | None = None) -> JSONResponse:
    body = {"code": code, "message": message, "request_id": request_id_var.get()}
    if details:
        body["details"] = details
    headers = {"Retry-After": "5"} if status == 503 else None
    return JSONResponse(status_code=status, content={"error": body}, headers=headers)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error(_: Request, exc: AppError):
        return error_response(exc.status_code, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        details = [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]
        return error_response(422, "validation_error", "Request validation failed", details)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException):
        return error_response(exc.status_code, "http_error", str(exc.detail))

    @app.exception_handler(psycopg.OperationalError)  # DB down / pool exhausted
    async def db_unavailable(_: Request, exc: psycopg.OperationalError):
        log.error("database unavailable", extra={"error": str(exc)})
        return error_response(503, "database_unavailable", "Database temporarily unavailable")

    @app.exception_handler(Exception)  # last resort: log it, never leak internals
    async def unhandled(_: Request, exc: Exception):
        log.exception("unhandled error", exc_info=exc)
        return error_response(500, "internal_error", "Internal server error")
