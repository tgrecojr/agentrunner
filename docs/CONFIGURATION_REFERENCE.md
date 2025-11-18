# Configuration Reference
**Multi-Agent Orchestration Platform**

Complete reference for all configuration options, environment variables, and agent configuration schemas.

---

## Table of Contents

1. [Environment Variables](#environment-variables)
2. [Agent Configuration (YAML)](#agent-configuration-yaml)
3. [Service Configuration](#service-configuration)
4. [Database Configuration](#database-configuration)
5. [LLM Provider Configuration](#llm-provider-configuration)
6. [Event Bus Configuration](#event-bus-configuration)
7. [Security Configuration](#security-configuration)
8. [Performance Tuning](#performance-tuning)

---

## Environment Variables

All environment variables are configured in the `.env` file at the project root. Use `.env.example` as a template.

### Core Service Ports

```bash
# StateManager API port (default: 8001)
STATE_MANAGER_PORT=8001

# ConfigurationService API port (default: 8002)
CONFIG_SERVICE_PORT=8002

# AgentOrchestrator API port (default: 8003)
ORCHESTRATOR_PORT=8003

# SchedulerService API port (default: 8004)
SCHEDULER_SERVICE_PORT=8004

# SlackGateway API port (default: 8005)
SLACK_GATEWAY_PORT=8005
```

### Database Configuration

#### PostgreSQL

```bash
# PostgreSQL connection settings
POSTGRES_HOST=postgres           # Database hostname
POSTGRES_PORT=5432               # Database port
POSTGRES_DB=agentrunner          # Database name
POSTGRES_USER=agentrunner        # Database username
POSTGRES_PASSWORD=secure_password # Database password

# Connection pool settings
POSTGRES_MIN_POOL_SIZE=5         # Minimum connections in pool
POSTGRES_MAX_POOL_SIZE=20        # Maximum connections in pool
POSTGRES_POOL_TIMEOUT=30         # Connection timeout (seconds)
POSTGRES_POOL_MAX_OVERFLOW=10    # Overflow connections allowed

# Query settings
POSTGRES_STATEMENT_TIMEOUT=30000 # Query timeout (milliseconds)
POSTGRES_ECHO_SQL=false          # Log all SQL queries (debug only)
```

**Production Recommendations**:
- Use strong passwords (min 16 characters, mixed case, numbers, symbols)
- Set `POSTGRES_ECHO_SQL=false` to avoid logging sensitive data
- Adjust pool size based on concurrent agent count: `max_pool_size = agents * 2`
- Enable SSL connections in production (see Security Configuration)

#### Redis

```bash
# Redis connection settings
REDIS_HOST=redis                 # Redis hostname
REDIS_PORT=6379                  # Redis port
REDIS_DB=0                       # Redis database number (0-15)
REDIS_PASSWORD=                  # Redis password (optional)

# Connection pool settings
REDIS_MAX_CONNECTIONS=50         # Maximum connections in pool
REDIS_SOCKET_TIMEOUT=5           # Socket timeout (seconds)
REDIS_SOCKET_CONNECT_TIMEOUT=5   # Connection timeout (seconds)

# Cache settings
REDIS_DEFAULT_TTL=3600           # Default cache TTL (seconds)
REDIS_STATE_TTL=1800             # Agent state cache TTL (seconds)
REDIS_CONFIG_TTL=3600            # Config cache TTL (seconds)

# Eviction policy
REDIS_MAXMEMORY_POLICY=allkeys-lru # LRU eviction when memory full
```

**Cache TTL Guidelines**:
- **Agent State**: 1800s (30 min) - Balances freshness with performance
- **Agent Config**: 3600s (1 hour) - Config changes are infrequent
- **Execution Results**: 300s (5 min) - Results are typically short-lived
- **Health Status**: 60s (1 min) - Health checks need recent data

### Message Broker (RabbitMQ)

```bash
# RabbitMQ connection settings
RABBITMQ_HOST=rabbitmq           # RabbitMQ hostname
RABBITMQ_PORT=5672               # AMQP port
RABBITMQ_MANAGEMENT_PORT=15672   # Management UI port
RABBITMQ_USER=guest              # RabbitMQ username
RABBITMQ_PASSWORD=guest          # RabbitMQ password
RABBITMQ_VHOST=/                 # Virtual host

# Full AMQP URL (alternative to individual settings)
RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672//

# Connection settings
RABBITMQ_HEARTBEAT=60            # Heartbeat interval (seconds)
RABBITMQ_CONNECTION_TIMEOUT=30   # Connection timeout (seconds)
RABBITMQ_BLOCKED_TIMEOUT=300     # Block timeout (seconds)

# Channel settings
RABBITMQ_CHANNEL_MAX=2047        # Maximum channels per connection
RABBITMQ_FRAME_MAX=131072        # Maximum frame size (bytes)

# Consumer settings
RABBITMQ_PREFETCH_COUNT=10       # Messages prefetched per consumer
RABBITMQ_CONSUMER_TIMEOUT=1800000 # Consumer timeout (milliseconds)

# Queue settings
RABBITMQ_QUEUE_MAX_LENGTH=10000  # Maximum messages per queue
RABBITMQ_MESSAGE_TTL=86400000    # Message TTL (milliseconds, 24h)
RABBITMQ_QUEUE_EXPIRES=300000    # Queue auto-delete time (milliseconds)
```

**Production Recommendations**:
- Change default `guest/guest` credentials
- Enable SSL/TLS for AMQP connections
- Set appropriate `PREFETCH_COUNT` based on agent processing time
- Monitor queue depths to prevent buildup

### LLM Provider API Keys

```bash
# OpenAI
OPENAI_API_KEY=sk-...            # OpenAI API key
OPENAI_ORG_ID=                   # OpenAI organization ID (optional)

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...     # Anthropic API key

# AWS Bedrock
AWS_ACCESS_KEY_ID=AKIA...        # AWS access key
AWS_SECRET_ACCESS_KEY=...        # AWS secret key
AWS_REGION=us-east-1             # AWS region for Bedrock
AWS_BEDROCK_ENDPOINT=            # Custom endpoint (optional)

# Ollama (Local)
OLLAMA_BASE_URL=http://localhost:11434 # Ollama server URL
```

**Security Best Practices**:
- Never commit API keys to version control
- Use secrets management (AWS Secrets Manager, HashiCorp Vault, etc.)
- Rotate API keys regularly (quarterly recommended)
- Use environment-specific keys (dev, staging, prod)
- Monitor API usage and costs

### StateManager Configuration

```bash
# StateManager service settings
STATE_MANAGER_LOG_LEVEL=INFO     # Logging level (DEBUG, INFO, WARN, ERROR)
STATE_COMPRESSION_ENABLED=true   # Compress large state objects
STATE_COMPRESSION_THRESHOLD=1024 # Compress if larger than N bytes

# State persistence settings
STATE_SAVE_INTERVAL=180          # Auto-save interval (seconds)
STATE_HISTORY_LIMIT=100          # Max conversation history items
STATE_IDLE_TIMEOUT=900           # Idle timeout for continuous agents (seconds)

# Cache settings
STATE_CACHE_ENABLED=true         # Enable Redis caching
STATE_CACHE_WRITE_THROUGH=true   # Write to cache and DB simultaneously
STATE_CACHE_TTL=1800             # Cache TTL (seconds)
```

### ConfigurationService Settings

```bash
# ConfigurationService settings
CONFIG_DIR=config                # Configuration directory path
CONFIG_AGENTS_DIR=config/agents  # Agent configurations directory
CONFIG_HOT_RELOAD=true           # Enable hot-reload via watchdog
CONFIG_WATCH_RECURSIVE=true      # Watch subdirectories

# Config validation
CONFIG_VALIDATE_ON_LOAD=true     # Validate configs on load
CONFIG_STRICT_MODE=false         # Fail on validation warnings

# Config caching
CONFIG_CACHE_ENABLED=true        # Enable config caching
CONFIG_CACHE_TTL=3600            # Cache TTL (seconds)
```

### AgentOrchestrator Settings

```bash
# Orchestrator settings
ORCHESTRATOR_LOG_LEVEL=INFO      # Logging level
ORCHESTRATOR_WORKER_THREADS=4    # Worker thread pool size

# Task routing
TASK_ROUTING_STRATEGY=round_robin # round_robin, least_busy, weighted
TASK_DEFAULT_TIMEOUT=300         # Default task timeout (seconds)
TASK_MAX_RETRIES=3               # Maximum retry attempts
TASK_RETRY_DELAY=5               # Retry delay (seconds)

# Agent registration
AGENT_REGISTRATION_TIMEOUT=30    # Registration timeout (seconds)
AGENT_HEALTH_CHECK_INTERVAL=60   # Health check interval (seconds)
AGENT_UNRESPONSIVE_THRESHOLD=180 # Mark unhealthy after N seconds
```

### SchedulerService Settings

```bash
# Scheduler settings
SCHEDULER_LOG_LEVEL=INFO         # Logging level
SCHEDULER_TIMEZONE=UTC           # Default timezone for cron schedules

# Celery settings
CELERY_BROKER_URL=${RABBITMQ_URL} # Celery broker (RabbitMQ)
CELERY_RESULT_BACKEND=redis://${REDIS_HOST}:${REDIS_PORT}/1 # Result backend
CELERY_TASK_SERIALIZER=json      # Task serialization format
CELERY_RESULT_SERIALIZER=json    # Result serialization format
CELERY_ACCEPT_CONTENT=["json"]   # Accepted content types
CELERY_TIMEZONE=UTC              # Celery timezone

# Celery Beat (scheduler)
CELERY_BEAT_SCHEDULE_FILENAME=celerybeat-schedule # Beat schedule file

# Celery Worker settings
CELERY_WORKER_CONCURRENCY=2      # Worker concurrent tasks
CELERY_WORKER_MAX_TASKS_PER_CHILD=100 # Restart worker after N tasks
CELERY_WORKER_PREFETCH_MULTIPLIER=4   # Prefetch multiplier

# Task settings
CELERY_TASK_TIME_LIMIT=600       # Hard time limit (seconds)
CELERY_TASK_SOFT_TIME_LIMIT=540  # Soft time limit (seconds)
CELERY_TASK_ACKS_LATE=true       # Acknowledge after completion
CELERY_TASK_REJECT_ON_WORKER_LOST=true # Requeue on worker loss
```

### SlackGateway Settings

```bash
# Slack API credentials
SLACK_BOT_TOKEN=xoxb-...         # Slack bot token
SLACK_APP_TOKEN=xapp-...         # Slack app token (socket mode)
SLACK_SIGNING_SECRET=...         # Slack signing secret

# Webhook settings
SLACK_WEBHOOK_PATH=/slack/events # Webhook endpoint path
SLACK_VERIFY_SIGNATURE=true      # Verify request signatures
SLACK_SIGNATURE_VERSION=v0       # Signature version

# Rate limiting
SLACK_RATE_LIMIT_ENABLED=true    # Enable rate limiting
SLACK_RATE_LIMIT_CALLS=1         # Calls per interval
SLACK_RATE_LIMIT_PERIOD=1        # Interval (seconds)

# Retry settings
SLACK_MAX_RETRY_ATTEMPTS=3       # Maximum retry attempts
SLACK_RETRY_DELAY=1              # Initial retry delay (seconds)
SLACK_RETRY_EXPONENTIAL_BASE=2   # Exponential backoff base

# Response settings
SLACK_RESPONSE_TIMEOUT=100       # Response timeout (milliseconds)
SLACK_EPHEMERAL_RESPONSES=false  # Use ephemeral messages
```

### Logging Configuration

```bash
# Global logging settings
LOG_LEVEL=INFO                   # Global log level
LOG_FORMAT=json                  # Log format: json, text
LOG_OUTPUT=stdout                # Log output: stdout, file
LOG_FILE_PATH=/var/log/agentrunner.log # Log file path

# Component-specific log levels
STATE_MANAGER_LOG_LEVEL=INFO
CONFIG_SERVICE_LOG_LEVEL=INFO
ORCHESTRATOR_LOG_LEVEL=INFO
SCHEDULER_LOG_LEVEL=INFO
SLACK_GATEWAY_LOG_LEVEL=INFO

# Log rotation (when LOG_OUTPUT=file)
LOG_MAX_SIZE=100M                # Maximum log file size
LOG_BACKUP_COUNT=10              # Number of backup files
LOG_ROTATION=daily               # Rotation: daily, weekly, size
```

### Security Settings

```bash
# Environment
ENVIRONMENT=production           # Environment: development, staging, production

# API Authentication
API_AUTH_ENABLED=true            # Enable API authentication
API_KEY_HEADER=X-API-Key         # API key header name
API_KEY=your-secure-api-key      # API key value

# TLS/SSL
TLS_ENABLED=true                 # Enable TLS
TLS_CERT_PATH=/etc/certs/server.crt # TLS certificate path
TLS_KEY_PATH=/etc/certs/server.key  # TLS private key path
TLS_CA_PATH=/etc/certs/ca.crt    # TLS CA certificate path

# CORS settings
CORS_ENABLED=true                # Enable CORS
CORS_ORIGINS=["https://app.example.com"] # Allowed origins
CORS_METHODS=["GET","POST","PUT","DELETE"] # Allowed methods
CORS_HEADERS=["Content-Type","Authorization"] # Allowed headers

# Rate limiting
RATE_LIMIT_ENABLED=true          # Enable global rate limiting
RATE_LIMIT_PER_MINUTE=60         # Requests per minute
RATE_LIMIT_BURST=10              # Burst allowance
```

### Performance Tuning

```bash
# Worker settings
WORKER_PROCESSES=4               # Number of worker processes
WORKER_THREADS_PER_PROCESS=2     # Threads per process
WORKER_MAX_REQUESTS=1000         # Restart worker after N requests
WORKER_MAX_REQUESTS_JITTER=100   # Add jitter to prevent simultaneous restarts

# Connection pools
DB_POOL_SIZE=20                  # Database connection pool size
DB_POOL_OVERFLOW=10              # Overflow connections
REDIS_POOL_SIZE=50               # Redis connection pool size
RABBITMQ_POOL_SIZE=10            # RabbitMQ connection pool size

# Timeouts
REQUEST_TIMEOUT=30               # HTTP request timeout (seconds)
DB_QUERY_TIMEOUT=30              # Database query timeout (seconds)
CACHE_OPERATION_TIMEOUT=5        # Cache operation timeout (seconds)
```

---

## Agent Configuration (YAML)

Agent configurations are stored in `config/agents/` directory. Each agent is defined in a separate YAML file.

### Complete Agent Configuration Schema

```yaml
# Required fields
name: agent-name                 # Unique agent identifier (lowercase, hyphens)
agent_type: assistant            # Agent type: assistant, specialist, coordinator
execution_mode: autonomous       # autonomous, continuous, collaborative, scheduled

# LLM Configuration (required)
llm_config:
  provider: openai               # openai, anthropic, bedrock, ollama
  model: gpt-4                   # Model name
  temperature: 0.7               # Temperature (0.0-2.0)
  max_tokens: 2000               # Maximum tokens per response
  top_p: 1.0                     # Nucleus sampling (0.0-1.0)
  frequency_penalty: 0.0         # Frequency penalty (-2.0 to 2.0)
  presence_penalty: 0.0          # Presence penalty (-2.0 to 2.0)
  timeout: 60                    # Request timeout (seconds)

# System prompt (required)
system_prompt: |
  You are a helpful AI assistant.
  Your purpose is to...

# Optional fields
description: "Brief agent description" # Agent description
tags: ["category1", "category2"]       # Categorization tags

# Event subscriptions (optional)
event_subscriptions:
  - "event.pattern.one"          # Event patterns to subscribe to
  - "event.pattern.*"            # Supports wildcards

# Custom tools (optional)
tools:
  - name: tool_name              # Tool identifier
    type: mcp                    # Tool type: mcp, function, api
    url: "https://tool.example.com/mcp" # MCP server URL
    description: "Tool description" # What the tool does
    auth:                         # Authentication (optional)
      type: bearer_token          # Auth type: bearer_token, api_key, oauth2
      token: "${TOOL_API_TOKEN}"  # Token from environment

# Retry configuration (optional)
retry_config:
  max_retries: 3                 # Maximum retry attempts
  retry_delay_seconds: 5         # Initial retry delay
  exponential_backoff: true      # Use exponential backoff
  backoff_multiplier: 2          # Backoff multiplier
  max_retry_delay: 60            # Maximum retry delay (seconds)

# Execution mode-specific configurations (see below)
```

### Execution Mode: Autonomous

```yaml
name: autonomous-agent
execution_mode: autonomous

# Autonomous agents are stateless and process tasks in isolation
# No additional configuration required

# Optional: Configure retry behavior
retry_config:
  max_retries: 3
  retry_delay_seconds: 5
  exponential_backoff: true
```

**Key Characteristics**:
- Stateless execution
- Load-balanced across multiple instances
- No conversation history
- Fast startup and execution
- Ideal for: Data processing, API calls, one-shot tasks

### Execution Mode: Continuous

```yaml
name: continuous-agent
execution_mode: continuous

# Continuous agent configuration (required)
continuous_config:
  idle_timeout_seconds: 900      # Shutdown after idle time (default: 900)
  save_interval_seconds: 180     # State save interval (default: 180)
  max_conversation_history: 100  # Max conversation turns (default: 100)
  conversation_pruning_strategy: sliding_window # sliding_window, summarize
  auto_save_on_shutdown: true    # Save state on shutdown (default: true)
  restore_on_startup: true       # Restore state on startup (default: true)
```

**Key Characteristics**:
- Stateful execution with persistent conversation history
- Long-running processes
- Context maintained across interactions
- Automatic state persistence
- Ideal for: Customer support, interactive assistants, ongoing conversations

### Execution Mode: Collaborative

```yaml
name: collaborative-agent
execution_mode: collaborative

# Collaborative configuration (required)
collaborative_config:
  preferred_collaborators:       # List of preferred agent names
    - data-analyzer
    - content-writer
  max_plan_steps: 10             # Maximum planning steps (default: 10)
  allow_human_clarification: true # Allow human input (default: true)
  min_collaborators: 1           # Minimum collaborators (default: 1)
  max_collaborators: 5           # Maximum collaborators (default: 5)
  planning_strategy: hierarchical # hierarchical, consensus, sequential
  timeout_seconds: 300           # Collaboration timeout (default: 300)
```

**Key Characteristics**:
- Multi-agent coordination
- Automated planning and task decomposition
- Human-in-the-loop support
- Complex problem solving
- Ideal for: Research tasks, content generation, complex analysis

### Execution Mode: Scheduled

#### Cron-based Schedule

```yaml
name: scheduled-agent
execution_mode: scheduled

# Schedule configuration (required)
schedule_config:
  type: cron                     # Schedule type: cron or interval
  cron: "0 9 * * *"              # Cron expression (daily at 9 AM)
  timezone: UTC                  # Timezone (default: UTC)
  task_data:                     # Static task data
    report_type: daily
    recipients: ["team@example.com"]
  timeout_seconds: 600           # Task timeout (default: 300)
  enabled: true                  # Schedule enabled (default: true)
```

**Cron Expression Format**:
```
┌───────────── minute (0-59)
│ ┌───────────── hour (0-23)
│ │ ┌───────────── day of month (1-31)
│ │ │ ┌───────────── month (1-12)
│ │ │ │ ┌───────────── day of week (0-6, Sunday=0)
│ │ │ │ │
* * * * *
```

**Common Cron Examples**:
```yaml
"0 9 * * *"        # Daily at 9:00 AM
"*/15 * * * *"     # Every 15 minutes
"0 0 * * 0"        # Weekly on Sunday at midnight
"0 9 1 * *"        # Monthly on 1st at 9:00 AM
"0 0 1 1 *"        # Yearly on January 1st at midnight
```

#### Interval-based Schedule

```yaml
name: interval-agent
execution_mode: scheduled

schedule_config:
  type: interval                 # Interval-based scheduling
  interval_seconds: 300          # Run every 5 minutes
  task_data:
    check_type: health
  timeout_seconds: 120           # Task timeout
  enabled: true
```

**Key Characteristics**:
- Time-triggered execution
- No persistent state by default (stateless)
- Automated reporting and monitoring
- Ideal for: Reports, health checks, data synchronization

---

## Service Configuration

### StateManager (`src/state/`)

```python
# Configuration via environment variables and code

class StateManagerConfig:
    # Database settings
    database_url: str = os.getenv("DATABASE_URL")
    min_pool_size: int = int(os.getenv("POSTGRES_MIN_POOL_SIZE", 5))
    max_pool_size: int = int(os.getenv("POSTGRES_MAX_POOL_SIZE", 20))

    # Cache settings
    redis_host: str = os.getenv("REDIS_HOST", "localhost")
    redis_port: int = int(os.getenv("REDIS_PORT", 6379))
    cache_enabled: bool = os.getenv("STATE_CACHE_ENABLED", "true").lower() == "true"
    cache_ttl: int = int(os.getenv("STATE_CACHE_TTL", 1800))

    # Compression settings
    compression_enabled: bool = os.getenv("STATE_COMPRESSION_ENABLED", "true").lower() == "true"
    compression_threshold: int = int(os.getenv("STATE_COMPRESSION_THRESHOLD", 1024))
```

### ConfigurationService (`src/config/`)

```python
class ConfigServiceConfig:
    # File watching
    config_dir: str = os.getenv("CONFIG_DIR", "config")
    agents_dir: str = os.getenv("CONFIG_AGENTS_DIR", "config/agents")
    hot_reload: bool = os.getenv("CONFIG_HOT_RELOAD", "true").lower() == "true"
    watch_recursive: bool = os.getenv("CONFIG_WATCH_RECURSIVE", "true").lower() == "true"

    # Validation
    validate_on_load: bool = os.getenv("CONFIG_VALIDATE_ON_LOAD", "true").lower() == "true"
    strict_mode: bool = os.getenv("CONFIG_STRICT_MODE", "false").lower() == "true"
```

### AgentOrchestrator (`src/orchestrator/`)

```python
class OrchestratorConfig:
    # Service discovery
    state_manager_host: str = os.getenv("STATE_MANAGER_HOST", "localhost")
    state_manager_port: int = int(os.getenv("STATE_MANAGER_PORT", 8001))
    config_service_host: str = os.getenv("CONFIG_SERVICE_HOST", "localhost")
    config_service_port: int = int(os.getenv("CONFIG_SERVICE_PORT", 8002))

    # EventBus
    rabbitmq_url: str = os.getenv("RABBITMQ_URL")

    # Task routing
    routing_strategy: str = os.getenv("TASK_ROUTING_STRATEGY", "round_robin")
    default_timeout: int = int(os.getenv("TASK_DEFAULT_TIMEOUT", 300))
```

---

## Database Configuration

### PostgreSQL Schema

The platform uses PostgreSQL for persistent storage of agent state, execution history, and configurations.

#### Tables

**agent_state**:
```sql
CREATE TABLE agent_state (
    agent_name VARCHAR(255) PRIMARY KEY,
    state_data JSONB NOT NULL,
    conversation_history JSONB,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP
);

CREATE INDEX idx_agent_state_updated ON agent_state(updated_at);
CREATE INDEX idx_agent_state_last_activity ON agent_state(last_activity);
```

**execution_history**:
```sql
CREATE TABLE execution_history (
    execution_id VARCHAR(255) PRIMARY KEY,
    agent_name VARCHAR(255) NOT NULL,
    task_type VARCHAR(100),
    status VARCHAR(50),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    duration_seconds INTEGER,
    result JSONB,
    error_message TEXT,
    trace_id VARCHAR(255)
);

CREATE INDEX idx_execution_agent ON execution_history(agent_name);
CREATE INDEX idx_execution_status ON execution_history(status);
CREATE INDEX idx_execution_started ON execution_history(started_at);
```

**schedules**:
```sql
CREATE TABLE schedules (
    schedule_name VARCHAR(255) PRIMARY KEY,
    agent_name VARCHAR(255) NOT NULL,
    schedule_type VARCHAR(50) NOT NULL,
    schedule_config JSONB NOT NULL,
    task_data JSONB,
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_execution TIMESTAMP
);

CREATE INDEX idx_schedules_agent ON schedules(agent_name);
CREATE INDEX idx_schedules_enabled ON schedules(enabled);
```

### Database Maintenance

```sql
-- Vacuum and analyze (run weekly)
VACUUM ANALYZE agent_state;
VACUUM ANALYZE execution_history;
VACUUM ANALYZE schedules;

-- Archive old execution history (run monthly)
DELETE FROM execution_history
WHERE started_at < NOW() - INTERVAL '90 days';

-- Clean up old agent state (run weekly)
DELETE FROM agent_state
WHERE last_activity < NOW() - INTERVAL '30 days';
```

---

## LLM Provider Configuration

### OpenAI

```yaml
llm_config:
  provider: openai
  model: gpt-4                   # gpt-4, gpt-4-turbo-preview, gpt-3.5-turbo
  temperature: 0.7
  max_tokens: 2000
  top_p: 1.0
  frequency_penalty: 0.0
  presence_penalty: 0.0
  timeout: 60

  # Optional: Model-specific settings
  response_format:               # For gpt-4-turbo-preview
    type: json_object            # Force JSON output

  seed: 42                       # Deterministic sampling (optional)
```

**Environment Variables**:
```bash
OPENAI_API_KEY=sk-...
OPENAI_ORG_ID=org-...            # Optional
```

**Model Comparison**:
- **gpt-4**: Most capable, slower, $0.03/1K tokens
- **gpt-4-turbo-preview**: Faster, cheaper, 128K context
- **gpt-3.5-turbo**: Fastest, cheapest, good for simple tasks

### Anthropic

```yaml
llm_config:
  provider: anthropic
  model: claude-3-opus-20240229  # opus, sonnet, haiku
  temperature: 0.7
  max_tokens: 2000
  top_p: 1.0
  top_k: 40                      # Anthropic-specific parameter
  timeout: 60
```

**Environment Variables**:
```bash
ANTHROPIC_API_KEY=sk-ant-...
```

**Model Comparison**:
- **claude-3-opus**: Most intelligent, 200K context
- **claude-3-sonnet**: Balanced performance and speed
- **claude-3-haiku**: Fastest, most affordable

### AWS Bedrock

```yaml
llm_config:
  provider: bedrock
  model: anthropic.claude-3-sonnet-20240229-v1:0
  temperature: 0.7
  max_tokens: 2000
  top_p: 1.0

  # AWS-specific settings
  region: us-east-1              # AWS region
  endpoint_url: null             # Custom endpoint (optional)
```

**Environment Variables**:
```bash
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
```

**Available Models**:
- `anthropic.claude-3-opus-20240229-v1:0`
- `anthropic.claude-3-sonnet-20240229-v1:0`
- `anthropic.claude-3-haiku-20240307-v1:0`
- `amazon.titan-text-express-v1`

### Ollama (Local)

```yaml
llm_config:
  provider: ollama
  model: llama2                  # Any model installed in Ollama
  temperature: 0.7
  max_tokens: 2000
  timeout: 120                   # Longer timeout for local models

  # Ollama-specific settings
  num_ctx: 4096                  # Context window size
  num_predict: 512               # Maximum tokens to generate
  repeat_penalty: 1.1            # Repetition penalty
```

**Environment Variables**:
```bash
OLLAMA_BASE_URL=http://localhost:11434
```

**Popular Models**:
- `llama2`: General purpose, 7B/13B/70B variants
- `mistral`: Fast, efficient, 7B parameters
- `codellama`: Code-specialized, 7B/13B/34B variants
- `phi`: Microsoft's compact model, 2.7B parameters

---

## Event Bus Configuration

### EventBus Routing Patterns

The platform uses RabbitMQ topic exchange for event routing with pattern matching.

#### Standard Routing Keys

```python
# Agent pool routing
"collaborative.task.submitted"      # Collaborative tasks
"autonomous.task.submitted"         # Autonomous tasks
"continuous.task.{agent_name}"      # Continuous agent tasks
"scheduled.task.{agent_name}"       # Scheduled tasks

# Integration events
"slack.command.*"                   # Slack commands
"slack.event.message"               # Slack messages
"slack.event.reaction_added"        # Slack reactions

# System events
"agent.registered"                  # Agent registration
"agent.health.changed"              # Health status changes
"agent.execution.completed"         # Execution completion
"agent.execution.failed"            # Execution failure

# Custom events
"customer.ticket.created"           # Custom business events
"data.analysis.requested"           # Custom integration events
```

#### Pattern Matching Rules

```python
# Exact match
"slack.command.help" -> Matches only "slack.command.help"

# Single-word wildcard (*)
"slack.command.*" -> Matches "slack.command.help", "slack.command.support"

# Multi-word wildcard (#)
"slack.#" -> Matches "slack.command.help", "slack.event.message.posted"

# Multiple patterns
["slack.command.*", "slack.event.message"] -> Matches both patterns
```

### Dead Letter Queue (DLQ)

Failed messages are routed to DLQ for manual inspection:

```yaml
# RabbitMQ automatically creates DLQ bindings
dlq:
  exchange: dlq-exchange
  routing_key: "{original_queue_name}.dlq"
  message_ttl: 604800000          # 7 days
```

**Accessing DLQ Messages**:
```bash
# Via RabbitMQ Management UI
http://localhost:15672/#/queues/%2F/{queue_name}.dlq

# Via rabbitmqadmin CLI
rabbitmqadmin get queue={queue_name}.dlq requeue=false
```

---

## Security Configuration

### API Authentication

```yaml
# Enable API key authentication
API_AUTH_ENABLED=true
API_KEY_HEADER=X-API-Key
API_KEY=your-secure-api-key-min-32-chars

# Generate secure API key
openssl rand -base64 32
```

**Usage**:
```bash
curl -H "X-API-Key: your-api-key" http://localhost:8003/agents
```

### TLS/SSL Configuration

```yaml
# Enable TLS for all services
TLS_ENABLED=true
TLS_CERT_PATH=/etc/certs/server.crt
TLS_KEY_PATH=/etc/certs/server.key
TLS_CA_PATH=/etc/certs/ca.crt

# TLS version and ciphers
TLS_MIN_VERSION=TLSv1.2
TLS_CIPHERS=ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384
```

**Generate Self-Signed Certificate** (for testing):
```bash
openssl req -x509 -newkey rsa:4096 -nodes \
  -keyout server.key -out server.crt \
  -days 365 -subj "/CN=localhost"
```

### Secrets Management

**Using Environment Variables**:
```bash
# Export from environment
export OPENAI_API_KEY=sk-...

# Or use .env file (not committed to git)
echo "OPENAI_API_KEY=sk-..." >> .env
```

**Using Docker Secrets**:
```yaml
# docker-compose.yml
services:
  agent-orchestrator:
    secrets:
      - openai_api_key
    environment:
      OPENAI_API_KEY_FILE: /run/secrets/openai_api_key

secrets:
  openai_api_key:
    file: ./secrets/openai_api_key.txt
```

**Using AWS Secrets Manager**:
```python
import boto3

def get_secret(secret_name):
    client = boto3.client('secretsmanager', region_name='us-east-1')
    response = client.get_secret_value(SecretId=secret_name)
    return response['SecretString']

os.environ['OPENAI_API_KEY'] = get_secret('prod/openai/api-key')
```

---

## Performance Tuning

### Database Optimization

```yaml
# Connection pooling
POSTGRES_MIN_POOL_SIZE=10        # Scale with agent count
POSTGRES_MAX_POOL_SIZE=50        # 2-3x min pool size
POSTGRES_POOL_TIMEOUT=30
POSTGRES_POOL_MAX_OVERFLOW=20    # Buffer for spikes

# Query optimization
POSTGRES_STATEMENT_TIMEOUT=30000 # Prevent long-running queries
POSTGRES_ENABLE_QUERY_CACHE=true
```

**Tuning Guidelines**:
- Min pool size ≈ concurrent agents
- Max pool size ≈ 2-3x min pool size
- Monitor connection usage: `SELECT count(*) FROM pg_stat_activity;`

### Redis Optimization

```yaml
# Memory management
REDIS_MAXMEMORY=2gb              # Set based on available RAM
REDIS_MAXMEMORY_POLICY=allkeys-lru # Eviction policy

# Connection pooling
REDIS_MAX_CONNECTIONS=100        # Scale with request volume

# Cache TTL optimization
REDIS_STATE_TTL=1800             # Agent state: 30 minutes
REDIS_CONFIG_TTL=3600            # Config: 1 hour
REDIS_RESULT_TTL=300             # Results: 5 minutes
```

### RabbitMQ Optimization

```yaml
# Prefetch tuning
RABBITMQ_PREFETCH_COUNT=10       # Messages per consumer
# Lower value (1-5): CPU-bound tasks, better distribution
# Higher value (10-20): I/O-bound tasks, better throughput

# Queue limits
RABBITMQ_QUEUE_MAX_LENGTH=10000  # Prevent unbounded growth
RABBITMQ_MESSAGE_TTL=86400000    # 24 hour message expiry
```

### Worker Process Tuning

```yaml
# Process-based parallelism
WORKER_PROCESSES=4               # Set to CPU core count

# Thread-based parallelism
WORKER_THREADS_PER_PROCESS=2     # 1-4 threads per process

# Total capacity
# Total concurrent tasks = WORKER_PROCESSES × WORKER_THREADS_PER_PROCESS
# Example: 4 processes × 2 threads = 8 concurrent tasks
```

**Tuning Formula**:
- CPU-bound tasks: `workers = CPU cores`
- I/O-bound tasks: `workers = CPU cores × 2-4`
- Hybrid: `workers = CPU cores × 1.5-2`

### Celery Tuning (Scheduler)

```yaml
# Worker concurrency
CELERY_WORKER_CONCURRENCY=4      # Concurrent task execution

# Task timeouts
CELERY_TASK_TIME_LIMIT=600       # Hard limit (kill task)
CELERY_TASK_SOFT_TIME_LIMIT=540  # Soft limit (exception)

# Memory management
CELERY_WORKER_MAX_TASKS_PER_CHILD=100 # Restart after N tasks
```

---

## Configuration Validation

### Validation Checklist

Before starting the platform, validate your configuration:

```bash
# Check environment variables
./scripts/validate_env.sh

# Validate agent configurations
python -c "
from src.config.configuration_service import ConfigurationService
service = ConfigurationService('config')
agents = service.get_all_agents()
print(f'✓ Loaded {len(agents)} valid agent configurations')
"

# Test database connection
psql $DATABASE_URL -c "SELECT 1;"

# Test Redis connection
redis-cli -h $REDIS_HOST -p $REDIS_PORT ping

# Test RabbitMQ connection
curl -u $RABBITMQ_USER:$RABBITMQ_PASSWORD \
  http://$RABBITMQ_HOST:15672/api/overview
```

### Common Configuration Errors

**Error: Database connection failed**
```
Solution: Check POSTGRES_* environment variables
Verify: docker-compose logs postgres
```

**Error: Redis connection timeout**
```
Solution: Increase REDIS_SOCKET_CONNECT_TIMEOUT
Verify: redis-cli -h $REDIS_HOST ping
```

**Error: Agent configuration invalid**
```
Solution: Validate YAML syntax and required fields
Verify: yamllint config/agents/*.yml
```

**Error: RabbitMQ authentication failed**
```
Solution: Check RABBITMQ_USER and RABBITMQ_PASSWORD
Verify: curl -u user:pass http://localhost:15672/api/overview
```

---

## Configuration Examples

### Development Environment

```bash
# .env.development
ENVIRONMENT=development
LOG_LEVEL=DEBUG
LOG_FORMAT=text

# Use local services
POSTGRES_HOST=localhost
REDIS_HOST=localhost
RABBITMQ_HOST=localhost

# Disable security features
TLS_ENABLED=false
API_AUTH_ENABLED=false

# Use cheaper models
DEFAULT_LLM_PROVIDER=openai
DEFAULT_LLM_MODEL=gpt-3.5-turbo
```

### Staging Environment

```bash
# .env.staging
ENVIRONMENT=staging
LOG_LEVEL=INFO
LOG_FORMAT=json

# Use staging services
POSTGRES_HOST=staging-db.example.com
REDIS_HOST=staging-cache.example.com
RABBITMQ_HOST=staging-mq.example.com

# Enable security
TLS_ENABLED=true
API_AUTH_ENABLED=true

# Use production-like models
DEFAULT_LLM_PROVIDER=openai
DEFAULT_LLM_MODEL=gpt-4-turbo-preview
```

### Production Environment

```bash
# .env.production
ENVIRONMENT=production
LOG_LEVEL=WARN
LOG_FORMAT=json
LOG_OUTPUT=file

# Use production services with TLS
POSTGRES_HOST=prod-db.example.com
POSTGRES_SSL_MODE=require
REDIS_HOST=prod-cache.example.com
REDIS_SSL=true
RABBITMQ_HOST=prod-mq.example.com
RABBITMQ_SSL=true

# Enable all security features
TLS_ENABLED=true
API_AUTH_ENABLED=true
CORS_ENABLED=true

# Use production models
DEFAULT_LLM_PROVIDER=openai
DEFAULT_LLM_MODEL=gpt-4

# Aggressive caching
REDIS_STATE_TTL=3600
REDIS_CONFIG_TTL=7200

# Monitoring
PROMETHEUS_ENABLED=true
METRICS_PORT=9090
```

---

## Further Reading

- [Operations Guide](OPERATIONS_GUIDE.md) - Deployment and operations
- [Agent Development Guide](AGENT_DEVELOPMENT_GUIDE.md) - Creating agents
- [API Reference](API_REFERENCE.md) - REST API documentation
- [Architecture Overview](../docs/01-requirements.md) - System architecture

---

**Last Updated**: 2025-11-18
**Version**: 1.0
