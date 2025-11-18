"""
Scheduler Service API

FastAPI endpoints for schedule management.
"""

import os
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from ..config.configuration_service import ConfigurationService
from ..messaging.event_bus import EventBus
from ..state.state_manager import StateManager
from .scheduler_service import SchedulerService

# ============================================
# Request/Response Models
# ============================================


class ScheduleCreateRequest(BaseModel):
    """Request model for creating a schedule."""
    schedule_name: str
    agent_name: str
    schedule_type: str  # "cron" or "interval"
    schedule_config: Dict[str, Any]  # {"cron": "0 0 * * *"} or {"interval_seconds": 3600}
    task_data: Optional[Dict[str, Any]] = None


class ScheduleResponse(BaseModel):
    """Response model for schedule operations."""
    schedule_name: str
    agent_name: Optional[str] = None
    status: str


# ============================================
# Initialize Services
# ============================================

# Configuration
config_service = ConfigurationService(
    config_dir=os.getenv("CONFIG_DIR", "config"),
    secrets={
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", ""),
        "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY", ""),
    }
)

# State Manager
state_manager = StateManager(
    db_url=os.getenv(
        "DATABASE_URL",
        "postgresql://agentrunner:agentrunner@postgres:5432/agentrunner"
    ),
    redis_url=os.getenv("REDIS_URL", "redis://redis:6379/0")
)

# Event Bus
event_bus = EventBus(
    rabbitmq_url=os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672//")
)

# Scheduler Service
scheduler_service = SchedulerService(
    config_service=config_service,
    state_manager=state_manager,
    event_bus=event_bus,
    broker_url=os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672//"),
    backend_url=os.getenv("REDIS_URL", "redis://redis:6379/0"),
    task_timeout_seconds=int(os.getenv("TASK_TIMEOUT_SECONDS", "300"))
)

# ============================================
# FastAPI App
# ============================================

app = FastAPI(
    title="Scheduler Service API",
    description="Manages scheduled agent executions using Celery",
    version="1.0.0"
)


# ============================================
# Startup/Shutdown Events
# ============================================


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    await config_service.initialize()
    await state_manager.initialize()
    await event_bus.connect()
    await scheduler_service.initialize()


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    await scheduler_service.stop()
    await event_bus.disconnect()
    await state_manager.close()
    await config_service.stop()


# ============================================
# Health Endpoints
# ============================================


@app.get("/health/live")
async def liveness_probe() -> Dict[str, str]:
    """Kubernetes liveness probe."""
    return {"status": "alive"}


@app.get("/health/ready")
async def readiness_probe() -> Dict[str, str]:
    """Kubernetes readiness probe."""
    # Check if services are ready
    try:
        # Verify EventBus connection
        if not event_bus.connection or event_bus.connection.is_closed:
            raise HTTPException(status_code=503, detail="EventBus not ready")

        return {"status": "ready"}

    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service not ready: {str(e)}")


# ============================================
# Schedule Management Endpoints
# ============================================


@app.get("/schedules")
async def list_schedules() -> Dict[str, Dict[str, Any]]:
    """
    List all registered schedules.

    Returns:
        Dictionary of schedules
    """
    return scheduler_service.get_schedules()


@app.post("/schedules", response_model=ScheduleResponse)
async def create_schedule(request: ScheduleCreateRequest) -> ScheduleResponse:
    """
    Create a new schedule.

    Args:
        request: Schedule creation request

    Returns:
        Schedule creation response
    """
    try:
        result = await scheduler_service.register_custom_schedule(
            schedule_name=request.schedule_name,
            agent_name=request.agent_name,
            schedule_type=request.schedule_type,
            schedule_config=request.schedule_config,
            task_data=request.task_data
        )

        return ScheduleResponse(**result)

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/schedules/{schedule_name}", response_model=ScheduleResponse)
async def delete_schedule(schedule_name: str) -> ScheduleResponse:
    """
    Delete a schedule.

    Args:
        schedule_name: Schedule name

    Returns:
        Schedule deletion response
    """
    try:
        result = await scheduler_service.unregister_schedule(schedule_name)
        return ScheduleResponse(**result)

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/schedules/{schedule_name}")
async def get_schedule(schedule_name: str) -> Dict[str, Any]:
    """
    Get schedule details.

    Args:
        schedule_name: Schedule name

    Returns:
        Schedule details
    """
    schedules = scheduler_service.get_schedules()

    if schedule_name not in schedules:
        raise HTTPException(status_code=404, detail=f"Schedule not found: {schedule_name}")

    return {
        "schedule_name": schedule_name,
        **schedules[schedule_name]
    }


# ============================================
# Manual Execution Endpoints
# ============================================


@app.post("/schedules/{schedule_name}/trigger")
async def trigger_schedule(schedule_name: str) -> Dict[str, Any]:
    """
    Manually trigger a scheduled task.

    Args:
        schedule_name: Schedule name

    Returns:
        Trigger result
    """
    schedules = scheduler_service.get_schedules()

    if schedule_name not in schedules:
        raise HTTPException(status_code=404, detail=f"Schedule not found: {schedule_name}")

    schedule_info = schedules[schedule_name]
    agent_name, task_data, _ = schedule_info["args"]

    # Execute task immediately
    result = scheduler_service.execute_scheduled_task.apply_async(
        args=[agent_name, task_data, schedule_name]
    )

    return {
        "schedule_name": schedule_name,
        "agent_name": agent_name,
        "task_id": result.id,
        "status": "triggered"
    }


# ============================================
# Celery Worker Management
# ============================================


@app.get("/workers")
async def list_workers() -> Dict[str, Any]:
    """
    List active Celery workers.

    Returns:
        Worker information
    """
    inspect = scheduler_service.celery_app.control.inspect()

    stats = inspect.stats()
    active = inspect.active()
    scheduled = inspect.scheduled()

    return {
        "stats": stats or {},
        "active_tasks": active or {},
        "scheduled_tasks": scheduled or {}
    }


# ============================================
# Run Server (for development)
# ============================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
