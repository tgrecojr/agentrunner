"""
Slack Gateway API

FastAPI endpoints for Slack webhook handling.
"""

import os
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from ..messaging.event_bus import EventBus
from .slack_gateway import SlackGateway

# ============================================
# Request/Response Models
# ============================================


class SlackMessageRequest(BaseModel):
    """Request model for sending Slack messages."""
    channel: str
    message: str
    bot_token: str
    attachments: list = None


class SlackResponseRequest(BaseModel):
    """Request model for sending async Slack responses."""
    response_url: str
    message: str
    response_type: str = "in_channel"
    attachments: list = None


# ============================================
# Initialize Services
# ============================================

# Event Bus
event_bus = EventBus(
    rabbitmq_url=os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672//")
)

# Slack Gateway
slack_gateway = SlackGateway(
    event_bus=event_bus,
    signing_secret=os.getenv("SLACK_SIGNING_SECRET", ""),
    max_retry_attempts=int(os.getenv("SLACK_MAX_RETRY_ATTEMPTS", "3")),
    initial_retry_delay=int(os.getenv("SLACK_RETRY_DELAY", "1"))
)

# ============================================
# FastAPI App
# ============================================

app = FastAPI(
    title="Slack Gateway API",
    description="Handles Slack webhook events and integrations",
    version="1.0.0"
)


# ============================================
# Startup/Shutdown Events
# ============================================


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    await event_bus.connect()


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    await slack_gateway.close()
    await event_bus.disconnect()


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
# Slack Webhook Endpoints
# ============================================


@app.post("/slack/events")
async def slack_events(request: Request) -> Dict[str, Any]:
    """
    Handle Slack webhook events.

    This endpoint receives all Slack events including:
    - Event callbacks (messages, reactions, etc.)
    - Slash commands
    - Interactive components (buttons, menus)

    Returns:
        Response for Slack (within 100ms)
    """
    # Get headers
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")

    # Get body
    body = await request.body()

    # Verify signature
    if not slack_gateway.verify_signature(body, timestamp, signature):
        slack_gateway.logger.warning("Invalid Slack signature")
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse body
    content_type = request.headers.get("content-type", "")

    if "application/json" in content_type:
        # JSON event (event_callback)
        event_data = await request.json()

    elif "application/x-www-form-urlencoded" in content_type:
        # Form-encoded (slash command or interactive component)
        form_data = await request.form()
        event_data = dict(form_data)

    else:
        raise HTTPException(status_code=400, detail="Unsupported content type")

    # Handle event (must respond within 100ms)
    try:
        response = await slack_gateway.handle_slack_event(event_data)
        return response

    except Exception as e:
        slack_gateway.logger.error(f"Error handling Slack event: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/slack/interactive")
async def slack_interactive(request: Request) -> Dict[str, Any]:
    """
    Handle Slack interactive components (buttons, menus, etc.).

    This is an alternative endpoint for interactive components.
    """
    # Get headers
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")

    # Get body
    body = await request.body()

    # Verify signature
    if not slack_gateway.verify_signature(body, timestamp, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse form data
    form_data = await request.form()
    event_data = dict(form_data)

    # Handle event
    try:
        response = await slack_gateway.handle_slack_event(event_data)
        return response

    except Exception as e:
        slack_gateway.logger.error(f"Error handling interactive component: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# Outbound Message Endpoints
# ============================================


@app.post("/slack/send-message")
async def send_message(request: SlackMessageRequest) -> Dict[str, Any]:
    """
    Send a message to a Slack channel.

    Args:
        request: Message request

    Returns:
        Send result
    """
    success = await slack_gateway.post_message(
        channel=request.channel,
        message=request.message,
        bot_token=request.bot_token,
        attachments=request.attachments
    )

    if success:
        return {"status": "sent", "channel": request.channel}
    else:
        raise HTTPException(status_code=500, detail="Failed to send message")


@app.post("/slack/send-response")
async def send_response(request: SlackResponseRequest) -> Dict[str, Any]:
    """
    Send an async response to Slack via response_url.

    Args:
        request: Response request

    Returns:
        Send result
    """
    success = await slack_gateway.send_response(
        response_url=request.response_url,
        message=request.message,
        response_type=request.response_type,
        attachments=request.attachments
    )

    if success:
        return {"status": "sent"}
    else:
        raise HTTPException(status_code=500, detail="Failed to send response")


# ============================================
# Testing Endpoints (Development Only)
# ============================================


@app.post("/slack/test-event")
async def test_event(event_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Test endpoint for simulating Slack events (development only).

    Args:
        event_data: Simulated event data

    Returns:
        Event handling result
    """
    # Only allow in development
    if os.getenv("ENVIRONMENT") != "development":
        raise HTTPException(status_code=403, detail="Only available in development")

    try:
        response = await slack_gateway.handle_slack_event(event_data)
        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# Run Server (for development)
# ============================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)
