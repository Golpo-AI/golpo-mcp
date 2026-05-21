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

KEY_PATH = pathlib.Path.home() / ".golpo" / "api_key"


class MissingCredentialError(RuntimeError):
    """Raised when no Golpo API key can be found."""


def get_key() -> str:
    env = os.environ.get("GOLPO_API_KEY")
    if env:
        return env.strip()
    if KEY_PATH.exists():
        return KEY_PATH.read_text().strip()
    raise MissingCredentialError(
        "No Golpo API key configured. Set the GOLPO_API_KEY env var, or "
        f"write your key to {KEY_PATH} with mode 0600. Get a key at "
        "https://video.golpoai.com."
    )


def save_key(key: str) -> pathlib.Path:
    """Save the key to ~/.golpo/api_key (0600). Returns the path."""
    KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(KEY_PATH.parent, 0o700)
    except OSError:
        pass
    KEY_PATH.write_text(key.strip() + "\n")
    os.chmod(KEY_PATH, 0o600)
    return KEY_PATH


def key_status() -> dict:
    """Diagnostic info (does NOT return the key itself)."""
    env_set = bool(os.environ.get("GOLPO_API_KEY"))
    file_present = KEY_PATH.exists()
    return {
        "configured": env_set or file_present,
        "source": "env" if env_set else ("file" if file_present else "none"),
        "key_path": str(KEY_PATH),
    }
