"""Pipeline + version-routing tests — no network calls.

Locks in:
  - GOLPO_API_VERSION routing (default v2, opt-out v1, invalid fallback,
    GOLPO_API_BASE override).
  - Each pipeline builds a NATIVE payload (v1 names for v1, v2 names for v2)
    and calls the matching submit function.
  - Every field the pipelines emit is a real field on the backend models
    (guards against a rename introducing an unknown-field 422).
"""

from __future__ import annotations

import inspect
import pathlib
import re

import pytest

from golpo_mcp import client, generate_v1, generate_v2


# ---------- version routing ----------

def test_default_version_is_v2(monkeypatch):
    monkeypatch.delenv("GOLPO_API_VERSION", raising=False)
    monkeypatch.delenv("GOLPO_API_BASE", raising=False)
    assert client.api_version() == "v2"
    assert client.api_base() == "https://api.golpoai.com/api/v2"


def test_opt_out_to_v1(monkeypatch):
    monkeypatch.delenv("GOLPO_API_BASE", raising=False)
    monkeypatch.setenv("GOLPO_API_VERSION", "v1")
    assert client.api_version() == "v1"
    assert client.api_base() == "https://api.golpoai.com/api/v1"


def test_invalid_version_falls_back_to_default(monkeypatch):
    monkeypatch.delenv("GOLPO_API_BASE", raising=False)
    monkeypatch.setenv("GOLPO_API_VERSION", "banana")
    assert client.api_version() == "v2"


def test_case_and_whitespace_insensitive(monkeypatch):
    monkeypatch.delenv("GOLPO_API_BASE", raising=False)
    monkeypatch.setenv("GOLPO_API_VERSION", "  V1 ")
    assert client.api_version() == "v1"


def test_explicit_base_overrides_version(monkeypatch):
    monkeypatch.setenv("GOLPO_API_VERSION", "v2")
    monkeypatch.setenv("GOLPO_API_BASE", "http://localhost:8080/api/v1")
    assert client.api_base() == "http://localhost:8080/api/v1"


# ---------- payload building (network stubbed) ----------

@pytest.fixture
def capture(monkeypatch):
    """Stub the network so we can inspect the built payload + which path ran."""
    seen: dict = {}

    def fake_v1(payload):
        seen["fn"] = "v1"
        seen["base"] = client.api_base()
        seen["payload"] = dict(payload)
        return {"job_id": "JOB"}

    def fake_v2(payload):
        seen["fn"] = "v2"
        seen["base"] = client.api_base()
        seen["payload"] = dict(payload)
        return {"job_id": "JOB"}

    monkeypatch.setattr(client, "generate", fake_v1)
    monkeypatch.setattr(client, "submit_generate_v2", fake_v2)
    monkeypatch.setattr(client, "poll_until_terminal",
                        lambda job_id, **k: {"status": "completed", "video_url": None})
    monkeypatch.setattr(client, "get_video", lambda vid: {})
    return seen


def test_v1_pipeline_builds_native_v1_payload(capture, monkeypatch):
    monkeypatch.delenv("GOLPO_API_BASE", raising=False)
    monkeypatch.setenv("GOLPO_API_VERSION", "v1")
    generate_v1.generate_video(
        "hello", timing="2", style="solo-male-3", video_type="short",
        use_lineart_2_style="storytelling", no_download=True,
    )
    assert capture["fn"] == "v1"
    assert capture["base"].endswith("/api/v1")
    p = capture["payload"]
    # native v1 vocabulary present
    assert p["style"] == "solo-male-3"
    assert p["video_type"] == "short"
    assert p["use_lineart_2_style"] == "storytelling"
    # v2-only names must NOT leak into a v1 payload
    assert "narration_voice" not in p
    assert "golpo_video_engine" not in p


def test_v2_pipeline_builds_native_v2_payload(capture, monkeypatch):
    monkeypatch.delenv("GOLPO_API_BASE", raising=False)
    monkeypatch.setenv("GOLPO_API_VERSION", "v2")
    generate_v2.generate_video(
        "hello", timing="2", narration_voice="male-1", video_orientation="vertical",
        golpo_video_engine="golpo_sketch", sketch_style_variant="crayon", no_download=True,
    )
    assert capture["fn"] == "v2"
    assert capture["base"].endswith("/api/v2")
    p = capture["payload"]
    # native v2 vocabulary present
    assert p["narration_voice"] == "male-1"
    assert p["video_orientation"] == "vertical"
    assert p["golpo_video_engine"] == "golpo_sketch"
    assert p["sketch_style_variant"] == "crayon"
    # v1-only names must NOT leak into a v2 payload
    assert "style" not in p
    assert "video_type" not in p
    assert "use_lineart_2_style" not in p


def test_v2_only_sends_set_fields(capture):
    """Optional params left unset should not appear in the payload."""
    generate_v2.generate_video("hi", no_download=True)
    p = capture["payload"]
    # always-sent, safe in both video + podcast modes
    assert set(p) == {"prompt", "timing", "narration_voice", "narration_language"}


def test_v2_podcast_has_no_video_fields(capture):
    """Podcast mode should not carry video-pipeline fields (v2 would 422)."""
    generate_v2.generate_video(
        "hi", enable_podcast_engine=True, background_track="lofi", no_download=True,
    )
    p = capture["payload"]
    assert p["enable_podcast_engine"] is True
    assert p["background_track"] == "lofi"
    for banned in ("golpo_video_engine", "video_orientation", "watermark",
                   "canvas_style_variant", "sketch_style_variant"):
        assert banned not in p


def test_extra_params_passthrough(capture):
    generate_v2.generate_video("hi", no_download=True, extra_params={"video_id": "abc"})
    assert capture["payload"]["video_id"] == "abc"


# ---------- wait=False (fire-and-forget: must not poll) ----------

@pytest.mark.parametrize("module", [generate_v1, generate_v2])
def test_wait_false_returns_immediately_without_polling(monkeypatch, module):
    """wait=False must return the job_id right after submit and NEVER poll
    (polling is what blocks the MCP server / times out the client)."""
    monkeypatch.setattr(client, "generate", lambda p: {"job_id": "JOB", "status": "processing"})
    monkeypatch.setattr(client, "submit_generate_v2", lambda p: {"job_id": "JOB", "status": "processing"})

    def boom(*a, **k):
        raise AssertionError("poll_until_terminal must NOT be called when wait=False")
    monkeypatch.setattr(client, "poll_until_terminal", boom)

    out = module.generate_video("hi", wait=False)
    assert out.get("error") is None
    assert out["job_id"] == "JOB"
    assert out["video_id"] == "JOB"      # falls back to job_id when submit omits video_id
    assert out["status"] == "processing"
    assert "note" in out                 # tells the caller how to poll/fetch
    assert "video_url" not in out        # nothing rendered yet


@pytest.mark.parametrize("module", [generate_v1, generate_v2])
def test_default_is_wait_true(module):
    import inspect
    sig = inspect.signature(module.generate_video)
    assert sig.parameters["wait"].default is True          # unchanged default behavior
    assert sig.parameters["max_wait_seconds"].default == 600  # lowered from 5400


def test_missing_job_id_returns_error(monkeypatch):
    monkeypatch.setattr(client, "submit_generate_v2", lambda p: {"status": "processing"})
    out = generate_v2.generate_video("hi", no_download=True)
    assert out["error"] == "no_job_id"


# ---------- script-only mode (regression: script_ready must be terminal) ----------

def test_script_ready_is_terminal():
    assert "script_ready" in client.TERMINAL_OK


def test_poll_returns_on_script_ready(monkeypatch):
    """A just_return_script / enable_script_only_mode job reports 'script_ready'
    with no video_url; the poller must treat that as done, not time out."""
    monkeypatch.setattr(client, "status_of",
                        lambda job_id, **k: {"status": "script_ready", "script_text": "S"})
    final = client.poll_until_terminal("JOB", max_wait_seconds=5)
    assert final["status"] == "script_ready"
    assert final["script_text"] == "S"


def test_poll_returns_when_script_text_present_despite_nonterminal_status(monkeypatch):
    """Robustness: even if the backend reports a non-terminal status string,
    the presence of script_text (script-only jobs only) must end polling."""
    monkeypatch.setattr(client, "status_of",
                        lambda job_id, **k: {"status": "generating", "script_text": "the script"})
    final = client.poll_until_terminal("JOB", max_wait_seconds=5)
    assert final["script_text"] == "the script"


def test_poll_keeps_going_when_no_script_yet(monkeypatch):
    """A script-only job still generating (empty script_text) is NOT terminal."""
    calls = {"n": 0}

    def fake_status(job_id, **k):
        calls["n"] += 1
        # first call: still generating; second: script ready
        return ({"status": "generating", "script_text": None} if calls["n"] == 1
                else {"status": "generating", "script_text": "done"})

    monkeypatch.setattr(client, "status_of", fake_status)
    monkeypatch.setattr(client.time, "sleep", lambda s: None)  # don't actually wait
    final = client.poll_until_terminal("JOB", max_wait_seconds=60)
    assert final["script_text"] == "done"
    assert calls["n"] == 2


@pytest.mark.parametrize("module,kw", [
    (generate_v1, {"just_return_script": True}),
    (generate_v2, {"enable_script_only_mode": True}),
])
def test_script_only_surfaces_script_text(monkeypatch, module, kw):
    monkeypatch.setattr(client, "generate", lambda p: {"job_id": "JOB"})
    monkeypatch.setattr(client, "submit_generate_v2", lambda p: {"job_id": "JOB"})
    monkeypatch.setattr(client, "poll_until_terminal",
                        lambda job_id, **k: {"status": "script_ready", "script_text": "the script"})
    monkeypatch.setattr(client, "get_video", lambda vid: {})
    out = module.generate_video("hi", no_download=True, **kw)
    assert out.get("error") is None
    assert out["status"] == "script_ready"
    assert out["script_text"] == "the script"


# ---------- field-name audit against the backend models ----------
# These skip cleanly if the sibling golpo-video-engine repo isn't present
# (e.g. in CI where golpo-mcp is checked out on its own).

_BACKEND = pathlib.Path(__file__).resolve().parents[2] / "golpo-video-engine" / "api"
_DOWNLOAD_ONLY = {"output_dir", "no_download", "wait", "max_wait_seconds", "extra_params"}


def _backend_model_fields(path: pathlib.Path) -> set[str]:
    src = path.read_text(encoding="utf-8")
    body = src[src.index("class VideoGenerationRequest"):]
    body = body[: body.index("\nclass ")]
    return set(re.findall(r"^    ([a-z_][a-z0-9_]*): ", body, re.M))


@pytest.mark.parametrize("ver,module", [("v1", generate_v1), ("v2", generate_v2)])
def test_pipeline_emits_only_valid_backend_fields(ver, module):
    model_file = _BACKEND / ver / "video_route.py"
    if not model_file.exists():
        pytest.skip(f"backend model not available: {model_file}")
    backend = _backend_model_fields(model_file)
    emitted = set(inspect.signature(module.generate_video).parameters) - _DOWNLOAD_ONLY
    unknown = emitted - backend
    assert not unknown, f"{ver} pipeline emits fields the backend model rejects: {sorted(unknown)}"
