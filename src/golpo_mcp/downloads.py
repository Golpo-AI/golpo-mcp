"""Stream a finished Golpo video to disk with a readable filename."""

from __future__ import annotations

import os
import pathlib
import re
from datetime import datetime
from typing import Optional

import requests

DEFAULT_VIDEO_DIR = pathlib.Path.home() / "Golpo" / "videos"

# Only ever write media extensions to disk. A crafted/redirected download URL
# must not be able to drop an executable or script onto the user's machine.
ALLOWED_EXTENSIONS = {
    ".mp4", ".mov", ".webm", ".mkv", ".m4v",
    ".mp3", ".m4a", ".wav", ".aac", ".ogg", ".flac",
}


def slugify(text: str | None, max_len: int = 50) -> str:
    if not text:
        return "video"
    s = re.sub(r"[^a-zA-Z0-9\s-]", "", text)
    s = re.sub(r"\s+", "-", s.strip()).lower()
    s = s[:max_len].rstrip("-")
    return s or "video"


def resolve_output_dir(override: str | None = None) -> pathlib.Path:
    """CLI/tool arg > GOLPO_VIDEO_DIR env > ~/Golpo/videos/."""
    if override:
        return pathlib.Path(override).expanduser()
    env = os.environ.get("GOLPO_VIDEO_DIR")
    if env:
        return pathlib.Path(env).expanduser()
    return DEFAULT_VIDEO_DIR


def download_video(
    video_url: str,
    output_dir: str | pathlib.Path,
    *,
    title: str | None = None,
    video_id: str | None = None,
) -> Optional[pathlib.Path]:
    """Stream a video to disk. Returns the absolute Path on success, None on failure.

    Filename: YYYYMMDD-HHMMSS_<title-slug>_<video-id-short>.mp4
    """
    out_dir = pathlib.Path(output_dir).expanduser()
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    parts = [ts, slugify(title) if title else "video"]
    if video_id:
        # slugify strips path separators, so a hostile title/id can't traverse.
        parts.append(slugify(str(video_id)[:8]))
    ext = pathlib.Path(video_url.split("?", 1)[0]).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        ext = ".mp4"
    out_path = out_dir / ("_".join(parts) + ext)

    # Defense in depth: the assembled filename must stay inside out_dir.
    try:
        out_path.resolve().relative_to(out_dir.resolve())
    except ValueError:
        return None

    try:
        with requests.get(video_url, stream=True, timeout=600) as r:
            r.raise_for_status()
            with out_path.open("wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
    except Exception:
        if out_path.exists():
            try:
                out_path.unlink()
            except OSError:
                pass
        return None
    return out_path.resolve()
