"""v1 generate pipeline.

Native Golpo /api/v1 vocabulary. Registered by server.py when
GOLPO_API_VERSION is unset-to-v1 (or v2 is not selected). This is the original
behavior, unchanged — kept fully separate from the v2 pipeline.
"""

from __future__ import annotations

from typing import Any

from . import client
from .client import GolpoAPIError
from .downloads import download_video, resolve_output_dir
from .results import error_result


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
    # download / wait behaviour
    output_dir: str | None = None,
    no_download: bool = False,
    wait: bool = True,
    max_wait_seconds: int = 600,
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

    `wait` (default True): poll until the job finishes, then return the video.
    Set `wait=False` to submit and return immediately with the job_id (no
    polling/download) — then use check_status(job_id) and, once done,
    get_video(video_id, download=True). Recommended for interactive MCP clients
    where a multi-minute render would otherwise exceed the client's timeout.

    Returns: {job_id, video_id, video_url, video_file?, status, params_used}
    on success (wait=True), {job_id, video_id, status, note, ...} when
    wait=False, or {error, message, ...} on failure.
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

        # Fire-and-forget: return immediately so long renders don't block the
        # MCP server or exceed the client's tool-call timeout.
        if not wait:
            return {
                "job_id": job_id,
                "video_id": video_id or job_id,
                "status": sub.get("status") or "processing",
                "params_used": payload,
                "note": ("Job submitted (wait=False). Poll with check_status(job_id); "
                         "when status is 'completed' (or 'script_ready'), fetch it with "
                         "get_video(video_id, download=True)."),
            }

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
        if final.get("script_text"):
            result["script_text"] = final["script_text"]
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
        return error_result(e)


def register(mcp) -> None:
    """Register the v1 generate_video tool on the given FastMCP instance."""
    mcp.tool(name="generate_video")(generate_video)
