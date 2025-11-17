# EventBus - Event-Driven Messaging

RabbitMQ-based publish/subscribe messaging system for the Multi-Agent Orchestration Platform.

## Features

- **Topic-Based Routing**: Flexible routing with wildcard patterns (`*`, `#`)
- **Dead-Letter Queue (DLQ)**: Automatic handling of failed messages
- **Retry Logic**: Configurable retry attempts with message tracking
- **Guaranteed Delivery**: Persistent messages survive broker restarts
- **Event Schemas**: Type-safe events with Pydantic validation
- **Trace Correlation**: Built-in trace IDs for distributed tracing
- **Health Monitoring**: Connection health checks

## Architecture

```
┌──────────────┐         ┌──────────────┐
│   Agent A    │         │   Agent B    │
└──────┬───────┘         └──────┬───────┘
       │ publish                │ subscribe
       ▼                        ▼
┌────────────────────────────────────────┐
│          RabbitMQ EventBus             │
│  Exchange: agent_events (topic)        │
│  ┌──────────────┐  ┌──────────────┐   │
│  │ Queue A      │  │ Queue B      │   │
│  │ Pattern:     │  │ Pattern:     │   │
│  │ task.*.#     │  │ agent.*.high │   │
│  └──────────────┘  └──────────────┘   │
│                                        │
│  DLX: agent_events_dlx                │
│  ┌──────────────┐                     │
│  │ DLQ Queue A  │ (failed messages)   │
│  └──────────────┘                     │
└────────────────────────────────────────┘
```

### Routing Key Pattern

Events use routing keys in the format: `{event_type}.{priority}`

Examples:
- `agent.started.normal` - Agent started, normal priority
- `task.completed.high` - Task completed, high priority
- `plan.failed.critical` - Plan failed, critical priority

### Wildcard Patterns

- `*` - Matches exactly one word
  - `agent.*.normal` matches `agent.started.normal`, `agent.stopped.normal`
- `#` - Matches zero or more words
  - `task.*.#` matches `task.started.normal`, `task.completed.high`

## Quick Start

### Installation

Ensure RabbitMQ is running:

```bash
# Docker
docker run -d --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3-management

# Or use existing RabbitMQ instance
```

### Basic Usage

```python
from uuid import uuid4
from src.messaging import (
    EventBus,
    EventType,
    EventPriority,
    create_agent_event,
    create_task_event,
)

# Initialize EventBus
event_bus = EventBus()

# Publish an event
event = create_agent_event(
    event_type=EventType.AGENT_STARTED,
    agent_id="my_agent",
    payload={"version": "1.0.0"},
    trace_id=uuid4(),
)
event_bus.publish(event)

# Subscribe to events
def handle_event(event):
    print(f"Received: {event.event_type.value}")
    print(f"Payload: {event.payload}")

event_bus.subscribe(
    queue_name="my_queue",
    routing_patterns=["agent.*.normal"],
    callback=handle_event,
    enable_dlq=True,
)

# Start consuming (blocking)
event_bus.start_consuming("my_queue", blocking=True)
```

## Event Types

### Agent Lifecycle Events

```python
EventType.AGENT_STARTED      # Agent initialization complete
EventType.AGENT_STOPPED      # Agent shutdown
EventType.AGENT_ERROR        # Agent error occurred
EventType.AGENT_HEARTBEAT    # Periodic health signal
```

### Task Execution Events

```python
EventType.TASK_SUBMITTED     # New task submitted
EventType.TASK_STARTED       # Task execution began
EventType.TASK_COMPLETED     # Task finished successfully
EventType.TASK_FAILED        # Task failed with error
EventType.TASK_TIMEOUT       # Task exceeded time limit
EventType.TASK_CANCELLED     # Task was cancelled
```

### State Events

```python
EventType.STATE_SAVED        # State persisted to storage
EventType.STATE_LOADED       # State retrieved from storage
EventType.STATE_RECOVERED    # State recovered after crash
```

### Plan Execution Events

```python
EventType.PLAN_CREATED       # Collaborative plan created
EventType.PLAN_STARTED       # Plan execution started
EventType.PLAN_STEP_COMPLETED  # Plan step completed
EventType.PLAN_STEP_FAILED   # Plan step failed
EventType.PLAN_COMPLETED     # Entire plan completed
EventType.PLAN_FAILED        # Plan execution failed
```

### System Events

```python
EventType.SYSTEM_SHUTDOWN    # System shutdown initiated
EventType.SYSTEM_HEALTH_CHECK  # Health check request
```

## Event Schema

All events follow this Pydantic schema:

```python
class Event(BaseModel):
    # Identification
    event_id: UUID              # Unique event identifier
    event_type: EventType       # Type of event
    timestamp: datetime         # Event timestamp (UTC)

    # Source
    source_agent_id: str        # Agent that emitted event
    source_service: str         # Service that emitted event

    # Correlation
    trace_id: UUID              # For distributed tracing
    execution_id: UUID          # Execution instance ID
    parent_event_id: UUID       # Parent event (causal chain)

    # Data
    payload: Dict[str, Any]     # Event-specific data

    # Metadata
    priority: EventPriority     # Event priority
    ttl_seconds: int            # Time-to-live
    retry_count: int            # Current retry attempt
    max_retries: int            # Maximum retries (default: 3)
```

## Event Creators

Convenience functions for creating type-safe events:

### Agent Events

```python
event = create_agent_event(
    event_type=EventType.AGENT_STARTED,
    agent_id="agent_001",
    payload={"version": "1.0.0", "capabilities": ["chat", "search"]},
    trace_id=uuid4(),
    priority=EventPriority.NORMAL,
)
```

### Task Events

```python
event = create_task_event(
    event_type=EventType.TASK_SUBMITTED,
    agent_id="agent_001",
    task_id="task_123",
    task_data={"description": "Process request", "priority": "high"},
    trace_id=uuid4(),
)
```

### State Events

```python
event = create_state_event(
    event_type=EventType.STATE_SAVED,
    agent_id="agent_001",
    state_info={"checkpoint_id": "cp_001", "size_bytes": 1024},
    trace_id=uuid4(),
)
```

### Plan Events

```python
event = create_plan_event(
    event_type=EventType.PLAN_CREATED,
    plan_id=uuid4(),
    plan_data={"steps": 5, "participants": ["agent_001", "agent_002"]},
    trace_id=uuid4(),
    priority=EventPriority.HIGH,
)
```

### System Events

```python
event = create_system_event(
    event_type=EventType.SYSTEM_HEALTH_CHECK,
    service_name="state_manager",
    system_data={"status": "healthy", "uptime_seconds": 3600},
    priority=EventPriority.NORMAL,
)
```

## Publishing Events

### Basic Publishing

```python
event_bus.publish(event)
```

### Custom Routing Key

```python
event_bus.publish(event, routing_key="custom.routing.key")
```

### Non-Persistent Messages

```python
# For high-throughput, non-critical events
event_bus.publish(event, persistent=False)
```

## Subscribing to Events

### Basic Subscription

```python
def my_handler(event: Event):
    print(f"Processing: {event.event_type.value}")
    # Process event...

event_bus.subscribe(
    queue_name="my_service_queue",
    routing_patterns=["task.*.#"],
    callback=my_handler,
)
```

### Multiple Patterns

```python
event_bus.subscribe(
    queue_name="multi_pattern_queue",
    routing_patterns=[
        "agent.started.*",
        "agent.stopped.*",
        "task.completed.high",
    ],
    callback=my_handler,
)
```

### Without Dead-Letter Queue

```python
event_bus.subscribe(
    queue_name="no_dlq_queue",
    routing_patterns=["agent.heartbeat.*"],
    callback=my_handler,
    enable_dlq=False,  # Disable DLQ
)
```

### With Message TTL

```python
event_bus.subscribe(
    queue_name="ttl_queue",
    routing_patterns=["agent.heartbeat.*"],
    callback=my_handler,
    message_ttl_ms=60000,  # Messages expire after 60 seconds
)
```

### Auto-Acknowledge Mode

```python
# Messages acknowledged automatically (use with caution)
event_bus.subscribe(
    queue_name="auto_ack_queue",
    routing_patterns=["task.*.#"],
    callback=my_handler,
    auto_ack=True,
)
```

## Consuming Events

### Blocking Mode

```python
# Blocks current thread
event_bus.start_consuming("my_queue", blocking=True)
```

### Background Mode

```python
# Runs in background thread
event_bus.start_consuming("my_queue", blocking=False)

# Your code continues here...

# Stop when done
event_bus.stop_consuming("my_queue")
```

## Dead-Letter Queue (DLQ)

### How It Works

1. Message processing fails (exception raised in callback)
2. Message is retried up to `max_retries` (default: 3)
3. After max retries, message is sent to DLQ
4. DLQ queue name: `dlq.{original_queue_name}`

### Monitoring DLQ

```python
dlq_info = event_bus.get_queue_info("dlq.my_queue")
if dlq_info:
    print(f"Failed messages in DLQ: {dlq_info['message_count']}")
```

### Processing DLQ Messages

```python
def dlq_handler(event: Event):
    # Log failed event
    print(f"DLQ Event: {event.event_id}")
    print(f"Retry count: {event.retry_count}")
    # Alert, store, or reprocess

event_bus.subscribe(
    queue_name="dlq.my_queue",
    routing_patterns=["#"],  # DLQ uses direct routing
    callback=dlq_handler,
    enable_dlq=False,  # Don't create DLQ for DLQ
)
```

## Queue Management

### Get Queue Information

```python
info = event_bus.get_queue_info("my_queue")
if info:
    print(f"Messages: {info['message_count']}")
    print(f"Consumers: {info['consumer_count']}")
```

### Purge Queue

```python
# Remove all messages from queue
purged_count = event_bus.purge_queue("my_queue")
print(f"Purged {purged_count} messages")
```

## Health Monitoring

```python
health = event_bus.health_check()
print(f"Status: {health['status']}")
print(f"Connected: {health['connected']}")

if health['status'] == 'healthy':
    details = health['details']
    print(f"Host: {details['host']}")
    print(f"Exchange: {details['exchange']}")
```

## Configuration

Environment variables:

```bash
# RabbitMQ Connection
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_USER=guest
RABBITMQ_PASSWORD=guest
RABBITMQ_VHOST=/

# Optional Advanced Settings
RABBITMQ_PREFETCH_COUNT=1      # Messages prefetched per consumer
RABBITMQ_CONNECTION_TIMEOUT=10  # Connection timeout (seconds)
RABBITMQ_HEARTBEAT=600         # Heartbeat interval (seconds)
```

### Programmatic Configuration

```python
event_bus = EventBus(
    host="rabbitmq.example.com",
    port=5672,
    username="myuser",
    password="mypass",
    vhost="/production",
    exchange_type="topic",
    prefetch_count=10,
    connection_timeout=30,
    heartbeat=300,
)
```

## Advanced Patterns

### Request-Reply Pattern

```python
# Service A - Make request
request_event = create_task_event(
    event_type=EventType.TASK_SUBMITTED,
    agent_id="requester",
    task_id="req_001",
    task_data={"action": "process_data", "data": {...}},
    trace_id=trace_id,
)
event_bus.publish(request_event)

# Service B - Handle request and send reply
def handle_request(event: Event):
    # Process request
    result = process_data(event.payload['data'])

    # Send reply
    reply_event = create_task_event(
        event_type=EventType.TASK_COMPLETED,
        agent_id="processor",
        task_id=event.payload['task_id'],
        task_data={"result": result},
        trace_id=event.trace_id,  # Same trace ID
        parent_event_id=event.event_id,  # Link to request
    )
    event_bus.publish(reply_event)
```

### Fan-Out Pattern

```python
# Publish to multiple consumers
event = create_system_event(
    event_type=EventType.SYSTEM_HEALTH_CHECK,
    service_name="orchestrator",
)
event_bus.publish(event)

# Multiple services subscribe with same pattern
# Each gets a copy of the message
```

### Priority Queues

```python
# High priority events
high_priority_event = create_task_event(
    event_type=EventType.TASK_SUBMITTED,
    agent_id="agent_001",
    task_id="urgent_task",
    task_data={...},
    priority=EventPriority.CRITICAL,
)
event_bus.publish(high_priority_event)

# Subscribe to high priority only
event_bus.subscribe(
    queue_name="high_priority_queue",
    routing_patterns=["task.*.critical", "task.*.high"],
    callback=handle_urgent_task,
)
```

## Context Manager Usage

```python
with EventBus() as bus:
    bus.publish(event)
    # Connection automatically closed on exit
```

## Error Handling

### Publication Errors

```python
success = event_bus.publish(event)
if not success:
    # Handle failure (logged automatically)
    print("Failed to publish event")
```

### Consumption Errors

```python
def safe_handler(event: Event):
    try:
        # Process event
        process_event(event)
    except TemporaryError:
        # Raise to trigger retry
        raise
    except PermanentError as e:
        # Log and don't raise (message will be acked)
        logger.error(f"Permanent error: {e}")
```

## Testing

Run the test suite:

```bash
python test_event_bus.py
```

Test output includes:
- Connection establishment
- Health check status
- Event publishing
- Queue creation and binding
- Event consumption
- Dead-letter queue behavior
- Queue management operations

## Performance Considerations

1. **Prefetch Count**: Set based on consumer processing speed
   - Low (1-5): Slow processing, fair distribution
   - High (10+): Fast processing, better throughput

2. **Persistent Messages**: Use for critical events only
   - Persistent: Survives broker restart (slower)
   - Non-persistent: Higher throughput (lost on restart)

3. **Connection Pooling**: Reuse EventBus instance
   - Create once per application
   - Thread-safe for publishing
   - Use separate channels for consumers

4. **Message Size**: Keep payloads reasonably sized
   - Large payloads (>1MB): Consider storing in StateManager
   - Event payload: Include reference/ID only

## Best Practices

1. **Use Trace IDs**: Always include trace_id for correlation
2. **Idempotency**: Design handlers to safely handle duplicate messages
3. **Error Handling**: Distinguish transient vs permanent errors
4. **DLQ Monitoring**: Set up alerts for DLQ message accumulation
5. **Queue Naming**: Use descriptive, service-specific queue names
6. **Routing Patterns**: Start specific, broaden as needed
7. **Event Versioning**: Include version info in payload for schema evolution

## Troubleshooting

### Connection Failures

```python
# Check health
health = event_bus.health_check()
if health['status'] == 'unhealthy':
    print(f"Error: {health['details']['error']}")
```

### Messages Not Being Consumed

1. Check routing patterns match event routing keys
2. Verify consumer is running: `event_bus.start_consuming(...)`
3. Check queue bindings: `event_bus.get_queue_info("queue_name")`

### DLQ Messages Accumulating

1. Review error logs for handler exceptions
2. Check retry logic in consumer callback
3. Inspect DLQ messages for patterns

## License

Internal use only - Multi-Agent Orchestration Platform
