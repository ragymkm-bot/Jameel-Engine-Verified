"""Secure Streamable-HTTP MCP Bridge — T3 of SEQ 007.

Fail-closed. Bearer auth from env or local vault (never code/git). Reuses mcp_stdio_server.handle.
Local-only. No secrets in source. No cloud/Worker/Tunnel. No new packages.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import threading
import uuid
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ragy_agents.audit import StructuredAuditLog
from ragy_agents.policy import PolicyEnforcer

from mcp_stdio_server import handle as mcp_handle  # single source of truth, no duplication

ROOT = Path(__file__).resolve().parent.parent
MAX_IDEMPOTENCY_ENTRIES = 512
ALLOWED_ORIGIN_PREFIXES = ("http://localhost", "http://127.0.0.1")


class BridgeConfig:
    """Loads the token from env or a gitignored local vault. Refuses empty config."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()
        self.token = self._load_token()
        self.audit = self._load_audit()

    def _load_token(self) -> str:
        env_token = os.environ.get("RAGY_BRIDGE_TOKEN", "").strip()
        if env_token:
            return env_token
        vault_path = self.project_root / "runtime" / "vault.json"
        if vault_path.exists():
            try:
                data = json.loads(vault_path.read_text(encoding="utf-8"))
                token = str(data.get("bridge_token", "")).strip()
                if token:
                    return token
            except (json.JSONDecodeError, OSError):
                pass
        return ""

    def _load_audit(self) -> StructuredAuditLog:
        policy = PolicyEnforcer(self.project_root)
        return StructuredAuditLog(
            policy.require_project_path(self.project_root / "runtime" / "audit.jsonl"),
            policy,
        )

    def is_ready(self) -> bool:
        return bool(self.token)


class BridgeState:
    """Sessions + bounded idempotency cache (in-memory, local process)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.sessions: set[str] = set()
        self._idem: OrderedDict[str, tuple[str, dict[str, Any]]] = OrderedDict()

    def new_session(self) -> str:
        sid = uuid.uuid4().hex
        with self._lock:
            self.sessions.add(sid)
        return sid

    def has_session(self, sid: str) -> bool:
        with self._lock:
            return sid in self.sessions

    def close_session(self, sid: str) -> None:
        with self._lock:
            self.sessions.discard(sid)

    @staticmethod
    def _hash(payload: dict[str, Any]) -> str:
        return hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()

    def get_cached(self, request_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        with self._lock:
            entry = self._idem.get(request_id)
            if entry is None:
                return None
            cached_hash, response = entry
            if cached_hash != self._hash(payload):
                return "CONFLICT"  # type: ignore[return-value]
            self._idem.move_to_end(request_id)
            return response

    def put_cached(self, request_id: str, payload: dict[str, Any], response: dict[str, Any]) -> None:
        with self._lock:
            self._idem[request_id] = (self._hash(payload), response)
            self._idem.move_to_end(request_id)
            while len(self._idem) > MAX_IDEMPOTENCY_ENTRIES:
                self._idem.popitem(last=False)


STATE = BridgeState()


class SecureBridgeHandler(BaseHTTPRequestHandler):
    config: BridgeConfig
    server_version = "RAGY-Secure-Bridge/1.0"
    protocol_version = "HTTP/1.1"

    # ---- low-level response helpers -------------------------------------
    def _respond(self, obj: dict[str, Any], code: int = 200, extra: dict[str, str] | None = None) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if extra:
            for key, value in extra.items():
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _deny(self, code: int, reason: str, *, audit_type: str, request_id: str) -> None:
        self.config.audit.append(
            audit_type, "secure-bridge", request_id or None, {"reason": reason, "path": urlparse(self.path).path}
        )
        headers = {"WWW-Authenticate": "Bearer"} if code == 401 else None
        self._respond({"error": reason}, code, headers)

    # ---- auth + origin --------------------------------------------------
    def _authorized(self) -> bool:
        header = self.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return False
        supplied = header[len("Bearer "):].strip()
        return bool(supplied) and hmac.compare_digest(supplied, self.config.token)

    def _origin_ok(self) -> bool:
        origin = self.headers.get("Origin")
        if origin is None:
            return True  # non-browser clients (MCP stdio-style) send no Origin
        return any(origin.startswith(prefix) for prefix in ALLOWED_ORIGIN_PREFIXES)

    def _request_id(self) -> str:
        return self.headers.get("X-Request-Id", "").strip()

    # ---- routes ---------------------------------------------------------
    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/health":
            return self._respond({"status": "ok", "service": "ragy-secure-mcp-bridge", "version": "1.0.0"})
        if path == "/mcp":
            if not self._authorized():
                return self._deny(401, "unauthorized", audit_type="bridge.auth.denied", request_id="")
            if not self._origin_ok():
                return self._deny(403, "origin not allowed", audit_type="bridge.origin.denied", request_id="")
            # Minimal SSE stream: one endpoint event, then keep-alive comments.
            sid = self.headers.get("Mcp-Session-Id", "")
            if not self.config_state.has_session(sid):
                return self._deny(404, "unknown session", audit_type="bridge.session.denied", request_id=sid)
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            try:
                self.wfile.write(f"event: endpoint\ndata: /mcp\nsession: {sid}\n\n".encode("utf-8"))
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            return
        self._respond({"error": "not found"}, 404)

    def do_DELETE(self) -> None:
        path = urlparse(self.path).path
        if path != "/mcp":
            return self._respond({"error": "not found"}, 404)
        if not self._authorized():
            return self._deny(401, "unauthorized", audit_type="bridge.auth.denied", request_id="")
        sid = self.headers.get("Mcp-Session-Id", "")
        self.config_state.close_session(sid)
        self.config.audit.append("bridge.session.closed", "secure-bridge", sid or None, {})
        self.send_response(204)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path != "/mcp":
            return self._respond({"error": "not found"}, 404)

        request_id = self._request_id()
        if not self._authorized():
            return self._deny(401, "unauthorized", audit_type="bridge.auth.denied", request_id=request_id)
        if not self._origin_ok():
            return self._deny(403, "origin not allowed", audit_type="bridge.origin.denied", request_id=request_id)

        length = int(self.headers.get("Content-Length", 0) or 0)
        if length > 1_000_000:
            return self._deny(413, "payload too large", audit_type="bridge.payload.denied", request_id=request_id)
        raw = self.rfile.read(length).decode("utf-8", "replace")
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return self._deny(400, "invalid json", audit_type="bridge.payload.denied", request_id=request_id)

        sid = self.headers.get("Mcp-Session-Id", "")
        method = payload.get("method", "") if isinstance(payload, dict) else ""

        # initialize opens a session; all other calls require a known session.
        if method != "initialize" and not self.config_state.has_session(sid):
            return self._deny(404, "unknown or missing session", audit_type="bridge.session.denied", request_id=request_id)

        # idempotency (T6) applies to JSON-RPC calls with an id
        if request_id and method != "initialize":
            cached = self.config_state.get_cached(request_id, payload)
            if cached == "CONFLICT":
                return self._deny(409, "request id reused with different payload",
                                  audit_type="bridge.idempotency.conflict", request_id=request_id)
            if cached is not None:
                self.config.audit.append("bridge.idempotent.hit", "secure-bridge", request_id, {"method": method})
                return self._respond(cached, 200, {"X-Idempotent-Hit": "true"})

        # delegate to the existing stdio handler (single source of truth)
        response = mcp_handle(payload) if isinstance(payload, dict) else None
        if response is None:
            # notifications: 202 Accepted, no body
            self.config.audit.append("bridge.notification.accepted", "secure-bridge", request_id or None, {"method": method})
            self.send_response(202)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        extra: dict[str, str] = {}
        if method == "initialize":
            new_sid = self.config_state.new_session()
            extra["Mcp-Session-Id"] = new_sid
            self.config.audit.append("bridge.session.created", "secure-bridge", request_id or None,
                                     {"method": method, "session_created": True})
        if request_id and method != "initialize":
            self.config_state.put_cached(request_id, payload, response)

        self.config.audit.append(
            "bridge.request.served", "secure-bridge", request_id or None,
            {"method": method, "ok": "error" not in response},
        )
        self._respond(response, 200, extra)

    @property
    def config_state(self) -> BridgeState:
        return STATE

    def log_message(self, format: str, *args: Any) -> None:
        return  # never log headers — the Authorization header must not be persisted


def build_server(project_root: Path, host: str = "127.0.0.1", port: int = 8903) -> ThreadingHTTPServer:
    config = BridgeConfig(project_root)
    if not config.is_ready():
        raise RuntimeError("FAIL-CLOSED: no bridge token configured. Set RAGY_BRIDGE_TOKEN or runtime/vault.json bridge_token")
    handler = type("ConfiguredSecureBridgeHandler", (SecureBridgeHandler,), {"config": config})
    return ThreadingHTTPServer((host, port), handler)


if __name__ == "__main__":
    import sys

    root = Path(__file__).resolve().parent.parent
    port = int(os.environ.get("PORT", "8903"))
    try:
        server = build_server(root, "127.0.0.1", port)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)
    print(f"RAGY Secure MCP Bridge on 127.0.0.1:{port} (fail-closed, token hidden)", flush=True)
    server.serve_forever()
