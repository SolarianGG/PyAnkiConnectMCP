import json

import anyio
import httpx
from mcp import Client

from anki_connect_mcp.client import AnkiConnectClient
from anki_connect_mcp.server import build_server
from anki_connect_mcp.spec import filter_methods, load_methods


class FakeAnki:
    """Minimal stand-in for the Anki-Connect /api/v1 endpoint."""

    def __init__(self):
        self.requests = []
        self.polls = 0

    def handle(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.requests.append(body)
        method, params, rid = body["method"], body["params"], body["id"]

        def ok(result):
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": rid, "result": result})

        if method == "decks.create":
            return ok({"id": "1700000000000", "name": params["name"], "kind": "normal", "presetId": "1"})
        if method == "notes.get":
            return httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": rid,
                    "error": {"code": 1001, "message": "Note not found.", "data": {"type": "notFound"}},
                },
            )
        if method == "collection.sync":
            return ok({"operationId": "op-1", "method": "collection.sync", "session": "s1"})
        if method == "operations.get":
            self.polls += 1
            record = {"operationId": "op-1", "method": "collection.sync", "session": "s1", "cancellable": False}
            if self.polls < 2:
                return ok({**record, "state": "running"})
            return ok({**record, "state": "succeeded", "result": {"synced": True}})
        if method == "decks.list":
            return httpx.Response(401)
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "?"}})


def run(coro_fn):
    fake = FakeAnki()

    async def main():
        async with AnkiConnectClient(transport=httpx.MockTransport(fake.handle)) as anki:
            async with Client(build_server(anki, load_methods())) as client:
                await coro_fn(client)

    anyio.run(main)
    return fake


def test_lists_all_methods_as_tools():
    async def check(client):
        tools = (await client.list_tools()).tools
        names = {t.name for t in tools}
        assert len(tools) == 95
        assert {"decks_create", "notes_search", "advanced_cards_update", "operations_get"} <= names
        sync = next(t for t in tools if t.name == "collection_sync")
        assert "waitForCompletion" in sync.input_schema["properties"]
        listing = next(t for t in tools if t.name == "decks_list")
        assert listing.annotations.read_only_hint is True

    run(check)


def test_completed_method_sends_jsonrpc_request():
    async def check(client):
        result = await client.call_tool("decks_create", {"name": "Vocabulary"})
        assert not result.is_error
        assert json.loads(result.content[0].text)["name"] == "Vocabulary"

    fake = run(check)
    assert fake.requests == [{"jsonrpc": "2.0", "id": 1, "method": "decks.create", "params": {"name": "Vocabulary"}}]


def test_rpc_error_is_reported_as_tool_error():
    async def check(client):
        result = await client.call_tool("notes_get", {"id": "1"})
        assert result.is_error
        error = json.loads(result.content[0].text)["error"]
        assert error["code"] == 1001 and error["type"] == "notFound"

    run(check)


def test_transport_error_is_reported():
    async def check(client):
        result = await client.call_tool("decks_list", {})
        assert result.is_error
        assert json.loads(result.content[0].text)["error"]["type"] == "unauthorized"

    run(check)


def test_operation_is_awaited_and_mcp_options_are_stripped():
    async def check(client):
        result = await client.call_tool("collection_sync", {"timeoutSeconds": 10})
        assert not result.is_error
        assert json.loads(result.content[0].text) == {"synced": True}

    fake = run(check)
    assert fake.requests[0]["params"] == {}
    assert [r["method"] for r in fake.requests] == ["collection.sync", "operations.get", "operations.get"]


def test_operation_handle_returned_without_waiting():
    async def check(client):
        result = await client.call_tool("collection_sync", {"waitForCompletion": False})
        assert json.loads(result.content[0].text)["operationId"] == "op-1"

    fake = run(check)
    assert len(fake.requests) == 1


def test_filters():
    methods = load_methods()
    read_only = filter_methods(methods, read_only=True)
    assert read_only and all(m.read_only or m.method == "operations.get" for m in read_only)
    decks = filter_methods(methods, include=["decks.*"], exclude=["decks.delete"])
    assert {m.method for m in decks} == {
        "decks.list", "decks.get", "decks.create", "decks.update", "decks.getCounts"
    }


def test_schemas_have_no_unresolved_refs():
    for spec in load_methods():
        assert "$ref" not in json.dumps(spec.input_schema()), spec.method
