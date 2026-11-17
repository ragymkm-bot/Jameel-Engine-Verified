"""T3 tests — Secure Streamable HTTP Bridge. Real HTTP server, real auth, real audit."""

from __future__ import annotations

import json
import os
import shutil
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

from ragy_agents.audit import StructuredAuditLog
from ragy_agents.policy import PolicyEnforcer

from engine.secure_mcp_bridge import BridgeConfig, SecureBridgeHandler, build_server


def request(port: int, method: str, path: str, *, token: str | None = None,
            body: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> tuple[int, dict, dict]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    hdrs = {"Content-Type": "application/json"}
    if token is not None:
        hdrs["Authorization"] = f"Bearer {token}"
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            raw = resp.read().decode("utf-8", "replace")
            return resp.status, (json.loads(raw) if raw else {}), dict(resp.headers)
    except urllib.error.HTTPError as exc:
        with exc:  # close the error response to avoid ResourceWarning
            raw = exc.read().decode("utf-8", "replace")
            return exc.code, (json.loads(raw) if raw else {}), dict(exc.headers)


class SecureBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parent.parent
        cls.token = "test-token-" + "a" * 24  # ephemeral, never written to git
        os.environ["RAGY_BRIDGE_TOKEN"] = cls.token
        cls.config = BridgeConfig(cls.root)
        handler = type("TestSecureBridgeHandler", (SecureBridgeHandler,), {"config": cls.config})
        cls.server: ThreadingHTTPServer = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        os.environ.pop("RAGY_BRIDGE_TOKEN", None)

    def _init(self, token: str | None = None, headers: dict[str, str] | None = None, *, use_default: bool = True):
        supplied = (token or self.token) if use_default else token
        return request(
            self.port, "POST", "/mcp", token=supplied,
            body={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            headers=headers,
        )

    def test_T3_no_token_is_401(self) -> None:
        code, body, hdrs = self._init(token=None, use_default=False)
        self.assertEqual(code, 401)
        self.assertEqual(body.get("error"), "unauthorized")
        self.assertIn("WWW-Authenticate", hdrs)

    def test_T3_wrong_token_is_401(self) -> None:
        code, body, _ = self._init(token="wrong-token")
        self.assertEqual(code, 401)

    def test_valid_token_initialize_returns_session(self) -> None:
        code, body, hdrs = self._init()
        self.assertEqual(code, 200)
        self.assertEqual(body["result"]["serverInfo"]["name"], "ragy-mcp")
        self.assertTrue(hdrs.get("Mcp-Session-Id"))

    def test_tools_list_requires_session(self) -> None:
        code, _, _ = request(
            self.port, "POST", "/mcp", token=self.token,
            body={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        )
        self.assertEqual(code, 404)

    def test_tools_list_with_session(self) -> None:
        _, _, hdrs = self._init()
        sid = hdrs["Mcp-Session-Id"]
        code, body, _ = request(
            self.port, "POST", "/mcp", token=self.token,
            body={"jsonrpc": "2.0", "id": 3, "method": "tools/list"},
            headers={"Mcp-Session-Id": sid},
        )
        self.assertEqual(code, 200)
        names = [t["name"] for t in body["result"]["tools"]]
        self.assertEqual(names, ["list_files", "read_file"])

    def test_safe_zone_blocks_traversal(self) -> None:
        _, _, hdrs = self._init()
        sid = hdrs["Mcp-Session-Id"]
        code, body, _ = request(
            self.port, "POST", "/mcp", token=self.token,
            body={"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                  "params": {"name": "read_file", "arguments": {"path": "../windows/win.ini"}}},
            headers={"Mcp-Session-Id": sid},
        )
        self.assertEqual(code, 200)
        self.assertIn("Access denied", body["result"]["content"][0]["text"])

    def test_T6_idempotent_duplicate_no_reexecution(self) -> None:
        _, _, hdrs = self._init()
        sid = hdrs["Mcp-Session-Id"]
        body = {"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                "params": {"name": "read_file", "arguments": {"path": "README.md"}}}
        h = {"Mcp-Session-Id": sid, "X-Request-Id": "idem-001"}
        code1, r1, _ = request(self.port, "POST", "/mcp", token=self.token, body=body, headers=h)
        code2, r2, hdrs2 = request(self.port, "POST", "/mcp", token=self.token, body=body, headers=h)
        self.assertEqual(code1, 200)
        self.assertEqual(code2, 200)
        self.assertEqual(r1, r2)
        self.assertEqual(hdrs2.get("X-Idempotent-Hit"), "true")

    def test_idempotency_conflict_on_same_id_different_payload(self) -> None:
        _, _, hdrs = self._init()
        sid = hdrs["Mcp-Session-Id"]
        h = {"Mcp-Session-Id": sid, "X-Request-Id": "idem-conflict"}
        request(self.port, "POST", "/mcp", token=self.token,
                body={"jsonrpc": "2.0", "id": 6, "method": "tools/list"}, headers=h)
        code, body, _ = request(self.port, "POST", "/mcp", token=self.token,
                                body={"jsonrpc": "2.0", "id": 7, "method": "ping"}, headers=h)
        self.assertEqual(code, 409)

    def test_origin_not_allowed_is_403(self) -> None:
        code, body, _ = self._init(headers={"Origin": "https://evil.example"})
        self.assertEqual(code, 403)
        self.assertEqual(body.get("error"), "origin not allowed")

    def test_health_is_public_and_secret_free(self) -> None:
        code, body, _ = request(self.port, "GET", "/health")
        self.assertEqual(code, 200)
        self.assertEqual(body["status"], "ok")
        self.assertNotIn("token", json.dumps(body).lower())

    def test_fail_closed_without_token(self) -> None:
        saved = os.environ.pop("RAGY_BRIDGE_TOKEN", None)
        try:
            with self.assertRaises(RuntimeError) as ctx:
                build_server(self.root, "127.0.0.1", 0)
            self.assertIn("FAIL-CLOSED", str(ctx.exception))
        finally:
            if saved is not None:
                os.environ["RAGY_BRIDGE_TOKEN"] = saved

    def test_audit_chain_valid_after_requests(self) -> None:
        self._init()
        self.assertTrue(self.config.audit.verify().valid)


if __name__ == "__main__":
    unittest.main()
