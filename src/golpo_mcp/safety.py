"""Security guards shared across the client and result layers.

This MCP server is driven by an LLM, so its tools can be steered by
prompt-injection (e.g. hidden instructions inside a document a user asks to
summarize). These helpers make the sharp edges safe:

  - `check_upload_path` refuses to upload credential/secret files (so a
    malicious prompt can't exfiltrate the Golpo API key, SSH keys, .env, …).
  - `redact` scrubs the API key value out of anything we hand back to the
    client, so it can never leak through an error body or message.

Only stdlib + `auth.KEY_PATH` is imported here to avoid import cycles.
"""

from __future__ import annotations

import pathlib

from .auth import KEY_PATH

# Directory names that, if they appear anywhere in a resolved path, mark it as
# holding credentials. Matched case-insensitively against each path component.
SENSITIVE_DIR_PARTS = {
    ".ssh", ".gnupg", ".aws", ".azure", ".kube", ".docker",
    ".golpo", ".gcloud", "gcloud",
}

# Exact file names (case-insensitive) that are credentials, never media.
SENSITIVE_NAMES = {
    "api_key", "credentials", "credentials.json", ".netrc", "_netrc",
    ".pgpass", ".htpasswd", ".npmrc", ".pypirc", ".git-credentials",
    "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519",
    "shadow", "master.key", "secrets.yaml", "secrets.yml",
}

# File suffixes that are keys/secrets, never legitimate Golpo media uploads
# (which are audio / PDF / DOCX / PPTX / TXT / images).
SENSITIVE_SUFFIXES = {
    ".pem", ".key", ".pfx", ".p12", ".keystore", ".jks", ".asc", ".gpg",
    ".ppk", ".crt", ".cer", ".der",
}


def check_upload_path(p: pathlib.Path) -> None:
    """Raise PermissionError if `p` looks like a credential/secret file.

    `p` should already be resolved (symlinks followed) so a symlink pointing
    at a secret can't slip past the name checks.
    """
    try:
        resolved = p.resolve()
    except OSError:
        resolved = p

    # Never upload the Golpo credential file itself, however it's referenced.
    try:
        if resolved == KEY_PATH.resolve():
            raise PermissionError(
                "refusing to upload the Golpo API key file "
                f"({KEY_PATH}); this would leak your credentials"
            )
    except OSError:
        pass

    name = resolved.name.lower()
    if name in SENSITIVE_NAMES:
        raise PermissionError(f"refusing to upload credential file '{resolved.name}'")

    # Dotenv files: .env, .env.local, .env.production, …
    if name == ".env" or name.startswith(".env."):
        raise PermissionError(f"refusing to upload environment/secrets file '{resolved.name}'")

    if resolved.suffix.lower() in SENSITIVE_SUFFIXES:
        raise PermissionError(
            f"refusing to upload '{resolved.name}': "
            f"'{resolved.suffix}' files are treated as private keys/secrets"
        )

    parts_lower = {part.lower() for part in resolved.parts}
    hit = parts_lower & SENSITIVE_DIR_PARTS
    if hit:
        raise PermissionError(
            f"refusing to upload from a credentials directory ({sorted(hit)[0]}): {resolved}"
        )


def redact(obj, secret: str | None):
    """Recursively replace occurrences of `secret` with a placeholder.

    Used on anything returned to the MCP client so the API key can never be
    echoed back through an error body or message.
    """
    if not secret:
        return obj
    placeholder = "***REDACTED***"
    if isinstance(obj, str):
        return obj.replace(secret, placeholder)
    if isinstance(obj, dict):
        return {k: redact(v, secret) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return type(obj)(redact(v, secret) for v in obj)
    return obj
