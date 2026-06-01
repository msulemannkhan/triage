"""Render every error as one consistent envelope: ``{"error": {"code", "message"}}``."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from triage.core.error_codes import ErrorCode
from triage.core.errors import AppError


def _envelope(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code, content=_envelope(exc.code, exc.message)
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(_request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=_envelope(ErrorCode.internal_error, "An unexpected error occurred"),
        )
