"""Shared tool-result helpers.

Lives in its own module so both the shared tools (server.py) and the
version-specific generate pipelines (generate_v1.py / generate_v2.py) can use
it without importing each other (avoids circular imports).
"""

from __future__ import annotations

from .auth import MissingCredentialError
from .client import GolpoAPIError


def error_result(exc: Exception) -> dict:
    """Convert an exception into a structured tool result instead of crashing."""
    if isinstance(exc, MissingCredentialError):
        return {"error": "missing_credential", "message": str(exc)}
    if isinstance(exc, GolpoAPIError):
        return {
            "error": f"http_{exc.status_code}",
            "status_code": exc.status_code,
            "body": exc.body,
            "message": str(exc),
        }
    if isinstance(exc, TimeoutError):
        return {"error": "poll_timeout", "message": str(exc)}
    if isinstance(exc, (ValueError, FileNotFoundError)):
        return {"error": "bad_input", "message": str(exc)}
    return {"error": "unexpected", "message": f"{type(exc).__name__}: {exc}"}
