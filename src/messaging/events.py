"""
Event types and schemas for the event-driven messaging system.

Defines standard event formats for agent communication and system events.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class EventType(str, Enum):
    """Standard event types for the platform."""

    # Agent lifecycle events
    AGENT_STARTED = "agent.started"
    AGENT_STOPPED = "agent.stopped"
    AGENT_ERROR = "agent.error"
    AGENT_HEARTBEAT = "agent.heartbeat"

    # Task execution events
    TASK_SUBMITTED = "task.submitted"
    TASK_STARTED = "task.started"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    TASK_TIMEOUT = "task.timeout"
    TASK_CANCELLED = "task.cancelled"

    # State events
    STATE_SAVED = "state.saved"
    STATE_LOADED = "state.loaded"
    STATE_RECOVERED = "state.recovered"

    # Plan execution events (collaborative)
    PLAN_CREATED = "plan.created"
    PLAN_STARTED = "plan.started"
    PLAN_STEP_COMPLETED = "plan.step.completed"
    PLAN_STEP_FAILED = "plan.step.failed"
    PLAN_COMPLETED = "plan.completed"
    PLAN_FAILED = "plan.failed"

    # Integration events
    SLACK_MESSAGE_RECEIVED = "slack.message.received"
    SLACK_MESSAGE_SENT = "slack.message.sent"

    # System events
    SYSTEM_SHUTDOWN = "system.shutdown"
    SYSTEM_HEALTH_CHECK = "system.health.check"


class EventPriority(str, Enum):
    """Event priority levels."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class Event(BaseModel):
    """
    Base event model for all platform events.

    All events follow this schema for consistency and traceability.
    """

    # Event identification
    event_id: UUID = Field(default_factory=uuid4, description="Unique event identifier")
    event_type: EventType = Field(..., description="Type of event")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Event timestamp (UTC)")

    # Event source
    source_agent_id: Optional[str] = Field(None, description="Agent that emitted the event")
    source_service: Optional[str] = Field(None, description="Service that emitted the event")

    # Event correlation
    trace_id: Optional[UUID] = Field(None, description="Trace ID for request correlation")
    execution_id: Optional[UUID] = Field(None, description="Execution instance ID")
    parent_event_id: Optional[UUID] = Field(None, description="Parent event ID for causal chains")

    # Event data
    payload: Dict[str, Any] = Field(default_factory=dict, description="Event-specific data")

    # Event metadata
    priority: EventPriority = Field(EventPriority.NORMAL, description="Event priority")
    ttl_seconds: Optional[int] = Field(None, description="Time-to-live in seconds")
    retry_count: int = Field(0, description="Number of retry attempts")
    max_retries: int = Field(3, description="Maximum retry attempts")

    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat() + "Z",
            UUID: lambda v: str(v),
        }

    def to_json(self) -> str:
        """
        Serialize event to JSON string.

        Returns:
            JSON string representation
        """
        return self.model_dump_json()

    @classmethod
    def from_json(cls, json_str: str) -> "Event":
        """
        Deserialize event from JSON string.

        Args:
            json_str: JSON string

        Returns:
            Event instance
        """
        return cls.model_validate_json(json_str)

    def get_routing_key(self) -> str:
        """
        Get RabbitMQ routing key for this event.

        The routing key follows the pattern: {event_type}.{priority}

        Returns:
            Routing key string
        """
        return f"{self.event_type.value}.{self.priority.value}"


# ============================================
# Convenience Event Creators
# ============================================

def create_agent_event(
    event_type: EventType,
    agent_id: str,
    payload: Optional[Dict[str, Any]] = None,
    trace_id: Optional[UUID] = None,
    execution_id: Optional[UUID] = None,
    priority: EventPriority = EventPriority.NORMAL,
) -> Event:
    """
    Create an agent-related event.

    Args:
        event_type: Type of event
        agent_id: Agent identifier
        payload: Event payload
        trace_id: Trace ID for correlation
        execution_id: Execution instance ID
        priority: Event priority

    Returns:
        Event instance
    """
    return Event(
        event_type=event_type,
        source_agent_id=agent_id,
        payload=payload or {},
        trace_id=trace_id,
        execution_id=execution_id,
        priority=priority,
    )


def create_task_event(
    event_type: EventType,
    agent_id: str,
    task_id: str,
    task_data: Optional[Dict[str, Any]] = None,
    trace_id: Optional[UUID] = None,
    execution_id: Optional[UUID] = None,
    priority: EventPriority = EventPriority.NORMAL,
) -> Event:
    """
    Create a task-related event.

    Args:
        event_type: Type of event
        agent_id: Agent identifier
        task_id: Task identifier
        task_data: Task-specific data
        trace_id: Trace ID for correlation
        execution_id: Execution instance ID
        priority: Event priority

    Returns:
        Event instance
    """
    payload = {"task_id": task_id}
    if task_data:
        payload.update(task_data)

    return Event(
        event_type=event_type,
        source_agent_id=agent_id,
        payload=payload,
        trace_id=trace_id,
        execution_id=execution_id,
        priority=priority,
    )


def create_state_event(
    event_type: EventType,
    agent_id: str,
    state_info: Dict[str, Any],
    trace_id: Optional[UUID] = None,
    execution_id: Optional[UUID] = None,
) -> Event:
    """
    Create a state-related event.

    Args:
        event_type: Type of event
        agent_id: Agent identifier
        state_info: State information
        trace_id: Trace ID for correlation
        execution_id: Execution instance ID

    Returns:
        Event instance
    """
    return Event(
        event_type=event_type,
        source_agent_id=agent_id,
        payload=state_info,
        trace_id=trace_id,
        execution_id=execution_id,
        priority=EventPriority.NORMAL,
    )


def create_plan_event(
    event_type: EventType,
    plan_id: UUID,
    plan_data: Dict[str, Any],
    trace_id: Optional[UUID] = None,
    priority: EventPriority = EventPriority.NORMAL,
) -> Event:
    """
    Create a plan-related event.

    Args:
        event_type: Type of event
        plan_id: Plan identifier
        plan_data: Plan-specific data
        trace_id: Trace ID for correlation
        priority: Event priority

    Returns:
        Event instance
    """
    payload = {"plan_id": str(plan_id)}
    payload.update(plan_data)

    return Event(
        event_type=event_type,
        source_service="plan_orchestrator",
        payload=payload,
        trace_id=trace_id,
        priority=priority,
    )


def create_system_event(
    event_type: EventType,
    service_name: str,
    system_data: Optional[Dict[str, Any]] = None,
    priority: EventPriority = EventPriority.NORMAL,
) -> Event:
    """
    Create a system-related event.

    Args:
        event_type: Type of event
        service_name: Service name
        system_data: System-specific data
        priority: Event priority

    Returns:
        Event instance
    """
    return Event(
        event_type=event_type,
        source_service=service_name,
        payload=system_data or {},
        priority=priority,
    )
