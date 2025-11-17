"""
ConfigurationService API - FastAPI endpoints for configuration management.

Provides health checks and configuration query endpoints.
"""

from typing import Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from .configuration_service import ConfigurationService
from .models import AgentConfig

# Initialize FastAPI app
app = FastAPI(
    title="ConfigurationService API",
    description="Agent configuration management with hot-reload",
    version="1.0.0"
)

# Initialize ConfigurationService
config_service = ConfigurationService(
    config_dir="config/agents",
    enable_hot_reload=True
)


@app.get("/health")
async def health_check() -> Dict:
    """
    Health check endpoint.

    Returns:
        Health status including loaded configs, errors, and watcher status
    """
    health = config_service.health_check()

    # Determine HTTP status based on health
    status_code = 200 if health["status"] == "healthy" else 503

    return JSONResponse(
        status_code=status_code,
        content=health
    )


@app.get("/health/ready")
async def readiness_probe() -> Dict:
    """
    Kubernetes readiness probe.

    Returns:
        Simple ready status
    """
    health = config_service.health_check()

    if health["status"] == "healthy":
        return {"status": "ready"}
    else:
        raise HTTPException(status_code=503, detail="Service not ready")


@app.get("/health/live")
async def liveness_probe() -> Dict:
    """
    Kubernetes liveness probe.

    Returns:
        Simple alive status
    """
    return {"status": "alive"}


@app.get("/configs")
async def list_configurations() -> Dict[str, Dict]:
    """
    List all loaded agent configurations.

    Returns:
        Dictionary of agent name -> configuration data
    """
    configs = config_service.get_all_configs()

    # Convert AgentConfig objects to dicts for JSON serialization
    return {
        name: config.model_dump(mode="json")
        for name, config in configs.items()
    }


@app.get("/configs/{agent_name}")
async def get_configuration(agent_name: str) -> Dict:
    """
    Get configuration for a specific agent.

    Args:
        agent_name: Name of the agent

    Returns:
        Agent configuration data
    """
    config = config_service.get_agent_config(agent_name)

    if config is None:
        raise HTTPException(
            status_code=404,
            detail=f"Configuration for agent '{agent_name}' not found"
        )

    return config.model_dump(mode="json")


@app.get("/configs/enabled")
async def list_enabled_configurations() -> List[Dict]:
    """
    List all enabled agent configurations.

    Returns:
        List of enabled agent configurations
    """
    enabled_configs = config_service.get_enabled_agents()

    return [config.model_dump(mode="json") for config in enabled_configs]


@app.get("/configs/type/{agent_type}")
async def list_configurations_by_type(agent_type: str) -> List[Dict]:
    """
    List agent configurations by type.

    Args:
        agent_type: Agent type (collaborative, autonomous, continuous)

    Returns:
        List of matching agent configurations
    """
    configs = config_service.get_agents_by_type(agent_type)

    return [config.model_dump(mode="json") for config in configs]


@app.get("/configs/mode/{execution_mode}")
async def list_configurations_by_mode(execution_mode: str) -> List[Dict]:
    """
    List agent configurations by execution mode.

    Args:
        execution_mode: Execution mode (on_demand, scheduled, continuous, event_driven)

    Returns:
        List of matching agent configurations
    """
    configs = config_service.get_agents_by_execution_mode(execution_mode)

    return [config.model_dump(mode="json") for config in configs]


@app.get("/errors")
async def list_configuration_errors() -> Dict[str, str]:
    """
    List all configuration loading errors.

    Returns:
        Dictionary of agent name -> error message
    """
    return config_service.get_configuration_errors()


@app.post("/reload")
async def reload_configurations() -> Dict:
    """
    Manually reload all configurations from disk.

    Returns:
        Reload status
    """
    config_service.reload_all_configurations()

    return {
        "status": "reloaded",
        "loaded_configs": len(config_service.get_all_configs()),
        "errors": len(config_service.get_configuration_errors())
    }


@app.on_event("shutdown")
async def shutdown_event():
    """Stop the configuration service on shutdown."""
    config_service.stop()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
