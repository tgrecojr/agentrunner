# ConfigurationService - Agent Configuration Management

YAML-based configuration management with hot-reload, validation, and secrets management for the Multi-Agent Orchestration Platform.

## Features

- **YAML-Based Configuration**: Human-readable agent definitions
- **Pydantic Validation**: Type-safe configurations with automatic validation
- **Hot-Reload**: Automatic detection and reload of configuration changes with watchdog
- **Secrets Management**: Secure injection of credentials from environment variables
- **Configuration Filtering**: Query agents by type, execution mode, or status
- **Health Monitoring**: Built-in health checks

## Quick Start

### Installation

Ensure required dependencies are installed:

```bash
pip install pyyaml pydantic watchdog python-dotenv
```

### Basic Usage

```python
from src.config import ConfigurationService

# Initialize service
config_service = ConfigurationService(
    config_dir="config/agents",
    enable_hot_reload=True
)

# Get all agent configurations
all_configs = config_service.get_all_configs()

# Get specific agent
agent_config = config_service.get_agent_config("customer_support_agent")

# Filter by type
autonomous_agents = config_service.get_agents_by_type("autonomous")

# Get enabled agents only
enabled_agents = config_service.get_enabled_agents()

# Health check
health = config_service.health_check()
print(f"Status: {health['status']}")
```

## Configuration Schema

### Agent Configuration File

Agent configurations are defined in YAML files in `config/agents/`:

```yaml
# config/agents/my_agent.yaml

name: my_agent
description: "Agent description"
version: "1.0.0"

# Agent type and execution
agent_type: autonomous  # collaborative | autonomous | continuous
execution_mode: event_driven  # on_demand | scheduled | continuous | event_driven

# LLM Configuration
llm_config:
  provider: aws_bedrock  # aws_bedrock | openai | anthropic | custom
  model: "anthropic.claude-3-sonnet-20240229-v1:0"
  temperature: 0.7
  max_tokens: 4096
  aws_region: us-east-1  # For AWS Bedrock

# System prompt
system_prompt: |
  You are a helpful AI assistant.

# Event subscriptions (for event-driven agents)
event_subscriptions:
  - "task.*.high"
  - "slack.message.received"

# Optional: Schedule configuration (for scheduled agents)
schedule:
  cron_expression: "0 9 * * *"  # 9 AM daily
  timezone: "UTC"
  enabled: true

# Optional: Slack integration
slack_integration:
  enabled: true
  notification_events:
    - "task.completed"
    - "task.failed"

# Resource limits
resource_limits:
  max_execution_time_seconds: 300
  max_retries: 3
  retry_delay_seconds: 5

# State management
state_config:
  enabled: true
  save_on_completion: true
  save_interval_seconds: 60  # For continuous agents
  compression_enabled: true

# Monitoring
monitoring:
  enabled: true
  heartbeat_interval_seconds: 60
  alert_on_failure: true

# Tags
tags:
  - production
  - critical

enabled: true
```

## Configuration Models

### AgentConfig

Main configuration model for agents:

```python
from src.config import AgentConfig, LLMConfig

# Programmatic configuration
agent_config = AgentConfig(
    name="my_agent",
    agent_type="autonomous",
    execution_mode="on_demand",
    llm_config=LLMConfig(
        provider="aws_bedrock",
        model="claude-3-sonnet",
        temperature=0.7,
        max_tokens=4096
    ),
    enabled=True
)
```

### LLM Providers

Supported LLM providers:

#### AWS Bedrock

```yaml
llm_config:
  provider: aws_bedrock
  model: "anthropic.claude-3-sonnet-20240229-v1:0"
  temperature: 0.7
  max_tokens: 4096
  aws_region: us-east-1  # Injected from AWS_REGION env var if not specified
```

AWS credentials are automatically loaded from:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_REGION`

#### OpenAI

```yaml
llm_config:
  provider: openai
  model: "gpt-4-turbo-preview"
  temperature: 0.7
  max_tokens: 4096
  # api_key injected from OPENAI_API_KEY env var
```

#### Anthropic

```yaml
llm_config:
  provider: anthropic
  model: "claude-3-opus-20240229"
  temperature: 0.7
  max_tokens: 4096
  # api_key injected from ANTHROPIC_API_KEY env var
```

### Agent Types

#### Collaborative Agents

Work together on complex multi-step tasks:

```yaml
agent_type: collaborative
execution_mode: on_demand

# Enable collaboration features
plan_coordination_enabled: true
shared_context_enabled: true

event_subscriptions:
  - "plan.created"
  - "plan.step.completed"
```

#### Autonomous Agents

Execute tasks independently:

```yaml
agent_type: autonomous
execution_mode: event_driven

event_subscriptions:
  - "task.assigned.agent_name"
  - "slack.message.received"
```

#### Continuous Agents

Run continuously with conversation state:

```yaml
agent_type: continuous
execution_mode: continuous

state_config:
  enabled: true
  save_interval_seconds: 300  # Save state every 5 minutes
  compression_enabled: true
```

### Execution Modes

#### On-Demand

```yaml
execution_mode: on_demand
# Triggered via API calls
```

#### Event-Driven

```yaml
execution_mode: event_driven

event_subscriptions:
  - "task.submitted.#"
  - "slack.message.received"
```

#### Scheduled

```yaml
execution_mode: scheduled

schedule:
  cron_expression: "0 9 * * *"  # 9 AM daily
  timezone: "America/New_York"
  enabled: true
  max_concurrent_runs: 1
```

#### Continuous

```yaml
execution_mode: continuous

state_config:
  save_interval_seconds: 300  # Periodic state saves
```

## Secrets Management

### Environment Variables

Secrets are automatically injected from environment variables:

**Required Infrastructure Secrets:**
- `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`
- `POSTGRES_USER`, `POSTGRES_PASSWORD`
- `REDIS_HOST`, `REDIS_PORT`
- `RABBITMQ_HOST`, `RABBITMQ_PORT`
- `RABBITMQ_USER`, `RABBITMQ_PASSWORD`

**LLM Provider Secrets (at least one required):**
- AWS Bedrock: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`
- OpenAI: `OPENAI_API_KEY`
- Anthropic: `ANTHROPIC_API_KEY`

**Integration Secrets:**
- Slack: `SLACK_BOT_TOKEN`

### .env File

Create a `.env` file in the project root:

```bash
# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=agentrunner
POSTGRES_USER=agentrunner_user
POSTGRES_PASSWORD=your_password

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# RabbitMQ
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_USER=guest
RABBITMQ_PASSWORD=guest

# AWS Bedrock
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=us-east-1

# Slack
SLACK_BOT_TOKEN=xoxb-your-token
```

## Hot-Reload

Configuration files are automatically monitored for changes:

```python
# Enable hot-reload (default)
config_service = ConfigurationService(
    config_dir="config/agents",
    enable_hot_reload=True
)

# File changes are detected automatically
# New files are loaded
# Modified files are reloaded
# Deleted files are removed from configurations
```

### Manual Reload

```python
# Reload all configurations
config_service.reload_all_configurations()

# Validate before loading
config_data = {...}
is_valid, error = config_service.validate_configuration(config_data)
if is_valid:
    # Save to file
    with open("config/agents/new_agent.yaml", "w") as f:
        yaml.dump(config_data, f)
```

## ConfigurationService API

### Initialization

```python
ConfigurationService(
    config_dir="config/agents",
    platform_config=None,  # Optional PlatformConfig
    enable_hot_reload=True
)
```

### Query Methods

```python
# Get specific agent
config = config_service.get_agent_config("agent_name")

# Get all configurations
all_configs = config_service.get_all_configs()

# Get enabled agents only
enabled = config_service.get_enabled_agents()

# Filter by agent type
autonomous = config_service.get_agents_by_type("autonomous")
collaborative = config_service.get_agents_by_type("collaborative")
continuous = config_service.get_agents_by_type("continuous")

# Filter by execution mode
event_driven = config_service.get_agents_by_execution_mode("event_driven")
scheduled = config_service.get_agents_by_execution_mode("scheduled")
```

### Management Methods

```python
# Reload all configurations
config_service.reload_all_configurations()

# Validate configuration
is_valid, error = config_service.validate_configuration(config_data)

# Get configuration errors
errors = config_service.get_configuration_errors()

# Health check
health = config_service.health_check()

# Get secrets
api_key = config_service.get_secret("OPENAI_API_KEY")

# Stop file watcher
config_service.stop()
```

### Context Manager

```python
with ConfigurationService(config_dir="config/agents") as service:
    configs = service.get_all_configs()
    # Automatically stops file watcher on exit
```

## Platform Configuration

Platform-wide settings loaded from environment:

```python
from src.config import PlatformConfig

# Loaded automatically by ConfigurationService
platform_config = config_service.platform_config

# Access settings
print(platform_config.environment)  # development/production
print(platform_config.log_level)  # INFO, DEBUG, etc.
print(platform_config.state_manager_url)
print(platform_config.rabbitmq_url)
```

Environment variables for platform config:

```bash
STATE_MANAGER_URL=http://localhost:8001
LOG_LEVEL=INFO
ENVIRONMENT=development
DEBUG=false
AGENT_CONFIG_DIR=config/agents
HOT_RELOAD_ENABLED=true
MAX_WORKERS=4
```

## Health Monitoring

```python
health = config_service.health_check()

# Returns:
{
    "status": "healthy",
    "loaded_configs": 5,
    "config_errors": 0,
    "hot_reload_enabled": True,
    "watcher_running": True,
    "config_directory": "config/agents"
}
```

## Best Practices

### Configuration Organization

1. **One File Per Agent**: Each agent should have its own YAML file
2. **Descriptive Names**: Use clear, descriptive names (e.g., `customer_support_agent.yaml`)
3. **Version Control**: Keep configurations in version control
4. **Environment-Specific Configs**: Use different directories for dev/staging/prod

### Security

1. **Never Commit Secrets**: Keep `.env` in `.gitignore`
2. **Use Environment Variables**: All secrets should be in `.env`, not YAML files
3. **Validate Configurations**: Always validate before deploying

### Performance

1. **Hot-Reload in Development**: Enable for faster iteration
2. **Disable in Production**: Consider disabling hot-reload for stability
3. **Monitor File Count**: Limit number of configuration files (< 100)

### Validation

```python
# Validate before saving
config_data = {
    "name": "new_agent",
    "agent_type": "autonomous",
    "execution_mode": "on_demand",
    "llm_config": {
        "provider": "aws_bedrock",
        "model": "claude-3-sonnet",
        "temperature": 0.7,
        "max_tokens": 4096
    }
}

is_valid, error = config_service.validate_configuration(config_data)
if is_valid:
    # Save configuration
    with open(f"config/agents/{config_data['name']}.yaml", "w") as f:
        yaml.dump(config_data, f)
else:
    print(f"Validation error: {error}")
```

## Error Handling

```python
# Check for configuration errors
errors = config_service.get_configuration_errors()
if errors:
    for agent_name, error_msg in errors.items():
        print(f"Error in {agent_name}: {error_msg}")

# Handle missing configurations
config = config_service.get_agent_config("nonexistent")
if config is None:
    print("Configuration not found")
```

## Example Configurations

### Customer Support Agent (Event-Driven)

```yaml
name: customer_support_agent
agent_type: autonomous
execution_mode: event_driven

llm_config:
  provider: aws_bedrock
  model: "anthropic.claude-3-sonnet-20240229-v1:0"
  temperature: 0.7
  max_tokens: 4096

system_prompt: |
  You are a helpful customer support agent.

event_subscriptions:
  - "slack.message.received"

slack_integration:
  enabled: true

enabled: true
```

### Data Analyzer (Scheduled)

```yaml
name: data_analyzer
agent_type: collaborative
execution_mode: scheduled

schedule:
  cron_expression: "0 6 * * *"  # 6 AM daily
  timezone: "America/New_York"

llm_config:
  provider: aws_bedrock
  model: "anthropic.claude-3-sonnet-20240229-v1:0"
  temperature: 0.3

plan_coordination_enabled: true
shared_context_enabled: true

enabled: true
```

### System Monitor (Continuous)

```yaml
name: system_monitor
agent_type: continuous
execution_mode: continuous

llm_config:
  provider: aws_bedrock
  model: "anthropic.claude-3-haiku-20240307-v1:0"
  temperature: 0.5
  max_tokens: 2048

state_config:
  enabled: true
  save_interval_seconds: 300
  compression_enabled: true

monitoring:
  enabled: true
  heartbeat_interval_seconds: 30

enabled: true
```

## Testing

Run the test script:

```bash
python test_config_service.py
```

Tests cover:
- Configuration loading
- Validation
- Hot-reload
- Filtering
- Health checks
- Context manager
- Error handling

## License

Internal use only - Multi-Agent Orchestration Platform
