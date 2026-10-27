"""Start the installed server over stdio and check that it answers an MCP handshake.

Usage: python scripts/smoke_test.py [server command ...]
Defaults to the `anki-connect-mcp` executable on PATH. Anki itself is not needed.
"""

import json
import shutil
import subprocess
import sys

EXPECTED_TOOLS = 95


def main() -> None:
    command = sys.argv[1:] or ["anki-connect-mcp"]
    command[0] = shutil.which(command[0]) or command[0]
    proc = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )

    def send(message: dict) -> None:
        proc.stdin.write(json.dumps(message) + "\n")
        proc.stdin.flush()

    def receive(rid: int) -> dict:
        for line in proc.stdout:
            message = json.loads(line)
            if message.get("id") == rid:
                if "error" in message:
                    raise SystemExit(f"server returned an error: {message['error']}")
                return message["result"]
        raise SystemExit(f"server exited with code {proc.wait()} before answering request {rid}")

    try:
        send(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "smoke-test", "version": "0"},
                },
            }
        )
        info = receive(1)["serverInfo"]
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        tools = receive(2)["tools"]
    finally:
        proc.stdin.close()
        proc.wait(timeout=30)

    print(f"{info['name']} {info.get('version', '')}: {len(tools)} tools")
    if len(tools) != EXPECTED_TOOLS:
        raise SystemExit(f"expected {EXPECTED_TOOLS} tools, got {len(tools)}")


if __name__ == "__main__":
    main()
