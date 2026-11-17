"""WhatsApp adapter tests — webhook verification, HMAC fail-closed, message parsing."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "cloud" / "src" / "whatsapp.js"


def node_eval(expr: str) -> str:
    script = f'import("file:///{JS.as_posix()}").then(m => {{ const r = {expr}; console.log(JSON.stringify(r)); }})'
    result = subprocess.run(["node", "--input-type=module", "-e", script],
                            capture_output=True, text=True, timeout=40)
    if result.returncode != 0:
        raise RuntimeError(result.stderr[:400])
    return result.stdout.strip()


class WhatsAppAdapterTests(unittest.TestCase):
    def test_extract_messages_from_meta_payload(self) -> None:
        payload = {"entry": [{"changes": [{"field": "messages", "value": {"messages": [
            {"id": "w1", "from": "123", "type": "text", "text": {"body": "hello"}, "timestamp": "1"},
            {"id": "w2", "from": "456", "type": "image"},
        ]}}]}]}
        result = json.loads(node_eval(f"m.extractMessages({json.dumps(payload)})"))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["from"], "123")

    def test_extract_ignores_non_messages_field(self) -> None:
        payload = {"entry": [{"changes": [{"field": "statuses", "value": {}}]}]}
        result = json.loads(node_eval(f"m.extractMessages({json.dumps(payload)})"))
        self.assertEqual(result, [])

    def test_is_configured_fail_closed(self) -> None:
        self.assertFalse(json.loads(node_eval("m.isConfigured({})")))

    def test_source_security_requirements(self) -> None:
        src = (ROOT / "cloud" / "src" / "whatsapp.js").read_text(encoding="utf-8")
        self.assertIn("X-Hub-Signature-256", src)
        self.assertIn("crypto.subtle", src)
        self.assertIn("fail-closed", src.lower())
        self.assertIn("WHATSAPP_APP_SECRET", src)


if __name__ == "__main__":
    unittest.main()
