"""Typed application errors. Each carries a stable code + HTTP status so the
error-handler middleware can render one consistent envelope."""

from .error_codes import ErrorCode


class AppError(Exception):
    """Base for errors that map to a structured API response."""

    def __init__(self, *, code: ErrorCode, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class AuthError(AppError):
    def __init__(self, message: str = "Invalid or missing API key") -> None:
        super().__init__(code=ErrorCode.unauthorized, message=message, status_code=401)


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(code=ErrorCode.not_found, message=message, status_code=404)


class PayloadTooLargeError(AppError):
    def __init__(self, message: str = "Payload exceeds the allowed size") -> None:
        super().__init__(code=ErrorCode.payload_too_large, message=message, status_code=413)
