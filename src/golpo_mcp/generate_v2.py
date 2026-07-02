"""v2 generate pipeline.

Native Golpo /api/v2 vocabulary — no translation from v1. Registered by
server.py when GOLPO_API_VERSION=v2 (the default). Kept fully separate from
the v1 pipeline so each version evolves independently.
"""

from __future__ import annotations

from typing import Any

from . import client
from .client import GolpoAPIError
from .downloads import download_video, resolve_output_dir
from .results import error_result


def generate_video(
    prompt: str,
    timing: str = "1",
    narration_voice: str = "female-1",
    narration_language: str = "en",
    # engine + orientation (omit for v2 defaults: golpo_canvas / horizontal)
    golpo_video_engine: str | None = None,
    video_orientation: str | None = None,
    canvas_style_variant: str | None = None,
    sketch_style_variant: str | None = None,
    pen_animation_style: str | None = None,
    onscreen_text_language: str | None = None,
    # alternative content sources
    custom_script: str | None = None,
    own_narration_source: str | None = None,
    reference_source: list[str] | None = None,
    reference_images: list[str] | None = None,
    # custom media inserts
    custom_images: list[str] | None = None,
    custom_images_description: list[str] | None = None,
    custom_videos: list[str] | None = None,
    custom_videos_description: list[str] | None = None,
    # styling / branding
    background_track: str | None = None,
    narration_instructions: str | None = None,
    visual_instructions: str | None = None,
    scene_pacing: str | None = None,
    enable_color: bool | None = None,
    watermark: bool | None = None,
    custom_logo: str | None = None,
    logo_position: str | None = None,
    visibility: str | None = None,
    # modes
    enable_podcast_engine: bool | None = None,
    enable_script_only_mode: bool | None = None,
    # multi-language
    language_variants: list[str] | None = None,
    variant_visuals_mode: str | None = None,
    # download / wait behaviour
    output_dir: str | None = None,
    no_download: bool = False,
    wait: bool = True,
    max_wait_seconds: int = 600,
    # escape hatch for fields this signature doesn't expose explicitly
    extra_params: dict | None = None,
) -> dict:
    """Submit a Golpo v2 video job, poll until it finishes, and (by default)
    download the rendered MP4 locally.

    `prompt` is required even when also passing `custom_script`,
    `own_narration_source`, or `reference_source` — the backend uses it as the
    title.

    `timing` is a string in minutes. Allowed: '0.25', '0.5', '1', '2', '4',
    '8', '10', '15', 'auto'.

    Voice/language use v2 vocabulary:
    - `narration_voice`: 'female-1', 'female-2', 'male-1', 'male-2'.
    - `narration_language` / `onscreen_text_language`: lowercase keyword
      ('english', 'hindi') or ISO code ('en', 'hi').
    - `video_orientation`: 'horizontal' (16:9) or 'vertical' (9:16).

    Engine + style are mutually exclusive per engine:
    - Canvas (`golpo_video_engine='golpo_canvas'`, the default): use
      `canvas_style_variant` (e.g. 'chalkboard_color', 'whiteboard',
      'illustrations'). `pen_animation_style` and `onscreen_text_language` are
      Canvas-only.
    - Sketch (`golpo_video_engine='golpo_sketch'`): use `sketch_style_variant`
      (e.g. 'classic', 'formal', 'crayon'). Do NOT set canvas-only fields.

    Podcast mode (`enable_podcast_engine=True`) generates audio only — do not
    set any video-pipeline field (engine, orientation, style, watermark, logo,
    etc.); v2 rejects them with a 422.

    Downloads to ~/Golpo/videos/ by default. Override with `output_dir` or set
    the GOLPO_VIDEO_DIR env var. Pass `no_download=True` for URL-only.

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
        # Always safe in both video and podcast modes.
        payload: dict[str, Any] = {
            "prompt": prompt,
            "timing": timing,
            "narration_voice": narration_voice,
            "narration_language": narration_language,
        }
        # add only the keys the user actually set, to avoid forcing defaults
        for k, v in {
            "golpo_video_engine": golpo_video_engine,
            "video_orientation": video_orientation,
            "canvas_style_variant": canvas_style_variant,
            "sketch_style_variant": sketch_style_variant,
            "pen_animation_style": pen_animation_style,
            "onscreen_text_language": onscreen_text_language,
            "custom_script": custom_script,
            "own_narration_source": own_narration_source,
            "reference_source": reference_source,
            "reference_images": reference_images,
            "custom_images": custom_images,
            "custom_images_description": custom_images_description,
            "custom_videos": custom_videos,
            "custom_videos_description": custom_videos_description,
            "background_track": background_track,
            "narration_instructions": narration_instructions,
            "visual_instructions": visual_instructions,
            "scene_pacing": scene_pacing,
            "enable_color": enable_color,
            "watermark": watermark,
            "custom_logo": custom_logo,
            "logo_position": logo_position,
            "visibility": visibility,
            "enable_podcast_engine": enable_podcast_engine,
            "enable_script_only_mode": enable_script_only_mode,
            "language_variants": language_variants,
            "variant_visuals_mode": variant_visuals_mode,
        }.items():
            if v is not None:
                payload[k] = v
        if extra_params:
            payload.update(extra_params)

        sub = client.submit_generate_v2(payload)
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
    """Register the v2 generate_video tool on the given FastMCP instance."""
    mcp.tool(name="generate_video")(generate_video)
