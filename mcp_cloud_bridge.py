"""RAGY MCP Cloud Bridge - HTTP wrapper around the real MCP stdio logic.
Exposes the same tools over HTTP so Claude/ChatGPT can reach it from any browser.
No secrets, no external calls. Binds to 0.0.0.0 for cloud hosting.
"""
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from mcp_stdio_server import handle, execute_tool, TOOLS
import json as _json
from pathlib import Path as _Path

# In cloud, only these bundled text files are readable (no local disk access).
_CLOUD_ALLOW = {
    "README.md": _Path("README.md"),
    "CONTEXT_PACK.md": _Path("CONTEXT_PACK.md"),
}

def _cloud_execute(name, args):
    if name == "list_files":
        files = [p for p in _CLOUD_ALLOW.values() if p.exists()]
        return {"content": [{"type": "text", "text": "\n".join(str(p) for p in files) or "(no catalog files)"}]}
    if name == "read_file":
        requested = args.get("path", "")
        key = _Path(requested).name
        target = _CLOUD_ALLOW.get(key)
        if target and target.exists():
            return {"content": [{"type": "text", "text": target.read_text(encoding="utf-8")}]}
        return {"content": [{"type": "text", "text": "Access denied: file not in cloud catalog"}]}
    return {"content": [{"type": "text", "text": f"Unknown tool: {name}"}]}

PORT = int(os.environ.get("PORT", 8000))


class Handler(BaseHTTPRequestHandler):
    def _send(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send({})

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/health":
            return self._send({"status": "ok", "service": "ragy-mcp-cloud", "version": "1.0.0"})
        if path == "/tools":
            return self._send({"tools": TOOLS})
        if path == "/":
            return self._send({"service": "RAGY MCP Cloud Bridge", "endpoints": ["/health", "/tools", "/mcp"]})
        self._send({"error": "not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode("utf-8")
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return self._send({"error": "invalid json"}, 400)

        if path == "/mcp":
            # JSON-RPC single message (same protocol as stdio)
            method = payload.get("method")
            mid = payload.get("id")
            if method == "tools/call":
                prm = payload.get("params", {})
                result = _cloud_execute(prm.get("name", ""), prm.get("arguments", {}))
                return self._send({"jsonrpc": "2.0", "id": mid, "result": result})
            result = handle(payload)
            return self._send(result if result is not None else {"status": "accepted"})

        if path == "/tools/call":
            name = payload.get("name", "")
            args = payload.get("arguments", {})
            return self._send(_cloud_execute(name, args))

        self._send({"error": "not found"}, 404)

    def log_message(self, format, *args):
        pass  # quiet logs


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"RAGY MCP Cloud Bridge listening on 0.0.0.0:{PORT}", flush=True)
    server.serve_forever()
