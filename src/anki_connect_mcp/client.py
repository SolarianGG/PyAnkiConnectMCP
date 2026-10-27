"""Async JSON-RPC 2.0 client for the Anki-Connect API v1 (``POST /api/v1``)."""

from __future__ import annotations

import itertools
import time
from typing import Any

import anyio
import httpx

DEFAULT_URL = "http://127.0.0.1:8765/api/v1"

PENDING_STATES = ("queued", "running", "waitingForUser")
TERMINAL_FAILURE_STATES = ("failed", "cancelled")

_TRANSPORT_ERRORS = {
    401: ("unauthorized", "Invalid or missing API key (set ANKICONNECT_API_KEY)."),
    403: ("forbidden", "Origin rejected by Anki-Connect (check webCorsOriginList)."),
    405: ("methodNotAllowed", "Anki-Connect rejected the HTTP method."),
    413: ("payloadTooLarge", "Request body exceeds the 16 MiB limit."),
}


class AnkiConnectError(Exception):
    """A JSON-RPC error or a transport failure. ``code``/``type`` follow API_V1.md."""

    def __init__(self, message: str, *, code: int | None = None, data: Any = None, type_: str | None = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.data = data
        self.type = type_ or (data.get("type") if isinstance(data, dict) else None)

    @classmethod
    def from_rpc(cls, error: dict[str, Any]) -> AnkiConnectError:
        return cls(str(error.get("message", "Unknown error")), code=error.get("code"), data=error.get("data"))

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"message": self.message}
        if self.code is not None:
            out["code"] = self.code
        if self.type is not None:
            out["type"] = self.type
        if self.data is not None:
            out["data"] = self.data
        return out


class AnkiConnectClient:
    def __init__(
        self,
        url: str = DEFAULT_URL,
        *,
        api_key: str | None = None,
        timeout: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.url = url
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._http = httpx.AsyncClient(headers=headers, timeout=timeout, transport=transport)
        self._ids = itertools.count(1)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> AnkiConnectClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def call(self, method: str, params: dict[str, Any] | None = None) -> Any:
        request_id = next(self._ids)
        body: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}}
        try:
            response = await self._http.post(self.url, json=body)
        except httpx.ConnectError as exc:
            raise AnkiConnectError(
                f"Cannot connect to Anki-Connect at {self.url}. Make sure Anki is running "
                "with the Anki-Connect add-on enabled.",
                type_="connectionFailed",
            ) from exc
        except httpx.TimeoutException as exc:
            raise AnkiConnectError(
                f"Timed out waiting for Anki-Connect to answer `{method}`. The request may still "
                "have been executed; do not retry writes blindly.",
                type_="timeout",
            ) from exc

        if response.status_code != 200:
            type_, message = _TRANSPORT_ERRORS.get(
                response.status_code, ("httpError", f"Unexpected HTTP status {response.status_code}.")
            )
            raise AnkiConnectError(message, code=response.status_code, type_=type_)

        try:
            reply = response.json()
        except ValueError as exc:
            raise AnkiConnectError("Anki-Connect returned invalid JSON.", type_="invalidResponse") from exc
        if not isinstance(reply, dict):
            raise AnkiConnectError("Anki-Connect returned an unexpected response.", type_="invalidResponse")
        if "error" in reply and reply["error"] is not None:
            raise AnkiConnectError.from_rpc(reply["error"])
        if reply.get("id") != request_id:
            raise AnkiConnectError("Unexpected response ID from Anki-Connect.", type_="invalidResponse")
        return reply.get("result")

    async def wait_for_operation(
        self,
        operation_id: str,
        *,
        timeout: float,
        initial_delay: float = 0.25,
        max_delay: float = 2.0,
    ) -> dict[str, Any]:
        """Poll ``operations.get`` until a terminal state or ``timeout`` and return the last record.

        A timeout does not cancel server work; the pending record is returned as is.
        """
        deadline = time.monotonic() + timeout
        delay = initial_delay
        while True:
            operation = await self.call("operations.get", {"operationId": operation_id})
            if operation.get("state") not in PENDING_STATES:
                return operation
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return operation
            await anyio.sleep(min(delay, remaining))
            delay = min(delay * 1.5, max_delay)
