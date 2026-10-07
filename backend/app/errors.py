"""Domain errors rendered as {"detail": "...", "code": "..."} by the handlers in main.py."""
from __future__ import annotations


class AppError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, detail: str, code: str | None = None, status_code: int | None = None):
        super().__init__(detail)
        self.detail = detail
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code


class BadRequest(AppError):
    status_code, code = 400, "bad_request"


class Unauthorized(AppError):
    status_code, code = 401, "not_authenticated"


class Forbidden(AppError):
    status_code, code = 403, "forbidden"


class NotFound(AppError):
    status_code, code = 404, "not_found"


class Conflict(AppError):
    status_code, code = 409, "conflict"


class PayloadTooLarge(AppError):
    status_code, code = 413, "file_too_large"


class UnsupportedMedia(AppError):
    status_code, code = 415, "unsupported_media_type"


class Unprocessable(AppError):
    status_code, code = 422, "validation_error"


class RangeNotSatisfiable(AppError):
    status_code, code = 416, "range_not_satisfiable"


class TooManyRequests(AppError):
    status_code, code = 429, "too_many_attempts"
