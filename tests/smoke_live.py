"""Live smoke test — hits the REAL Golpo API. Requires a valid API key.

Exercises both the v1 and v2 pipelines end-to-end by rendering a short
**15-second classic (Golpo Sketch) video**, proving the full round-trip:
payload accepted, job created, polled until a video_url is returned.

Note: this renders a real video and spends credits (~15s of video). A full
render can take several minutes.

Usage:
    export GOLPO_API_KEY=your-key           # or put it in ~/.golpo/api_key
    python tests/smoke_live.py              # test both v1 and v2
    python tests/smoke_live.py v2           # test only v2
    python tests/smoke_live.py v1           # test only v1

Exit code 0 = all tested versions passed, 1 = at least one failed.
This is NOT part of the pytest suite (it needs a key + network); run it by hand.
"""

from __future__ import annotations

import os
import sys

# make `golpo_mcp` importable when run straight from the repo (src/ layout)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from golpo_mcp import client  # noqa: E402


def _run(version: str) -> bool:
    os.environ["GOLPO_API_VERSION"] = version
    # import lazily AFTER setting the version so any import-time reads are correct
    from golpo_mcp import generate_v1, generate_v2

    print(f"\n=== {version.upper()}  (base: {client.api_base()}) ===")
    print("  submitting a 15s classic video + polling until the render "
          "completes (can take several minutes; not frozen)...", flush=True)
    prompt = "Why is the sky blue? Keep it to one short sentence."
    if version == "v2":
        # Golpo Sketch engine, 'classic' style variant, 15s (0.25 min).
        out = generate_v2.generate_video(
            prompt, timing="0.25",
            golpo_video_engine="golpo_sketch", sketch_style_variant="classic",
            no_download=True, max_wait_seconds=1800,
        )
    else:
        # v1: use_lineart_2_style='false' is the classic Sketch style; 15s.
        out = generate_v1.generate_video(
            prompt, timing="0.25", use_lineart_2_style="false",
            no_download=True, max_wait_seconds=1800,
        )

    if out.get("error"):
        print(f"  FAIL: {out.get('error')} — {out.get('message')}")
        if out.get("body"):
            print(f"        body: {out['body']}")
        return False

    ok = bool(out.get("video_url"))
    print(f"  job_id    : {out.get('job_id')}")
    print(f"  status    : {out.get('status')}")
    print(f"  video_url : {'present' if ok else 'MISSING'}")
    print(f"  {'PASS' if ok else 'FAIL'}: "
          f"{'video rendered' if ok else 'no video_url returned'} on {version}")
    return ok


def main() -> int:
    versions = sys.argv[1:] or ["v1", "v2"]
    bad = [v for v in versions if v not in ("v1", "v2")]
    if bad:
        print(f"unknown version(s): {bad}; use v1 and/or v2")
        return 2

    # Fail fast with a clear message if no key is configured.
    try:
        from golpo_mcp.auth import get_key
        get_key()
    except Exception as e:
        print(f"no API key: {e}")
        return 2

    results = {v: _run(v) for v in versions}
    print("\n--- summary ---")
    for v, ok in results.items():
        print(f"  {v}: {'PASS' if ok else 'FAIL'}")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
