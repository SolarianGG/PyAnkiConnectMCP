"""MCP server exposing every Anki-Connect API v1 method as a tool."""

from __future__ import annotations

import argparse
import json
import logging
import os
from typing import Any

import anyio
import mcp_types as types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from . import __version__
from .client import DEFAULT_URL, TERMINAL_FAILURE_STATES, AnkiConnectClient, AnkiConnectError
from .spec import DEFAULT_OPERATION_TIMEOUT, TIMEOUT_ARG, WAIT_ARG, MethodSpec, filter_methods, load_methods

logger = logging.getLogger("anki_connect_mcp")

INSTRUCTIONS = """\
Tools map 1:1 to Anki-Connect API v1 methods (tool `decks_create` = method `decks.create`).
Anki Desktop must be running with the Anki-Connect add-on.

- Entity IDs are decimal strings. Reference a deck, preset or note type with exactly one of
  {"id": "..."} or {"name": "..."}.
- Note fields contain HTML; field names are exact. Supplied tags replace the whole tag set.
- Searches use Anki query syntax and are paginated: repeat the same call with `cursor` set to the
  returned `nextCursor` until it is null.
- Validate notes with `notes_validate` before creating them when eligibility matters.
- Store media with `media_store` first and insert the *returned* filename into fields.
- To answer cards use `scheduling_predict` to get a `stateToken`, then `scheduling_answer`.
- Long-running methods return operations; these tools wait for the final result by default.
- Do not retry write calls automatically after a timeout: the write may already have happened.
"""


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _success(result: Any) -> types.CallToolResult:
    return types.CallToolResult(
        content=[types.TextContent(text=_dump(result))],
        structured_content={"result": result},
    )


def _failure(error: dict[str, Any]) -> types.CallToolResult:
    return types.CallToolResult(
        content=[types.TextContent(text=_dump({"error": error}))],
        structured_content={"error": error},
        is_error=True,
    )


def build_tools(methods: list[MethodSpec]) -> list[types.Tool]:
    return [
        types.Tool(
            name=spec.tool_name,
            title=spec.method,
            description=spec.description(),
            input_schema=spec.input_schema(),
            annotations=types.ToolAnnotations(
                title=spec.method,
                read_only_hint=spec.read_only,
                destructive_hint=spec.destructive,
                open_world_hint=False,
            ),
        )
        for spec in methods
    ]


async def execute_tool(client: AnkiConnectClient, spec: MethodSpec, arguments: dict[str, Any]) -> types.CallToolResult:
    params = dict(arguments)
    wait = params.pop(WAIT_ARG, True) if spec.is_operation else False
    timeout = params.pop(TIMEOUT_ARG, DEFAULT_OPERATION_TIMEOUT) if spec.is_operation else 0
    try:
        result = await client.call(spec.method, params)
        if not (wait and isinstance(result, dict) and result.get("operationId")):
            return _success(result)
        operation = await client.wait_for_operation(result["operationId"], timeout=float(timeout))
    except AnkiConnectError as exc:
        return _failure(exc.to_dict())

    state = operation.get("state")
    if state == "succeeded":
        return _success(operation.get("result"))
    if state in TERMINAL_FAILURE_STATES:
        error = dict(operation.get("error") or {"message": f"Operation {state}."})
        error["operation"] = {k: v for k, v in operation.items() if k != "error"}
        return _failure(error)
    # Still pending after the timeout: hand back the record so the caller can poll operations_get.
    return _success(
        {
            "pending": True,
            "note": "Operation is still running; poll operations_get with this operationId.",
            "operation": operation,
        }
    )


def build_server(client: AnkiConnectClient, methods: list[MethodSpec]) -> Server:
    by_tool = {spec.tool_name: spec for spec in methods}
    tools = build_tools(methods)

    async def on_list_tools(ctx: Any, params: types.PaginatedRequestParams | None) -> types.ListToolsResult:
        return types.ListToolsResult(tools=tools)

    async def on_call_tool(ctx: Any, params: types.CallToolRequestParams) -> types.CallToolResult:
        spec = by_tool.get(params.name)
        if spec is None:
            return _failure({"message": f"Unknown tool: {params.name}", "type": "unknownTool"})
        return await execute_tool(client, spec, params.arguments or {})

    return Server(
        "anki-connect",
        version=__version__,
        title="Anki-Connect",
        instructions=INSTRUCTIONS,
        on_list_tools=on_list_tools,
        on_call_tool=on_call_tool,
    )


def _split(value: str | None) -> list[str]:
    return [part.strip() for part in (value or "").split(",") if part.strip()]


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="anki-connect-mcp", description=__doc__)
    parser.add_argument("--url", default=os.environ.get("ANKICONNECT_URL", DEFAULT_URL), help="Anki-Connect API v1 endpoint")
    parser.add_argument("--api-key", default=os.environ.get("ANKICONNECT_API_KEY"), help="Anki-Connect apiKey, if configured")
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.environ.get("ANKICONNECT_TIMEOUT", "60")),
        help="HTTP timeout per request, seconds",
    )
    parser.add_argument(
        "--read-only",
        action="store_true",
        default=_env_flag("ANKI_MCP_READ_ONLY"),
        help="expose only read methods",
    )
    parser.add_argument(
        "--include",
        default=os.environ.get("ANKI_MCP_INCLUDE"),
        help="comma-separated method patterns to expose, e.g. 'decks.*,notes.*'",
    )
    parser.add_argument(
        "--exclude",
        default=os.environ.get("ANKI_MCP_EXCLUDE"),
        help="comma-separated method patterns to hide, e.g. 'application.exit,advanced.*'",
    )
    return parser.parse_args(argv)


async def serve(args: argparse.Namespace) -> None:
    methods = filter_methods(
        load_methods(),
        read_only=args.read_only,
        include=_split(args.include),
        exclude=_split(args.exclude),
    )
    logger.info("Exposing %d Anki-Connect methods from %s", len(methods), args.url)
    async with AnkiConnectClient(args.url, api_key=args.api_key, timeout=args.timeout) as client:
        server = build_server(client, methods)
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=os.environ.get("ANKI_MCP_LOG_LEVEL", "WARNING"))
    anyio.run(serve, parse_args(argv))


if __name__ == "__main__":
    main()
