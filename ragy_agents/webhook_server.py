"""n8n Webhook Receiver - HTTP server to receive callbacks from n8n workflows."""

from __future__ import annotations

import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict
from urllib.parse import urlparse, parse_qs

from .orchestrator import CoreOrchestrator
from .models import AgentRole
from .config_loader import get_agent_config
from .real_agents import create_real_agents


class WebhookHandler(BaseHTTPRequestHandler):
    """Handle incoming webhooks from n8n."""
    
    orchestrator: CoreOrchestrator = None
    
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        
        try:
            payload = json.loads(body) if body else {}
        except json.JSONDecodeError:
            payload = {"raw": body}
        
        response = self._route_webhook(path, payload)
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode('utf-8'))
    
    def _route_webhook(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Route webhook to appropriate handler."""
        
        if path == '/webhook/task/create':
            return self._handle_create_task(payload)
        elif path == '/webhook/task/status':
            return self._handle_task_status(payload)
        elif path == '/webhook/agent/result':
            return self._handle_agent_result(payload)
        elif path == '/webhook/health':
            return {"status": "ok", "service": "ragy-webhook"}
        else:
            return {"error": f"Unknown webhook path: {path}"}
    
    def _handle_create_task(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new task from n8n."""
        title = payload.get('title', 'Task from n8n')
        description = payload.get('description', '')
        role_str = payload.get('role', 'research')
        
        try:
            role = AgentRole(role_str)
        except ValueError:
            role = AgentRole.RESEARCH
        
        task, approval = self.orchestrator.create_planned_task(title, description)
        
        # Auto-approve for n8n-triggered tasks
        approval = self.orchestrator.grant_human_approval(approval.request_id, "n8n-auto")
        
        # Assign and dispatch
        task = self.orchestrator.assign_approved_task(task.task_id, role)
        task = self.orchestrator.dispatch_assigned_task(task.task_id)
        
        return {
            "task_id": task.task_id,
            "state": task.state.value,
            "assigned_role": task.assigned_role.value if task.assigned_role else None,
        }
    
    def _handle_task_status(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Get task status."""
        task_id = payload.get('task_id')
        if not task_id:
            return {"error": "task_id required"}
        
        try:
            task = self.orchestrator.task_manager.get_task(task_id)
            results = self.orchestrator.task_manager.list_results(task_id)
            return {
                "task_id": task.task_id,
                "title": task.title,
                "state": task.state.value,
                "assigned_role": task.assigned_role.value if task.assigned_role else None,
                "attempt_count": task.attempt_count,
                "results_count": len(results),
            }
        except Exception as e:
            return {"error": str(e)}
    
    def _handle_agent_result(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Receive agent result from n8n (for async agents)."""
        # This would be used for long-running agents that complete via webhook
        return {"received": True, "note": "Async result handling not yet implemented"}


def create_webhook_server(
    orchestrator: CoreOrchestrator,
    host: str = "localhost",
    port: int = 5679,
) -> HTTPServer:
    """Create and configure the webhook server."""
    WebhookHandler.orchestrator = orchestrator
    server = HTTPServer((host, port), WebhookHandler)
    return server


def run_webhook_server(
    project_root: Path | None = None,
    data_directory: Path | None = None,
    host: str = "localhost",
    port: int = 5679,
):
    """Run the webhook server in a background thread."""
    
    project_root = project_root or Path("/c/AI-Agents-Lab")
    data_directory = data_directory or Path("/c/RagyAI/Data")
    
    config = get_agent_config()
    real_agents = create_real_agents(config)
    
    orchestrator = CoreOrchestrator(
        project_root=project_root,
        data_directory=data_directory,
        agents=real_agents,
        allowed_paths=[data_directory],
    )
    
    server = create_webhook_server(orchestrator, host, port)
    
    def serve():
        print(f"Ragy webhook server running on http://{host}:{port}")
        server.serve_forever()
    
    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    
    return server, orchestrator


if __name__ == "__main__":
    server, orchestrator = run_webhook_server()
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down...")
        server.shutdown()
        orchestrator.close()