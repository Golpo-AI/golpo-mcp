"""Golpo MCP server.

Exposes the Golpo Video API as MCP tools. Drop a new ``@mcp.tool()`` function
at the bottom of this file to add another tool — no other plumbing required.

Tools (v0.1.0):
  - generate_video    submit a job, poll, optionally download the MP4
  - upload_file       upload audio/document/image to Golpo (two-step S3 PUT)
  - list_videos       list the caller's recent videos
  - get_video         fetch metadata for one video; optionally re-download
  - check_status      one-shot status check for an in-flight job

Extension hook: every tool that calls /videos/generate accepts an
``extra_params`` dict that is shallow-merged into the request payload. Power
users can set Golpo API fields the tool signature doesn't expose explicitly.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from . import client
from .auth import MissingCredentialError, key_status
from .client import GolpoAPIError
from .downloads import download_video, resolve_output_dir

mcp = FastMCP("golpo")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _error(exc: Exception) -> dict:
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


# ---------------------------------------------------------------------------
# tools
# ---------------------------------------------------------------------------

@mcp.tool()
def generate_video(
    prompt: str,
    timing: str = "0.5",
    video_type: str = "long",
    style: str = "solo-female-3",
    language: str = "en",
    # alternative content sources
    new_script: str | None = None,
    audio_clip: str | None = None,
    upload_urls: list[str] | None = None,
    # engine A — Sketch
    use_lineart_2_style: str | None = None,
    use_color: bool | None = None,
    # engine B — Canvas
    use_2_0_style: bool | None = None,
    image_style: str | None = None,
    pen_style: str | None = None,
    display_language: str | None = None,
    # styling / branding
    bg_music: str | None = None,
    voice_instructions: str | None = None,
    video_instructions: str | None = None,
    pacing: str | None = None,
    include_watermark: bool | None = None,
    audio_only: bool | None = None,
    logo: str | None = None,
    logo_placement: str | None = None,
    is_public: bool | None = None,
    just_return_script: bool | None = None,
    # download behaviour
    output_dir: str | None = None,
    no_download: bool = False,
    max_wait_seconds: int = 5400,
    # escape hatch for fields this signature doesn't expose explicitly
    extra_params: dict | None = None,
) -> dict:
    """Submit a Golpo video job, poll until it finishes, and (by default)
    download the rendered MP4 locally.

    `prompt` is required even when also passing `new_script`, `audio_clip`,
    or `upload_urls` — the Golpo backend uses it as the title.

    `timing` is a string in minutes. Allowed: '0.25', '0.5', '1', '2', '4',
    '8', '10', 'auto'.

    Engines are mutually exclusive: set EITHER `use_lineart_2_style` (Sketch)
    OR `use_2_0_style=True` + `image_style` (Canvas).

    Downloads to ~/Golpo/videos/ by default. Override with `output_dir` or
    set the GOLPO_VIDEO_DIR env var. Pass `no_download=True` for URL-only.

    Returns: {job_id, video_id, video_url, video_file?, status, params_used}
    on success, or {error, message, ...} on failure.
    """
    try:
        payload: dict[str, Any] = {
            "prompt": prompt,
            "timing": timing,
            "video_type": video_type,
            "style": style,
            "language": language,
        }
        # add only the keys the user actually set, to avoid forcing defaults
        for k, v in {
            "new_script": new_script,
            "audio_clip": audio_clip,
            "upload_urls": upload_urls,
            "use_lineart_2_style": use_lineart_2_style,
            "use_color": use_color,
            "use_2_0_style": use_2_0_style,
            "image_style": image_style,
            "pen_style": pen_style,
            "display_language": display_language,
            "bg_music": bg_music,
            "voice_instructions": voice_instructions,
            "video_instructions": video_instructions,
            "pacing": pacing,
            "include_watermark": include_watermark,
            "audio_only": audio_only,
            "logo": logo,
            "logo_placement": logo_placement,
            "is_public": is_public,
            "just_return_script": just_return_script,
        }.items():
            if v is not None:
                payload[k] = v
        if extra_params:
            payload.update(extra_params)

        sub = client.generate(payload)
        job_id = sub.get("job_id")
        video_id = sub.get("video_id")
        if not job_id:
            return {"error": "no_job_id", "message": "API response missing job_id", "raw": sub}

        final = client.poll_until_terminal(job_id, max_wait_seconds=max_wait_seconds)
        video_url = final.get("video_url")
        target_id = video_id or final.get("video_id")

        # Pull canonical title for the download filename.
        title = None
        if target_id:
            try:
                meta = client.get_video(target_id)
                title = meta.get("title") or meta.get("prompt")
                if not video_url:
                    video_url = meta.get("video_url")
            except GolpoAPIError:
                pass

        result: dict[str, Any] = {
            "job_id": job_id,
            "video_id": target_id,
            "video_url": video_url,
            "status": final.get("status"),
            "params_used": payload,
        }
        if video_url and not no_download:
            out_dir = resolve_output_dir(output_dir)
            local = download_video(
                video_url, out_dir,
                title=title or prompt,
                video_id=target_id,
            )
            if local:
                result["video_file"] = str(local)
        return result
    except Exception as e:
        return _error(e)


@mcp.tool()
def upload_file(path: str) -> dict:
    """Upload an audio file, document (PDF/DOCX/PPTX/TXT), or image to Golpo.

    `path` is a local filesystem path; max 15 MB. Does the two-step upload
    flow: multipart POST to /videos/upload-file to get a presigned S3 URL,
    then PUT the file bytes to that URL.

    Returns: {file_url, upload_url, file_name, content_type, put_status}
    or {error, ...}. Pass `file_url` into `generate_video` as `audio_clip`
    or one of the `upload_urls`.

    Note: document URLs are SINGLE-USE — Golpo deletes the file after
    extraction. Re-upload if you want to regenerate.
    """
    try:
        return client.upload(path)
    except Exception as e:
        return _error(e)


@mcp.tool()
def list_videos(limit: int = 20, offset: int = 0) -> dict:
    """List the caller's recent videos.

    Returns: {videos: [...], total} or {error, ...}. Each video entry
    includes id, title, status, created_at, and (when ready) video_url.
    """
    try:
        return client.list_videos(limit=limit, offset=offset)
    except Exception as e:
        return _error(e)


@mcp.tool()
def get_video(
    video_id: str,
    download: bool = False,
    output_dir: str | None = None,
) -> dict:
    """Fetch metadata for one video. When `download=True`, also stream the
    MP4 to disk (default location ~/Golpo/videos/).

    Returns the video metadata plus `video_file` if downloaded, or
    {error, ...}.
    """
    try:
        v = client.get_video(video_id)
        video_url = v.get("video_url")
        result: dict[str, Any] = {"video": v}
        if download and video_url:
            out_dir = resolve_output_dir(output_dir)
            local = download_video(
                video_url, out_dir,
                title=v.get("title") or v.get("prompt"),
                video_id=video_id,
            )
            if local:
                result["video_file"] = str(local)
        return result
    except Exception as e:
        return _error(e)


@mcp.tool()
def check_status(job_id: str) -> dict:
    """One-shot status check for an in-flight generation job.

    Returns the API status payload (status, progress, video_url, ...) or
    {error, ...}.
    """
    try:
        return client.status_of(job_id)
    except Exception as e:
        return _error(e)


# ---------------------------------------------------------------------------
# diagnostic tool — handy for client config debugging
# ---------------------------------------------------------------------------

@mcp.tool()
def status() -> dict:
    """Report whether a Golpo API key is configured and which source it came from.

    Returns: {configured: bool, source: 'env' | 'file' | 'none', key_path}.
    Does NOT return the key itself.
    """
    from . import __version__
    out = key_status()
    out["server_version"] = __version__
    out["api_base"] = client.api_base()
    return out


# ---------------------------------------------------------------------------
# Adding a new tool:
#   1. Add a `@mcp.tool()`-decorated function above (or in a sub-module that
#      imports `mcp` from here and registers tools at import time).
#   2. Type-annotate every argument; FastMCP turns the signature into JSON
#      Schema automatically.
#   3. Return a JSON-serializable dict. Use _error(exc) for failure paths.
#   4. Document the tool in README.md's "Tool catalog" table.
# ---------------------------------------------------------------------------
