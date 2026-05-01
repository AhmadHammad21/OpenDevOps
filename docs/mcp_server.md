# MCP Server

OpenDevOps Agent exposes itself as an [MCP (Model Context Protocol)](https://modelcontextprotocol.io) server, so it can be driven directly from Claude Desktop, Cursor, or any MCP-compatible client — no web UI needed.

## Tools exposed

| Tool | Description |
|---|---|
| `investigate` | Full root-cause investigation — runs the agent with all 19 AWS tools, returns a structured report |
| `ask` | Freeform Q&A with AWS context — no structured output, just a direct answer |
| `list_sessions` | Lists recent investigation sessions from the database |

---

## Claude Desktop setup

### 1. Find the config file

| OS | Path |
|---|---|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |

### 2. Add the server

```json
{
  "mcpServers": {
    "opendevops": {
      "command": "uv",
      "args": [
        "--directory", "/absolute/path/to/OpenDevOps",
        "run", "devops-agent", "mcp"
      ]
    }
  }
}
```

Replace `/absolute/path/to/OpenDevOps` with the actual repo path. On Windows use forward slashes or escaped backslashes:
```json
"args": ["--directory", "D:/Github Repos/OpenDevOps", "run", "devops-agent", "mcp"]
```

### 3. Restart Claude Desktop

The server starts automatically when Claude Desktop launches. You'll see `opendevops` in the tools panel.

### 4. Use it

```
Investigate high error rate on my payment Lambda
```
```
Ask why would an ECS task keep restarting?
```

---

## Cursor / other MCP clients (HTTP transport)

For clients that connect over HTTP instead of stdio:

```bash
uv run devops-agent mcp --http --port 8001
```

Then point your MCP client at: `http://localhost:8001/sse`

---

## Transport modes

| Mode | Command | Use case |
|---|---|---|
| **stdio** (default) | `devops-agent mcp` | Claude Desktop, Cursor local |
| **HTTP + SSE** | `devops-agent mcp --http` | Remote clients, multiple users |

---

## Source files

| File | Purpose |
|---|---|
| `src/mcp_server.py` | FastMCP server — tool definitions and agent wiring |
| `src/cli/mcp.py` | CLI command that starts the server |
