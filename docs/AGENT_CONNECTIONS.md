# Agent Connection Guide

Last researched: 2026-07-15.

GFI Scout is an MCP server. AI agents connect to it either by launching it as a local
stdio process, or by connecting to a local Streamable HTTP/SSE endpoint.

Use stdio for local desktop/CLI agents unless you specifically need a URL. Use
Streamable HTTP for clients that prefer a local `http://127.0.0.1:8000/mcp` endpoint.

## Prerequisites

From the project root:

```powershell
uv sync
Copy-Item .env.example .env
# Edit .env and set GITHUB_TOKEN to a read-only GitHub PAT with public_repo scope.
```

On macOS/Linux, use `cp .env.example .env` instead of `Copy-Item`.

The examples below use a placeholder Windows project path:

```text
C:\path\to\gfi-scout
```

Replace it with the absolute path to your own checkout.

## Localhost Server

Start a local Streamable HTTP MCP endpoint:

```powershell
uv run gfi-scout --transport streamable-http --host 127.0.0.1 --port 8000
```

The MCP endpoint is:

```text
http://127.0.0.1:8000/mcp
```

For the older SSE transport:

```powershell
uv run gfi-scout --transport sse --host 127.0.0.1 --port 8000
```

The SSE endpoint is:

```text
http://127.0.0.1:8000/sse
```

To inspect tools in a browser UI, run the MCP Inspector:

```powershell
uv run mcp dev src/gfi_scout/server.py
```

## Shared stdio Command

Most local agents can launch this server directly:

```json
{
  "command": "uv",
  "args": ["run", "--directory", "C:\\path\\to\\gfi-scout", "gfi-scout"]
}
```

Keep `GITHUB_TOKEN` in `.env` at the project root. Passing `--directory` is important
because the server loads `.env` from its working directory.

## OpenAI Codex

Codex supports MCP in both the CLI and IDE extension, and stores MCP config in
`~/.codex/config.toml` or project-scoped `.codex/config.toml`.

### stdio

```toml
[mcp_servers.gfi_scout]
command = "uv"
args = ["run", "--directory", "C:\\path\\to\\gfi-scout", "gfi-scout"]
```

### Streamable HTTP

Start the localhost server first, then add:

```toml
[mcp_servers.gfi_scout]
url = "http://127.0.0.1:8000/mcp"
```

Verify inside Codex with `/mcp` or from the CLI with:

```powershell
codex mcp list
```

Source: [OpenAI Codex MCP docs](https://developers.openai.com/codex/mcp).

## Claude Code

Claude Code supports local, project, and user scopes. Project scope writes a shared
`.mcp.json`; local/user scopes are private in `~/.claude.json`.

Pick the scope that matches how you want to use the server:

| Scope | Available where | Best for |
|---|---|---|
| **user** | Every Claude Code session on this machine, any folder | Daily driver — recommended |
| **project** | Anyone who opens this repo | Sharing with collaborators |
| **local** | Just you, only inside this repo | Quick local testing |

### User scope (run from anywhere) — recommended

Requires `uv tool install .` from the repo root first so the `gfi-scout`
executable is on your `PATH` (see [`SETUP.md`](SETUP.md)).

```powershell
# Windows (PowerShell)
claude mcp add --scope user gfi-scout "C:\Users\<you>\.local\bin\gfi-scout.exe" -e GITHUB_TOKEN=<your_token>
```

```bash
# macOS / Linux
claude mcp add --scope user gfi-scout "$(which gfi-scout)" -e GITHUB_TOKEN=<your_token>
```

After this, open Claude Code in *any* directory — `gfi-scout` auto-launches as
a stdio subprocess. No manual start command needed. Use `/mcp` inside the
session to inspect status, or `claude mcp list` from any terminal.

### Project / local scope (from the repo)

Run from this project:

```powershell
claude mcp add-json gfi-scout '{"type":"stdio","command":"uv","args":["run","--directory","C:\\path\\to\\gfi-scout","gfi-scout"]}' --scope local
claude mcp list
```

Inside Claude Code, run:

```text
/mcp
```

### Project `.mcp.json`

```json
{
  "mcpServers": {
    "gfi-scout": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "--directory", "C:\\path\\to\\gfi-scout", "gfi-scout"]
    }
  }
}
```

Source: [Claude Code MCP docs](https://code.claude.com/docs/en/mcp).

## Cursor

Cursor reads project MCP config from `.cursor/mcp.json` and global config from
`~/.cursor/mcp.json`.

### stdio

Create `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "gfi-scout": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "--directory", "C:\\path\\to\\gfi-scout", "gfi-scout"]
    }
  }
}
```

### Streamable HTTP

Start the localhost server first, then use:

```json
{
  "mcpServers": {
    "gfi-scout": {
      "url": "http://127.0.0.1:8000/mcp"
    }
  }
}
```

Source: [Cursor MCP docs](https://docs.cursor.com/advanced/model-context-protocol).

## Google Antigravity

Antigravity exposes MCP management from the Agent Panel. Open the Agent Panel,
choose the top-right `...`, select `Manage MCP Servers`, then choose `View raw config`
to edit `mcp_config.json`.

### stdio

```json
{
  "mcpServers": {
    "gfi-scout": {
      "command": "uv",
      "args": ["run", "--directory", "C:\\path\\to\\gfi-scout", "gfi-scout"]
    }
  }
}
```

### Streamable HTTP

Start the localhost server first. Antigravity examples commonly use `serverUrl`:

```json
{
  "mcpServers": {
    "gfi-scout": {
      "serverUrl": "http://127.0.0.1:8000/mcp"
    }
  }
}
```

Note: I found current third-party documentation for Antigravity's MCP config path and
shape, but not a Google-hosted reference page for custom local MCP JSON. If the UI
rejects `serverUrl`, use the stdio form above or the MCP Store's custom-server flow.

Source: [HasMCP Antigravity setup guide](https://docs.hasmcp.com/ai-tools/antigravity).

## Pi Agent

Pi's MCP adapter prefers shared project config in `.mcp.json`; it also reads global
`~/.config/mcp/mcp.json`, Pi global `~/.pi/agent/mcp.json`, and project `.pi/mcp.json`.

### `.mcp.json`

```json
{
  "mcpServers": {
    "gfi-scout": {
      "command": "uv",
      "args": ["run", "--directory", "C:\\path\\to\\gfi-scout", "gfi-scout"],
      "lifecycle": "lazy"
    }
  }
}
```

### Streamable HTTP

```json
{
  "mcpServers": {
    "gfi-scout": {
      "url": "http://127.0.0.1:8000/mcp",
      "lifecycle": "lazy"
    }
  }
}
```

Use `/mcp` in Pi to inspect status.

Source: [Pi MCP adapter docs](https://pi.dev/packages/pi-mcp-adapter).

## Hermes Agent

Hermes uses YAML under `mcp_servers`. Configure it in `~/.hermes/config.yaml` or
your active Hermes profile config.

### stdio

```yaml
mcp_servers:
  gfi-scout:
    command: "uv"
    args: ["run", "--directory", "C:\\path\\to\\gfi-scout", "gfi-scout"]
    enabled: true
    timeout: 120
    connect_timeout: 60
```

### Streamable HTTP

Start the localhost server first, then use:

```yaml
mcp_servers:
  gfi-scout:
    url: "http://127.0.0.1:8000/mcp"
    enabled: true
    timeout: 120
    connect_timeout: 60
```

Reload Hermes MCP config with:

```text
/reload-mcp
```

Source: [Hermes MCP config reference](https://hermes-agent.nousresearch.com/docs/reference/mcp-config-reference/).

## Smoke Test Prompts

After connecting, ask your agent:

```text
Use gfi-scout to find 5 Python good first issues in repositories with at least 500 stars.
```

```text
Use gfi-scout to check the contributor health of fastapi/fastapi.
```

Expected tools:

- `find_issues`
- `check_repo_health`
- `check_issue_status`
- `get_contribution_guide`

## Troubleshooting

| Symptom | Fix |
|---|---|
| Server starts but tool calls fail with missing `GITHUB_TOKEN` | Confirm `.env` exists in the project root and your config uses `uv run --directory <project-path> gfi-scout`. |
| Agent shows no tools | Restart/reload the agent, then inspect MCP status with `/mcp`, `/reload-mcp`, or the agent's MCP settings screen. |
| HTTP connection fails | Confirm the localhost server is still running and that the client uses `http://127.0.0.1:8000/mcp` for Streamable HTTP. |
| Path fails on Windows | Keep the command and each argument as separate JSON array entries; do not paste one quoted command string. |
