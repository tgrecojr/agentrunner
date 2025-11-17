"""
Messaging module for Multi-Agent Orchestration Platform.

Provides:
- EventBus: RabbitMQ-based pub/sub messaging
- Event types and schemas
- Dead-letter queue support
- Retry logic with exponential backoff
"""

from .event_bus import EventBus
from .events import (
    Event,
    EventPriority,
    EventType,
    create_agent_event,
    create_plan_event,
    create_state_event,
    create_system_event,
    create_task_event,
)

__all__ = [
    # EventBus
    "EventBus",
    # Event types
    "Event",
    "EventType",
    "EventPriority",
    # Event creators
    "create_agent_event",
    "create_task_event",
    "create_state_event",
    "create_plan_event",
    "create_system_event",
]
