# PyAnkiConnectMCP
MCP Server for anki connect

The `anki-connect-mcp` package is an MCP server for the
[Anki-Connect API v1](https://git.sr.ht/~foosoft/anki-connect/tree/master/API_V1.md)
(JSON-RPC 2.0, `POST http://127.0.0.1:8765/api/v1`).

Each of the 95 API methods is exposed as a separate MCP tool: `decks.create` → `decks_create`,
`advanced.cards.update` → `advanced_cards_update`, and so on. Tool input schemas are generated
from the official machine-readable contract `api-v1.schema.json` (bundled with the package), so
parameters, required fields and constraints match the documentation exactly.

## Requirements

- Python 3.11+
- Anki 26.08+ with the Anki-Connect add-on (a version providing API v1) installed and enabled

## Installation

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

## Connecting a client

The server speaks MCP over stdio. The examples below use `/path/to/PyAnkiConnectMCP` for the
directory you cloned the repository into. The executable is
`.venv/bin/anki-connect-mcp` on Linux/macOS and `.venv\Scripts\anki-connect-mcp.exe` on Windows;
`python -m anki_connect_mcp` from the virtual environment works as well.

### Claude Code

```bash
claude mcp add anki -- /path/to/PyAnkiConnectMCP/.venv/bin/anki-connect-mcp
```

### Claude Desktop and other clients

Add the server to `mcpServers` in the client config:

```json
{
  "mcpServers": {
    "anki": {
      "command": "/path/to/PyAnkiConnectMCP/.venv/bin/anki-connect-mcp",
      "env": { "ANKICONNECT_API_KEY": "" }
    }
  }
}
```

### LangGraph

LangChain agents are LangGraph graphs, and LangChain loads MCP tools through `langchain.mcp`
(`langchain[mcp]>=1.4.0`). Install it in your agent's environment:

```bash
pip install "langchain[mcp]" "langchain[anthropic]"
```

Then connect the server and hand its tools to an agent:

```python
import asyncio

from langchain.agents import create_agent
from langchain.mcp import MCPAdapter

CONFIG = {
    "mcpServers": {
        "anki": {
            "command": "/path/to/PyAnkiConnectMCP/.venv/bin/anki-connect-mcp",
            # Any CLI flag from the Configuration table can be passed here.
            "args": ["--include", "decks.*,notes.*,cards.*"],
        },
    }
}


async def main():
    async with MCPAdapter(CONFIG) as adapter:
        tools = await adapter.list_tools()
        agent = create_agent("claude-sonnet-5-5", tools)
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": "Create a deck called Vocabulary."}]}
        )
        print(result["messages"][-1].content)


asyncio.run(main())
```

Notes:

- With a single server the tool names are unchanged (`decks_create`); when the config lists
  several servers, LangChain prefixes them with the config key (`anki_decks_create`).
- `langchain.mcp` is in beta and emits a `LangChainBetaWarning` on import.
- The server process lives as long as the `async with` block; run the agent inside it.
- Pass the API key with `"args": ["--api-key", "..."]` if Anki-Connect requires one.
- `create_agent` returns a compiled LangGraph graph, so the agent can also be used as a node in
  your own `StateGraph`.
- On LangChain versions before 1.4.0, use `MultiServerMCPClient` from the
  `langchain-mcp-adapters` package with `{"anki": {"command": ..., "args": [...], "transport": "stdio"}}`
  and `await client.get_tools()` instead.

## Configuration

| Environment variable | Flag | Default | Purpose |
| --- | --- | --- | --- |
| `ANKICONNECT_URL` | `--url` | `http://127.0.0.1:8765/api/v1` | API v1 endpoint |
| `ANKICONNECT_API_KEY` | `--api-key` | — | `apiKey` from the add-on settings (sent as `Authorization: Bearer`) |
| `ANKICONNECT_TIMEOUT` | `--timeout` | `60` | HTTP timeout per request, seconds |
| `ANKI_MCP_READ_ONLY` | `--read-only` | off | Expose only read methods (plus `operations_get`) |
| `ANKI_MCP_INCLUDE` | `--include` | all | Comma-separated method patterns, e.g. `decks.*,notes.*` |
| `ANKI_MCP_EXCLUDE` | `--exclude` | — | Hide methods, e.g. `application.exit,advanced.*` |
| `ANKI_MCP_LOG_LEVEL` | — | `WARNING` | Log level (logs go to stderr) |

If your client struggles with a large number of tools, narrow the set with `--include`.

## How it works

- **Errors.** JSON-RPC errors are returned as a tool result with `isError: true` and the fields
  `code`, `type` (`notFound`, `validationFailed`, `staleSession`, …), `message` and `data`.
  HTTP rejections (401/403/405/413) and an unreachable Anki are also turned into clear errors.
- **Long-running operations.** Methods with `Completion: operation` (`collection.sync`,
  `packages.import`, `browser.open`, `api.execute`, …) return a handle. The server polls
  `operations.get` itself and returns the final result. These tools accept two extra arguments
  that are not sent to Anki:
  - `waitForCompletion` (default `true`) — `false` returns the handle immediately;
  - `timeoutSeconds` (default `300`) — when it expires, the pending operation record is
    returned; the work in Anki is not cancelled.
- **Annotations.** `readOnlyHint` is set for methods with `effect: read`, and `destructiveHint`
  for methods that delete or overwrite data. Clients use these hints to ask for confirmation.
- Write requests are never retried automatically (the documentation states explicitly that a
  request ID is not an idempotency key).

## Updating the schema

When a new API version is released, replace `src/anki_connect_mcp/api-v1.schema.json` with
`api-v1.schema.json` from the Anki-Connect repository — new methods will appear automatically.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
.\.venv\Scripts\python.exe -m pytest
```
