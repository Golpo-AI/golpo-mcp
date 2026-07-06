"""Diagnostic: print the raw status the backend returns for a job.

Usage:
    export GOLPO_API_KEY=your-key
    python tests/check_job.py <job_id>              # uses default version (v2)
    GOLPO_API_VERSION=v1 python tests/check_job.py <job_id>

Tells us exactly what `status` the backend reports (so we know why polling
does/doesn't terminate) and confirms the locally-loaded code is fresh.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from golpo_mcp import client  # noqa: E402

if len(sys.argv) < 2:
    print("usage: python tests/check_job.py <job_id>")
    raise SystemExit(2)

job_id = sys.argv[1]
print("loaded from   :", client.__file__)
print("api_base      :", client.api_base())
print("TERMINAL_OK   :", sorted(client.TERMINAL_OK))
print("has script_ready:", "script_ready" in client.TERMINAL_OK)
print(f"\nraw status for {job_id}:")
try:
    raw = client.status_of(job_id)
    print(json.dumps(raw, indent=2, default=str))
    st = (raw.get("status") or "").strip().lower()
    print("\nwould poller stop? ->",
          st in client.TERMINAL_OK or bool(raw.get("video_url")),
          f"(status={st!r}, has video_url={bool(raw.get('video_url'))})")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
