"""RAGY MCP Server - real Model Context Protocol (JSON-RPC over stdio)."""
import sys
import json
from pathlib import Path

ROOT = Path("C:/AI-Agents-Lab")

TOOLS = [
    {
        "name": "list_files",
        "description": "List files in the RAGY project.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Subfolder (default: project root)"}
            },
        },
    },
    {
        "name": "read_file",
        "description": "Read a text file inside the RAGY project (safe zone only).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path inside C:/AI-Agents-Lab"}
            },
            "required": ["path"],
        },
    },
]


def is_safe(path_str: str) -> bool:
    try:
        p = Path(path_str).resolve()
        return ROOT.resolve() in p.parents or p == ROOT.resolve()
    except Exception:
        return False


def execute_tool(name: str, arguments: dict) -> dict:
    if name == "list_files":
        sub = arguments.get("path", "")
        base = (ROOT / sub).resolve() if sub else ROOT.resolve()
        if not is_safe(str(base)):
            return {"content": [{"type": "text", "text": "Access denied"}]}
        try:
            files = [str(p) for p in base.rglob("*") if p.is_file() and ".git" not in str(p)]
            text = "\n".join(files) if files else "(empty)"
        except Exception as e:
            text = f"Error: {e}"
        return {"content": [{"type": "text", "text": text}]}

    if name == "read_file":
        path = arguments.get("path", "")
        if not path or not is_safe(path):
            return {"content": [{"type": "text", "text": "Access denied: outside safe zone"}]}
        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            text = f"Error reading file: {e}"
        return {"content": [{"type": "text", "text": text}]}

    return {"content": [{"type": "text", "text": f"Unknown tool: {name}"}]}


def handle(msg: dict):
    method = msg.get("method")
    mid = msg.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0", "id": mid,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "ragy-mcp", "version": "1.0.0"},
            },
        }
    if method == "notifications/initialized":
        return None
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = msg.get("params", {})
        return {
            "jsonrpc": "2.0", "id": mid,
            "result": execute_tool(params.get("name", ""), params.get("arguments", {})),
        }
    if method == "ping":
        return {"jsonrpc": "2.0", "id": mid, "result": {}}
    if mid is not None:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": "Method not found"}}
    return None


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        response = handle(msg)
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
