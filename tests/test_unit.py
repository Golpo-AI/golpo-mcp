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
