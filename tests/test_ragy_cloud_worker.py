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
        try:
            return exc.code, (json.loads(raw) if raw else {})
        except json.JSONDecodeError:
            return exc.code, {"raw": raw[:200]}


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
            self.assertIn("location.href='/app'", page)
        with _u.urlopen(BASE + "/app", timeout=8) as resp:
            console = resp.read().decode("utf-8", "replace")
            self.assertEqual(resp.status, 200)
            self.assertIn("RAGY Cloud Console", console)
            self.assertIn("fetch('/audit'", console)
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

    def test_same_origin_is_allowed(self) -> None:
        code, _ = call("/mcp", token=self.token,
                       headers={"Origin": "https://ragy-cloud-engine.aragy76.workers.dev"},
                       body={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        self.assertEqual(code, 200)

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
        self.assertEqual(names, ["list_tasks", "get_task", "create_task", "verify_audit",
                                 "create_automation", "list_automations", "run_automation", "list_runs",
                                 "post_command", "list_commands", "delete_automation", "delete_command"])
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

    def test_automation_lifecycle_create_run_audit(self) -> None:
        def tool(name, args):
            return call("/mcp", token=self.token,
                        body={"jsonrpc": "2.0", "id": 7, "method": "tools/call",
                              "params": {"name": name, "arguments": args}})

        # create an automation with two real steps
        code, body = tool("create_automation", {
            "name": "test-auto-daily",
            "steps": [
                {"tool": "verify_audit", "args": {}},
                {"tool": "create_task", "args": {"title": "مهمة من أتمتة"}},
            ],
        })
        self.assertEqual(code, 200)
        created = json.loads(body["result"]["content"][0]["text"])
        aid = created["automation_id"]
        self.assertEqual(created["steps"], 2)

        # run it
        code, body = tool("run_automation", {"automation_id": aid})
        self.assertEqual(code, 200)
        run = json.loads(body["result"]["content"][0]["text"])
        self.assertIn(run["status"], ("success", "partial"))
        self.assertEqual(len(run["results"]), 2)
        self.assertTrue(all(r["ok"] for r in run["results"]))

        # events are stored in D1; verify the chain and inspect event types there
        code, body = call("/audit", token=self.token)
        self.assertTrue(body["valid"])
        self.assertGreaterEqual(body["checked"], 1)
        import subprocess as _sp
        q = "SELECT DISTINCT event_type FROM audit_log WHERE event_type LIKE 'cloud.automation.%';"
        import shutil as _sh
        _wrangler = _sh.which("wrangler") or _sh.which("wrangler.cmd")
        if not _wrangler:
            self.skipTest("wrangler CLI not on PATH")
        out = _sp.run([_wrangler, "d1", "execute", "ragy-tasks", "--local", "--command", q],
                      cwd=str(__import__("pathlib").Path(__file__).resolve().parent.parent / "cloud"),
                      capture_output=True, text=True, timeout=45).stdout
        self.assertIn("cloud.automation.started", out)
        self.assertIn("cloud.automation.finished", out)

    def test_command_queue_and_delete_lifecycle(self) -> None:
        def tool(name, args):
            return call("/mcp", token=self.token,
                        body={"jsonrpc": "2.0", "id": 11, "method": "tools/call",
                              "params": {"name": name, "arguments": args}})

        # post a command
        code, body = tool("post_command", {"task": "read README.md"})
        self.assertEqual(code, 200)
        posted = json.loads(body["result"]["content"][0]["text"])
        cid = posted["command_id"]
        self.assertEqual(posted["status"], "pending")

        # it appears in the list
        _, body = tool("list_commands", {})
        cmds = json.loads(body["result"]["content"][0]["text"])
        self.assertTrue(any(c["command_id"] == cid for c in cmds))

        # delete requires explicit confirm
        _, body = tool("delete_command", {"command_id": cid})
        self.assertTrue(json.loads(body["result"]["content"][0]["text"]).get("error"))
        # with confirm it works
        _, body = tool("delete_command", {"command_id": cid, "confirm": "DELETE"})
        self.assertTrue(json.loads(body["result"]["content"][0]["text"])["deleted"])

    def test_recursive_automation_is_rejected(self) -> None:
        code, body = call("/mcp", token=self.token,
                          body={"jsonrpc": "2.0", "id": 8, "method": "tools/call",
                                "params": {"name": "create_automation",
                                           "arguments": {"name": "loop", "steps": [{"tool": "run_automation", "args": {}}]}}})
        self.assertEqual(code, 200)
        result = json.loads(body["result"]["content"][0]["text"])
        self.assertIn("error", result)
        self.assertTrue(body["result"].get("isError"))


if __name__ == "__main__":
    unittest.main()
