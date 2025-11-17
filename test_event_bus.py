"""
Test script to verify EventBus functionality.
"""

import time
from uuid import uuid4

from dotenv import load_dotenv

from src.messaging import (
    Event,
    EventBus,
    EventType,
    create_agent_event,
    create_task_event,
)

# Load environment variables
load_dotenv()


def main():
    print("=" * 60)
    print("Testing EventBus Implementation")
    print("=" * 60)

    # Initialize EventBus
    print("\n1. Initializing EventBus...")
    try:
        event_bus = EventBus()
        print("✓ EventBus initialized")
        print(f"  - Host: {event_bus.host}")
        print(f"  - Port: {event_bus.port}")
        print(f"  - Exchange: {event_bus.MAIN_EXCHANGE}")
    except Exception as e:
        print(f"✗ Failed to initialize EventBus: {e}")
        return

    # Health check
    print("\n2. Running health check...")
    health = event_bus.health_check()
    print(f"  - Status: {health['status']}")
    print(f"  - Connected: {health['connected']}")
    if health['status'] == 'healthy':
        print("✓ EventBus is healthy")
    else:
        print(f"✗ EventBus is unhealthy: {health.get('details', {})}")
        return

    # Test publishing events
    print("\n3. Testing event publishing...")

    # Create test events
    trace_id = uuid4()

    # Agent started event
    agent_event = create_agent_event(
        event_type=EventType.AGENT_STARTED,
        agent_id="test_agent_001",
        payload={"version": "1.0.0", "capabilities": ["chat", "search"]},
        trace_id=trace_id,
    )

    # Task event
    task_event = create_task_event(
        event_type=EventType.TASK_SUBMITTED,
        agent_id="test_agent_001",
        task_id="task_001",
        task_data={"description": "Process user request", "priority": "high"},
        trace_id=trace_id,
    )

    # Publish events
    if event_bus.publish(agent_event):
        print("✓ Published AGENT_STARTED event")
        print(f"  - Event ID: {agent_event.event_id}")
        print(f"  - Routing Key: {agent_event.get_routing_key()}")
    else:
        print("✗ Failed to publish AGENT_STARTED event")

    if event_bus.publish(task_event):
        print("✓ Published TASK_SUBMITTED event")
        print(f"  - Event ID: {task_event.event_id}")
        print(f"  - Routing Key: {task_event.get_routing_key()}")
    else:
        print("✗ Failed to publish TASK_SUBMITTED event")

    # Test subscribing
    print("\n4. Testing event subscription...")

    received_events = []

    def event_handler(event):
        """Handle received events."""
        print(f"  → Received: {event.event_type.value}")
        print(f"    Event ID: {event.event_id}")
        print(f"    Source: {event.source_agent_id}")
        print(f"    Payload: {event.payload}")
        received_events.append(event)

    # Subscribe to agent events
    event_bus.subscribe(
        queue_name="test_agent_queue",
        routing_patterns=["agent.*.normal"],  # All agent events with normal priority
        callback=event_handler,
        enable_dlq=True,
    )
    print("✓ Subscribed to queue: test_agent_queue")
    print("  - Patterns: ['agent.*.normal']")

    # Subscribe to task events
    event_bus.subscribe(
        queue_name="test_task_queue",
        routing_patterns=["task.*.#"],  # All task events
        callback=event_handler,
        enable_dlq=True,
    )
    print("✓ Subscribed to queue: test_task_queue")
    print("  - Patterns: ['task.*.#']")

    # Publish more test events to be consumed
    print("\n5. Publishing additional events for consumption...")
    for i in range(3):
        event = create_agent_event(
            event_type=EventType.AGENT_HEARTBEAT,
            agent_id=f"test_agent_{i:03d}",
            payload={"timestamp": time.time(), "status": "active"},
            trace_id=trace_id,
        )
        event_bus.publish(event)
        print(f"  - Published AGENT_HEARTBEAT #{i+1}")

    # Get queue info
    print("\n6. Checking queue information...")
    for queue_name in ["test_agent_queue", "test_task_queue"]:
        info = event_bus.get_queue_info(queue_name)
        if info:
            print(f"✓ Queue: {queue_name}")
            print(f"  - Messages: {info['message_count']}")
            print(f"  - Consumers: {info['consumer_count']}")
        else:
            print(f"✗ Queue {queue_name} not found")

    # Consume events from agent queue
    print("\n7. Consuming events from test_agent_queue...")
    print("  Starting consumer (will consume for 3 seconds)...")

    def message_callback(ch, method, properties, body):
        """Process message and acknowledge."""
        try:
            event = Event.from_json(body.decode("utf-8"))
            event_handler(event)
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            print(f"  Error processing message: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    # Set up consumer
    event_bus.channel.basic_consume(
        queue="test_agent_queue",
        on_message_callback=message_callback,
        auto_ack=False,
    )

    # Process events for 3 seconds
    try:
        event_bus.connection.process_data_events(time_limit=3)
    except Exception as e:
        print(f"  Note: Consumer ended: {type(e).__name__}")

    # Cancel the consumer
    try:
        event_bus.channel.cancel()
    except:
        pass

    print(f"\n✓ Consumed {len(received_events)} events from test_agent_queue")

    # Test dead-letter queue
    print("\n8. Testing dead-letter queue...")
    print("  (Creating failing consumer to test DLQ...)")

    def failing_handler(event):
        """Handler that always fails."""
        raise Exception("Intentional failure for DLQ test")

    event_bus.subscribe(
        queue_name="test_dlq_queue",
        routing_patterns=["agent.error.#"],
        callback=failing_handler,
        enable_dlq=True,
    )

    # Publish event that will fail
    error_event = create_agent_event(
        event_type=EventType.AGENT_ERROR,
        agent_id="failing_agent",
        payload={"error": "Test error"},
    )
    event_bus.publish(error_event)
    print("✓ Published AGENT_ERROR event for DLQ test")

    # Try to consume (will fail and go to DLQ after retries)
    # Note: In production, this would retry 3 times then go to DLQ
    print("  (In production, this would retry 3 times then move to DLQ)")

    # Check DLQ
    dlq_info = event_bus.get_queue_info("dlq.test_dlq_queue")
    if dlq_info:
        print(f"✓ Dead-letter queue exists")
        print(f"  - Messages in DLQ: {dlq_info['message_count']}")

    # Cleanup
    print("\n9. Cleanup...")
    print("  Purging test queues...")
    for queue_name in ["test_agent_queue", "test_task_queue", "test_dlq_queue"]:
        count = event_bus.purge_queue(queue_name)
        print(f"  - Purged {count} messages from {queue_name}")

    # Close connection
    event_bus.close()
    print("✓ Closed EventBus connection")

    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
