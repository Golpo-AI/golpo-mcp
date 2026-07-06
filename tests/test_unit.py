"""Unit tests — no network calls."""

from __future__ import annotations

import pytest

from golpo_mcp import auth, client, downloads, results, safety


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
    import sys
    monkeypatch.delenv("GOLPO_API_KEY", raising=False)
    monkeypatch.setattr(auth, "KEY_PATH", tmp_path / "api_key")
    path = auth.save_key("saved-key-123")
    assert path.exists()
    if sys.platform != "win32":
        # POSIX: owner-only 0600. (On Windows chmod can't express this; the ACL
        # is locked down via icacls instead, which st_mode doesn't reflect.)
        assert oct(path.stat().st_mode)[-3:] == "600"
    assert auth.get_key() == "saved-key-123"


def test_get_key_blank_env_raises(monkeypatch, tmp_path):
    """A whitespace-only env var must NOT count as a key."""
    monkeypatch.setenv("GOLPO_API_KEY", "   ")
    monkeypatch.setattr(auth, "KEY_PATH", tmp_path / "nope")
    with pytest.raises(auth.MissingCredentialError):
        auth.get_key()


def test_get_key_empty_file_raises(monkeypatch, tmp_path):
    """An empty/whitespace key file must NOT count as a key."""
    monkeypatch.delenv("GOLPO_API_KEY", raising=False)
    kf = tmp_path / "api_key"
    kf.write_text("\n  \n")
    monkeypatch.setattr(auth, "KEY_PATH", kf)
    with pytest.raises(auth.MissingCredentialError):
        auth.get_key()


def test_request_never_calls_without_key(monkeypatch, tmp_path):
    """No key -> get_key raises before any HTTP call is attempted."""
    monkeypatch.delenv("GOLPO_API_KEY", raising=False)
    monkeypatch.setattr(auth, "KEY_PATH", tmp_path / "absent")

    def _boom(*a, **k):
        raise AssertionError("HTTP call attempted without an API key!")

    monkeypatch.setattr(client.requests, "request", _boom)
    with pytest.raises(auth.MissingCredentialError):
        client.request("GET", "/videos")


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


# ---------- list_videos summarization ----------

SAMPLE_RAW_VIDEO = {
    "id": "abc-123",
    "title": "Why is the sky blue?",
    "prompt": "Why is the sky blue?",
    "status": "completed",
    "video_url": "https://golpo-podcast-inputs.s3.amazonaws.com/files/x.mp4?X-Amz-Signature=...",
    "video_filename": "https://golpo-podcast-inputs.s3.us-east-2.amazonaws.com/files/x.mp4",
    "thumbnail_url": "https://golpo-podcast-inputs.s3.us-east-2.amazonaws.com/files/y.png",
    "video_duration": "0.5",
    "video_type": "long",
    "scenes": 6,
    "is_public": False,
    "ispodcast": False,
    "created_at": "2026-05-21T04:05:04+00:00",
    "updated_at": "2026-05-21T04:09:50+00:00",
    # noise that should be dropped — sized realistically (~25 KB of transcript
    # is typical for a 1-min video; this mirrors what the real Golpo API returns)
    "transcript": "{\"sentences\": [" + ", ".join(
        ['{"text": "sentence ' + str(i) + ' of many words here.", "start": ' + str(i) + ', "end": ' + str(i+1) + '}'
         for i in range(100)]
    ) + "]}",
    "request_payload": {f"field_{i}": f"value_{i}" for i in range(40)},
    "frame_image_urls": [f"https://golpo.example/files/frame-{i}.png" for i in range(20)],
    "user_id": "user-123",
    "attempt_count": 1,
    "pipeline": "color",
    "script_text": "Plants are nature's solar panels. " * 50,
}


def test_summarize_keeps_urls_and_drops_noise():
    summary = client.summarize_video_entry(SAMPLE_RAW_VIDEO)
    # URLs surface
    assert summary["video_url"].startswith("https://")
    assert summary["video_filename"].startswith("https://")
    assert summary["thumbnail_url"].startswith("https://")
    # ID and metadata kept
    assert summary["id"] == "abc-123"
    assert summary["title"] == "Why is the sky blue?"
    assert summary["status"] == "completed"
    assert summary["video_duration"] == "0.5"
    # Noise dropped
    assert "transcript" not in summary
    assert "request_payload" not in summary
    assert "frame_image_urls" not in summary
    assert "script_text" not in summary
    assert "user_id" not in summary


def test_summarize_is_small():
    """A summarized entry should be << the raw entry size."""
    import json as _json
    raw_size = len(_json.dumps(SAMPLE_RAW_VIDEO))
    summary_size = len(_json.dumps(client.summarize_video_entry(SAMPLE_RAW_VIDEO)))
    assert summary_size < raw_size / 2, \
        f"summary not noticeably smaller: raw={raw_size} summary={summary_size}"


def test_summarize_missing_fields_dont_appear_as_none():
    """If the API omits a field, the summary should omit it too (not key=None)."""
    minimal = {"id": "x", "status": "completed", "video_url": "https://..."}
    s = client.summarize_video_entry(minimal)
    assert s == {"id": "x", "status": "completed", "video_url": "https://..."}


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


# ---------- security: upload path guard ----------

def test_upload_refuses_api_key_file(monkeypatch, tmp_path):
    key_file = tmp_path / "api_key"
    key_file.write_text("super-secret-key\n")
    monkeypatch.setattr(auth, "KEY_PATH", key_file)
    monkeypatch.setattr(safety, "KEY_PATH", key_file)
    with pytest.raises(PermissionError):
        safety.check_upload_path(key_file)


@pytest.mark.parametrize("name", [
    "id_rsa", ".env", ".env.production", "credentials", ".netrc",
    "server.pem", "private.key", "cert.pfx", ".pypirc",
])
def test_upload_refuses_secret_names(tmp_path, name):
    f = tmp_path / name
    f.write_text("x")
    with pytest.raises(PermissionError):
        safety.check_upload_path(f)


@pytest.mark.parametrize("rel", [".ssh/known_file", ".aws/config", ".gnupg/data"])
def test_upload_refuses_credential_dirs(tmp_path, rel):
    f = tmp_path / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("x")
    with pytest.raises(PermissionError):
        safety.check_upload_path(f)


def test_upload_allows_ordinary_media(tmp_path):
    f = tmp_path / "report.pdf"
    f.write_text("x")
    safety.check_upload_path(f)  # must not raise
    (tmp_path / "clip.mp3").write_text("x")
    safety.check_upload_path(tmp_path / "clip.mp3")


def test_upload_refuses_symlink_to_secret(tmp_path, monkeypatch):
    secret = tmp_path / "id_rsa"
    secret.write_text("KEY")
    link = tmp_path / "innocent.pdf"
    try:
        link.symlink_to(secret)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported on this platform/user")
    with pytest.raises(PermissionError):
        safety.check_upload_path(link)


# ---------- security: API base must not leak the key over cleartext ----------

def test_api_base_rejects_http_remote(monkeypatch):
    monkeypatch.setenv("GOLPO_API_BASE", "http://evil.example.com/api/v2")
    with pytest.raises(ValueError):
        client.api_base()


def test_api_base_allows_https(monkeypatch):
    monkeypatch.setenv("GOLPO_API_BASE", "https://api.golpoai.com/api/v2")
    assert client.api_base() == "https://api.golpoai.com/api/v2"


def test_api_base_allows_http_localhost(monkeypatch):
    monkeypatch.setenv("GOLPO_API_BASE", "http://localhost:8080/api/v2")
    assert client.api_base() == "http://localhost:8080/api/v2"


def test_api_base_default_is_https(monkeypatch):
    monkeypatch.delenv("GOLPO_API_BASE", raising=False)
    assert client.api_base().startswith("https://")


# ---------- security: downloads stay safe ----------

def test_download_rejects_nonmedia_extension(monkeypatch, tmp_path):
    """A URL ending in .exe must be written as .mp4, never executable."""

    class _FakeResp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def raise_for_status(self): pass
        def iter_content(self, chunk_size): return [b"data"]

    def _fake_get(url, **kw):
        return _FakeResp()

    monkeypatch.setattr(downloads.requests, "get", _fake_get)
    out = downloads.download_video(
        "https://evil.example/x.exe?sig=1", tmp_path, title="t", video_id="abc",
    )
    assert out is not None
    assert out.suffix == ".mp4"


# ---------- security: error results never echo the key ----------

def test_error_result_redacts_key(monkeypatch):
    monkeypatch.setenv("GOLPO_API_KEY", "sk-live-do-not-leak")
    exc = client.GolpoAPIError(401, {"detail": "bad key sk-live-do-not-leak"})
    out = results.error_result(exc)
    assert "sk-live-do-not-leak" not in repr(out)
    assert "REDACTED" in out["body"]["detail"]


def test_redact_handles_nested_and_none():
    assert safety.redact({"a": ["x", "SECRET"]}, "SECRET") == {"a": ["x", "***REDACTED***"]}
    assert safety.redact("SECRET", None) == "SECRET"  # no key -> unchanged


def test_status_tool_survives_bad_api_base(monkeypatch):
    """The diagnostic must not crash when GOLPO_API_BASE is misconfigured."""
    from golpo_mcp import server as srv
    monkeypatch.setenv("GOLPO_API_BASE", "http://evil.example.com/api/v2")
    monkeypatch.setenv("GOLPO_API_KEY", "k")
    out = srv.status.fn() if hasattr(srv.status, "fn") else srv.status()
    assert out["api_base"] is None
    assert "api_base_error" in out
