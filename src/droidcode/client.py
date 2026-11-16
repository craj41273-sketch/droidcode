"""SDK client: one socket, one request at a time, plain dicts back."""

from __future__ import annotations

import itertools
import json
import socket
from typing import Any


class DaemonError(RuntimeError):
    pass


class DaemonClient:
    def __init__(self, socket_path: str, timeout_s: float = 60.0) -> None:
        self.socket_path = socket_path
        self.timeout_s = timeout_s
        self._ids = itertools.count(1)

    def _request(self, method: str, params: dict[str, Any] | None = None) -> dict:
        payload = {"id": next(self._ids), "method": method, "params": params or {}}
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(self.timeout_s)
            connection.connect(self.socket_path)
            connection.sendall((json.dumps(payload) + "\n").encode("utf-8"))
            buffer = b""
            while not buffer.endswith(b"\n"):
                chunk = connection.recv(65536)
                if not chunk:
                    break
                buffer += chunk
        reply = json.loads(buffer.decode("utf-8"))
        if not reply.get("ok"):
            raise DaemonError(reply.get("error", "unknown daemon error"))
        return reply["result"]

    def ping(self) -> dict:
        return self._request("ping")

    def tools(self) -> list[dict]:
        return self._request("tools.list")

    def call_tool(self, name: str, arguments: dict | None = None) -> dict:
        return self._request("tool.call", {"name": name, "arguments": arguments or {}})

    def audit(self) -> dict:
        return self._request("audit.run")

    def create_session(self, goal: str, budget_tokens: int = 200_000) -> str:
        return self._request("session.create", {"goal": goal, "budget_tokens": budget_tokens})["id"]

    def run_session(self, session_id: str, script: list[dict] | None = None) -> dict:
        return self._request("session.run", {"id": session_id, "script": script or []})
