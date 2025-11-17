"""
Configuration models for Multi-Agent Orchestration Platform.

Defines Pydantic models for agent configurations, LLM settings,
and platform configuration with validation.
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class AgentType(str, Enum):
    """Types of agents in the platform."""

    COLLABORATIVE = "collaborative"
    AUTONOMOUS = "autonomous"
    CONTINUOUS = "continuous"


class ExecutionMode(str, Enum):
    """Execution modes for agents."""

    ON_DEMAND = "on_demand"
    SCHEDULED = "scheduled"
    CONTINUOUS = "continuous"
    EVENT_DRIVEN = "event_driven"


class LLMProvider(str, Enum):
    """Supported LLM providers."""

    AWS_BEDROCK = "aws_bedrock"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    CUSTOM = "custom"


class LLMConfig(BaseModel):
    """LLM configuration for agents."""

    provider: LLMProvider = Field(..., description="LLM provider")
    model: str = Field(..., description="Model identifier (e.g., 'claude-3-sonnet')")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="Temperature for generation")
    max_tokens: int = Field(4096, gt=0, description="Maximum tokens for generation")
    top_p: Optional[float] = Field(None, ge=0.0, le=1.0, description="Top-p sampling")
    top_k: Optional[int] = Field(None, gt=0, description="Top-k sampling")
    stop_sequences: Optional[List[str]] = Field(None, description="Stop sequences")

    # Provider-specific settings
    aws_region: Optional[str] = Field(None, description="AWS region for Bedrock")
    api_key: Optional[str] = Field(None, description="API key (loaded from env)")
    api_base: Optional[str] = Field(None, description="Custom API base URL")
    additional_params: Dict[str, Any] = Field(default_factory=dict, description="Additional parameters")

    class Config:
        """Pydantic configuration."""
        use_enum_values = True


class ScheduleConfig(BaseModel):
    """Scheduling configuration for agents."""

    cron_expression: str = Field(..., description="Cron expression for scheduling")
    timezone: str = Field("UTC", description="Timezone for schedule")
    enabled: bool = Field(True, description="Whether schedule is enabled")
    max_concurrent_runs: int = Field(1, gt=0, description="Max concurrent executions")


class SlackIntegrationConfig(BaseModel):
    """Slack integration configuration."""

    enabled: bool = Field(False, description="Enable Slack integration")
    channel_id: Optional[str] = Field(None, description="Slack channel ID")
    bot_token: Optional[str] = Field(None, description="Slack bot token (loaded from env)")
    notification_events: List[str] = Field(
        default_factory=lambda: ["task.completed", "task.failed"],
        description="Events that trigger Slack notifications"
    )


class MonitoringConfig(BaseModel):
    """Monitoring and alerting configuration."""

    enabled: bool = Field(True, description="Enable monitoring")
    heartbeat_interval_seconds: int = Field(60, gt=0, description="Heartbeat interval")
    health_check_enabled: bool = Field(True, description="Enable health checks")
    alert_on_failure: bool = Field(True, description="Alert on task failures")
    alert_threshold: int = Field(3, gt=0, description="Number of failures before alert")


class ResourceLimits(BaseModel):
    """Resource limits for agent execution."""

    max_execution_time_seconds: int = Field(300, gt=0, description="Max execution time")
    max_memory_mb: Optional[int] = Field(None, gt=0, description="Max memory in MB")
    max_retries: int = Field(3, ge=0, description="Max retry attempts")
    retry_delay_seconds: int = Field(5, gt=0, description="Delay between retries")


class StateConfig(BaseModel):
    """State persistence configuration."""

    enabled: bool = Field(True, description="Enable state persistence")
    save_on_completion: bool = Field(True, description="Save state on task completion")
    save_interval_seconds: Optional[int] = Field(
        None, gt=0, description="Periodic save interval (for continuous agents)"
    )
    compression_enabled: bool = Field(True, description="Enable state compression")
    ttl_seconds: Optional[int] = Field(None, gt=0, description="State TTL in cache")


class AgentConfig(BaseModel):
    """
    Complete agent configuration.

    This is the main configuration model that defines an agent's behavior,
    execution parameters, and integrations.
    """

    # Core identification
    name: str = Field(..., min_length=1, description="Unique agent name")
    description: Optional[str] = Field(None, description="Agent description")
    version: str = Field("1.0.0", description="Configuration version")

    # Agent type and execution
    agent_type: AgentType = Field(..., description="Type of agent")
    execution_mode: ExecutionMode = Field(..., description="Execution mode")

    # LLM configuration
    llm_config: LLMConfig = Field(..., description="LLM configuration")

    # System prompt and instructions
    system_prompt: Optional[str] = Field(None, description="System prompt for LLM")
    instructions: Optional[str] = Field(None, description="Additional instructions")

    # Execution settings
    schedule: Optional[ScheduleConfig] = Field(None, description="Schedule configuration")
    resource_limits: ResourceLimits = Field(
        default_factory=ResourceLimits, description="Resource limits"
    )

    # State management
    state_config: StateConfig = Field(
        default_factory=StateConfig, description="State persistence config"
    )

    # Integrations
    slack_integration: Optional[SlackIntegrationConfig] = Field(
        None, description="Slack integration config"
    )

    # Monitoring
    monitoring: MonitoringConfig = Field(
        default_factory=MonitoringConfig, description="Monitoring config"
    )

    # Collaborative agent settings
    plan_coordination_enabled: bool = Field(
        False, description="Enable plan coordination (for collaborative agents)"
    )
    shared_context_enabled: bool = Field(
        False, description="Enable shared context (for collaborative agents)"
    )

    # Event subscriptions
    event_subscriptions: List[str] = Field(
        default_factory=list,
        description="Event routing patterns to subscribe to"
    )

    # Tags and metadata
    tags: List[str] = Field(default_factory=list, description="Agent tags")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Custom metadata")

    # Feature flags
    enabled: bool = Field(True, description="Whether agent is enabled")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate agent name format."""
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Agent name must be alphanumeric (underscores and hyphens allowed)")
        return v

    @field_validator("event_subscriptions")
    @classmethod
    def validate_event_subscriptions(cls, v: List[str]) -> List[str]:
        """Validate event subscription patterns."""
        for pattern in v:
            if not pattern:
                raise ValueError("Event subscription pattern cannot be empty")
        return v

    class Config:
        """Pydantic configuration."""
        use_enum_values = True
        json_schema_extra = {
            "example": {
                "name": "customer_support_agent",
                "description": "Handles customer support inquiries",
                "agent_type": "autonomous",
                "execution_mode": "event_driven",
                "llm_config": {
                    "provider": "aws_bedrock",
                    "model": "anthropic.claude-3-sonnet-20240229-v1:0",
                    "temperature": 0.7,
                    "max_tokens": 4096,
                    "aws_region": "us-east-1"
                },
                "system_prompt": "You are a helpful customer support agent.",
                "event_subscriptions": ["slack.message.received"],
                "enabled": True
            }
        }


class PlatformConfig(BaseModel):
    """
    Platform-wide configuration settings.

    Loaded from environment variables and configuration files.
    """

    # Service endpoints
    state_manager_url: str = Field("http://localhost:8001", description="StateManager URL")
    rabbitmq_url: str = Field("amqp://guest:guest@localhost:5672/", description="RabbitMQ URL")
    redis_url: str = Field("redis://localhost:6379/0", description="Redis URL")
    postgres_url: str = Field(
        "postgresql://agentrunner_user:agentrunner@localhost:5432/agentrunner",
        description="PostgreSQL URL"
    )

    # Platform settings
    log_level: str = Field("INFO", description="Logging level")
    environment: str = Field("development", description="Environment (development/production)")
    debug: bool = Field(False, description="Debug mode")

    # Agent discovery
    agent_config_dir: str = Field("config/agents", description="Agent config directory")
    hot_reload_enabled: bool = Field(True, description="Enable config hot-reload")
    hot_reload_interval_seconds: int = Field(5, gt=0, description="Hot-reload check interval")

    # Security
    enable_auth: bool = Field(False, description="Enable authentication")
    api_key_header: str = Field("X-API-Key", description="API key header name")

    # Performance
    max_workers: int = Field(4, gt=0, description="Max worker threads")
    task_timeout_seconds: int = Field(300, gt=0, description="Default task timeout")

    class Config:
        """Pydantic configuration."""
        env_prefix = "PLATFORM_"
