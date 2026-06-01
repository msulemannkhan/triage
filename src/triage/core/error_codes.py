"""Stable, machine-readable error codes returned in the API error envelope."""

from enum import StrEnum


class ErrorCode(StrEnum):
    unauthorized = "unauthorized"
    not_found = "not_found"
    validation_error = "validation_error"
    payload_too_large = "payload_too_large"
    internal_error = "internal_error"
