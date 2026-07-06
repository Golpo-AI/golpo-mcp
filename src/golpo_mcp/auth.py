"""API key resolution.

Shares the on-disk credential file with the Golpo Claude Code skill so users
only configure the key once. Resolution priority:

  1. GOLPO_API_KEY env var
  2. ~/.golpo/api_key (mode 0600)
  3. raises MissingCredentialError
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys

KEY_PATH = pathlib.Path.home() / ".golpo" / "api_key"


class MissingCredentialError(RuntimeError):
    """Raised when no Golpo API key can be found."""


def _lock_down(path: pathlib.Path) -> None:
    """Restrict a file so only the current user can read it.

    POSIX: chmod 0600. Windows: `os.chmod(0o600)` only flips the read-only bit
    (ACLs are untouched, so other local accounts can still read the key), so we
    reset the ACL with icacls — disable inheritance and grant the current user
    alone. Best-effort: failures don't block saving, but we try hard because
    this file holds a live API credential.
    """
    if sys.platform == "win32":
        user = os.environ.get("USERNAME") or os.environ.get("USER") or ""
        try:
            # Remove inherited ACEs, then grant only the current user full control.
            subprocess.run(
                ["icacls", str(path), "/inheritance:r"],
                check=False, capture_output=True,
            )
            if user:
                subprocess.run(
                    ["icacls", str(path), "/grant:r", f"{user}:F"],
                    check=False, capture_output=True,
                )
        except (OSError, subprocess.SubprocessError):
            pass
    else:
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass


def _env_key() -> str:
    """The env-var key, stripped. Empty string if unset/blank."""
    return os.environ.get("GOLPO_API_KEY", "").strip()


def _file_key() -> str:
    """The on-disk key, stripped. Empty string if absent/blank/unreadable."""
    try:
        if KEY_PATH.exists():
            return KEY_PATH.read_text().strip()
    except OSError:
        pass
    return ""


def get_key() -> str:
    """Return a non-empty API key, or raise.

    A blank env var or an empty/whitespace-only key file counts as "no key" —
    we never return "" and never let a caller make a request with an empty
    credential.
    """
    key = _env_key() or _file_key()
    if key:
        return key
    raise MissingCredentialError(
        "No Golpo API key configured. Set the GOLPO_API_KEY env var, or "
        f"write your key to {KEY_PATH} with mode 0600. Get a key at "
        "https://video.golpoai.com."
    )


def save_key(key: str) -> pathlib.Path:
    """Save the key to ~/.golpo/api_key, restricted to the current user."""
    KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    if sys.platform != "win32":
        try:
            os.chmod(KEY_PATH.parent, 0o700)
        except OSError:
            pass
    KEY_PATH.write_text(key.strip() + "\n")
    _lock_down(KEY_PATH)
    return KEY_PATH


def key_status() -> dict:
    """Diagnostic info (does NOT return the key itself).

    Reports "configured" only when a non-empty key actually exists — a blank
    env var or an empty key file reads as unconfigured, matching get_key().
    """
    env_set = bool(_env_key())
    file_present = bool(_file_key())
    return {
        "configured": env_set or file_present,
        "source": "env" if env_set else ("file" if file_present else "none"),
        "key_path": str(KEY_PATH),
    }
