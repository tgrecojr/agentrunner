"""
Slack Gateway Integration

Handles Slack webhook events and publishes them to EventBus.

Features:
- Webhook signature verification
- Event parsing (slash commands, messages, button clicks)
- Fast response within 100ms
- Async response handling via response_url
- Rate limit handling with exponential backoff
"""

import hashlib
import hmac
import time
from typing import Any, Dict, Optional

import httpx

from ..messaging.event_bus import EventBus
from ..messaging.events import Event, EventType
from ..utils.logger import StructuredLogger


class SlackGateway:
    """
    Slack Gateway for handling webhook events.

    Features:
    - Signature verification for security
    - Fast event publishing (< 100ms)
    - Async response handling
    - Rate limiting with exponential backoff
    """

    def __init__(
        self,
        event_bus: EventBus,
        signing_secret: str,
        max_retry_attempts: int = 3,
        initial_retry_delay: int = 1
    ):
        """
        Initialize Slack Gateway.

        Args:
            event_bus: Event bus for publishing events
            signing_secret: Slack app signing secret
            max_retry_attempts: Maximum retry attempts for rate limits
            initial_retry_delay: Initial retry delay in seconds
        """
        self.event_bus = event_bus
        self.signing_secret = signing_secret
        self.max_retry_attempts = max_retry_attempts
        self.initial_retry_delay = initial_retry_delay

        # HTTP client for async responses
        self.http_client = httpx.AsyncClient(timeout=30.0)

        # Logger
        self.logger = StructuredLogger("SlackGateway")

        self.logger.info(
            "SlackGateway initialized",
            metadata={
                "max_retry_attempts": max_retry_attempts,
                "initial_retry_delay": initial_retry_delay
            }
        )

    def verify_signature(
        self,
        body: bytes,
        timestamp: str,
        signature: str
    ) -> bool:
        """
        Verify Slack request signature.

        Args:
            body: Request body
            timestamp: Request timestamp from headers
            signature: Request signature from headers

        Returns:
            True if signature is valid, False otherwise
        """
        # Check timestamp to prevent replay attacks (within 5 minutes)
        current_timestamp = int(time.time())
        request_timestamp = int(timestamp)

        if abs(current_timestamp - request_timestamp) > 60 * 5:
            self.logger.warning("Request timestamp too old - possible replay attack")
            return False

        # Calculate signature
        sig_basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
        my_signature = 'v0=' + hmac.new(
            self.signing_secret.encode(),
            sig_basestring.encode(),
            hashlib.sha256
        ).hexdigest()

        # Compare signatures
        return hmac.compare_digest(my_signature, signature)

    def parse_slack_event(
        self,
        event_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Parse Slack event data.

        Args:
            event_data: Raw event data from Slack

        Returns:
            Parsed event or None
        """
        event_type = event_data.get("type")

        # URL verification challenge
        if event_type == "url_verification":
            return {
                "event_type": "url_verification",
                "challenge": event_data.get("challenge")
            }

        # Event callback
        if event_type == "event_callback":
            event = event_data.get("event", {})
            return {
                "event_type": "slack_event",
                "event_subtype": event.get("type"),
                "user": event.get("user"),
                "text": event.get("text", ""),
                "channel": event.get("channel"),
                "ts": event.get("ts"),
                "raw_event": event
            }

        # Slash command
        if event_data.get("command"):
            return {
                "event_type": "slash_command",
                "command": event_data.get("command"),
                "text": event_data.get("text", ""),
                "user_id": event_data.get("user_id"),
                "channel_id": event_data.get("channel_id"),
                "response_url": event_data.get("response_url"),
                "trigger_id": event_data.get("trigger_id")
            }

        # Interactive component (button, menu, etc.)
        if event_data.get("payload"):
            import json
            payload = json.loads(event_data["payload"]) if isinstance(event_data["payload"], str) else event_data["payload"]

            return {
                "event_type": "interactive_component",
                "component_type": payload.get("type"),
                "actions": payload.get("actions", []),
                "user": payload.get("user", {}),
                "channel": payload.get("channel", {}),
                "response_url": payload.get("response_url"),
                "raw_payload": payload
            }

        # Unknown event type
        self.logger.warning(
            f"Unknown Slack event type: {event_type}",
            metadata={"event_data": event_data}
        )
        return None

    async def handle_slack_event(
        self,
        event_data: Dict[str, Any],
        trace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Handle incoming Slack event.

        Args:
            event_data: Slack event data
            trace_id: Optional trace ID for logging

        Returns:
            Response data
        """
        trace_id = trace_id or StructuredLogger.generate_trace_id()

        self.logger.info(
            "Processing Slack event",
            trace_id=trace_id,
            metadata={"event_type": event_data.get("type")}
        )

        # Parse event
        parsed_event = self.parse_slack_event(event_data)

        if not parsed_event:
            self.logger.warning(
                "Failed to parse Slack event",
                trace_id=trace_id
            )
            return {"status": "ignored"}

        # Handle URL verification
        if parsed_event["event_type"] == "url_verification":
            self.logger.info(
                "URL verification challenge received",
                trace_id=trace_id
            )
            return {"challenge": parsed_event["challenge"]}

        # Publish to EventBus (within 100ms)
        event = Event(
            event_type=EventType.EXTERNAL_EVENT,
            payload={
                "source": "slack",
                "parsed_event": parsed_event,
                "raw_event": event_data
            },
            trace_id=trace_id
        )

        # Route based on event type
        routing_key = self._get_routing_key(parsed_event)

        self.event_bus.publish(event=event, routing_key=routing_key)

        self.logger.info(
            f"Slack event published to EventBus",
            trace_id=trace_id,
            metadata={
                "event_type": parsed_event["event_type"],
                "routing_key": routing_key
            }
        )

        # Handle async response if needed
        if "response_url" in parsed_event and parsed_event.get("event_type") in ["slash_command", "interactive_component"]:
            # Queue async response handling
            # For now, return immediate acknowledgment
            return {
                "response_type": "in_channel",
                "text": "Processing your request..."
            }

        return {"status": "ok"}

    def _get_routing_key(self, parsed_event: Dict[str, Any]) -> str:
        """
        Get routing key for event.

        Args:
            parsed_event: Parsed event data

        Returns:
            Routing key
        """
        event_type = parsed_event.get("event_type")

        if event_type == "slash_command":
            command = parsed_event.get("command", "").replace("/", "")
            return f"slack.command.{command}"

        elif event_type == "slack_event":
            subtype = parsed_event.get("event_subtype", "message")
            return f"slack.event.{subtype}"

        elif event_type == "interactive_component":
            component_type = parsed_event.get("component_type", "interaction")
            return f"slack.interaction.{component_type}"

        else:
            return "slack.event.unknown"

    async def send_response(
        self,
        response_url: str,
        message: str,
        response_type: str = "in_channel",
        attachments: Optional[list] = None,
        trace_id: Optional[str] = None
    ) -> bool:
        """
        Send async response to Slack via response_url.

        Args:
            response_url: Slack response URL
            message: Message text
            response_type: "in_channel" or "ephemeral"
            attachments: Optional message attachments
            trace_id: Optional trace ID for logging

        Returns:
            True if successful, False otherwise
        """
        trace_id = trace_id or StructuredLogger.generate_trace_id()

        payload = {
            "response_type": response_type,
            "text": message
        }

        if attachments:
            payload["attachments"] = attachments

        # Retry with exponential backoff
        retry_delay = self.initial_retry_delay

        for attempt in range(self.max_retry_attempts):
            try:
                response = await self.http_client.post(
                    response_url,
                    json=payload
                )

                if response.status_code == 200:
                    self.logger.info(
                        "Response sent to Slack successfully",
                        trace_id=trace_id
                    )
                    return True

                elif response.status_code == 429:
                    # Rate limited - retry with backoff
                    retry_after = int(response.headers.get("Retry-After", retry_delay))

                    self.logger.warning(
                        f"Rate limited by Slack, retrying after {retry_after}s",
                        trace_id=trace_id,
                        metadata={"attempt": attempt + 1}
                    )

                    await asyncio.sleep(retry_after)
                    retry_delay *= 2  # Exponential backoff

                else:
                    self.logger.error(
                        f"Failed to send response to Slack: {response.status_code}",
                        trace_id=trace_id,
                        metadata={"response": response.text}
                    )
                    return False

            except Exception as e:
                self.logger.error(
                    f"Error sending response to Slack: {str(e)}",
                    trace_id=trace_id
                )

                if attempt < self.max_retry_attempts - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2

        return False

    async def post_message(
        self,
        channel: str,
        message: str,
        bot_token: str,
        attachments: Optional[list] = None,
        trace_id: Optional[str] = None
    ) -> bool:
        """
        Post a message to a Slack channel.

        Args:
            channel: Channel ID
            message: Message text
            bot_token: Slack bot token
            attachments: Optional message attachments
            trace_id: Optional trace ID for logging

        Returns:
            True if successful, False otherwise
        """
        trace_id = trace_id or StructuredLogger.generate_trace_id()

        payload = {
            "channel": channel,
            "text": message
        }

        if attachments:
            payload["attachments"] = attachments

        headers = {
            "Authorization": f"Bearer {bot_token}",
            "Content-Type": "application/json"
        }

        try:
            response = await self.http_client.post(
                "https://slack.com/api/chat.postMessage",
                json=payload,
                headers=headers
            )

            result = response.json()

            if result.get("ok"):
                self.logger.info(
                    "Message posted to Slack successfully",
                    trace_id=trace_id,
                    metadata={"channel": channel}
                )
                return True
            else:
                self.logger.error(
                    f"Failed to post message to Slack: {result.get('error')}",
                    trace_id=trace_id
                )
                return False

        except Exception as e:
            self.logger.error(
                f"Error posting message to Slack: {str(e)}",
                trace_id=trace_id
            )
            return False

    async def close(self) -> None:
        """Close HTTP client."""
        await self.http_client.aclose()
        self.logger.info("SlackGateway closed")


# Import asyncio for sleep
import asyncio
