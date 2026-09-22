"""Structured exception hierarchy for the reconciliation engine.

Purpose
-------
Every controlled failure raised anywhere in ``iraq_recon`` should be a
subclass of :class:`ReconError`. This lets the thin Dataiku WebApp backend
catch a single base type and convert it into a compact, user-friendly JSON
error response (see ``@app.errorhandler(ReconError)`` in the backend),
without the engine ever knowing about Flask or HTTP.

Public contents
----------------
``ReconError`` (base, carries ``code``, ``http_status``, ``details``,
``to_dict()``) and subclasses: ``ConfigurationError``, ``ValidationError``,
``IngestionError``, ``UnsupportedFileError``, ``MappingError``,
``CalculationError``, ``ScheduleError``, ``ControlError``, ``ExportError``,
``NotFoundError``, ``SnapshotError``.

Dependencies: standard library only.
"""

from __future__ import annotations

from typing import Any


class ReconError(Exception):
    """Base class for every controlled exception raised by iraq_recon.

    Attributes:
        message: Human-readable description.
        code: Stable machine-readable error code (e.g. ``"MAPPING_CONFLICT"``).
        http_status: Suggested HTTP status code for API adapters to use.
        details: Arbitrary JSON-compatible context for diagnostics.
    """

    code: str = "RECON_ERROR"
    http_status: int = 400

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        """Return a compact, JSON-compatible representation of the error."""
        return {
            "error_code": self.code,
            "message": self.message,
            "details": self.details,
        }


class ConfigurationError(ReconError):
    """Raised when a configuration object is missing or malformed."""

    code = "CONFIGURATION_ERROR"
    http_status = 400


class ValidationError(ReconError):
    """Raised when input payloads or data fail structural validation."""

    code = "VALIDATION_ERROR"
    http_status = 422


class IngestionError(ReconError):
    """Raised when a source workbook cannot be read or parsed."""

    code = "INGESTION_ERROR"
    http_status = 422


class UnsupportedFileError(IngestionError):
    """Raised for file types, encodings, or protections the reader cannot handle."""

    code = "UNSUPPORTED_FILE"
    http_status = 415


class MappingError(ReconError):
    """Raised for unresolvable or conflicting account mapping conditions."""

    code = "MAPPING_ERROR"
    http_status = 422


class CalculationError(ReconError):
    """Raised when an accounting calculator cannot produce a result."""

    code = "CALCULATION_ERROR"
    http_status = 422


class ScheduleError(ReconError):
    """Raised when a supporting schedule cannot be built or validated."""

    code = "SCHEDULE_ERROR"
    http_status = 422


class ControlError(ReconError):
    """Raised when a control cannot be evaluated (not for control failures)."""

    code = "CONTROL_ERROR"
    http_status = 422


class ExportError(ReconError):
    """Raised when an export (Excel/JSON) cannot be generated."""

    code = "EXPORT_ERROR"
    http_status = 500


class NotFoundError(ReconError):
    """Raised when a referenced run, line, or resource cannot be located."""

    code = "NOT_FOUND"
    http_status = 404


class SnapshotError(ReconError):
    """Raised when trial-balance snapshot comparison/selection fails."""

    code = "SNAPSHOT_ERROR"
    http_status = 422
