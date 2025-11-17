# Implementation Plan (Simplified - No Prometheus/Grafana)

## Overview

This document provides a granular, actionable implementation plan for the Multi-Agent Orchestration Platform with simplified logging (no Prometheus/Grafana). Tasks are organized by component and include specific file paths, requirement references, and dependencies.

## Implementation Strategy

1. **Infrastructure First**: Set up Docker, databases, message broker
2. **Core Services**: Build ConfigurationService, StateManager, EventBus
3. **Logging Utility**: Simple structured logging with trace IDs
4. **Orchestration Layer**: Implement AgentOrchestrator
5. **Agent Pools**: Build collaborative, autonomous, and continuous agent pools
6. **Integrations**: Add SlackGateway and SchedulerService
7. **Deployment**: Finalize docker-compose
8. **Testing & Validation**: Integration tests and end-to-end validation

---

## Tasks

- [ ] **1. Project Setup and Infrastructure**
  - [ ] 1.1 Initialize Python project with Poetry/pip requirements file
    - Create `pyproject.toml` or `requirements.txt`
    - Add dependencies: `portia-sdk-python`, `fastapi`, `celery`, `sqlalchemy`, `redis`, `pika`, `slack-sdk`, `pyyaml`, `pydantic`, `python-dotenv`, `asyncpg`, `aiohttp`
    - _Requirements: All (foundational)_

  - [ ] 1.2 Create project directory structure
    - Create directories: `src/`, `src/orchestrator/`, `src/messaging/`, `src/scheduler/`, `src/integrations/`, `src/agents/`, `src/state/`, `src/config/`, `src/utils/`, `config/agents/`, `logs/`, `data/`, `tests/`
    - _Requirements: All (foundational)_

  - [ ] 1.3 Set up environment configuration
    - Create `.env.example` with all required environment variables
    - Create `config/.env` for local development
    - Document all environment variables in README
    - _Requirements: 9.2_

  - [ ] 1.4 Create base Docker images
    - Create `Dockerfile.base` with Python 3.11+ and common dependencies
    - Optimize layer caching with requirements installation before code copy
    - _Requirements: 11.1, 11.4_

- [x] **2. Database and State Infrastructure** ✅ COMPLETED
  - [x] 2.1 Create SQLAlchemy models
    - Create `src/state/models.py` with SQLAlchemy models: `AgentState`, `ExecutionResult`, `PlanRunState`
    - Define relationships, indexes, and constraints using SQLAlchemy ORM
    - Add JSONB fields for flexible data storage
    - Include timestamps with automatic updates
    - _Requirements: 7.1, 7.4_

  - [x] 2.2 Set up Alembic for database migrations
    - Initialize Alembic in project root with `alembic init alembic`
    - Configure `alembic.ini` with database connection
    - Update `alembic/env.py` to import SQLAlchemy models
    - Generate initial migration with `alembic revision --autogenerate`
    - _Requirements: 7.1, 7.4_

  - [x] 2.3 Implement StateManager class in `src/state/state_manager.py`
    - Create `StateManager` class with SQLAlchemy Session and Redis clients
    - Implement `save_state()` method with tiered storage logic (Redis + PostgreSQL via ORM)
    - Implement `load_state()` method with cache-first fallback
    - Implement `compress_data()` and `decompress_data()` for >1MB payloads
    - Add error handling for Redis unavailability (bypass to PostgreSQL)
    - Use SQLAlchemy async session for better performance
    - _Requirements: 7.1, 7.2, 7.3, 7.5_

  - [x] 2.4 Implement execution result persistence
    - Add `save_execution_result()` method to StateManager using ExecutionResult model
    - Add `update_plan_run_state()` method for collaborative tasks using PlanRunState model
    - Implement query methods using SQLAlchemy ORM for common state operations
    - Add proper transaction handling and rollback support
    - _Requirements: 3.4, 4.3, 5.3_

  - [x] 2.5 Implement state recovery for continuous agents
    - Add `load_latest_agent_state()` method with conversation history using AgentState model
    - Add `save_state()` method for incremental updates
    - Implement state restoration logic for crash recovery with ORM queries
    - Add support for querying latest state by agent_id
    - _Requirements: 6.2, 6.3, 6.4, 7.4_

  - [x] 2.6 Create StateManager health check endpoint
    - Add FastAPI app with `/health` endpoint checking Redis and PostgreSQL connectivity
    - Test database connection using SQLAlchemy session
    - Test Redis connection with ping
    - _Requirements: 11.2_

  - [x] 2.7 Create Dockerfile for StateManager
    - Create `Dockerfile.state-manager` extending base image
    - Include Alembic for database migrations
    - Add health check configuration
    - Add entrypoint script to run migrations on startup
    - _Requirements: 11.1, 11.2_

- [x] **3. Message Bus (EventBus)** ✅ COMPLETED
  - [x] 3.1 Implement EventBus class in `src/messaging/event_bus.py`
    - Create `EventBus` class with RabbitMQ connection using `pika` library
    - Implement connection with retry logic and exponential backoff
    - Configure topic exchange with persistent message delivery
    - _Requirements: 2.2_

  - [x] 3.2 Implement publish method
    - Add `publish()` method with topic routing and message persistence
    - Implement priority-based routing (via EventPriority enum)
    - Add reliable delivery with persistent messages
    - _Requirements: 2.2_

  - [x] 3.3 Implement subscribe and consume methods
    - Add `subscribe()` method with topic pattern matching
    - Add `start_consuming()` with blocking/background modes
    - Implement dynamic queue creation and binding
    - _Requirements: 6.1, 12.5_

  - [x] 3.4 Implement message acknowledgment and rejection
    - Add message acknowledgment in consumer callback
    - Add `reject()` with requeue logic
    - Implement retry tracking with message headers
    - _Requirements: 2.5_

  - [x] 3.5 Set up dead-letter queue (DLQ)
    - Configure DLQ in `subscribe()` method
    - DLQ routing after 3 failed attempts (configurable)
    - Added DLQ monitoring via `get_queue_info()`
    - _Requirements: 2.5_

  - [x] 3.6 Create Event data class
    - Define `Event` Pydantic model in `src/messaging/events.py`
    - Include fields: `event_id`, `event_type`, `timestamp`, `payload`, `trace_id`, `retry_count`, `priority`
    - Add serialization/deserialization methods (to_json/from_json)
    - Created EventType and EventPriority enums
    - _Requirements: 2.2, 10.3_

  - [x] 3.7 Create EventBus health check
    - Add `health_check()` method checking RabbitMQ connection
    - Returns status and connection details
    - _Requirements: 11.2_

  - [x] 3.8 Create comprehensive documentation
    - Created `src/messaging/README.md` with full usage guide
    - Documented all event types, routing patterns, and best practices
    - _Requirements: Documentation_

- [x] **4. Configuration Service** ✅ COMPLETED
  - [x] 4.1 Implement ConfigurationService class in `src/config/configuration_service.py`
    - Created `ConfigurationService` class
    - Implemented automatic YAML file discovery in `config/agents/`
    - Added watchdog file watcher for hot-reload capability
    - _Requirements: 9.1, 12.1_

  - [x] 4.2 Implement configuration validation
    - Created comprehensive Pydantic models in `src/config/models.py`
    - Implemented `validate_configuration()` method with full validation
    - Defined required fields: `name`, `agent_type`, `execution_mode`, `llm_config`
    - Added detailed validation error reporting
    - _Requirements: 1.2, 9.1_

  - [x] 4.3 Implement secrets management
    - Implemented secrets loading from environment using `python-dotenv`
    - Automatic injection of LLM provider credentials (AWS, OpenAI, Anthropic)
    - Injection of Slack integration tokens
    - Safe handling of missing secrets
    - _Requirements: 9.2_

  - [x] 4.4 Implement hot-reload functionality
    - Implemented automatic file change detection with watchdog Observer
    - Real-time configuration reload on file modifications
    - Detection of new and deleted configuration files
    - Automatic error handling and logging
    - _Requirements: 9.3_

  - [x] 4.5 Implement credential injection
    - Added `get_agent_config()` method for agent-specific retrieval
    - Implemented `_inject_secrets()` method for safe credential injection
    - Secrets never logged or exposed in configurations
    - Provider-specific credential injection (AWS, OpenAI, Anthropic, Slack)
    - _Requirements: 9.4, 9.5_

  - [x] 4.6 Create sample agent configuration files
    - Created `config/agents/customer_support_agent.yaml` (autonomous, event-driven)
    - Created `config/agents/data_analyzer.yaml` (collaborative, scheduled)
    - Created `config/agents/system_monitor.yaml` (continuous)
    - Created comprehensive README with examples
    - _Requirements: Documentation_
    - Create `config/agents/example-scheduled.yaml`
    - _Requirements: 12.1, 12.2, 12.3_

  - [ ] 4.7 Create ConfigurationService health check
    - Add `/health` endpoint
    - _Requirements: 11.2_

  - [ ] 4.8 Create Dockerfile for ConfigurationService
    - Create `Dockerfile.config-service`
    - Mount config directory as read-only volume
    - _Requirements: 11.1, 11.4_

- [ ] **5. LLM Provider Abstraction Layer**
  - [ ] 5.1 Create base provider interface in `src/llm/providers/base.py`
    - Define `LLMProvider` abstract base class with abstract methods: `complete()`, `stream()`, `count_tokens()`, `get_cost()`
    - Create `LLMResponse` dataclass with fields: content, model, input_tokens, output_tokens, finish_reason, cost_usd, metadata
    - Create `LLMConfig` dataclass with fields: provider, model_id, temperature, max_tokens, credentials
    - _Requirements: 13.1_

  - [ ] 5.2 Create exception hierarchy in `src/llm/providers/exceptions.py`
    - Define `LLMProviderError` base exception
    - Create specific exceptions: `LLMRateLimitError`, `LLMServiceUnavailableError`, `LLMAuthenticationError`, `LLMInvalidRequestError`
    - Add `retry_after` parameter to `LLMRateLimitError`
    - _Requirements: 13.3_

  - [ ] 5.3 Implement BedrockProvider in `src/llm/providers/bedrock_provider.py`
    - Implement `complete()` method with boto3 `invoke_model` for Claude and Llama models
    - Implement `stream()` method with `invoke_model_with_response_stream`
    - Add provider-specific request/response parsing for Anthropic and Meta model families
    - Implement `count_tokens()` with character-based estimation
    - Implement `get_cost()` with pricing table for Claude Sonnet, Haiku, and Llama models
    - Add error handling mapping boto3 exceptions to custom exception hierarchy
    - _Requirements: 13.1, 13.2, 13.3, 13.4_

  - [ ] 5.4 Implement OpenAIProvider in `src/llm/providers/openai_provider.py`
    - Implement `complete()` method using openai SDK `ChatCompletion.create()`
    - Implement `stream()` method with `stream=True` parameter
    - Implement `count_tokens()` using tiktoken library
    - Implement `get_cost()` with pricing for GPT-4, GPT-4-Turbo, GPT-3.5 models
    - Add retry logic with exponential backoff for rate limits
    - _Requirements: 13.1, 13.2, 13.3, 13.4_

  - [ ] 5.5 Implement AnthropicProvider in `src/llm/providers/anthropic_provider.py`
    - Implement `complete()` method using anthropic SDK `messages.create()`
    - Implement `stream()` method with `stream=True` parameter
    - Implement `count_tokens()` using anthropic's count_tokens API
    - Implement `get_cost()` with pricing for Claude Opus, Sonnet, Haiku
    - Add support for system prompts and tool use
    - _Requirements: 13.1, 13.2, 13.3, 13.4_

  - [ ] 5.6 Implement OllamaProvider in `src/llm/providers/ollama_provider.py`
    - Implement `complete()` method using httpx to call Ollama HTTP API `/api/generate`
    - Implement `stream()` method with streaming endpoint
    - Implement `count_tokens()` with character-based estimation
    - Implement `get_cost()` returning 0.0 (local inference is free)
    - Add connection health check to verify Ollama service availability
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5_

  - [ ] 5.7 Implement LLMProviderFactory in `src/llm/provider_factory.py`
    - Create `LLMProviderFactory` class with `_providers` registry dictionary
    - Implement `register_providers()` class method to register all provider implementations
    - Implement `create_provider(config: LLMConfig)` method to instantiate providers based on config.provider
    - Implement `list_providers()` method to return available provider names
    - Add validation to raise `ValueError` for unknown providers
    - _Requirements: 13.1, 13.2_

  - [ ] 5.8 Add LLM provider integration to agent pools
    - Update `CollaborativeAgentPool` to use `LLMProviderFactory.create_provider()` instead of hardcoded Bedrock client
    - Update `AutonomousAgentPool` to use provider factory
    - Update `ContinuousAgentRunner` to use provider factory
    - Add provider retry logic with exponential backoff (catch `LLMRateLimitError`, retry up to 3 times)
    - Log provider selection and cost metadata to StateManager
    - _Requirements: 13.2, 13.3, 13.4, 13.5_

  - [ ] 5.9 Add LLM provider credentials to ConfigurationService
    - Update `load_secrets()` to load AWS Bedrock, OpenAI, Anthropic, and Ollama credentials
    - Add validation for provider-specific required credentials
    - Update agent YAML schema to support multi-provider llm_config format
    - _Requirements: 13.2_

  - [ ] 5.10 Create provider integration tests
    - Create `tests/llm/test_providers.py` with mock tests for each provider
    - Test provider factory creation and registration
    - Test error handling and exception mapping
    - Test cost calculation for different models
    - Test concurrent multi-provider usage (Req 13.5)
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5_

- [ ] **6. Logging Utility**
  - [ ] 8.1 Implement StructuredLogger class in `src/utils/logger.py`
    - Create `StructuredLogger` class with JSON logging to stdout
    - Implement `generate_trace_id()` static method for UUID generation
    - Set up JSON formatting for log messages
    - _Requirements: 10.1, 10.2_

  - [ ] 8.2 Implement logging methods
    - Add `info()`, `warning()`, `error()` methods with trace_id parameter
    - Implement log formatting with timestamp, level, component, message, trace_id, metadata
    - Add stack trace extraction for errors
    - _Requirements: 10.1, 10.3_

  - [ ] 8.3 Create logging usage examples and documentation
    - Document how to initialize logger in each component
    - Provide examples of trace_id propagation
    - Add guide for viewing logs with docker-compose
    - _Requirements: 10.4_

- [ ] **7. Agent Orchestrator**
  - [ ] 7.1 Implement AgentOrchestrator class in `src/orchestrator/agent_orchestrator.py`
    - Create `AgentOrchestrator` class with dependencies (ConfigService, StateManager)
    - Initialize agent registry dictionary
    - Initialize StructuredLogger for the component
    - _Requirements: 1.1_

  - [ ] 7.2 Implement agent registration
    - Add `initialize()` method to load all configurations and register agents
    - Add `register_agent()` method with validation
    - Create `AgentMetadata` and `AgentRegistration` dataclasses
    - Implement registry with agent capabilities and execution modes
    - Log registration events with trace_id
    - _Requirements: 1.1, 1.2, 1.3, 12.2, 12.4_

  - [ ] 7.3 Implement agent startup
    - Add `start_agent()` method to initialize agents
    - Implement initialization failure handling with logging
    - Mark failed agents as unavailable in registry
    - _Requirements: 1.3_

  - [ ] 7.4 Implement agent invocation
    - Add `invoke_agent()` method for event-driven execution
    - Route agents to appropriate pools based on execution_mode
    - Record execution start time in StateManager
    - _Requirements: 3.3_

  - [ ] 7.5 Implement health monitoring
    - Add `health_check_agent()` method with 60-second detection window
    - Add `restart_agent()` method with max 3 retry attempts
    - Implement automatic restart on unresponsive agents
    - Track retry counts in agent metadata
    - _Requirements: 1.5_

  - [ ] 7.6 Implement graceful shutdown
    - Add `shutdown()` method with 30-second timeout
    - Notify all running agents to complete current tasks
    - Implement force termination after timeout
    - _Requirements: 1.4_

  - [ ] 7.7 Implement agent registry query
    - Add `get_agent_registry()` method returning snapshot
    - Add filtering by status, type, execution_mode
    - _Requirements: 1.1, 12.4_

  - [ ] 7.8 Create Dockerfile for AgentOrchestrator
    - Create `Dockerfile.orchestrator`
    - Include Portia AI SDK and all dependencies
    - _Requirements: 11.1_

- [ ] **8. Collaborative Agent Pool**
  - [ ] 9.1 Implement CollaborativeAgentPool class in `src/agents/collaborative_agent_pool.py`
    - Create `CollaborativeAgentPool` class
    - Initialize Portia AI PlanningAgent and ExecutionAgent clients
    - Initialize StructuredLogger for the component
    - _Requirements: 4.1_

  - [ ] 9.2 Implement multi-agent plan creation
    - Add `create_execution_plan()` method using Portia AI PlanningAgent
    - Generate plans with role assignments for participating agents
    - Store plan in StateManager
    - Log plan creation with trace_id
    - _Requirements: 4.1_

  - [ ] 9.3 Implement agent initialization for collaboration
    - Add `initialize_agents()` method creating ExecutionAgent instances
    - Initialize agents with shared state access
    - Set up agent roles and capabilities
    - _Requirements: 4.2_

  - [ ] 9.4 Implement plan execution
    - Add `execute_plan_step()` method for sequential execution
    - Update PlanRunState after each step
    - Trigger next agent in sequence via EventBus
    - _Requirements: 4.3_

  - [ ] 9.5 Implement human-in-the-loop clarification
    - Add `handle_clarification()` method using Portia AI Clarification interface
    - Pause execution until clarification is provided
    - Resume execution with clarification response
    - _Requirements: 4.4_

  - [ ] 9.6 Implement result aggregation
    - Add `aggregate_results()` method combining agent outputs
    - Store final results in StateManager
    - Publish completion event to EventBus on topic `collaboration.completed.{task_id}`
    - _Requirements: 4.5_

  - [ ] 9.7 Create Dockerfile for CollaborativeAgentPool
    - Create `Dockerfile.collaborative-pool`
    - _Requirements: 11.1_

- [ ] **9. Autonomous Agent Pool**
  - [ ] 9.1 Implement AutonomousAgentPool class in `src/agents/autonomous_agent_pool.py`
    - Create `AutonomousAgentPool` class
    - Initialize agent instances for each autonomous agent type
    - Initialize StructuredLogger for the component
    - _Requirements: 5.1_

  - [ ] 9.2 Implement isolated execution
    - Add `execute_autonomous_task()` method with isolated context
    - Prevent access to other agents' state
    - Provide Portia AI tools with authentication from ConfigService
    - Log execution with trace_id
    - _Requirements: 5.1, 5.2, 5.4_

  - [ ] 9.3 Implement result persistence
    - Store results in StateManager keyed by `agent_id` and `execution_id`
    - Ensure no state sharing between autonomous agents
    - _Requirements: 5.3_

  - [ ] 9.4 Implement failure handling and retry
    - Add `retry_on_failure()` method with max 2 retries
    - Execute with fresh context on each retry
    - Log errors with trace_id
    - Mark task as failed after exhausting retries
    - _Requirements: 5.4_

  - [ ] 9.5 Implement round-robin load balancing
    - Create `RoundRobinLoadBalancer` class
    - Add `get_agent_instance()` method for instance selection
    - Distribute events across multiple agent instances
    - _Requirements: 5.5_

  - [ ] 9.6 Create Dockerfile for AutonomousAgentPool
    - Create `Dockerfile.autonomous-pool`
    - Support horizontal scaling via docker-compose
    - _Requirements: 11.1, 11.5_

- [ ] **10. Continuous Agent Runner**
  - [ ] 10.1 Implement ContinuousAgentRunner class in `src/agents/continuous_agent_runner.py`
    - Create `ContinuousAgentRunner` class
    - Set up event consumption from EventBus with prefetch=1
    - Initialize StructuredLogger for the component
    - _Requirements: 6.1_

  - [ ] 10.2 Implement agent subscription to dedicated queues
    - Add `start_continuous_agents()` method
    - Subscribe each agent to queue `agent.input.{agent_id}`
    - Configure prefetch count of 1 per agent
    - _Requirements: 6.1_

  - [ ] 10.3 Implement event processing with state management
    - Add `process_event()` method
    - Load persistent state from StateManager (conversation history, memory)
    - Execute Portia AI agent with event payload
    - Update and persist state incrementally
    - Log all operations with trace_id
    - _Requirements: 2.3, 6.2, 6.3_

  - [ ] 10.4 Implement continuous processing loop
    - Create `run_continuous_agent()` async method
    - Consume events continuously from dedicated queue
    - Publish results to EventBus on topic `agent.output.{agent_id}`
    - Acknowledge messages on success, reject with requeue on failure
    - _Requirements: 2.3_

  - [ ] 10.5 Implement state restoration for crash recovery
    - Add `load_agent_state()` method restoring from StateManager
    - Resume processing from last acknowledged message
    - _Requirements: 6.4_

  - [ ] 10.6 Implement idle agent optimization
    - Add `flush_idle_agent()` method triggered after 10 minutes of inactivity
    - Persist current state to StateManager
    - Flush in-memory caches to reduce resource consumption
    - _Requirements: 6.5_

  - [ ] 10.7 Create Dockerfile for ContinuousAgentRunner
    - Create `Dockerfile.continuous-runner`
    - _Requirements: 11.1_

- [ ] **11. Scheduler Service**
  - [ ] 11.1 Set up Celery configuration in `src/scheduler/celery_config.py`
    - Create Celery app with RabbitMQ broker
    - Configure task serialization (JSON), timezone (UTC)
    - Set soft time limit to 300 seconds (5 minutes)
    - _Requirements: 3.5_

  - [ ] 11.2 Implement SchedulerService class in `src/scheduler/scheduler_service.py`
    - Create `SchedulerService` class
    - Initialize Celery Beat scheduler
    - Initialize StructuredLogger for the component
    - _Requirements: 3.1_

  - [ ] 11.3 Implement schedule registration
    - Add `initialize()` method loading scheduled tasks from ConfigService
    - Add `register_schedule()` method for cron and interval schedules
    - Create `ScheduleConfig` dataclass with cron_expression and interval_seconds
    - Register schedules with Celery Beat
    - Log schedule registration with trace_id
    - _Requirements: 3.1, 3.5_

  - [ ] 11.4 Implement scheduled task publishing
    - Add `publish_scheduled_task()` method
    - Publish events to EventBus queue `scheduled.tasks` with agent_id and timestamp
    - _Requirements: 3.2_

  - [ ] 11.5 Implement timeout handling
    - Add `cancel_timeout()` method for tasks exceeding 5-minute timeout
    - Log timeout errors with trace_id
    - _Requirements: 3.5_

  - [ ] 11.6 Create Celery task for agent execution
    - Define `execute_scheduled_agent()` Celery task
    - Integrate with SchedulerService.publish_scheduled_task()
    - _Requirements: 3.2_

  - [ ] 11.7 Create Dockerfiles for SchedulerService
    - Create `Dockerfile.scheduler` for both Celery Beat and Worker
    - Support separate containers for beat and worker processes
    - _Requirements: 11.1_

- [ ] **12. Slack Gateway Integration**
  - [ ] 12.1 Implement SlackGateway class in `src/integrations/slack_gateway.py`
    - Create `SlackGateway` class with FastAPI app
    - Initialize `slack_sdk.signature.SignatureVerifier` with signing secret
    - Initialize StructuredLogger for the component
    - _Requirements: 8.1_

  - [ ] 12.2 Implement webhook endpoint
    - Create FastAPI POST route `/slack/events`
    - Add `handle_webhook()` method processing incoming requests
    - Return HTTP 200 on success, HTTP 401 on invalid signature
    - Generate trace_id for incoming requests
    - _Requirements: 8.1, 10.2_

  - [ ] 12.3 Implement signature verification
    - Add `verify_signature()` method using SignatureVerifier
    - Validate HMAC signature from Slack headers
    - Reject requests with invalid signatures
    - _Requirements: 8.1_

  - [ ] 12.4 Implement event parsing
    - Add `parse_slack_event()` method extracting event_type, user_id, channel_id, text, response_url
    - Create `SlackEvent` dataclass
    - Parse slash_command, message, button_click event types
    - _Requirements: 8.2, 8.3_

  - [ ] 12.5 Implement event publishing to EventBus
    - Publish parsed event to EventBus topic `slack.events.*` within 100ms
    - Include response_url and trace_id in event metadata
    - _Requirements: 2.1, 8.3_

  - [ ] 12.6 Implement async response to Slack
    - Add `send_response()` method using `slack_sdk.webhook.WebhookClient`
    - Post results to Slack via response_url
    - Implement rate limit handling with exponential backoff
    - _Requirements: 8.4, 8.5_

  - [ ] 12.7 Create health check endpoint
    - Add GET route `/health` returning {"status": "healthy"}
    - _Requirements: 11.2_

  - [ ] 12.8 Create Dockerfile for SlackGateway
    - Create `Dockerfile.slack-gateway`
    - Expose port 8080 for webhook receiver
    - _Requirements: 11.1_

- [ ] **13. Docker Compose Orchestration**
  - [ ] 13.1 Create main docker-compose.yml
    - Define version 3.9
    - Create `agent-network` bridge network
    - Define named volumes for postgres-data, redis-data, rabbitmq-data
    - _Requirements: 11.3, 11.4_

  - [ ] 13.2 Configure infrastructure services
    - Add `postgres` service with PostgreSQL 15, health checks, volume mounts
    - Add `redis` service with Redis 7, AOF persistence, health checks
    - Add `rabbitmq` service with management UI, health checks, volume mounts
    - Configure health check intervals (10-30 seconds)
    - _Requirements: 11.1, 11.2_

  - [ ] 13.3 Configure core application services
    - Add `config-service` with dependency on postgres and redis
    - Add `state-manager` with dependency on postgres and redis
    - Add `event-bus` with dependency on rabbitmq
    - Configure read-only mount for `./config` directory
    - Configure read-write mounts for `./logs` and `./data`
    - _Requirements: 11.1, 11.4_

  - [ ] 13.4 Configure scheduler services
    - Add `scheduler-service` with Celery Beat command
    - Add `celery-worker` with Celery worker command
    - Set dependencies on rabbitmq and config-service
    - _Requirements: 11.1_

  - [ ] 13.5 Configure gateway and orchestrator
    - Add `slack-gateway` with port 8080 exposed
    - Add `agent-orchestrator` with all environment variables
    - Set correct service dependencies
    - _Requirements: 11.1_

  - [ ] 13.6 Configure agent pool services
    - Add `collaborative-agent-pool` service
    - Add `autonomous-agent-pool` service (scalable)
    - Add `continuous-agent-runner` service
    - Set dependencies on agent-orchestrator
    - _Requirements: 11.1, 11.5_

  - [ ] 13.7 Add environment variable template
    - Create `.env.example` with all required variables
    - Document each variable with comments
    - Include database, Redis, RabbitMQ, AWS Bedrock credentials, Slack secrets
    - _Requirements: 9.2_

  - [ ] 13.8 Test horizontal scaling
    - Verify `docker-compose up --scale autonomous-agent-pool=3` works correctly
    - Test load distribution across scaled instances
    - _Requirements: 11.5_

- [ ] **14. Extensibility Implementation**
  - [ ] 14.1 Implement auto-discovery for new agents
    - Verify ConfigurationService automatically discovers YAML files in `config/agents/`
    - Test loading new agent without code changes
    - _Requirements: 12.1_

  - [ ] 14.2 Implement execution mode routing
    - Verify AgentOrchestrator routes agents to correct pools based on execution_mode
    - Test collaborative, autonomous, continuous, and scheduled modes
    - _Requirements: 12.2_

  - [ ] 14.3 Implement custom tool support
    - Verify agent configurations can specify MCP server URLs
    - Test Portia AI dynamic tool loading and authentication
    - _Requirements: 12.3_

  - [ ] 14.4 Test agent scaling to 20+ agents
    - Create 20 sample agent configurations
    - Verify AgentOrchestrator startup time <5 seconds
    - Test performance with full agent registry
    - _Requirements: 12.4_

  - [ ] 14.5 Implement event subscription from config
    - Verify agents subscribe to topics based on configuration
    - Test EventBus automatic subscription creation
    - Verify topic pattern matching (e.g., `slack.events.command.*`)
    - _Requirements: 12.5_

- [ ] **15. Integration Testing**
  - [ ] 15.1 Create integration test suite
    - Set up pytest framework in `tests/integration/`
    - Create fixtures for test database, Redis, RabbitMQ
    - _Requirements: All_

  - [ ] 15.2 Test Slack-triggered agent flow with trace_id
    - Send test Slack webhook to SlackGateway
    - Verify trace_id generation and propagation
    - Verify signature validation
    - Verify event published to EventBus
    - Verify autonomous agent execution
    - Verify response sent back to Slack
    - Verify logs contain trace_id throughout workflow
    - _Requirements: 2.1, 8.1, 8.2, 8.3, 8.4, 10.2, 10.3_

  - [ ] 15.3 Test scheduled agent execution
    - Configure test scheduled agent with short interval
    - Verify SchedulerService publishes events
    - Verify AgentOrchestrator invokes agent
    - Verify execution results stored in StateManager
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [ ] 15.4 Test collaborative multi-agent task
    - Submit collaborative task to CollaborativeAgentPool
    - Verify plan creation with PlanningAgent
    - Verify ExecutionAgent initialization with shared state
    - Verify PlanRunState updates
    - Verify final result aggregation and event publishing
    - _Requirements: 4.1, 4.2, 4.3, 4.5_

  - [ ] 15.5 Test continuous agent processing
    - Publish events to continuous agent queue
    - Verify state loading and persistence
    - Verify incremental state updates
    - Test crash recovery and state restoration
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

  - [ ] 15.6 Test state persistence and recovery
    - Write state to StateManager
    - Verify Redis cache hit
    - Test PostgreSQL fallback on cache miss
    - Test compression for >1MB payloads
    - Simulate Redis failure and verify bypass
    - _Requirements: 7.1, 7.2, 7.3, 7.5_

  - [ ] 15.7 Test EventBus reliability
    - Publish messages with persistence
    - Simulate consumer failure and verify redelivery
    - Test exponential backoff retry logic
    - Verify DLQ routing after 5 attempts
    - _Requirements: 2.2, 2.5_

  - [ ] 15.8 Test agent health monitoring
    - Simulate agent unresponsiveness
    - Verify health check detection within 60 seconds
    - Verify automatic restart (max 3 attempts)
    - Verify failed agent marked in registry
    - _Requirements: 1.5_

  - [ ] 15.9 Test graceful shutdown
    - Send shutdown signal to AgentOrchestrator
    - Verify agents complete tasks within 30 seconds
    - Verify force termination after timeout
    - _Requirements: 1.4_

  - [ ] 15.10 Test logging and trace_id propagation
    - Verify structured logs emitted by all components
    - Verify trace_id propagation through multi-component workflows
    - Test log filtering by trace_id using docker-compose logs
    - Verify error logs include stack traces
    - _Requirements: 10.1, 10.2, 10.3, 10.4_

- [ ] **16. Documentation and Deployment**
  - [ ] 16.1 Create comprehensive README.md
    - Add project overview and architecture diagram
    - Document prerequisites (Docker, docker-compose)
    - Add quick start guide
    - Document environment variables
    - Add troubleshooting section including log viewing
    - _Requirements: All_

  - [ ] 16.2 Create deployment guide
    - Document production deployment steps
    - Add security hardening recommendations (TLS, secrets management)
    - Document log viewing and analysis with docker-compose
    - Add backup and disaster recovery procedures
    - _Requirements: All_

  - [ ] 16.3 Create agent development guide
    - Document how to add new agents
    - Provide YAML configuration examples
    - Document tool integration with Portia AI
    - Add best practices for agent design
    - Include logging best practices with trace_id
    - _Requirements: 12.1, 12.2, 12.3_

  - [ ] 16.4 Create operational runbook
    - Document common operational tasks
    - Add scaling guide for agent pools
    - Document log analysis and debugging with trace_id
    - Add performance tuning recommendations
    - _Requirements: 11.5_

  - [ ] 16.5 Test end-to-end deployment
    - Deploy full stack with `docker-compose up`
    - Verify all service health checks pass
    - Test complete workflows (Slack trigger, scheduled, collaborative)
    - Validate logs are viewable and filterable
    - _Requirements: 11.1, 11.2_

---

## Summary

This simplified implementation plan contains **15 major phases** with **125 granular tasks** covering:
- Infrastructure setup (Docker, databases, message broker)
- Core service implementation (9 components + logging utility)
- Integration testing (10 test suites)
- Documentation and deployment

**Removed from original plan**:
- Prometheus metrics collection (~10 tasks)
- Grafana dashboards (~4 tasks)
- Advanced alerting (~4 tasks)
- MonitoringCollector as separate service

**Kept for future consideration**:
- Centralized monitoring infrastructure
- Log aggregation platforms
- Real-time metrics and alerting
- Performance analytics dashboards

## Estimated Timeline

- **Week 1-2**: Infrastructure and Core Services (Tasks 1-5)
- **Week 3**: Orchestration Layer (Task 6)
- **Week 4-5**: Agent Pools (Tasks 7-9)
- **Week 6**: Integrations (Tasks 10-11)
- **Week 7**: Deployment and Testing (Tasks 12-14)
- **Week 8**: Documentation and Production Readiness (Task 15)

**Total**: 125 tasks (down from 143 tasks)
**Coverage**: All 56 acceptance criteria
