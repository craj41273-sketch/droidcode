"""Long-lived harness server over a unix socket, newline-delimited JSON.

Same idea as jcode's daemon: the expensive thing (a device, a warm app, an
emulator) is started once and many clients - CLI runs, an editor plugin, a CI
job, an agent - talk to it. One request, one reply, no shared state between
connections beyond the harness itself.
"""

from __future__ import annotations

import json
import os
import socketserver
import threading
from pathlib import Path
from typing import Any

from .harness import Harness
from .session import ToolCall


class HarnessServer:
    """Transport-agnostic request handler; testable without a socket."""

    def __init__(self, harness: Harness) -> None:
        self.harness = harness
        self._methods = {
            "ping": self._ping,
            "tools.list": self._tools_list,
            "tool.call": self._tool_call,
            "audit.run": self._audit_run,
            "session.create": self._session_create,
            "session.run": self._session_run,
            "session.get": self._session_get,
        }

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        request_id = request.get("id")
        method = request.get("method", "")
        handler = self._methods.get(method)
        if handler is None:
            return {"id": request_id, "ok": False, "error": f"unknown method {method!r}"}
        try:
            return {"id": request_id, "ok": True, "result": handler(request.get("params") or {})}
        except Exception as error:  # a bad request must not kill the daemon
            return {"id": request_id, "ok": False, "error": f"{type(error).__name__}: {error}"}

    def handle_line(self, line: str) -> str:
        try:
            request = json.loads(line)
        except json.JSONDecodeError as error:
            return json.dumps({"id": None, "ok": False, "error": f"bad json: {error}"})
        return json.dumps(self.handle(request))

    # -- methods -----------------------------------------------------------
    def _ping(self, params: dict) -> dict:
        return {"pong": True, "device": self.harness.device.spec.key}

    def _tools_list(self, params: dict) -> list[dict]:
        return self.harness.registry.specs()

    def _tool_call(self, params: dict) -> dict:
        return self.harness.call_tool(params["name"], params.get("arguments"))

    def _audit_run(self, params: dict) -> dict:
        return self.harness.audit(params.get("screenshots_dir"))

    def _session_create(self, params: dict) -> dict:
        session = self.harness.start_session(params.get("goal", ""), int(params.get("budget_tokens", 200_000)))
        return {"id": session.id}

    def _session_run(self, params: dict) -> dict:
        session = self.harness.sessions.get(params["id"])
        if session is None:
            raise KeyError(f"unknown session {params['id']!r}")
        calls = [ToolCall(item["name"], item.get("arguments", {})) for item in params.get("script", [])]
        model = None
        if calls:
            from .session import ScriptedModel

            model = ScriptedModel(calls)
        self.harness.run_session(session, model=model, max_turns=int(params.get("max_turns", 12)))
        return session.to_dict()

    def _session_get(self, params: dict) -> dict:
        session = self.harness.sessions.get(params["id"])
        if session is None:
            raise KeyError(f"unknown session {params['id']!r}")
        return session.to_dict()


class _UnixHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        server: "_UnixServer" = self.server  # type: ignore[assignment]
        for raw in self.rfile:
            line = raw.decode("utf-8").strip()
            if not line:
                continue
            self.wfile.write((server.server_impl.handle_line(line) + "\n").encode("utf-8"))
            self.wfile.flush()


class _UnixServer(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True

    def __init__(self, path: str, server_impl: HarnessServer) -> None:
        self.server_impl = server_impl
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        if os.path.exists(path):
            os.unlink(path)
        super().__init__(path, _UnixHandler)


def serve(harness: Harness, socket_path: str) -> None:
    server = _UnixServer(socket_path, HarnessServer(harness))
    try:
        server.serve_forever()
    finally:
        server.server_close()
        if os.path.exists(socket_path):
            os.unlink(socket_path)


def serve_in_thread(harness: Harness, socket_path: str) -> tuple[_UnixServer, threading.Thread]:
    """Used by tests and by `droidcode daemon --background`."""
    server = _UnixServer(socket_path, HarnessServer(harness))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread
