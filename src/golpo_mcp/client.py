"""Golpo HTTP API client.

Pure HTTP, no MCP. The MCP layer in `server.py` calls these functions; they
also work as a standalone library if anyone wants to import the package and
use it directly.
"""

from __future__ import annotations

import os
import time
from typing import Any

import requests

from .auth import get_key

API_BASE_DEFAULT = "https://api.golpoai.com/api/v1"
TERMINAL_OK = {"completed", "ready", "done", "success", "finished"}
TERMINAL_FAIL = {"failed", "error", "errored", "cancelled", "canceled"}

# Fields that the Golpo API requires as strings even though they look numeric/bool.
STRING_COERCE_FIELDS = {"timing", "use_lineart_2_style"}


def api_base() -> str:
    return os.environ.get("GOLPO_API_BASE", API_BASE_DEFAULT)


class GolpoAPIError(RuntimeError):
    """Wraps any non-2xx response from the Golpo API with structured info."""

    def __init__(self, status_code: int, body: Any, message: str | None = None):
        self.status_code = status_code
        self.body = body
        super().__init__(message or f"HTTP {status_code}: {body!r}")


def _coerce_string_fields(payload: dict) -> dict:
    """Force the API's stringly-typed fields to be lowercase strings."""
    for f in STRING_COERCE_FIELDS:
        v = payload.get(f)
        if v is None:
            continue
        if isinstance(v, bool):
            payload[f] = "true" if v else "false"
        elif not isinstance(v, str):
            payload[f] = str(v)
    return payload


def request(
    method: str,
    path: str,
    *,
    json_body: dict | None = None,
    files: Any = None,
    data: Any = None,
    timeout: int = 120,
    retry_5xx: bool = False,
    max_retries: int = 5,
) -> Any:
    """Make a request to the Golpo API. Returns parsed JSON or raises GolpoAPIError."""
    url = api_base() + path
    headers = {"x-api-key": get_key()}
    if json_body is not None:
        headers["Content-Type"] = "application/json"

    attempt = 0
    while True:
        attempt += 1
        try:
            r = requests.request(
                method, url,
                headers=headers, json=json_body, files=files, data=data,
                timeout=timeout,
            )
        except requests.exceptions.RequestException as e:
            if retry_5xx and attempt < max_retries:
                time.sleep(min(2 ** attempt, 30))
                continue
            raise GolpoAPIError(0, str(e), f"network failure: {e}") from e

        if retry_5xx and 500 <= r.status_code < 600 and attempt < max_retries:
            time.sleep(min(2 ** attempt, 30))
            continue
        break

    if not r.ok:
        try:
            body: Any = r.json()
        except Exception:
            body = r.text
        raise GolpoAPIError(r.status_code, body)

    try:
        return r.json()
    except Exception:
        return {"raw": r.text}


def upload(path: str) -> dict:
    """Two-step file upload: multipart POST to /videos/upload-file, then PUT to S3.

    Returns {file_url, upload_url, file_name, content_type, put_status}.
    """
    import pathlib
    p = pathlib.Path(path).expanduser()
    if not p.is_file():
        raise FileNotFoundError(f"upload source not found: {p}")
    size_mb = p.stat().st_size / (1024 * 1024)
    if size_mb > 15:
        raise ValueError(f"file is {size_mb:.1f} MB; Golpo upload limit is 15 MB")

    url = api_base() + "/videos/upload-file"
    headers = {"x-api-key": get_key()}
    with p.open("rb") as f:
        files = {"file": (p.name, f)}
        r = requests.post(url, headers=headers, files=files, timeout=300)
    if not r.ok:
        try:
            body = r.json()
        except Exception:
            body = r.text
        raise GolpoAPIError(r.status_code, body)
    out = r.json()

    put_status = None
    upload_url = out.get("upload_url")
    if upload_url:
        content_type = out.get("content_type") or "application/octet-stream"
        with p.open("rb") as f:
            pr = requests.put(
                upload_url,
                data=f,
                headers={"Content-Type": content_type},
                timeout=600,
            )
        if not pr.ok:
            raise GolpoAPIError(pr.status_code, pr.text[:500])
        put_status = pr.status_code

    return {
        "file_url": out.get("file_url"),
        "upload_url": upload_url,
        "file_name": out.get("file_name"),
        "content_type": out.get("content_type"),
        "put_status": put_status,
    }


def generate(payload: dict) -> dict:
    """Submit a generate job. Returns the API response (job_id, video_id, status)."""
    if "prompt" not in payload and "audio_clip" not in payload:
        raise ValueError("at least one of `prompt` or `audio_clip` is required")
    _coerce_string_fields(payload)
    return request("POST", "/videos/generate", json_body=payload)


def status_of(job_id: str) -> dict:
    """One-shot status check for a job."""
    return request("GET", f"/videos/status/{job_id}", retry_5xx=True)


def poll_until_terminal(
    job_id: str,
    *,
    max_wait_seconds: int = 5400,
    progress_cb=None,
) -> dict:
    """Poll /videos/status/{job_id} with exponential backoff until terminal.

    Returns the final status payload. progress_cb (optional) is invoked with the
    raw status dict on each poll so callers can stream progress.
    """
    delay = 5.0
    deadline = time.time() + max_wait_seconds
    while time.time() < deadline:
        st = status_of(job_id)
        if progress_cb is not None:
            try:
                progress_cb(st)
            except Exception:
                pass
        status = (st.get("status") or "").strip().lower()
        if status in TERMINAL_OK or st.get("video_url"):
            return st
        if status in TERMINAL_FAIL:
            raise GolpoAPIError(0, st, f"job failed: {st.get('status')}")
        time.sleep(delay)
        delay = min(delay * 1.5, 30.0)
    raise TimeoutError(
        f"timed out after {max_wait_seconds}s polling job {job_id}; "
        f"the job may still be running — resume with status_of({job_id!r})"
    )


def get_video(video_id: str) -> dict:
    """GET /videos/{id}. Returns the unwrapped video dict (handles both flat and {'video': {...}} envelopes)."""
    raw = request("GET", f"/videos/{video_id}")
    if isinstance(raw, dict):
        return raw.get("video", raw) or {}
    return {}


def list_videos(limit: int | None = None, offset: int | None = None) -> dict:
    """GET /videos. Returns the raw response (typically {videos: [...], total: N})."""
    qs: list[str] = []
    if limit is not None:
        qs.append(f"limit={limit}")
    if offset is not None:
        qs.append(f"offset={offset}")
    suffix = ("?" + "&".join(qs)) if qs else ""
    return request("GET", f"/videos{suffix}")


# Curated fields kept by `list_videos` summarization. Each entry shrinks from
# ~30 keys / ~25 KB down to ~13 keys / ~1 KB, surfaces URLs prominently, and
# drops the noisy fields (transcript, request_payload, frame_image_urls, ...).
LIST_SUMMARY_FIELDS = (
    "id",
    "title",
    "prompt",
    "status",
    "video_url",        # presigned, expires in ~7 days; download-ready now
    "video_filename",   # bare, persistent URL; safe to share long-term
    "thumbnail_url",
    "video_duration",
    "video_type",
    "scenes",
    "is_public",
    "ispodcast",
    "created_at",
    "updated_at",
)


def summarize_video_entry(v: dict) -> dict:
    """Project a raw /videos list entry down to the fields that matter."""
    return {k: v.get(k) for k in LIST_SUMMARY_FIELDS if k in v}
