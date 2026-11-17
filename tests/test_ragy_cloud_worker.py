"""RAGY Cloud Worker tests — real local wrangler dev, real HTTP, real auth, real D1 audit."""

from __future__ import annotations

import json
import os
import subprocess
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8799"
CLOUD = Path(__file__).resolve().parent.parent / "cloud"


def call(path: str, *, token: str | None = None, body: dict | None = None,
         headers: dict[str, str] | None = None) -> tuple[int, dict]:
    hdrs = {"Content-Type": "application/json"}
    if token is not None:
        hdrs["Authorization"] = f"Bearer {token}"
    if headers:
        hdrs.update(headers)
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, headers=hdrs,
                                 method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            raw = resp.read().decode("utf-8", "replace")
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as exc:
        with exc:
            raw = exc.read().decode("utf-8", "replace")
            return exc.code, (json.loads(raw) if raw else {})


class CloudWorkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.token = (CLOUD / ".dev-token").read_text(encoding="utf-8").strip()
        cls.proc: subprocess.Popen | None = None
        try:
            code, _ = call("/health")
            if code != 200:
                raise OSError("not ready")
        except OSError:
            cls.proc = subprocess.Popen(
                ["wrangler", "dev", "--local", "--port", "8799"],
                cwd=str(CLOUD), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            for _ in range(40):
                time.sleep(1)
                try:
                    code, _ = call("/health")
                    if code == 200:
                        break
                except OSError:
                    continue
            else:
                raise RuntimeError("wrangler dev did not start")

    @classmethod
    def tearDownClass(cls) -> None:
        if cls.proc:
            cls.proc.terminate()
            try:
                cls.proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                cls.proc.kill()

    def test_landing_page_is_public_and_api_still_guarded(self) -> None:
        import urllib.request as _u
        with _u.urlopen(BASE + "/", timeout=8) as resp:
            page = resp.read().decode("utf-8", "replace")
            self.assertEqual(resp.status, 200)
            self.assertIn("RAGY Cloud Engine", page)
            self.assertIn("localStorage", page)
        # the API itself must still reject unauthenticated calls
        code, body = call("/mcp", body={"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        self.assertEqual(code, 401)

    def test_health_ready_no_secret_leak(self) -> None:
        code, body = call("/health")
        self.assertEqual(code, 200)
        self.assertTrue(body["ready"])
        self.assertNotIn(self.token, json.dumps(body))

    def test_no_token_is_401(self) -> None:
        code, body = call("/mcp", body={"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        self.assertEqual(code, 401)
        self.assertEqual(body["error"], "unauthorized")

    def test_wrong_token_is_401(self) -> None:
        code, _ = call("/mcp", token="wrong-token",
                       body={"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        self.assertEqual(code, 401)

    def test_bad_origin_is_403(self) -> None:
        code, body = call("/mcp", token=self.token,
                          headers={"Origin": "https://evil.example"},
                          body={"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        self.assertEqual(code, 403)

    def test_initialize_and_tools_list(self) -> None:
        code, body = call("/mcp", token=self.token,
                          body={"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        self.assertEqual(code, 200)
        names = [t["name"] for t in body["result"]["tools"]]
        self.assertEqual(names, ["list_tasks", "get_task", "verify_audit"])
        code, body = call("/mcp", token=self.token,
                          body={"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        self.assertEqual(code, 200)

    def test_verify_audit_tool(self) -> None:
        code, body = call("/mcp", token=self.token,
                          body={"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                                "params": {"name": "verify_audit", "arguments": {}}})
        self.assertEqual(code, 200)
        result = json.loads(body["result"]["content"][0]["text"])
        self.assertTrue(result["valid"])

    def test_idempotency_hit(self) -> None:
        payload = {"jsonrpc": "2.0", "id": 9, "method": "tools/list"}
        call("/mcp", token=self.token, headers={"X-Request-Id": "cloud-idem"}, body=payload)
        code, body = call("/mcp", token=self.token, headers={"X-Request-Id": "cloud-idem"}, body=payload)
        self.assertEqual(code, 200)

    def test_audit_endpoint_chain_valid(self) -> None:
        code, body = call("/audit", token=self.token)
        self.assertEqual(code, 200)
        self.assertTrue(body["valid"])
        self.assertGreaterEqual(body["checked"], 1)


if __name__ == "__main__":
    unittest.main()
