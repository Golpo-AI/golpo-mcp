"""Unit tests — no network calls."""

from __future__ import annotations

import pytest

from golpo_mcp import auth, client, downloads


# ---------- slugify ----------

@pytest.mark.parametrize("text,expected", [
    ("Why is the sky blue?", "why-is-the-sky-blue"),
    ("Summarize this document about ocean tides...", "summarize-this-document-about-ocean-tides"),
    ("  Multiple   spaces  ", "multiple-spaces"),
    # Underscore/dot/exclamation get stripped; hyphen and spaces survive.
    ("Mixed-Case_With.Special!Chars", "mixed-casewithspecialchars"),
    ("", "video"),
    (None, "video"),
    ("!" * 50, "video"),  # only special chars -> "video" fallback
])
def test_slugify(text, expected):
    assert downloads.slugify(text) == expected


def test_slugify_truncates():
    out = downloads.slugify("a" * 200)
    assert len(out) <= 50


# ---------- resolve_output_dir ----------

def test_resolve_output_dir_override(tmp_path):
    p = downloads.resolve_output_dir(str(tmp_path / "x"))
    assert p == (tmp_path / "x").expanduser()


def test_resolve_output_dir_env(monkeypatch, tmp_path):
    monkeypatch.setenv("GOLPO_VIDEO_DIR", str(tmp_path / "fromenv"))
    p = downloads.resolve_output_dir(None)
    assert p == (tmp_path / "fromenv").expanduser()


def test_resolve_output_dir_default(monkeypatch):
    monkeypatch.delenv("GOLPO_VIDEO_DIR", raising=False)
    p = downloads.resolve_output_dir(None)
    assert p == downloads.DEFAULT_VIDEO_DIR


# ---------- auth ----------

def test_get_key_from_env(monkeypatch):
    monkeypatch.setenv("GOLPO_API_KEY", "test-key-from-env")
    assert auth.get_key() == "test-key-from-env"


def test_get_key_missing_raises(monkeypatch, tmp_path):
    monkeypatch.delenv("GOLPO_API_KEY", raising=False)
    monkeypatch.setattr(auth, "KEY_PATH", tmp_path / "nope")
    with pytest.raises(auth.MissingCredentialError):
        auth.get_key()


def test_save_then_get_key(monkeypatch, tmp_path):
    monkeypatch.delenv("GOLPO_API_KEY", raising=False)
    monkeypatch.setattr(auth, "KEY_PATH", tmp_path / "api_key")
    path = auth.save_key("saved-key-123")
    assert path.exists()
    assert oct(path.stat().st_mode)[-3:] == "600"
    assert auth.get_key() == "saved-key-123"


def test_key_status_reports_correctly(monkeypatch, tmp_path):
    monkeypatch.setattr(auth, "KEY_PATH", tmp_path / "missing")
    monkeypatch.delenv("GOLPO_API_KEY", raising=False)
    s = auth.key_status()
    assert s["configured"] is False
    assert s["source"] == "none"

    monkeypatch.setenv("GOLPO_API_KEY", "k")
    s = auth.key_status()
    assert s["configured"] is True
    assert s["source"] == "env"


# ---------- string coercion ----------

def test_string_coerce_timing_bool_and_int():
    p = {"timing": 0.5, "use_lineart_2_style": False, "prompt": "x"}
    client._coerce_string_fields(p)
    assert p["timing"] == "0.5"
    assert p["use_lineart_2_style"] == "false"


def test_string_coerce_skips_unset():
    p = {"prompt": "x"}
    client._coerce_string_fields(p)
    assert "timing" not in p


# ---------- MCP tool registration ----------

def test_server_tools_registered():
    """Importing server.py should register all v0.1.0 tools."""
    from golpo_mcp import server as srv  # noqa: F401
    # FastMCP keeps tools on the instance; sanity-check the count.
    # If a tool gets accidentally deleted, this fails.
    expected_tools = {
        "generate_video", "upload_file", "list_videos",
        "get_video", "check_status", "status",
    }
    import asyncio
    listed = asyncio.run(srv.mcp.list_tools())
    names = {t.name for t in listed}
    missing = expected_tools - names
    assert not missing, f"missing tools: {missing}"
