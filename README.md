# golpo-mcp

[![CI](https://github.com/Golpo-AI/golpo-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/Golpo-AI/golpo-mcp/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)]()
[![PyPI](https://img.shields.io/pypi/v/golpo-mcp.svg)](https://pypi.org/project/golpo-mcp/)

> Model Context Protocol server for the [Golpo](https://video.golpoai.com) AI
> video API. Generate, list, and download Golpo videos from any
> MCP-compatible client — Claude Desktop, Claude Code, Cursor, Continue,
> Zed, Windsurf, or your own.

## What it does

Wraps the Golpo Video API as a set of MCP tools so an LLM (or any MCP
client) can generate and manage videos directly. Same underlying API as the
[Golpo Claude Code skill](https://github.com/Golpo-AI/golpo-claude-skill);
this is the broader-reach packaging.

## Install

### Run-without-install (recommended)

If you have [uv](https://github.com/astral-sh/uv):

```bash
uvx golpo-mcp
```

`uvx` downloads the package on first run, caches it, and re-uses the cache
on subsequent calls.

### Install into your environment

```bash
pip install golpo-mcp
# or
uv pip install golpo-mcp
```

Then run with `golpo-mcp` or `python -m golpo_mcp`.

### From source (for development)

```bash
git clone https://github.com/Golpo-AI/golpo-mcp.git
cd golpo-mcp
uv sync                  # or: pip install -e .[dev]
uv run python -m golpo_mcp
```

## Configure your MCP client

### Claude Desktop

`~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

```json
{
  "mcpServers": {
    "golpo": {
      "command": "uvx",
      "args": ["golpo-mcp"],
      "env": {
        "GOLPO_API_KEY": "your-key-here"
      }
    }
  }
}
```

Restart Claude Desktop after editing. The 6 Golpo tools appear in the tools
menu.

### Claude Code

```bash
claude mcp add golpo --env GOLPO_API_KEY=your-key -- uvx golpo-mcp
```

Or by editing `~/.claude.json` directly:

```json
{
  "mcpServers": {
    "golpo": {
      "command": "uvx",
      "args": ["golpo-mcp"],
      "env": { "GOLPO_API_KEY": "your-key" }
    }
  }
}
```

### Cursor

`~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "golpo": {
      "command": "uvx",
      "args": ["golpo-mcp"],
      "env": { "GOLPO_API_KEY": "your-key" }
    }
  }
}
```

### Any other MCP client

Use the same shape. The server speaks stdio MCP — no special transport.

## API key

Resolution order:

1. `GOLPO_API_KEY` env var (preferred in client configs above)
2. `~/.golpo/api_key` file with mode `0600`

The file location is shared with the Golpo Claude Code skill, so users who
already have that skill authenticated don't need to re-enter the key.

Get a key at [video.golpoai.com](https://video.golpoai.com).

## Tool catalog (v0.1.0)

| Tool | What it does |
|---|---|
| `generate_video` | Submit a job (prompt / script / audio / docs), poll until done, optionally download the MP4. Returns `{job_id, video_id, video_url, video_file, status, params_used}`. |
| `upload_file` | Upload an audio / document / image (≤ 15 MB). Two-step: multipart POST + S3 PUT. Returns `{file_url, …}`. Pass `file_url` into `generate_video`. |
| `list_videos` | List the caller's recent videos. Args: `limit`, `offset`. |
| `get_video` | Fetch metadata for one video; optionally re-download the MP4. Args: `video_id`, `download`, `output_dir`. |
| `check_status` | One-shot status check on an in-flight `job_id`. |
| `status` | Diagnostic: report whether an API key is configured and which source (env / file / none). Doesn't return the key. |

Every tool returns a JSON-serializable dict. Errors come back as
`{error: "...", message: "..."}` instead of crashing the server.

## Examples

In a client connected to the server, an LLM might call:

```jsonc
// Plain prompt, auto-download
generate_video({ "prompt": "Why is the sky blue?", "timing": "0.5" })

// Custom script + Canvas Sharpie + stylus cursor
generate_video({
  "prompt": "Photosynthesis explained simply",
  "new_script": "Plants are nature's solar panels...",
  "use_2_0_style": true,
  "image_style": "marker",
  "pen_style": "stylus",
  "timing": "0.5"
})

// Two-step upload + generate from PDF
upload_file({ "path": "/Users/me/report.pdf" })
// -> { "file_url": "https://...", ... }
generate_video({
  "prompt": "Summarize this report",
  "upload_urls": ["https://..."],
  "timing": "1"
})

// Power-user escape hatch — pass arbitrary fields not in the signature
generate_video({
  "prompt": "Branded promo",
  "extra_params": { "logo": "https://...", "logo_placement": "tr" }
})
```

## Where downloaded videos go

Default: **`~/Golpo/videos/`**. Filename pattern:

```
YYYYMMDD-HHMMSS_<title-slug>_<video-id-short>.mp4
```

Override per call with `output_dir`, or globally with `GOLPO_VIDEO_DIR` env
var. Pass `no_download=True` to skip.

## Visual styles cheat sheet

**Golpo Sketch** (`use_lineart_2_style`):

| Value | Style |
|---|---|
| `false` | Classic (default) |
| `true` | Improved (BETA) |
| `advanced` | Formal |
| `whiteboard` | Dry Erase |
| `modern_minimal` | Professional Clean |
| `storytelling` | Crayon |

**Golpo Canvas** (`use_2_0_style: true`, `image_style`):

| Value | Style |
|---|---|
| `chalkboard_white` | Chalkboard (B/W, default) |
| `neon` | Chalkboard Color |
| `whiteboard` | Whiteboard |
| `modern_minimal` | Modern Minimal |
| `playful` | Playful |
| `technical` | Technical |
| `editorial` | Editorial |
| `marker` | Sharpie |

Canvas-only pen cursors: `pen_style` = `none` | `stylus` | `marker` | `pen`.

> Sketch and Canvas are **mutually exclusive** — pick one engine per video.

## Voices, languages, music

- **Voices** (`style`): `solo-female-3` (default), `solo-female-4`,
  `solo-male-3`, `solo-male-4`.
- **Languages** (`language`): 44+ codes — `en`, `hi`, `es`, `fr`, `de`,
  `pt`, `ja`, `zh`, `ar`, `bn`, `ta`, `ur`, …
- **Background music** (`bg_music`): `jazz`, `lofi`, `whimsical`,
  `dramatic`, `engaging`, `hyper`, `inspirational`, `documentary`.

Canvas additionally supports `display_language` for separating narration
language from on-screen text language.

## Architecture

```
src/golpo_mcp/
├── __init__.py    # __version__
├── __main__.py    # entry point (`golpo-mcp` console script)
├── server.py      # FastMCP instance + @mcp.tool() decorators
├── client.py      # Golpo HTTP client (pure functions, no MCP)
├── auth.py        # API key resolution
└── downloads.py   # MP4 streaming + filename slug logic
```

The package is layered:

- `client.py` is a usable Golpo Python client on its own — `import golpo_mcp.client`
  and call functions directly without MCP.
- `server.py` is a thin MCP wrapper around `client.py`.
- Adding a new tool: drop a `@mcp.tool()` function into `server.py`. Type
  annotations become JSON Schema automatically.

## Extending: adding new tools

```python
# in server.py

@mcp.tool()
def my_new_tool(arg1: str, arg2: int = 42) -> dict:
    """Docstring becomes the tool description seen by the LLM."""
    try:
        return {"ok": True, "echoed": arg1, "n": arg2}
    except Exception as e:
        return _error(e)
```

That's it — the server picks it up at import time. Add a row to the tool
catalog table in this README and ship.

## Pricing

Golpo API: $1 = 1 credit, 2 credits per minute of generated video. Minimum
$200 entry on the API tier. Billing happens server-side; check usage at
[video.golpoai.com](https://video.golpoai.com).

## Related

- **[Golpo Claude Code skill](https://github.com/Golpo-AI/golpo-claude-skill)** —
  the Claude-Code-specific packaging (uses the same auth file).
- **Golpo Video API docs** — https://video.golpoai.com/api-docs/endpoints/v1
- **Payload examples** — https://video.golpoai.com/guide/golpo-ai-video-api-payload-examples
- **MCP spec** — https://modelcontextprotocol.io

## License

MIT.
