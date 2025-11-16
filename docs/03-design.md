# Design Document

## 1. Overview

This document provides detailed technical specifications for the Multi-Agent Orchestration Platform. Each component from the architectural blueprint is elaborated with implementation details, interfaces, data structures, and requirement traceability.

## 2. Design Principles

- **Separation of Concerns**: Each component has a single, well-defined responsibility
- **Event-Driven Architecture**: Components communicate asynchronously via RabbitMQ message bus
- **Configuration Over Code**: Agent definitions and behaviors are driven by YAML configuration files
- **Fail-Safe Operations**: Graceful degradation with retry logic and dead-letter queues
- **Observability First**: All operations emit structured logs and metrics
- **Docker Native**: All services designed for containerized deployment with docker-compose

## 3. Technology Stack

- **Language**: Python 3.11+
- **Agent Framework**: Portia AI SDK (`portia-sdk-python`)
- **Message Broker**: RabbitMQ 3.12+
- **Task Queue**: Celery 5.3+ with Celery Beat
- **Cache**: Redis 7.0+
- **Database**: PostgreSQL 15+
- **Logging**: Python stdlib logging (JSON to stdout)
- **Web Framework**: FastAPI (for health endpoints and SlackGateway)
- **ORM**: SQLAlchemy 2.0+
- **Async Support**: asyncio, aiohttp, celery with async workers

---

## 4. Component Specifications

### Component: AgentOrchestrator

**Purpose**: Manages agent lifecycle (initialization, startup, shutdown) and maintains the agent registry with metadata about each agent's capabilities and execution mode.

**Location**: `src/orchestrator/agent_orchestrator.py`

**Interface**:
```python
class AgentOrchestrator:
    """
    Implements Req 1.1, 1.2, 1.3, 1.4, 1.5, 3.3, 12.2, 12.4
    """

    def __init__(self, config_service: ConfigurationService,
                 state_manager: StateManager):
        """Initialize orchestrator with dependencies"""

    async def initialize(self) -> None:
        """
        Load agent configurations and register all agents
        Implements Req 1.1, 1.2, 12.1, 12.4
        """

    async def register_agent(self, agent_config: dict) -> AgentRegistration:
        """
        Validate and register a single agent
        Implements Req 1.2, 12.2
        Returns: AgentRegistration object with id, type, status
        Raises: ValidationError if config is invalid
        """

    async def start_agent(self, agent_id: str) -> bool:
        """
        Initialize and start a registered agent
        Implements Req 1.1, 1.3
        Returns: True if successful, False otherwise
        """

    async def invoke_agent(self, agent_id: str, event: Event) -> ExecutionResult:
        """
        Execute a specific agent with event payload
        Implements Req 3.3
        """

    async def health_check_agent(self, agent_id: str) -> HealthStatus:
        """
        Check agent responsiveness
        Implements Req 1.5
        Returns: HealthStatus with response_time and status
        """

    async def restart_agent(self, agent_id: str) -> bool:
        """
        Restart unresponsive agent with retry limits
        Implements Req 1.5 (max 3 retries)
        """

    async def shutdown(self, timeout: int = 30) -> None:
        """
        Gracefully shutdown all agents
        Implements Req 1.4 (30-second timeout)
        """

    def get_agent_registry(self) -> Dict[str, AgentMetadata]:
        """Return current agent registry snapshot"""
```

**Data Structures**:
```python
@dataclass
class AgentMetadata:
    id: str
    name: str
    type: str  # collaborative, autonomous, continuous, scheduled
    execution_mode: str
    capabilities: List[str]
    status: str  # registered, running, failed, stopped
    retry_count: int
    last_health_check: datetime

@dataclass
class AgentRegistration:
    agent_id: str
    status: str
    registered_at: datetime
```

**Dependencies**: ConfigurationService, StateManager, Agent Pools

**Logging**: Uses Python logging module to emit structured JSON logs to stdout with trace_id

**Configuration**: Loaded via ConfigurationService from `config/orchestrator.yaml`

---

### Component: EventBus

**Purpose**: Routes messages between agents and external systems using RabbitMQ topic exchanges with persistent message delivery.

**Location**: `src/messaging/event_bus.py`

**Interface**:
```python
class EventBus:
    """
    Implements Req 2.2, 2.4, 2.5, 12.5
    """

    def __init__(self, rabbitmq_url: str):
        """Initialize RabbitMQ connection with persistent delivery"""

    async def connect(self) -> None:
        """Establish connection to RabbitMQ with retry logic"""

    async def publish(self, topic: str, event: Event,
                     priority: int = 0) -> bool:
        """
        Publish event to topic with persistence
        Implements Req 2.2 (at-least-once delivery)
        Args:
            topic: Topic pattern (e.g., 'slack.events.command')
            event: Event object to publish
            priority: Message priority (0-9)
        Returns: True if published successfully
        """

    async def subscribe(self, queue_name: str,
                       topic_patterns: List[str],
                       callback: Callable[[Event], Awaitable[None]]) -> str:
        """
        Subscribe to topics and register callback
        Implements Req 12.5 (automatic subscription)
        Returns: Subscription ID
        """

    async def consume(self, queue_name: str,
                     prefetch_count: int = 1) -> AsyncIterator[Event]:
        """
        Async iterator for consuming events from queue
        Implements Req 6.1 (prefetch control)
        """

    async def acknowledge(self, delivery_tag: int) -> None:
        """Acknowledge message processing completion"""

    async def reject(self, delivery_tag: int, requeue: bool = True) -> None:
        """
        Reject message with retry logic
        Implements Req 2.5 (exponential backoff, dead-letter queue)
        """

    async def setup_dead_letter_queue(self, queue_name: str) -> None:
        """
        Configure DLQ for failed messages
        Implements Req 2.5 (5 retry attempts before DLQ)
        """
```

**Data Structures**:
```python
@dataclass
class Event:
    event_id: str
    event_type: str
    timestamp: datetime
    payload: dict
    metadata: dict
    trace_id: str  # For distributed tracing
    retry_count: int = 0
```

**RabbitMQ Configuration**:
- **Exchange Type**: Topic exchange for pattern matching
- **Message Persistence**: Durable queues and persistent messages
- **Retry Policy**: Exponential backoff (1s, 2s, 4s, 8s, 16s)
- **Max Retries**: 5 attempts before dead-letter queue
- **Prefetch**: Configurable per consumer (default 1 for continuous agents)

**Dependencies**: None (standalone component)

**Configuration**: `RABBITMQ_URL`, `RABBITMQ_USER`, `RABBITMQ_PASS` environment variables

**Logging**: Emits structured logs to stdout with trace_id for all operations

---

### Component: StateManager

**Purpose**: Persists agent state, conversation history, and execution results using Redis (cache) and PostgreSQL (durable storage).

**Location**: `src/state/state_manager.py`

**Interface**:
```python
class StateManager:
    """
    Implements Req 3.4, 4.3, 5.3, 6.2, 6.3, 6.4, 7.1, 7.2, 7.3, 7.4, 7.5
    """

    def __init__(self, redis_client: Redis,
                 postgres_session: AsyncSession):
        """Initialize with Redis and PostgreSQL connections"""

    async def save_state(self, key: str, value: dict,
                        ttl: Optional[int] = None,
                        durable: bool = True) -> None:
        """
        Save state to Redis (cache) and/or PostgreSQL (durable)
        Implements Req 7.1 (tiered storage)
        Implements Req 7.3 (compression for >1MB)
        """

    async def load_state(self, key: str) -> Optional[dict]:
        """
        Load from Redis cache, fallback to PostgreSQL
        Implements Req 7.2 (cache-first with fallback)
        Implements Req 7.5 (bypass cache if Redis unavailable)
        """

    async def save_execution_result(self, agent_id: str,
                                    execution_id: str,
                                    result: dict) -> None:
        """
        Store execution result durably
        Implements Req 3.4, 5.3
        """

    async def update_plan_run_state(self, task_id: str,
                                    plan_state: PlanRunState) -> None:
        """
        Update collaborative task state
        Implements Req 4.3
        """

    async def compress_data(self, data: dict) -> bytes:
        """
        Compress large data with gzip
        Implements Req 7.3 (>1MB threshold)
        """

    async def decompress_data(self, compressed: bytes) -> dict:
        """Decompress gzipped data transparently"""
```

**Database Schema** (PostgreSQL):
```sql
-- Agent state table
CREATE TABLE agent_states (
    id SERIAL PRIMARY KEY,
    agent_id VARCHAR(255) NOT NULL,
    state_key VARCHAR(255) NOT NULL,
    state_data JSONB NOT NULL,
    compressed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(agent_id, state_key)
);

-- Execution results table (Req 3.4, 5.3)
CREATE TABLE execution_results (
    id SERIAL PRIMARY KEY,
    agent_id VARCHAR(255) NOT NULL,
    execution_id VARCHAR(255) NOT NULL,
    event_id VARCHAR(255),
    result_data JSONB NOT NULL,
    execution_timestamp TIMESTAMP NOT NULL,
    completed_at TIMESTAMP DEFAULT NOW(),
    INDEX(agent_id, execution_timestamp)
);

-- Collaborative task state (Req 4.3)
CREATE TABLE plan_run_states (
    id SERIAL PRIMARY KEY,
    task_id VARCHAR(255) UNIQUE NOT NULL,
    plan_data JSONB NOT NULL,
    current_step INTEGER,
    status VARCHAR(50),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

**Redis Key Patterns**:
- `agent:state:{agent_id}:{state_key}` - Agent state cache
- `agent:conversation:{agent_id}` - Conversation history (TTL: 1 hour)
- `execution:result:{execution_id}` - Recent execution results (TTL: 24 hours)

**Dependencies**: Redis client, SQLAlchemy AsyncSession

**Configuration**: `REDIS_URL`, `POSTGRES_URL` environment variables

**Logging**: Logs cache misses, compression operations, and errors to stdout with trace_id

---

### Component: ConfigurationService

**Purpose**: Loads and validates agent configurations and credentials securely from environment variables and YAML files.

**Location**: `src/config/configuration_service.py`

**Interface**:
```python
class ConfigurationService:
    """
    Implements Req 1.1, 3.1, 9.1, 9.2, 9.3, 9.4, 9.5, 12.1
    """

    def __init__(self, config_dir: str = "config/agents/"):
        """Initialize with configuration directory"""

    async def load_configurations(self) -> Dict[str, AgentConfig]:
        """
        Load all YAML agent configurations
        Implements Req 9.1, 12.1 (auto-discovery)
        Returns: Dictionary of agent_id -> AgentConfig
        """

    async def validate_config(self, config: dict) -> AgentConfig:
        """
        Validate configuration schema
        Implements Req 9.1 (required fields validation)
        Raises: ValidationError if schema is invalid
        """

    async def load_secrets(self) -> Secrets:
        """
        Load secrets from environment variables
        Implements Req 9.2 (rejects startup if missing)
        """

    async def reload_configurations(self) -> None:
        """
        Hot-reload configurations without restart
        Implements Req 9.3
        """

    def get_agent_config(self, agent_id: str) -> AgentConfig:
        """
        Retrieve agent-specific configuration
        Implements Req 9.4
        """

    def inject_credentials(self, agent: ExecutionAgent,
                          config: AgentConfig) -> None:
        """
        Inject secrets into agent without logging
        Implements Req 9.5
        """
```

**Agent Configuration Schema** (YAML):
```yaml
# config/agents/sentiment-analyzer.yaml
name: "Sentiment Analyzer"
type: "autonomous"
execution_mode: "autonomous"
description: "Analyzes sentiment of customer feedback"

llm_config:
  provider: "bedrock"
  model_id: "anthropic.claude-3-5-sonnet-20241022-v2:0"
  region: "us-east-1"
  temperature: 0.7
  max_tokens: 1000

tools:
  - "text-analysis-mcp-server"
  - "sentiment-api"

timeout_seconds: 120

event_subscriptions:
  - "slack.events.feedback.*"
  - "scheduled.daily.sentiment"

# Implements Req 12.1, 12.2, 12.3, 12.5
```

**Environment Variables** (Req 9.2):
```bash
# AWS Bedrock Configuration
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0

# Database credentials
POSTGRES_URL=postgresql://user:pass@postgres:5432/agents
REDIS_URL=redis://redis:6379/0

# RabbitMQ
RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/

# Slack
SLACK_SIGNING_SECRET=...
SLACK_BOT_TOKEN=xoxb-...
```

**Dependencies**: pyyaml, pydantic (for validation), python-dotenv

---

### Component: LLMProviderFactory

**Purpose**: Provides a pluggable abstraction layer for multiple LLM providers, enabling agents to use AWS Bedrock, OpenAI, Anthropic, or Ollama interchangeably based on configuration.

**Location**: `src/llm/provider_factory.py`

**Interface**:
```python
from typing import Dict, Type
from src.llm.providers.base import LLMProvider, LLMConfig

class LLMProviderFactory:
    """
    Implements Req 13.1, 13.2
    Factory for creating LLM provider instances
    """

    _providers: Dict[str, Type[LLMProvider]] = {}

    @classmethod
    def register_providers(cls):
        """Register all available provider implementations"""
        from src.llm.providers.bedrock_provider import BedrockProvider
        from src.llm.providers.openai_provider import OpenAIProvider
        from src.llm.providers.anthropic_provider import AnthropicProvider
        from src.llm.providers.ollama_provider import OllamaProvider

        cls._providers = {
            'bedrock': BedrockProvider,
            'openai': OpenAIProvider,
            'anthropic': AnthropicProvider,
            'ollama': OllamaProvider,
        }

    @classmethod
    def create_provider(cls, config: LLMConfig) -> LLMProvider:
        """
        Create provider instance from configuration
        Implements Req 13.2

        Args:
            config: LLM configuration with provider type

        Returns:
            Instantiated provider

        Raises:
            ValueError: If provider not registered
        """
        provider_name = config.provider.lower()

        if provider_name not in cls._providers:
            raise ValueError(
                f"Unknown LLM provider: {provider_name}. "
                f"Available: {list(cls._providers.keys())}"
            )

        provider_class = cls._providers[provider_name]
        return provider_class(config)

    @classmethod
    def list_providers(cls) -> list[str]:
        """Get list of registered provider names"""
        return list(cls._providers.keys())
```

**Base Provider Interface** (`src/llm/providers/base.py`):
```python
from abc import ABC, abstractmethod
from typing import Iterator, Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class LLMResponse:
    """Standard response format across all providers"""
    content: str
    model: str
    input_tokens: int
    output_tokens: int
    finish_reason: str
    cost_usd: float
    metadata: Dict[str, Any]

@dataclass
class LLMConfig:
    """Provider-agnostic configuration"""
    provider: str  # 'bedrock', 'openai', 'anthropic', 'ollama'
    model_id: str
    temperature: float = 0.7
    max_tokens: int = 4096
    credentials: Optional[Dict[str, str]] = None

class LLMProvider(ABC):
    """
    Abstract interface for LLM providers
    Implements Req 13.1, 13.3, 13.4
    """

    def __init__(self, config: LLMConfig):
        self.config = config
        self.model_id = config.model_id
        self.temperature = config.temperature
        self.max_tokens = config.max_tokens

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate completion for the given prompt
        Implements Req 13.4 (token tracking and cost calculation)

        Raises:
            LLMRateLimitError: On rate limit (Req 13.3)
            LLMServiceUnavailableError: On service unavailable (Req 13.3)
        """
        pass

    @abstractmethod
    async def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Iterator[str]:
        """Stream completion tokens as they're generated"""
        pass

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Count tokens in text using provider's tokenizer"""
        pass

    @abstractmethod
    def get_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost for token usage (Req 13.4)"""
        pass
```

**Exception Hierarchy** (`src/llm/providers/exceptions.py`):
```python
class LLMProviderError(Exception):
    """Base exception for LLM provider errors"""
    pass

class LLMRateLimitError(LLMProviderError):
    """Raised when rate limit is exceeded (Req 13.3)"""
    def __init__(self, retry_after: Optional[int] = None):
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after}s")

class LLMServiceUnavailableError(LLMProviderError):
    """Raised when provider service is down (Req 13.3)"""
    pass

class LLMAuthenticationError(LLMProviderError):
    """Raised when authentication fails"""
    pass

class LLMInvalidRequestError(LLMProviderError):
    """Raised for invalid parameters"""
    pass
```

**Provider Implementations**:

1. **BedrockProvider** (`src/llm/providers/bedrock_provider.py`) - AWS Bedrock via boto3
   - Supports Claude (anthropic.claude-*) and Llama (meta.llama*) models
   - IAM authentication with access key/secret or instance profile
   - Cost tracking: Claude Sonnet ($3/$15 per 1M tokens), Haiku ($0.25/$1.25), Llama ($0.99)

2. **OpenAIProvider** (`src/llm/providers/openai_provider.py`) - OpenAI API via openai SDK
   - Supports GPT-4, GPT-3.5, GPT-4-Turbo models
   - API key authentication
   - Cost tracking: GPT-4 ($30/$60 per 1M tokens), GPT-3.5 ($0.50/$1.50)

3. **AnthropicProvider** (`src/llm/providers/anthropic_provider.py`) - Anthropic API via anthropic SDK
   - Direct Claude API access (claude-3-opus, claude-3-sonnet, claude-3-haiku)
   - API key authentication
   - Lower latency than Bedrock for Claude models

4. **OllamaProvider** (`src/llm/providers/ollama_provider.py`) - Local models via Ollama HTTP API
   - Supports Llama3, Mistral, CodeLlama, and other local models
   - No authentication (local HTTP connection)
   - Zero cost for inference

**Configuration Example**:
```yaml
# config/agents/multi-provider-example.yaml

# Research agent using Bedrock Claude for complex analysis
research_agent:
  name: "Research Agent"
  execution_mode: "autonomous"
  llm_config:
    provider: "bedrock"
    model_id: "anthropic.claude-3-5-sonnet-20241022-v2:0"
    temperature: 0.7
    max_tokens: 4096
    credentials:
      region: "${AWS_REGION}"
      access_key_id: "${AWS_ACCESS_KEY_ID}"
      secret_access_key: "${AWS_SECRET_ACCESS_KEY}"

# Classifier using local Ollama for cost savings
classifier_agent:
  name: "Classifier Agent"
  execution_mode: "autonomous"
  llm_config:
    provider: "ollama"
    model_id: "llama3:70b"
    temperature: 0.3
    max_tokens: 1024
    credentials:
      base_url: "http://ollama:11434"

# Creative agent using OpenAI GPT-4
creative_agent:
  name: "Creative Agent"
  execution_mode: "collaborative"
  llm_config:
    provider: "openai"
    model_id: "gpt-4"
    temperature: 0.9
    max_tokens: 2048
    credentials:
      api_key: "${OPENAI_API_KEY}"
```

**Environment Variables**:
```bash
# AWS Bedrock
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...

# OpenAI
OPENAI_API_KEY=sk-...

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Ollama (local - no credentials needed)
OLLAMA_BASE_URL=http://localhost:11434
```

**Dependencies**: boto3, openai, anthropic, httpx (for Ollama)

**Requirements**: 13.1, 13.2, 13.3, 13.4, 13.5

---

### Logging Utility

**Purpose**: Provides structured JSON logging with trace IDs for all components.

**Location**: `src/utils/logger.py`

**Interface**:
```python
import logging
import json
import uuid
from datetime import datetime
from typing import Optional, Dict, Any

class StructuredLogger:
    """
    Implements Req 10.1, 10.2, 10.3, 10.4
    Provides structured JSON logging to stdout with trace_id support
    """

    def __init__(self, component_name: str):
        """Initialize logger for specific component"""
        self.component = component_name
        self.logger = logging.getLogger(component_name)
        self._setup_json_handler()

    def _setup_json_handler(self):
        """Configure JSON formatter for stdout"""
        handler = logging.StreamHandler()
        handler.setFormatter(self._json_formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

    @staticmethod
    def generate_trace_id() -> str:
        """Generate new trace ID for request tracking"""
        return str(uuid.uuid4())

    def info(self, message: str, trace_id: Optional[str] = None,
             **metadata) -> None:
        """Log info level message with trace_id"""
        self._log("INFO", message, trace_id, metadata)

    def warning(self, message: str, trace_id: Optional[str] = None,
                **metadata) -> None:
        """Log warning level message with trace_id"""
        self._log("WARNING", message, trace_id, metadata)

    def error(self, message: str, trace_id: Optional[str] = None,
              error: Optional[Exception] = None, **metadata) -> None:
        """Log error level message with trace_id and optional exception"""
        if error:
            metadata['error_type'] = type(error).__name__
            metadata['error_message'] = str(error)
            metadata['stack_trace'] = self._get_stack_trace(error)
        self._log("ERROR", message, trace_id, metadata)

    def _log(self, level: str, message: str,
             trace_id: Optional[str], metadata: Dict[str, Any]) -> None:
        """Internal logging method that outputs JSON"""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": level,
            "component": self.component,
            "message": message,
            "trace_id": trace_id or "no-trace",
            **metadata
        }
        print(json.dumps(log_entry), flush=True)

    @staticmethod
    def _get_stack_trace(error: Exception) -> str:
        """Extract stack trace from exception"""
        import traceback
        return ''.join(traceback.format_exception(
            type(error), error, error.__traceback__
        ))
```

**Structured Logging Format**:
```json
{
  "timestamp": "2025-01-16T10:30:45.123Z",
  "level": "INFO",
  "component": "AutonomousAgentPool",
  "message": "Agent execution completed",
  "trace_id": "550e8400-e29b-41d4-a716-446655440000",
  "agent_id": "sentiment-analyzer",
  "execution_id": "exec-12345",
  "duration_ms": 1234
}
```

**Usage Example**:
```python
from src.utils.logger import StructuredLogger

logger = StructuredLogger("AgentOrchestrator")
trace_id = StructuredLogger.generate_trace_id()

logger.info("Starting agent", trace_id=trace_id, agent_id="sentiment-analyzer")
try:
    # ... agent execution ...
    logger.info("Agent completed", trace_id=trace_id, duration_ms=1234)
except Exception as e:
    logger.error("Agent failed", trace_id=trace_id, error=e, agent_id="sentiment-analyzer")
```

**Dependencies**: Python standard library only (logging, json, uuid, datetime)

**Viewing Logs**:
- View all logs: `docker-compose logs -f`
- View specific service: `docker-compose logs -f agent-orchestrator`
- Filter by trace_id: `docker-compose logs -f | grep "550e8400"`

---

## 5. Agent Pool Components

### CollaborativeAgentPool

**Location**: `src/agents/collaborative_agent_pool.py`

**Key Methods**: `create_execution_plan()`, `initialize_agents()`, `execute_plan_step()`, `handle_clarification()`, `aggregate_results()`

**Portia AI Integration**:
```python
from portia_sdk import PlanningAgent, ExecutionAgent, Plan, PlanRunState
import boto3

# Configure AWS Bedrock client
bedrock_client = boto3.client(
    'bedrock-runtime',
    region_name=os.getenv('AWS_REGION', 'us-east-1'),
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
)

llm_config = {
    'provider': 'bedrock',
    'client': bedrock_client,
    'model_id': os.getenv('BEDROCK_MODEL_ID', 'anthropic.claude-3-5-sonnet-20241022-v2:0'),
    'temperature': 0.7,
    'max_tokens': 4096
}

planning_agent = PlanningAgent(llm_config=llm_config, tools=tool_registry)
plan: Plan = await planning_agent.create_plan(task_description)

execution_agents = [
    ExecutionAgent(role=role, plan=plan, state_manager=portia_state, tools=role.tools)
    for role in plan.roles
]
```

**Requirements**: 4.1, 4.2, 4.3, 4.4, 4.5

---

### AutonomousAgentPool

**Location**: `src/agents/autonomous_agent_pool.py`

**Key Features**:
- Isolated execution contexts (no shared state)
- Round-robin load balancing
- Retry logic (max 2 retries)
- Access to Portia AI tools with authentication

**Requirements**: 5.1, 5.2, 5.3, 5.4, 5.5

---

### ContinuousAgentRunner

**Location**: `src/agents/continuous_agent_runner.py`

**Key Features**:
- Dedicated queue per agent (`agent.input.{agent_id}`)
- Prefetch count of 1
- Persistent state across restarts
- Incremental state updates
- Idle agent optimization (10-minute threshold)

**Requirements**: 2.3, 6.1, 6.2, 6.3, 6.4, 6.5

---

## 6. Integration Components

### SchedulerService

**Location**: `src/scheduler/scheduler_service.py`

**Celery Configuration**:
```python
from celery import Celery
from celery.schedules import crontab

app = Celery('scheduler_service', broker='amqp://rabbitmq:5672')
app.conf.update(
    task_soft_time_limit=300,  # 5 minutes
    task_time_limit=330,
)
```

**Requirements**: 3.1, 3.2, 3.5

---

### SlackGateway

**Location**: `src/integrations/slack_gateway.py`

**FastAPI Application**:
```python
from fastapi import FastAPI, Request
from slack_sdk.signature import SignatureVerifier
from slack_sdk.webhook import WebhookClient

app = FastAPI()

@app.post("/slack/events")
async def slack_events_endpoint(request: Request):
    # Verify signature, parse event, publish to EventBus
    return {"status": "ok"}

@app.get("/health")
async def health():
    return {"status": "healthy"}
```

**Requirements**: 2.1, 8.1, 8.2, 8.3, 8.4, 8.5

---

## 7. Docker Compose Architecture

**File**: `docker-compose.yml`

**Service Startup Order**:
1. Infrastructure: postgres, redis, rabbitmq
2. Core: config-service, state-manager, event-bus
3. Scheduling: scheduler-service, celery-worker
4. Gateway: slack-gateway
5. Orchestration: agent-orchestrator
6. Agents: collaborative-agent-pool, autonomous-agent-pool, continuous-agent-runner

**Networking**: `agent-network` bridge network with DNS-based service discovery

**Volumes**:
- Named volumes: `postgres-data`, `redis-data`, `rabbitmq-data`
- Bind mounts: `./config` (read-only), `./logs` (read-write), `./data` (read-write)

**Scaling**: `docker-compose up --scale autonomous-agent-pool=3`

**Requirements**: 11.1, 11.2, 11.3, 11.4, 11.5

---

## 8. Security Considerations

- Credential management via environment variables (never in code)
- Slack webhook HMAC signature verification
- PostgreSQL role-based access control
- Redis AUTH enabled
- TLS for RabbitMQ and PostgreSQL in production
- Hot-reloadable secrets without restart

---

## 9. Performance Optimizations

- Redis cache-first strategy
- RabbitMQ persistent delivery
- Round-robin load balancing
- SQLAlchemy connection pooling
- Gzip compression for state >1MB
- Horizontal scaling via docker-compose

---

## 10. Error Handling

- Exponential backoff retry logic
- Dead-letter queues after 5 attempts
- Health check probes (30-second intervals)
- Graceful shutdown (30-second timeout)
- Automatic agent restart (max 3 attempts)
- Circuit breaker for Redis failures

---

**Design document complete with full specifications for all 9 components plus logging utility, including interfaces, data structures, database schemas, and implementation details. Advanced monitoring (Prometheus/Grafana) deferred to future consideration.**
