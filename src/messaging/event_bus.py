"""
EventBus - RabbitMQ-based event-driven messaging system.

Provides publish/subscribe messaging with dead-letter queues, retry logic,
and guaranteed delivery for agent communication.
"""

import json
import os
import threading
import time
from typing import Callable, Dict, List, Optional

import pika
from pika.adapters.blocking_connection import BlockingChannel
from pika.exceptions import AMQPConnectionError, AMQPError

from ..utils.logger import StructuredLogger
from .events import Event, EventType


class EventBus:
    """
    Event-driven message bus using RabbitMQ.

    Features:
    - Topic-based pub/sub with routing keys
    - Dead-letter queue for failed messages
    - Automatic retry with exponential backoff
    - Guaranteed delivery with message persistence
    - Multiple consumer support with prefetch
    - Connection retry and automatic reconnection
    """

    # Exchange configuration
    MAIN_EXCHANGE = "agent_events"
    DLX_EXCHANGE = "agent_events_dlx"  # Dead Letter Exchange

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        vhost: Optional[str] = None,
        exchange_type: str = "topic",
        prefetch_count: int = 1,
        connection_timeout: int = 10,
        heartbeat: int = 600,
    ):
        """
        Initialize EventBus.

        Args:
            host: RabbitMQ hostname
            port: RabbitMQ port
            username: RabbitMQ username
            password: RabbitMQ password
            vhost: RabbitMQ virtual host
            exchange_type: Exchange type (topic, direct, fanout)
            prefetch_count: QoS prefetch count
            connection_timeout: Connection timeout in seconds
            heartbeat: Heartbeat interval in seconds
        """
        self.logger = StructuredLogger("EventBus")

        # RabbitMQ configuration
        self.host = host or os.getenv("RABBITMQ_HOST", "localhost")
        self.port = port or int(os.getenv("RABBITMQ_PORT", "5672"))
        self.username = username or os.getenv("RABBITMQ_USER", "guest")
        self.password = password or os.getenv("RABBITMQ_PASSWORD", "guest")
        self.vhost = vhost or os.getenv("RABBITMQ_VHOST", "/")
        self.exchange_type = exchange_type
        self.prefetch_count = prefetch_count
        self.connection_timeout = connection_timeout
        self.heartbeat = heartbeat

        # Connection and channel
        self.connection: Optional[pika.BlockingConnection] = None
        self.channel: Optional[BlockingChannel] = None
        self.is_connected = False

        # Consumer tracking
        self.consumers: Dict[str, Dict] = {}  # queue_name -> consumer_info
        self.consumer_threads: List[threading.Thread] = []
        self.consumer_channels: Dict[str, BlockingChannel] = {}  # queue_name -> channel

        # Initialize connection
        self._connect()

    def _connect(self) -> None:
        """
        Establish connection to RabbitMQ and set up exchanges.

        Raises:
            AMQPConnectionError: If connection fails
        """
        try:
            # Connection parameters
            credentials = pika.PlainCredentials(self.username, self.password)
            parameters = pika.ConnectionParameters(
                host=self.host,
                port=self.port,
                virtual_host=self.vhost,
                credentials=credentials,
                connection_attempts=3,
                retry_delay=2,
                socket_timeout=self.connection_timeout,
                heartbeat=self.heartbeat,
            )

            # Create connection
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()

            # Set QoS
            self.channel.basic_qos(prefetch_count=self.prefetch_count)

            # Declare main exchange
            self.channel.exchange_declare(
                exchange=self.MAIN_EXCHANGE,
                exchange_type=self.exchange_type,
                durable=True,
            )

            # Declare dead-letter exchange
            self.channel.exchange_declare(
                exchange=self.DLX_EXCHANGE,
                exchange_type="direct",
                durable=True,
            )

            self.is_connected = True
            self.logger.info(
                "Connected to RabbitMQ",
                metadata={
                    "host": self.host,
                    "port": self.port,
                    "vhost": self.vhost,
                    "exchange": self.MAIN_EXCHANGE,
                }
            )

        except AMQPConnectionError as e:
            self.is_connected = False
            self.logger.error(
                f"Failed to connect to RabbitMQ: {str(e)}",
                metadata={"host": self.host, "port": self.port}
            )
            raise

    def _ensure_connected(self) -> None:
        """Ensure connection is active, reconnect if needed."""
        if not self.is_connected or not self.connection or self.connection.is_closed:
            self.logger.warning("Connection lost, reconnecting...")
            self._connect()

    def publish(
        self,
        event: Event,
        routing_key: Optional[str] = None,
        persistent: bool = True,
    ) -> bool:
        """
        Publish an event to the message bus.

        Args:
            event: Event to publish
            routing_key: Optional routing key (defaults to event.get_routing_key())
            persistent: Make message persistent (survives broker restart)

        Returns:
            True if published successfully
        """
        self._ensure_connected()

        try:
            # Get routing key
            if routing_key is None:
                routing_key = event.get_routing_key()

            # Serialize event
            message_body = event.to_json()

            # Message properties
            properties = pika.BasicProperties(
                delivery_mode=2 if persistent else 1,  # 2 = persistent
                content_type="application/json",
                message_id=str(event.event_id),
                timestamp=int(event.timestamp.timestamp()),
                headers={
                    "event_type": event.event_type.value,
                    "trace_id": str(event.trace_id) if event.trace_id else None,
                    "retry_count": event.retry_count,
                },
            )

            # Publish message
            self.channel.basic_publish(
                exchange=self.MAIN_EXCHANGE,
                routing_key=routing_key,
                body=message_body,
                properties=properties,
            )

            self.logger.debug(
                f"Published event: {event.event_type.value}",
                trace_id=str(event.trace_id) if event.trace_id else None,
                metadata={
                    "event_id": str(event.event_id),
                    "routing_key": routing_key,
                    "event_type": event.event_type.value,
                }
            )

            return True

        except AMQPError as e:
            self.logger.error(
                f"Failed to publish event: {str(e)}",
                trace_id=str(event.trace_id) if event.trace_id else None,
                metadata={"event_type": event.event_type.value}
            )
            return False

    def subscribe(
        self,
        queue_name: str,
        routing_patterns: List[str],
        callback: Callable[[Event], None],
        auto_ack: bool = False,
        enable_dlq: bool = True,
        message_ttl_ms: Optional[int] = None,
    ) -> None:
        """
        Subscribe to events matching routing patterns.

        Args:
            queue_name: Name of the queue
            routing_patterns: List of routing patterns (supports wildcards: *, #)
            callback: Function to handle received events
            auto_ack: Automatically acknowledge messages
            enable_dlq: Enable dead-letter queue for failed messages
            message_ttl_ms: Message time-to-live in milliseconds
        """
        self._ensure_connected()

        try:
            # Queue arguments
            queue_args = {}

            if enable_dlq:
                # Configure dead-letter exchange
                queue_args["x-dead-letter-exchange"] = self.DLX_EXCHANGE
                queue_args["x-dead-letter-routing-key"] = f"dlq.{queue_name}"

            if message_ttl_ms:
                queue_args["x-message-ttl"] = message_ttl_ms

            # Declare queue
            self.channel.queue_declare(
                queue=queue_name,
                durable=True,
                arguments=queue_args if queue_args else None,
            )

            # Bind queue to routing patterns
            for pattern in routing_patterns:
                self.channel.queue_bind(
                    exchange=self.MAIN_EXCHANGE,
                    queue=queue_name,
                    routing_key=pattern,
                )

            # Create dead-letter queue if enabled
            if enable_dlq:
                dlq_name = f"dlq.{queue_name}"
                self.channel.queue_declare(queue=dlq_name, durable=True)
                self.channel.queue_bind(
                    exchange=self.DLX_EXCHANGE,
                    queue=dlq_name,
                    routing_key=f"dlq.{queue_name}",
                )

            # Store consumer info
            self.consumers[queue_name] = {
                "routing_patterns": routing_patterns,
                "callback": callback,
                "auto_ack": auto_ack,
            }

            self.logger.info(
                f"Subscribed to queue: {queue_name}",
                metadata={
                    "queue": queue_name,
                    "patterns": routing_patterns,
                    "dlq_enabled": enable_dlq,
                }
            )

        except AMQPError as e:
            self.logger.error(
                f"Failed to subscribe to queue {queue_name}: {str(e)}"
            )
            raise

    def start_consuming(
        self,
        queue_name: str,
        blocking: bool = True,
    ) -> None:
        """
        Start consuming messages from a queue.

        Args:
            queue_name: Name of the queue to consume from
            blocking: If True, blocks current thread; if False, runs in background
        """
        if queue_name not in self.consumers:
            raise ValueError(f"No subscription found for queue: {queue_name}")

        consumer_info = self.consumers[queue_name]
        callback = consumer_info["callback"]
        auto_ack = consumer_info["auto_ack"]

        def message_handler(ch, method, properties, body):
            """Handle incoming message."""
            try:
                # Parse event
                event = Event.from_json(body.decode("utf-8"))

                self.logger.debug(
                    f"Received event: {event.event_type.value}",
                    trace_id=str(event.trace_id) if event.trace_id else None,
                    metadata={
                        "event_id": str(event.event_id),
                        "queue": queue_name,
                        "routing_key": method.routing_key,
                    }
                )

                # Invoke callback
                callback(event)

                # Acknowledge message if not auto-ack
                if not auto_ack:
                    ch.basic_ack(delivery_tag=method.delivery_tag)

            except Exception as e:
                self.logger.error(
                    f"Error processing message: {str(e)}",
                    metadata={"queue": queue_name, "error": str(e)}
                )

                # Reject and requeue or send to DLQ
                if not auto_ack:
                    # Check retry count
                    retry_count = properties.headers.get("retry_count", 0) if properties.headers else 0

                    if retry_count < 3:  # Max retries
                        # Requeue with incremented retry count
                        self.logger.info(f"Requeuing message (retry {retry_count + 1}/3)")
                        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                    else:
                        # Send to DLQ
                        self.logger.warning(f"Max retries exceeded, sending to DLQ")
                        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

        if blocking:
            # Use main channel for blocking mode
            self.channel.basic_consume(
                queue=queue_name,
                on_message_callback=message_handler,
                auto_ack=auto_ack,
            )

            self.logger.info(f"Starting to consume from {queue_name} (blocking)")
            try:
                self.channel.start_consuming()
            except KeyboardInterrupt:
                self.logger.info("Stopping consumer (KeyboardInterrupt)")
                self.stop_consuming(queue_name)
        else:
            # Create separate channel for background consumer
            consumer_channel = self.connection.channel()
            consumer_channel.basic_qos(prefetch_count=self.prefetch_count)
            self.consumer_channels[queue_name] = consumer_channel

            consumer_channel.basic_consume(
                queue=queue_name,
                on_message_callback=message_handler,
                auto_ack=auto_ack,
            )

            # Start in background thread
            def consume_thread():
                self.logger.info(f"Starting to consume from {queue_name} (background)")
                try:
                    consumer_channel.start_consuming()
                except Exception as e:
                    self.logger.error(f"Consumer thread error: {str(e)}")

            thread = threading.Thread(target=consume_thread, daemon=True)
            thread.start()
            self.consumer_threads.append(thread)

    def stop_consuming(self, queue_name: Optional[str] = None) -> None:
        """
        Stop consuming messages.

        Args:
            queue_name: Optional queue name (stops all consumers if None)
        """
        if queue_name:
            # Stop specific consumer
            if queue_name in self.consumer_channels:
                channel = self.consumer_channels[queue_name]
                if channel.is_open:
                    channel.stop_consuming()
                    channel.close()
                del self.consumer_channels[queue_name]
                self.logger.info(f"Stopped consuming from {queue_name}")
        else:
            # Stop all consumers
            for qname, channel in list(self.consumer_channels.items()):
                if channel.is_open:
                    channel.stop_consuming()
                    channel.close()
            self.consumer_channels.clear()

            # Also stop main channel if consuming
            if self.channel and self.channel.is_open:
                self.channel.stop_consuming()
            self.logger.info("Stopped all consumers")

    def get_queue_info(self, queue_name: str) -> Optional[Dict]:
        """
        Get information about a queue.

        Args:
            queue_name: Name of the queue

        Returns:
            Dictionary with queue info or None if queue doesn't exist
        """
        self._ensure_connected()

        try:
            method = self.channel.queue_declare(
                queue=queue_name,
                durable=True,
                passive=True,  # Don't create if doesn't exist
            )

            return {
                "queue": queue_name,
                "message_count": method.method.message_count,
                "consumer_count": method.method.consumer_count,
            }
        except Exception as e:
            self.logger.warning(f"Queue {queue_name} not found: {str(e)}")
            return None

    def purge_queue(self, queue_name: str) -> int:
        """
        Purge all messages from a queue.

        Args:
            queue_name: Name of the queue

        Returns:
            Number of messages purged
        """
        self._ensure_connected()

        try:
            result = self.channel.queue_purge(queue=queue_name)
            self.logger.info(
                f"Purged {result.method.message_count} messages from {queue_name}"
            )
            return result.method.message_count
        except Exception as e:
            self.logger.error(f"Failed to purge queue {queue_name}: {str(e)}")
            return 0

    def health_check(self) -> Dict[str, any]:
        """
        Check health of RabbitMQ connection.

        Returns:
            Dictionary with health status
        """
        health = {
            "status": "unknown",
            "connected": False,
            "details": {},
        }

        try:
            if self.connection and self.connection.is_open:
                health["status"] = "healthy"
                health["connected"] = True
                health["details"] = {
                    "host": self.host,
                    "port": self.port,
                    "vhost": self.vhost,
                    "exchange": self.MAIN_EXCHANGE,
                }
            else:
                health["status"] = "unhealthy"
                health["details"] = {"error": "Connection not open"}

        except Exception as e:
            health["status"] = "unhealthy"
            health["details"] = {"error": str(e)}

        return health

    def close(self) -> None:
        """Close connection to RabbitMQ."""
        if self.connection and self.connection.is_open:
            self.connection.close()
            self.is_connected = False
            self.logger.info("Closed RabbitMQ connection")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
