"""Local E2E client for RAGY Secure Bridge — T4 of SEQ 007.

Real HTTP, real bearer auth, real session, explicit outage detection.
No secrets in source. No cloud. No new packages.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


class BridgeOffline(RuntimeError):
    """Raised when the bridge is unreachable. Never hidden by a blind retry."""


class BridgeRejected(RuntimeError):
    """Raised for an explicit HTTP rejection (401/403/404/409)."""

    def __init__(self, code: int, reason: str) -> None:
        super().__init__(f"HTTP {code}: {reason}")
        self.code = code
        self.reason = reason


@dataclass
class ClientResult:
    request_id: str
    correlation_id: str
    response: dict[str, Any]
    session_id: str
    idempotent_hit: bool


class RAGYLocalClient:
    """Minimal MCP client over the secure bridge, with session + correlation tracking."""

    def __init__(self, base_url: str, token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.session_id: str | None = None
        self._next_id = 1

    def _call(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        request_id: str | None = None,
        correlation_id: str | None = None,
        reinitialize: bool = True,
    ) -> ClientResult:
        import uuid

        rid = request_id or str(uuid.uuid4())
        cid = correlation_id or str(uuid.uuid4())
        msg: dict[str, Any] = {"jsonrpc": "2.0", "id": self._next_id, "method": method}
        if params is not None:
            msg["params"] = params
        self._next_id += 1

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
            "X-Request-Id": rid,
            "X-Correlation-Id": cid,
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id

        payload = json.dumps(msg, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(f"{self.base_url}/mcp", data=payload, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                raw = resp.read().decode("utf-8", "replace")
                new_sid = resp.headers.get("Mcp-Session-Id")
                if new_sid:
                    self.session_id = new_sid
                body = json.loads(raw) if raw else {}
                return ClientResult(rid, cid, body, self.session_id or "",
                                    resp.headers.get("X-Idempotent-Hit") == "true")
        except urllib.error.HTTPError as exc:
            with exc:
                reason = exc.read().decode("utf-8", "replace")[:200]
            if exc.code == 404 and "session" in reason.lower() and reinitialize and self.session_id:
                # Session lost (bridge restarted): reinitialize ONCE, then retry the same logical call.
                self.session_id = None
                self.initialize()
                return self._call(method, params, request_id=rid, correlation_id=cid, reinitialize=False)
            raise BridgeRejected(exc.code, reason) from exc
        except (urllib.error.URLError, OSError) as exc:
            raise BridgeOffline(f"bridge unreachable: {exc}") from exc

    def initialize(self) -> ClientResult:
        return self._call("initialize", {}, reinitialize=False)

    def tools_list(self) -> ClientResult:
        return self._call("tools/list", {})

    def read_file(self, path: str, *, request_id: str | None = None,
                  correlation_id: str | None = None) -> ClientResult:
        return self._call(
            "tools/call",
            {"name": "read_file", "arguments": {"path": path}},
            request_id=request_id,
            correlation_id=correlation_id,
        )
