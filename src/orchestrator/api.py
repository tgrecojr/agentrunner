"""
AgentOrchestrator API - FastAPI endpoints for orchestration management.

Provides health checks, agent registry queries, and agent invocation endpoints.
"""

from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from ..config.configuration_service import ConfigurationService
from ..messaging.event_bus import EventBus
from ..state.state_manager import StateManager
from .agent_orchestrator import AgentOrchestrator

# Initialize FastAPI app
app = FastAPI(
    title="AgentOrchestrator API",
    description="Central orchestration for multi-agent platform",
    version="1.0.0"
)

# Initialize services
config_service = ConfigurationService(
    config_dir="config/agents",
    enable_hot_reload=True
)

state_manager = StateManager()

event_bus = EventBus()

# Initialize AgentOrchestrator
orchestrator = AgentOrchestrator(
    config_service=config_service,
    state_manager=state_manager,
    event_bus=event_bus
)


@app.on_event("startup")
async def startup_event():
    """Initialize orchestrator on startup."""
    await orchestrator.initialize()


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown orchestrator on app shutdown."""
    await orchestrator.shutdown()


@app.get("/health")
async def health_check() -> Dict:
    """
    Health check endpoint.

    Returns:
        Health status including agent count and service status
    """
    registry = orchestrator.get_agent_registry()

    # Count agents by status
    status_counts = {}
    for agent_info in registry.values():
        status = agent_info["status"]
        status_counts[status] = status_counts.get(status, 0) + 1

    health = {
        "status": "healthy",
        "total_agents": len(registry),
        "agent_status": status_counts,
        "services": {
            "config_service": "healthy",
            "state_manager": "healthy",
            "event_bus": "healthy"
        }
    }

    return health


@app.get("/health/ready")
async def readiness_probe() -> Dict:
    """
    Kubernetes readiness probe.

    Returns:
        Simple ready status
    """
    registry = orchestrator.get_agent_registry()

    # Check if at least one agent is ready
    ready_agents = [
        agent for agent in registry.values()
        if agent["status"] in ["ready", "running"]
    ]

    if ready_agents or len(registry) == 0:
        return {"status": "ready", "ready_agents": len(ready_agents)}
    else:
        raise HTTPException(status_code=503, detail="No agents ready")


@app.get("/health/live")
async def liveness_probe() -> Dict:
    """
    Kubernetes liveness probe.

    Returns:
        Simple alive status
    """
    return {"status": "alive"}


@app.get("/agents")
async def list_agents(
    status: Optional[str] = None,
    agent_type: Optional[str] = None,
    execution_mode: Optional[str] = None
) -> Dict[str, Dict]:
    """
    List all registered agents with optional filtering.

    Args:
        status: Filter by agent status
        agent_type: Filter by agent type
        execution_mode: Filter by execution mode

    Returns:
        Dictionary of agent name -> agent info
    """
    return orchestrator.get_agent_registry(
        status=status,
        agent_type=agent_type,
        execution_mode=execution_mode
    )


@app.get("/agents/{agent_name}")
async def get_agent(agent_name: str) -> Dict:
    """
    Get information about a specific agent.

    Args:
        agent_name: Name of the agent

    Returns:
        Agent information
    """
    registry = orchestrator.get_agent_registry()

    if agent_name not in registry:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_name}' not found"
        )

    return registry[agent_name]


@app.post("/agents/{agent_name}/invoke")
async def invoke_agent(agent_name: str, task_data: Dict) -> Dict:
    """
    Invoke an agent to execute a task.

    Args:
        agent_name: Name of the agent to invoke
        task_data: Task data payload

    Returns:
        Execution information
    """
    execution_id = await orchestrator.invoke_agent(
        agent_name=agent_name,
        task_data=task_data
    )

    if execution_id is None:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to invoke agent '{agent_name}'"
        )

    return {
        "agent_name": agent_name,
        "execution_id": execution_id,
        "status": "started"
    }


@app.post("/agents/{agent_name}/restart")
async def restart_agent(agent_name: str) -> Dict:
    """
    Restart a failed agent.

    Args:
        agent_name: Name of the agent to restart

    Returns:
        Restart status
    """
    success = await orchestrator.restart_agent(agent_name)

    if not success:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to restart agent '{agent_name}'"
        )

    return {
        "agent_name": agent_name,
        "status": "restarted"
    }


@app.get("/agents/{agent_name}/health")
async def check_agent_health(agent_name: str) -> Dict:
    """
    Check health of a specific agent.

    Args:
        agent_name: Name of the agent

    Returns:
        Health status
    """
    is_healthy = await orchestrator.health_check_agent(agent_name)

    registry = orchestrator.get_agent_registry()
    if agent_name not in registry:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_name}' not found"
        )

    agent_info = registry[agent_name]

    return {
        "agent_name": agent_name,
        "healthy": is_healthy,
        "status": agent_info["status"],
        "last_heartbeat": agent_info["last_heartbeat"],
        "restart_count": agent_info["restart_count"]
    }


@app.get("/stats")
async def get_stats() -> Dict:
    """
    Get orchestrator statistics.

    Returns:
        Platform statistics
    """
    registry = orchestrator.get_agent_registry()

    # Count by status
    by_status = {}
    for agent_info in registry.values():
        status = agent_info["status"]
        by_status[status] = by_status.get(status, 0) + 1

    # Count by type
    by_type = {}
    for agent_info in registry.values():
        agent_type = agent_info["type"]
        by_type[agent_type] = by_type.get(agent_type, 0) + 1

    # Count by execution mode
    by_mode = {}
    for agent_info in registry.values():
        mode = agent_info["execution_mode"]
        by_mode[mode] = by_mode.get(mode, 0) + 1

    return {
        "total_agents": len(registry),
        "by_status": by_status,
        "by_type": by_type,
        "by_execution_mode": by_mode
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
