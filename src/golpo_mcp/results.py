"""Shared tool-result helpers.

Lives in its own module so both the shared tools (server.py) and the
version-specific generate pipelines (generate_v1.py / generate_v2.py) can use
it without importing each other (avoids circular imports).
"""

from __future__ import annotations

from .auth import MissingCredentialError
from .client import GolpoAPIError
from .safety import redact


def _current_key() -> str | None:
    """Best-effort fetch of the configured key, for redaction only."""
    try:
        from .auth import get_key
        return get_key()
    except Exception:
        return None


def error_result(exc: Exception) -> dict:
    """Convert an exception into a structured tool result instead of crashing.

    Everything returned here is scrubbed of the API key so a reflected error
    body or message can never leak the credential back to the client.
    """
    if isinstance(exc, MissingCredentialError):
        out = {"error": "missing_credential", "message": str(exc)}
    elif isinstance(exc, GolpoAPIError):
        out = {
            "error": f"http_{exc.status_code}",
            "status_code": exc.status_code,
            "body": exc.body,
            "message": str(exc),
        }
    elif isinstance(exc, TimeoutError):
        out = {"error": "poll_timeout", "message": str(exc)}
    elif isinstance(exc, PermissionError):
        out = {"error": "forbidden", "message": str(exc)}
    elif isinstance(exc, (ValueError, FileNotFoundError)):
        out = {"error": "bad_input", "message": str(exc)}
    else:
        out = {"error": "unexpected", "message": f"{type(exc).__name__}: {exc}"}
    return redact(out, _current_key())
