"""Builds MCP tool definitions from the official Anki-Connect API v1 schema.

The bundled ``api-v1.schema.json`` is the machine-readable contract published
alongside API_V1.md. Every method in ``x-methods`` becomes one MCP tool whose
input schema is the method's ``params`` schema with all ``$ref``s inlined.
"""

from __future__ import annotations

import copy
import fnmatch
import json
from dataclasses import dataclass
from importlib import resources
from typing import Any

from . import arguments

SCHEMA_FILE = "api-v1.schema.json"

# Extra MCP-only arguments for methods whose completion is "operation".
# They are stripped before the request is sent to Anki-Connect.
WAIT_ARG = "waitForCompletion"
TIMEOUT_ARG = "timeoutSeconds"
DEFAULT_OPERATION_TIMEOUT = 300.0

_DESTRUCTIVE_WORDS = ("delete", "reset", "replace", "convert", "exit", "import", "undo")


@dataclass(frozen=True)
class MethodSpec:
    method: str
    tool_name: str
    summary: str
    notes: str
    scope: str
    effect: str
    completion: str
    undo: str
    errors: tuple[str, ...]
    params_schema: dict[str, Any]

    @property
    def is_operation(self) -> bool:
        return self.completion == "operation"

    @property
    def read_only(self) -> bool:
        return self.effect == "read"

    @property
    def destructive(self) -> bool:
        if self.read_only:
            return False
        if self.effect in ("advancedWrite", "lifecycle"):
            return True
        name = self.method.rsplit(".", 1)[-1].lower()
        return any(word in name for word in _DESTRUCTIVE_WORDS)

    def input_schema(self) -> dict[str, Any]:
        schema = copy.deepcopy(self.params_schema)
        for name, prop in schema.get("properties", {}).items():
            text = arguments.describe(self.method, name)
            if text:
                # Replaces generic type notes inherited from $defs (e.g. EntityId).
                prop["description"] = text
        if self.is_operation:
            props = schema.setdefault("properties", {})
            props[WAIT_ARG] = {
                "type": "boolean",
                "default": True,
                "description": (
                    "MCP option (not sent to Anki): poll operations.get until the operation "
                    "finishes and return its final record. If false, return the operation handle."
                ),
            }
            props[TIMEOUT_ARG] = {
                "type": "number",
                "exclusiveMinimum": 0,
                "default": DEFAULT_OPERATION_TIMEOUT,
                "description": (
                    "MCP option (not sent to Anki): how long to wait for completion. "
                    "A timeout does not cancel the work; the pending record is returned."
                ),
            }
        return schema

    def description(self) -> str:
        parts = [self.summary]
        if self.notes:
            parts.append(self.notes)
        parts.append(
            f"Anki-Connect method `{self.method}`. Scope: {self.scope}. Effect: {self.effect}. "
            f"Completion: {self.completion}. Undo: {self.undo}."
        )
        if self.is_operation:
            parts.append(
                "Long-running operation: by default the server waits for the final result "
                f"(see `{WAIT_ARG}` / `{TIMEOUT_ARG}`)."
            )
        if self.errors:
            parts.append("Possible errors: " + ", ".join(self.errors) + ".")
        return "\n\n".join(parts)


def tool_name_for(method: str) -> str:
    """``decks.create`` -> ``decks_create`` (MCP clients restrict tool names to [A-Za-z0-9_-])."""
    return method.replace(".", "_")


def load_schema() -> dict[str, Any]:
    text = resources.files(__package__).joinpath(SCHEMA_FILE).read_text(encoding="utf-8")
    return json.loads(text)


def _inline_refs(node: Any, defs: dict[str, Any], stack: tuple[str, ...] = ()) -> Any:
    if isinstance(node, list):
        return [_inline_refs(item, defs, stack) for item in node]
    if not isinstance(node, dict):
        return node
    ref = node.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/$defs/"):
        name = ref.removeprefix("#/$defs/")
        if name in stack:
            raise ValueError(f"Recursive schema reference: {' -> '.join((*stack, name))}")
        target = _inline_refs(defs[name], defs, (*stack, name))
        siblings = {k: _inline_refs(v, defs, stack) for k, v in node.items() if k != "$ref"}
        if not siblings:
            return target
        if isinstance(target, dict) and not set(siblings) & set(target):
            return {**target, **siblings}
        return {"allOf": [target], **siblings}
    return {key: _inline_refs(value, defs, stack) for key, value in node.items()}


def load_methods(schema: dict[str, Any] | None = None) -> list[MethodSpec]:
    schema = schema or load_schema()
    defs = schema["$defs"]
    methods: list[MethodSpec] = []
    seen: dict[str, str] = {}
    for method, entry in schema["x-methods"].items():
        tool_name = tool_name_for(method)
        if tool_name in seen:
            raise ValueError(f"Tool name collision: {method} and {seen[tool_name]}")
        seen[tool_name] = method
        params_schema = _inline_refs(entry["params"], defs)
        if params_schema.get("type") != "object":
            raise ValueError(f"Params schema of {method} is not an object schema")
        methods.append(
            MethodSpec(
                method=method,
                tool_name=tool_name,
                summary=entry.get("summary", ""),
                notes=entry.get("notes", ""),
                scope=entry.get("scope", ""),
                effect=entry.get("effect", ""),
                completion=entry.get("completion", "completed"),
                undo=entry.get("undo", ""),
                errors=tuple(entry.get("errors", ())),
                params_schema=params_schema,
            )
        )
    return methods


def filter_methods(
    methods: list[MethodSpec],
    *,
    read_only: bool = False,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
) -> list[MethodSpec]:
    """Select methods by effect and by fnmatch patterns over method names (e.g. ``decks.*``)."""

    def matches(method: str, patterns: list[str]) -> bool:
        return any(fnmatch.fnmatchcase(method, p) for p in patterns)

    selected = []
    for spec in methods:
        if read_only and not spec.read_only and spec.method != "operations.get":
            continue
        if include and not matches(spec.method, include):
            continue
        if exclude and matches(spec.method, exclude):
            continue
        selected.append(spec)
    return selected
