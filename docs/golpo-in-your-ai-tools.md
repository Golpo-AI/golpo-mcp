# Use Golpo from your favorite AI tool

**Make Golpo videos by just talking to your AI assistant.**

If you already use Cursor, Claude, VS Code, or any modern AI coding tool, you can connect Golpo directly. Instead of opening the Golpo website, you ask your AI assistant in plain English — *"make a 30-second video about why the sky is blue"* — and a finished MP4 lands on your computer.

This guide walks you through the setup. It usually takes **2–5 minutes** once you have a Golpo API key.

---

## How it works (in plain English)

Modern AI tools support something called **MCP**. Don't worry about the acronym — all it means is that your AI assistant can plug into outside services. We've published a small Golpo plug-in for it. Once installed, your AI tool can:

- generate Golpo videos from prompts, scripts, audio, or documents,
- save the MP4 to your computer automatically,
- show you a shareable link,
- list and re-download your past videos.

> You won't run a separate program named `mcp` or `golpo`. Some tools use "MCP" in setup menus or CLI subcommands, but after setup you just chat normally — no terminal commands needed for everyday use.

---

## 🔒 Keep your API key safe (please read)

Treat your Golpo API key like a password.

- Never paste it into a public chat, screenshot, support ticket, or shared document.
- Never commit it to a public repo. If you accidentally do, **rotate it immediately** at [video.golpoai.com](https://video.golpoai.com).
- Only install the Golpo MCP server from [the official GitHub repo](https://github.com/Golpo-AI/golpo-mcp) or PyPI — `pypi.org/project/golpo-mcp`.
- When an AI tool asks to run a Golpo tool (especially `generate_video`), glance at the parameters before approving. Most AI tools show you a confirmation dialog the first time.

The MCP server only sends your key to the official Golpo API (`api.golpoai.com`). It never phones home, logs your key, or shares it with third parties — but security is layered, and you owning the key is the first layer.

---

## Step 0 — Get your Golpo API key (one-time, all tools)

1. Go to **[video.golpoai.com](https://video.golpoai.com)** and sign in.
2. Open your account dashboard and copy your **API key**. It's a long string of letters and numbers.
3. Keep it in a notepad — you'll paste it in once, below.

> Don't have a Golpo account yet? Sign up at [video.golpoai.com](https://video.golpoai.com). The API works on the **Scale** plan, the **Business + API add-on** plan, or the **API-Only** plan.

---

## Step 1 — Install `uv` (one-time, all tools)

`uv` is a tiny tool that downloads and runs the Golpo plug-in for you. You only install it once.

### On Mac or Linux

Open the **Terminal** app (Cmd+Space → type "Terminal" → Enter) and paste this:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Close and reopen Terminal. Type `uv --version` to confirm it works — you should see a version number.

### On Windows

Open **PowerShell** (Start menu → type "PowerShell" → Enter) and paste:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Close and reopen PowerShell. Type `uv --version` to confirm.

---

## Step 2 — Pick your AI tool

Click the tool you use:

- [**Cursor**](#cursor) — easiest, one click
- [**Claude Code**](#claude-code) — one command
- [**VS Code** (with GitHub Copilot)](#vs-code-with-github-copilot) — one command or GUI
- [**Claude Desktop (Mac)**](#claude-desktop-mac) — paste a small command
- [**Claude Desktop (Windows)**](#claude-desktop-windows) — paste a small command
- [**Visual Studio** (Windows)](#visual-studio-windows) — paste a small file

After your tool is set up, jump to [**How to use it**](#how-to-use-it).

---

## Cursor

The easiest of all. One click installs everything.

### Steps

1. **Click this link:**

   👉 [**Add Golpo to Cursor**](cursor://anysphere.cursor-deeplink/mcp/install?name=golpo&config=eyJjb21tYW5kIjogInV2eCIsICJhcmdzIjogWyJnb2xwby1tY3AiXSwgImVudiI6IHsiR09MUE9fQVBJX0tFWSI6ICJZT1VSX0tFWV9IRVJFIn19)

2. Your browser will ask "Open in Cursor?" — say **Yes**.
3. Cursor opens with a confirmation dialog. **Replace `YOUR_KEY_HERE` with your Golpo API key**, then click **Install**.
4. **Quit Cursor completely** (`Cmd+Q` on Mac, `Alt+F4` on Windows) and reopen it.
5. Done. Skip to [How to use it](#how-to-use-it).

### Doesn't work? Manual install

If clicking the link doesn't open Cursor, do this instead:

1. In Cursor, press **Cmd+Shift+P** (Mac) or **Ctrl+Shift+P** (Windows/Linux).
2. Type **"MCP"** and pick **"Settings: Open MCP Settings."**
3. Click **"Add Server"** and paste this exactly (replace the key):
   ```json
   {
     "command": "uvx",
     "args": ["golpo-mcp"],
     "env": { "GOLPO_API_KEY": "your-key-here" }
   }
   ```
4. Save, quit Cursor (`Cmd+Q`), reopen.

### Verify it worked

1. Open Cursor's **Settings → MCP**.
2. You should see **`golpo`** with a **green dot** next to it.
3. Click it — six tools listed (generate_video, list_videos, etc.).

---

## Claude Code

Claude Code has a single command that does everything.

### Steps

1. Open Terminal.
2. Paste this, **replacing `your-key-here` with your real Golpo API key**:

   ```bash
   claude mcp add --transport stdio --scope user \
     --env GOLPO_API_KEY=your-key-here \
     golpo -- uvx golpo-mcp
   ```

3. Press Enter. You'll see "Added stdio MCP server golpo."
4. That's it — no restart needed. Skip to [How to use it](#how-to-use-it).

### Verify it worked

```bash
claude mcp list
```

You should see `golpo` with **✓ Connected**.

### To remove later

```bash
claude mcp remove --scope user golpo
```

---

## VS Code (with GitHub Copilot)

**Requirement:** you need **GitHub Copilot** installed and signed in to VS Code. The Golpo plug-in connects through Copilot Chat. If you don't have Copilot, this won't work.

### Steps (one-line)

1. Open Terminal (Mac/Linux) or PowerShell (Windows).
2. Paste this, replacing the key:

   ```bash
   code --add-mcp '{"name":"golpo","command":"uvx","args":["golpo-mcp"],"env":{"GOLPO_API_KEY":"your-key-here"}}'
   ```

3. VS Code opens and asks you to confirm. Click **Install**.
4. Done. Skip to [How to use it](#how-to-use-it).

> If you get *"command not found: code"*, open VS Code first, press `Cmd+Shift+P`, type "Shell Command: Install 'code' command in PATH," then try the command again.

### Steps (using the menu)

If you'd rather click than type:

1. In VS Code, press **Cmd+Shift+P** (Mac) or **Ctrl+Shift+P** (Windows).
2. Type **"MCP: Add Server"** and pick it.
3. Choose **"Command (stdio)"**.
4. Paste this command:
   ```
   uvx golpo-mcp
   ```
5. Name it `golpo`.
6. When asked for environment variables, paste `GOLPO_API_KEY=your-key-here`.
7. Pick **"User"** scope when prompted.

> Tip: VS Code supports `input variables` in MCP config for sensitive values, so you can prompt-at-startup rather than store the key in plaintext. See VS Code's MCP docs if you're setting up a shared workspace.

### Verify it worked

1. Open the **GitHub Copilot Chat** panel (Cmd+Ctrl+I on Mac).
2. Switch the mode dropdown to **Agent**.
3. Click the **🔧 tools** icon above the chat input. You should see six Golpo tools.

---

## Claude Desktop (Mac)

Claude Desktop on Mac doesn't have a one-line CLI. You paste a short command that writes the config file.

### Steps

1. Open Terminal (Cmd+Space → "Terminal" → Enter).
2. Paste this — **all of it at once** — replacing the key:

   ```bash
   GOLPO_API_KEY="your-key-here" python3 - <<'PY'
   import json, os, pathlib
   p = pathlib.Path.home() / "Library/Application Support/Claude/claude_desktop_config.json"
   p.parent.mkdir(parents=True, exist_ok=True)
   cfg = json.loads(p.read_text()) if p.exists() and p.stat().st_size else {}
   cfg.setdefault("mcpServers", {})["golpo"] = {
       "command": "uvx",
       "args": ["golpo-mcp"],
       "env": {"GOLPO_API_KEY": os.environ["GOLPO_API_KEY"]},
   }
   p.write_text(json.dumps(cfg, indent=2) + "\n")
   print(f"OK -> {p}")
   PY
   ```

3. Press Enter. You should see `OK -> /Users/.../claude_desktop_config.json`.
4. **Quit Claude Desktop completely** (`Cmd+Q`) and reopen.
5. Done. Skip to [How to use it](#how-to-use-it).

### Verify it worked

1. In Claude Desktop, look for the **🔌 plug** icon near the chat input.
2. Click it. You should see **Golpo** listed with six tools.

---

## Claude Desktop (Windows)

### Steps

1. Open **PowerShell** (Start menu → type "PowerShell" → Enter).
2. Paste this — **all of it** — replacing the key:

   ```powershell
   $env:GOLPO_API_KEY = "your-key-here"
   python - @"
   import json, os, pathlib
   p = pathlib.Path(os.environ['APPDATA']) / 'Claude' / 'claude_desktop_config.json'
   p.parent.mkdir(parents=True, exist_ok=True)
   cfg = json.loads(p.read_text()) if p.exists() and p.stat().st_size else {}
   cfg.setdefault('mcpServers', {})['golpo'] = {
       'command': 'uvx',
       'args': ['golpo-mcp'],
       'env': {'GOLPO_API_KEY': os.environ['GOLPO_API_KEY']},
   }
   p.write_text(json.dumps(cfg, indent=2) + '\n')
   print(f'OK -> {p}')
   "@
   ```

3. **Quit Claude Desktop completely** (Alt+F4 or right-click tray icon → Quit) and reopen.
4. Done. Skip to [How to use it](#how-to-use-it).

> No Python on Windows? Open `%APPDATA%\Claude\claude_desktop_config.json` in Notepad and paste:
> ```json
> {
>   "mcpServers": {
>     "golpo": {
>       "command": "uvx",
>       "args": ["golpo-mcp"],
>       "env": { "GOLPO_API_KEY": "your-key-here" }
>     }
>   }
> }
> ```

---

## Visual Studio (Windows)

For **Visual Studio 2022 17.14+** with the GitHub Copilot extension. MCP tools require **Agent mode** in Copilot Chat.

### Steps

1. Open **Notepad**.
2. Paste this — replace `your-key-here`:

   ```json
   {
     "servers": {
       "golpo": {
         "type": "stdio",
         "command": "uvx",
         "args": ["golpo-mcp"],
         "env": {
           "GOLPO_API_KEY": "your-key-here"
         }
       }
     }
   }
   ```

3. Save it as `.mcp.json` (with the leading dot) in your user folder — usually `C:\Users\YourName\.mcp.json`.
4. **Restart Visual Studio**.
5. Open Copilot Chat in Visual Studio, switch to **Agent** mode.
6. Done.

---

# How to use it

After install, you don't run any commands. You just chat with your AI tool in **Agent mode**.

> **Important:** in Cursor, VS Code, and Visual Studio, MCP tools only work when the chat is in **Agent mode**. Look for the mode toggle near the chat input. In Claude Code and Claude Desktop, this is automatic.

## Try these prompts

Paste any of these into your AI tool's chat. The AI will figure out which Golpo tool to call and do the rest.

### Make a simple video

> Make a 30-second Golpo video about why the sky is blue.

### Make a vertical short for social

> Make a vertical Golpo short about coffee, with the "Sharpie" style.

### Use your own script

> Here's a script. Make a Golpo video out of it:
>
> Plants are nature's solar panels. Their leaves absorb sunlight, pull water through their roots, and breathe in carbon dioxide. Inside chloroplasts, sunlight powers a chemical reaction that turns water and CO2 into sugar and oxygen.

### Summarize a PDF

> Summarize this PDF as a 1-minute Golpo video: /path/to/report.pdf

### Use your own voice

> Use this audio file as narration for a Golpo video about machine learning: /path/to/voice.mp3

### Browse your videos

> List my last 5 Golpo videos and show their links.

### Re-download a past video

> Download Golpo video with ID 88db3281-...

---

## Where your videos end up

By default, finished MP4s are saved to:

- **Mac/Linux:** `~/Golpo/videos/`
- **Windows:** `C:\Users\YourName\Golpo\videos\`

Filenames look like:
```
20260522-142030_why-is-the-sky-blue_a1b2c3d4.mp4
```
Date and time first (so they sort by recency), then the video title, then a short ID.

To change where they save, just say "save it to my desktop instead" — the AI will use the right folder.

---

## Visual styles you can ask for

You can mix and match. Common requests:

| Want | Just say |
|---|---|
| Whiteboard / sketch look | "make it a sketch" or "Sketch Classic" |
| Cleaner, more polished sketch | "Professional Clean style" |
| Crayon, kid-friendly | "Crayon style" |
| Bold marker drawn | "Sharpie style" |
| Whiteboard with images | "Canvas Whiteboard" |
| Magazine illustration | "Editorial style" |
| Chalkboard | "Chalkboard style" |
| Colorful neon chalkboard | "Chalkboard Color" |
| Modern minimal | "Modern Minimal" |
| Playful, fun | "Playful style" |
| Technical diagrams | "Technical style" |

---

## Languages

Golpo speaks 44+ languages. Just say what you want:

> Make this video in Spanish.
> Hindi narration, English on-screen text.

---

## Background music

If you want a music bed, say so:

> Add lofi music.
> Add documentary background music.

Available: jazz, lofi, whimsical, dramatic, engaging, hyper, inspirational, documentary.

---

# Troubleshooting

| What you see | What it means | Fix |
|---|---|---|
| "I don't see Golpo tools" | The AI tool wasn't restarted after install | Fully quit (Cmd+Q / Alt+F4) and reopen |
| Tools listed but nothing happens when you ask | You're not in Agent mode | Switch the mode dropdown to Agent |
| Red dot next to Golpo in MCP settings | API key wrong or `uv` not installed | Re-check the key. If still red, restart your computer after installing `uv` |
| Error like `missing_credential` | API key wasn't passed through | Re-check the `GOLPO_API_KEY=...` part of your config |
| Error `http_401` | API key is invalid or revoked | Get a fresh key from [video.golpoai.com](https://video.golpoai.com) |
| Error `http_403` | Your plan doesn't include API access | Upgrade to Scale, Business + API add-on, or API-Only |
| First request after install is slow | `uv` is downloading the Golpo plug-in (one-time, ~30 seconds). Subsequent server starts are faster — but **video generation itself still takes the normal generation time** (a 1-minute video still takes ~1 minute to render, regardless of cache). | Wait for the first install; future starts are cached. |
| `cannot find executable 'uvx'` | `uv` was installed but the AI tool can't see it | Close the AI tool, restart your computer, reopen the AI tool |

---

# What does it cost?

The plug-in itself is **free and open-source** ([MIT licensed](https://github.com/Golpo-AI/golpo-mcp/blob/main/LICENSE)). You only pay for the videos you generate, billed by Golpo's normal pricing — **2 credits per minute of generated video** (≈$0.50 for 15 seconds, $2 for a minute). Check your usage at [video.golpoai.com](https://video.golpoai.com).

---

# Need help?

- 🐛 **Bugs or feature requests:** [github.com/Golpo-AI/golpo-mcp/issues](https://github.com/Golpo-AI/golpo-mcp/issues)
- 📚 **Source code & docs:** [github.com/Golpo-AI/golpo-mcp](https://github.com/Golpo-AI/golpo-mcp)
- 📦 **PyPI:** [pypi.org/project/golpo-mcp](https://pypi.org/project/golpo-mcp/)
- 💬 **Support:** founders@golpoai.com
- 📖 **Golpo API docs:** [video.golpoai.com/api-docs](https://video.golpoai.com/api-docs)

Also see: the [Golpo Claude Code skill](https://github.com/Golpo-AI/golpo-claude-skill) if you specifically use Claude Code — it's a parallel package that's a touch more conversational than the MCP server, and they share the same API key file.

---

## Summary cheat-sheet

Pick your tool and follow the one line:

| Tool | One-line install (replace `YOUR_KEY`) |
|---|---|
| **Cursor** | Click [**Add Golpo to Cursor**](cursor://anysphere.cursor-deeplink/mcp/install?name=golpo&config=eyJjb21tYW5kIjogInV2eCIsICJhcmdzIjogWyJnb2xwby1tY3AiXSwgImVudiI6IHsiR09MUE9fQVBJX0tFWSI6ICJZT1VSX0tFWV9IRVJFIn19), paste key, click Install |
| **Claude Code** | `claude mcp add --transport stdio --scope user --env GOLPO_API_KEY=YOUR_KEY golpo -- uvx golpo-mcp` |
| **VS Code** | `code --add-mcp '{"name":"golpo","command":"uvx","args":["golpo-mcp"],"env":{"GOLPO_API_KEY":"YOUR_KEY"}}'` |
| **Claude Desktop (Mac/Win)** | Run the platform-appropriate one-liner from the section above |
| **Visual Studio** | Save the JSON to `%USERPROFILE%\.mcp.json` (see section above) |

After install: **restart the app**, switch to **Agent mode** (if applicable), and start chatting.

> Want this in your team's docs? The page lives at [`github.com/Golpo-AI/golpo-mcp/blob/main/docs/golpo-in-your-ai-tools.md`](https://github.com/Golpo-AI/golpo-mcp/blob/main/docs/golpo-in-your-ai-tools.md) — feel free to link it directly or fork it.
