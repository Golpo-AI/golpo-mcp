"""Golpo MCP server.

Exposes the Golpo Video API as MCP tools.

The `generate_video` tool comes from a version-specific pipeline module,
selected at startup by GOLPO_API_VERSION (see client.api_version()):
  - v2 (default) -> generate_v2.py  (native /api/v2 vocabulary)
  - v1           -> generate_v1.py  (native /api/v1 vocabulary)
The two pipelines are fully separate. Everything else (upload, list, get,
status) shares one contract across both API versions and lives here.

Tools:
  - generate_video    submit a job, poll, optionally download the MP4
  - upload_file       upload audio/document/image to Golpo (two-step S3 PUT)
  - list_videos       list the caller's recent videos
  - get_video         fetch metadata for one video; optionally re-download
  - check_status      one-shot status check for an in-flight job
  - status            report configured API key + active API version

Extension hook: every generate pipeline accepts an ``extra_params`` dict that
is shallow-merged into the request payload. Power users can set API fields the
tool signature doesn't expose explicitly.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from . import client, generate_v1, generate_v2
from .auth import key_status
from .downloads import download_video, resolve_output_dir
from .results import error_result

mcp = FastMCP("golpo")


# ---------------------------------------------------------------------------
# generate_video — version-specific pipeline selected at startup
# ---------------------------------------------------------------------------

if client.api_version() == "v2":
    generate_v2.register(mcp)
else:
    generate_v1.register(mcp)


# ---------------------------------------------------------------------------
# shared tools (identical contract across v1 and v2)
# ---------------------------------------------------------------------------

@mcp.tool()
def upload_file(path: str) -> dict:
    """Upload an audio file, document (PDF/DOCX/PPTX/TXT), or image to Golpo.

    `path` is a local filesystem path; max 15 MB. Does the two-step upload
    flow: multipart POST to /videos/upload-file to get a presigned S3 URL,
    then PUT the file bytes to that URL.

    Returns: {file_url, upload_url, file_name, content_type, put_status}
    or {error, ...}. Pass `file_url` into `generate_video`.

    Note: document URLs are SINGLE-USE — Golpo deletes the file after
    extraction. Re-upload if you want to regenerate.
    """
    try:
        return client.upload(path)
    except Exception as e:
        return error_result(e)


@mcp.tool()
def list_videos(
    limit: int = 20,
    offset: int = 0,
    include_full: bool = False,
) -> dict:
    """List the caller's recent videos. Returns a curated summary by default.

    Each returned video includes: id, title, prompt, status, video_url
    (presigned, ~7-day signed URL — ready to download right now),
    video_filename (bare S3 URL — safe to share long-term), thumbnail_url,
    video_duration, video_type, scenes, is_public, ispodcast, created_at,
    updated_at.

    Pass `include_full=True` to receive the raw API response with every
    field per video (transcript, request_payload, per-frame image URLs,
    etc.) — useful for debugging but very verbose (~25 KB per video).

    Args:
        limit: max videos to return (default 20)
        offset: skip this many videos (for pagination)
        include_full: return raw API payload instead of the curated summary

    Returns: {videos: [...], total, limit, offset} or {error, ...}.
    """
    try:
        raw = client.list_videos(limit=limit, offset=offset)
        if include_full or not isinstance(raw, dict):
            return raw
        videos = raw.get("videos", []) or []
        return {
            "videos": [client.summarize_video_entry(v) for v in videos],
            "total": raw.get("total"),
            "limit": raw.get("limit", limit),
            "offset": raw.get("offset", offset),
        }
    except Exception as e:
        return error_result(e)


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
        return error_result(e)


@mcp.tool()
def check_status(job_id: str) -> dict:
    """One-shot status check for an in-flight generation job.

    Returns the API status payload (status, progress, video_url, ...) or
    {error, ...}.
    """
    try:
        return client.status_of(job_id)
    except Exception as e:
        return error_result(e)


# ---------------------------------------------------------------------------
# diagnostic tool — handy for client config debugging
# ---------------------------------------------------------------------------

@mcp.tool()
def status() -> dict:
    """Report whether a Golpo API key is configured and which source it came from.

    Returns: {configured, source, key_path, server_version, api_version,
    api_base}. Does NOT return the key itself.
    """
    from . import __version__
    out = key_status()
    out["server_version"] = __version__
    out["api_version"] = client.api_version()
    out["api_base"] = client.api_base()
    return out
