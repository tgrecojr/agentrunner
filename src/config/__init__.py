"""
Configuration module for Multi-Agent Orchestration Platform.

Provides:
- ConfigurationService: Agent configuration management with hot-reload
- AgentConfig: Complete agent configuration model
- PlatformConfig: Platform-wide settings
- LLMConfig: LLM provider configuration
"""

from .configuration_service import ConfigurationService
from .models import (
    AgentConfig,
    AgentType,
    ExecutionMode,
    LLMConfig,
    LLMProvider,
    MonitoringConfig,
    PlatformConfig,
    ResourceLimits,
    ScheduleConfig,
    SlackIntegrationConfig,
    StateConfig,
)

__all__ = [
    # Service
    "ConfigurationService",
    # Main Models
    "AgentConfig",
    "PlatformConfig",
    "LLMConfig",
    # Enums
    "AgentType",
    "ExecutionMode",
    "LLMProvider",
    # Sub-configs
    "ScheduleConfig",
    "SlackIntegrationConfig",
    "MonitoringConfig",
    "ResourceLimits",
    "StateConfig",
]
