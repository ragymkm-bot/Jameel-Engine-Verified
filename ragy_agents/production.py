"""Production entry point for Ragy AI with real agents."""

from __future__ import annotations

import json
from pathlib import Path

from .orchestrator import CoreOrchestrator
from .config_loader import get_agent_config
from .real_agents import create_real_agents
from .models import AgentRole


def create_production_orchestrator(
    project_root: Path | None = None,
    data_directory: Path | None = None,
) -> CoreOrchestrator:
    """Create a CoreOrchestrator configured with real production agents."""
    
    project_root = project_root or Path("/c/AI-Agents-Lab")
    data_directory = data_directory or Path("/c/RagyAI/Data")
    
    # Load configuration
    config = get_agent_config()
    
    # Create real agents
    real_agents = create_real_agents(config)
    
    # Create orchestrator with real agents
    orchestrator = CoreOrchestrator(
        project_root=project_root,
        data_directory=data_directory,
        agents=real_agents,
        allowed_paths=[data_directory],
    )
    
    return orchestrator


def run_task_pipeline(
    title: str,
    description: str,
    assigned_role: AgentRole,
    approver: str = "human",
) -> dict:
    """Run a complete task pipeline: create -> plan -> approve -> assign -> work -> review -> close."""
    
    orchestrator = create_production_orchestrator()
    
    try:
        # 1. Create and plan
        task, approval = orchestrator.create_planned_task(title, description)
        print(f"Created task: {task.task_id}")
        
        # 2. Grant approval (in production, this would wait for human)
        approval = orchestrator.grant_human_approval(approval.request_id, approver)
        print(f"Approval granted by: {approval.approver}")
        
        # 3. Assign agent
        task = orchestrator.assign_approved_task(task.task_id, assigned_role)
        print(f"Assigned to: {assigned_role.value}")
        
        # 4. Dispatch work
        task = orchestrator.dispatch_assigned_task(task.task_id)
        print(f"Work completed: {task.state.value}")
        
        # 5. Review
        task = orchestrator.review_evidence(task.task_id)
        print(f"Review result: {task.state.value}")
        
        # 6. Close if accepted
        if task.state.value == "Accepted":
            task = orchestrator.close_if_accepted(task.task_id)
            print(f"Task closed: {task.task_id}")
        
        return {
            "task_id": task.task_id,
            "final_state": task.state.value,
            "success": task.state.value in ("Accepted", "Closed"),
        }
        
    finally:
        orchestrator.close()


if __name__ == "__main__":
    # Demo: Run a research task
    result = run_task_pipeline(
        title="Research: n8n self-hosting best practices",
        description="Find the best free ways to run n8n 24/7 on Windows. Query: n8n free hosting Windows always-on",
        assigned_role=AgentRole.RESEARCH,
    )
    print(json.dumps(result, indent=2))