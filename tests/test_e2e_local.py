"""T4 tests — local E2E client against the real secure bridge (real HTTP, real shutdown)."""

from __future__ import annotations

import os
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from ragy_agents.audit import StructuredAuditLog
from ragy_agents.policy import PolicyEnforcer

from engine.e2e_client import BridgeOffline, BridgeRejected, RAGYLocalClient
from engine.secure_mcp_bridge import SecureBridgeHandler, BridgeConfig, STATE


class LocalE2ETests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parent.parent
        cls.token = "e2e-token-" + "b" * 20
        os.environ["RAGY_BRIDGE_TOKEN"] = cls.token
        cls.config = BridgeConfig(cls.root)
        cls.handler = type("E2EHandler", (SecureBridgeHandler,), {"config": cls.config})

    @classmethod
    def tearDownClass(cls) -> None:
        os.environ.pop("RAGY_BRIDGE_TOKEN", None)

    def setUp(self) -> None:
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self.handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        try:
            self.server.shutdown()
            self.server.server_close()
        finally:
            self.thread.join(timeout=2)

    def _client(self) -> RAGYLocalClient:
        return RAGYLocalClient(f"http://127.0.0.1:{self.port}", self.token)

    def _audit_events(self) -> list[dict]:
        return [__import__("json").loads(x) for x in self.config.audit.path.read_text(encoding="utf-8").splitlines() if x.strip()]

    def _start_fresh_server(self) -> None:
        self.server = ThreadingHTTPServer(("127.0.0.1", self.port), self.handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def test_e2e_initialize_tools_list_read(self) -> None:
        c = self._client()
        init = c.initialize()
        self.assertEqual(init.response["result"]["serverInfo"]["name"], "ragy-mcp")
        self.assertTrue(c.session_id)
        tools = c.tools_list()
        self.assertEqual([t["name"] for t in tools.response["result"]["tools"]], ["list_files", "read_file"])
        read = c.read_file("README.md", request_id="e2e-001", correlation_id="corr-001")
        self.assertIn("Jameel", read.response["result"]["content"][0]["text"])
        self.assertEqual(read.request_id, "e2e-001")
        self.assertEqual(read.correlation_id, "corr-001")

    def test_correlation_ids_are_audited(self) -> None:
        c = self._client()
        c.initialize()
        c.read_file("README.md", request_id="e2e-audit", correlation_id="corr-audit")
        events = self._audit_events()
        self.assertTrue(any(e.get("task_id") == "e2e-audit" for e in events))
        self.assertTrue(any("corr-audit" in __import__("json").dumps(e) for e in events))

    def test_T7_outage_is_explicit_not_fabricated(self) -> None:
        c = self._client()
        c.initialize()
        self.server.shutdown()          # stop only THIS test's server
        self.server.server_close()
        with self.assertRaises(BridgeOffline):
            c.read_file("README.md", request_id="e2e-outage")

    def test_T8_resume_after_bridge_restart(self) -> None:
        c = self._client()
        first = c.initialize()
        sid_before = c.session_id
        # real restart of this test's server on the same port
        self.server.shutdown()
        self.server.server_close()
        STATE.reset()              # simulate a brand-new process: sessions + cache gone
        self._start_fresh_server()
        # keep the stale session id on purpose — the client must detect the
        # 404 "unknown session" and reinitialize on its own (real resume behaviour).
        resumed = c.read_file("README.md", request_id="e2e-resume", correlation_id="corr-resume")
        self.assertEqual(resumed.request_id, "e2e-resume")
        self.assertTrue(c.session_id)
        self.assertNotEqual(c.session_id, sid_before)
        self.assertTrue(self.config.audit.verify().valid)

    def test_wrong_token_is_rejected(self) -> None:
        bad = RAGYLocalClient(f"http://127.0.0.1:{self.port}", "wrong-token")
        with self.assertRaises(BridgeRejected) as ctx:
            bad.initialize()
        self.assertEqual(ctx.exception.code, 401)

    def test_audit_chain_valid_after_all(self) -> None:
        self.assertTrue(self.config.audit.verify().valid)


if __name__ == "__main__":
    unittest.main()
