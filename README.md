# Multi-Agent Orchestration Platform

A production-ready, event-driven multi-agent orchestration system built with Python, Portia AI, and RabbitMQ. Supports 20+ specialized AI agents with heterogeneous execution patterns including collaborative, autonomous, continuous, and scheduled modes.

## Features

✅ **4 Agent Execution Patterns**
- **Collaborative**: Multi-agent coordination for complex tasks
- **Autonomous**: Independent execution with load balancing
- **Continuous**: Long-running event processors with persistent state
- **Scheduled**: Time-based execution with cron and interval support

✅ **Pluggable LLM Providers**
- AWS Bedrock (Claude, Llama, Titan)
- OpenAI (GPT-4, GPT-3.5)
- Anthropic (Claude API)
- Ollama (local models)

✅ **Enterprise Features**
- Event-driven architecture with RabbitMQ
- Tiered state persistence (Redis + PostgreSQL)
- Configuration-based agent management (no code changes)
- Horizontal scaling with Docker Compose
- Crash recovery for continuous agents
- Slack integration with webhook support
- Structured JSON logging with trace IDs

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌───────────────────┐
│  Slack Gateway  │────▶│  AgentOrchestrator│────▶│  Agent Pools      │
│  (Port 8005)    │     │  (Port 8003)      │     │  - Collaborative  │
└─────────────────┘     └──────────────────┘     │  - Autonomous     │
                                │                 │  - Continuous     │
                                │                 └───────────────────┘
                                ▼
┌─────────────────┐     ┌──────────────────┐
│ SchedulerService│     │    EventBus      │
│  (Port 8004)    │────▶│   (RabbitMQ)     │
└─────────────────┘     └──────────────────┘
                                │
                                ▼
                        ┌──────────────────┐
                        │  StateManager    │
                        │  (Port 8001)     │
                        │  Redis + PG      │
                        └──────────────────┘
```

## Quick Start

### Prerequisites

- Docker & Docker Compose
- At least one LLM provider API key (OpenAI, Anthropic, AWS Bedrock, or Ollama)
- (Optional) Slack workspace for integrations

### 1. Clone and Configure

```bash
git clone <repository-url>
cd agentrunner

# Copy environment template
cp .env.example .env

# Edit .env and add your API keys
nano .env
```

**Required Environment Variables:**
```bash
# At least one LLM provider:
OPENAI_API_KEY=your_openai_api_key
# OR
ANTHROPIC_API_KEY=your_anthropic_api_key
# OR
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_REGION=us-east-1

# Optional: Slack integration
SLACK_SIGNING_SECRET=your_slack_signing_secret
SLACK_BOT_TOKEN=xoxb-your-slack-bot-token
```

### 2. Start All Services

```bash
# Start infrastructure and all services
docker-compose up -d

# View logs
docker-compose logs -f

# Check service health
curl http://localhost:8001/health/live  # StateManager
curl http://localhost:8002/health/live  # ConfigService
curl http://localhost:8003/health/live  # AgentOrchestrator
curl http://localhost:8004/health/live  # SchedulerService
curl http://localhost:8005/health/live  # SlackGateway
```

### 3. Configure Your First Agent

Create a YAML file in `config/agents/`:

```yaml
# config/agents/my-assistant.yml
name: my-assistant
agent_type: task_executor
execution_mode: autonomous
description: "A helpful AI assistant"

llm_config:
  provider: openai
  model: gpt-4
  temperature: 0.7
  max_tokens: 2000

system_prompt: |
  You are a helpful AI assistant that answers questions accurately and concisely.

tags:
  - general
  - qa

event_subscriptions:
  - "slack.command.ask"
  - "task.submitted.general"
```

### 4. Invoke an Agent

```bash
# Via REST API
curl -X POST http://localhost:8003/agents/my-assistant/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "task_data": {
      "prompt": "What is the capital of France?"
    }
  }'

# Via Slack (if configured)
/ask What is the capital of France?
```

## Service Endpoints

| Service | Port | Health Check | Management UI |
|---------|------|--------------|---------------|
| StateManager | 8001 | `/health/live` | - |
| ConfigService | 8002 | `/health/live` | - |
| AgentOrchestrator | 8003 | `/health/live` | `/docs` (Swagger) |
| SchedulerService | 8004 | `/health/live` | `/docs` (Swagger) |
| SlackGateway | 8005 | `/health/live` | `/docs` (Swagger) |
| RabbitMQ | 5672 | - | http://localhost:15672 |
| PostgreSQL | 5432 | - | - |
| Redis | 6379 | - | - |

## Scaling Agent Pools

```bash
# Scale autonomous agent pool to 3 instances
docker-compose up -d --scale autonomous-agent-pool=3

# Verify scaling
docker-compose ps
```

## Agent Configuration Reference

### Execution Modes

**Collaborative** (`execution_mode: collaborative`)
- Multiple agents work together on complex tasks
- Uses Portia AI for planning and coordination
- Supports human-in-the-loop clarifications

**Autonomous** (`execution_mode: autonomous`)
- Independent execution in isolation
- Round-robin load balancing
- Automatic retry on failure (max 2 retries)

**Continuous** (`execution_mode: continuous`)
- Long-running event processors
- Persistent conversation history
- Crash recovery with state restoration
- Idle timeout (10 minutes default)

**Scheduled** (`execution_mode: scheduled`)
- Time-based execution with Celery Beat
- Supports cron and interval schedules

### LLM Provider Configuration

```yaml
# OpenAI
llm_config:
  provider: openai
  model: gpt-4
  temperature: 0.7

# Anthropic
llm_config:
  provider: anthropic
  model: claude-3-sonnet-20240229
  max_tokens: 4096

# AWS Bedrock
llm_config:
  provider: bedrock
  model: anthropic.claude-3-sonnet-20240229-v1:0
  region: us-east-1

# Ollama (local)
llm_config:
  provider: ollama
  model: llama2
  host: http://localhost:11434
```

### Schedule Configuration

```yaml
# Cron schedule (daily at midnight)
schedule_config:
  type: cron
  cron: "0 0 * * *"  # minute hour day month day_of_week
  task_data:
    prompt: "Generate daily report"

# Interval schedule (every hour)
schedule_config:
  type: interval
  interval_seconds: 3600
  task_data:
    prompt: "Check system status"
```

## Development

### Project Structure

```
agentrunner/
├── config/
│   └── agents/          # Agent YAML configurations
├── src/
│   ├── agents/          # Agent pool implementations
│   ├── config/          # Configuration service
│   ├── integrations/    # Slack gateway
│   ├── messaging/       # EventBus (RabbitMQ)
│   ├── orchestrator/    # AgentOrchestrator
│   ├── scheduler/       # SchedulerService (Celery)
│   ├── state/          # StateManager
│   └── utils/          # Logging, helpers
├── tests/              # Integration tests
├── logs/               # Application logs
├── data/               # Persistent data
├── docker-compose.yml  # Service orchestration
├── requirements.txt    # Python dependencies
└── .env               # Environment variables
```

### Running Tests

```bash
# Run integration tests
docker-compose exec state-manager pytest tests/

# Run with coverage
docker-compose exec state-manager pytest tests/ --cov=src --cov-report=html
```

### Viewing Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f agent-orchestrator

# Follow trace ID across services
docker-compose logs -f | grep "trace_id\":\"abc-123"
```

### Database Migrations

```bash
# Create new migration
docker-compose exec state-manager alembic revision --autogenerate -m "description"

# Apply migrations
docker-compose exec state-manager alembic upgrade head

# Rollback
docker-compose exec state-manager alembic downgrade -1
```

## Monitoring

### Health Checks

All services expose `/health/live` (liveness) and `/health/ready` (readiness) endpoints:

```bash
# Check all services
for port in 8001 8002 8003 8004 8005; do
  echo "Port $port: $(curl -s http://localhost:$port/health/live | jq -r .status)"
done
```

### Structured Logging

All services log in JSON format with trace IDs for request correlation:

```json
{
  "timestamp": "2025-01-18T10:30:00Z",
  "level": "INFO",
  "service": "AgentOrchestrator",
  "trace_id": "abc-123-def-456",
  "message": "Agent invoked successfully",
  "metadata": {
    "agent_name": "my-assistant",
    "execution_id": "exec-789"
  }
}
```

### RabbitMQ Management

Access RabbitMQ management UI at http://localhost:15672
- Username: `guest` (default)
- Password: `guest` (default)

## Troubleshooting

### Service Won't Start

```bash
# Check service logs
docker-compose logs <service-name>

# Verify dependencies are healthy
docker-compose ps

# Restart specific service
docker-compose restart <service-name>
```

### Agent Invocation Fails

```bash
# Check agent registration
curl http://localhost:8003/agents

# View agent configuration
curl http://localhost:8002/configs/<agent-name>

# Check EventBus connectivity
docker-compose logs rabbitmq
```

### Database Connection Issues

```bash
# Check PostgreSQL health
docker-compose exec postgres pg_isready -U agentrunner

# Check Redis connectivity
docker-compose exec redis redis-cli ping

# View StateManager logs
docker-compose logs state-manager
```

## Production Deployment

### Security Checklist

- [ ] Change default passwords in `.env`
- [ ] Enable TLS for external endpoints (`ENABLE_TLS=true`)
- [ ] Configure API authentication (`ENABLE_API_AUTH=true`)
- [ ] Use secrets management (AWS Secrets Manager, HashiCorp Vault)
- [ ] Restrict network access with firewall rules
- [ ] Enable Slack signature verification (already configured)
- [ ] Review and rotate LLM provider API keys regularly

### Performance Tuning

```bash
# Scale agent pools
docker-compose up -d --scale autonomous-agent-pool=5

# Increase database connection pool
# In .env:
DB_POOL_SIZE=50
DB_MAX_OVERFLOW=20

# Adjust RabbitMQ prefetch count
RABBITMQ_PREFETCH_COUNT=5

# Configure Redis persistence
# Edit docker-compose.yml redis command:
command: redis-server --appendonly yes --appendfsync everysec
```

## License

[Your License Here]

## Support

For issues and questions:
- GitHub Issues: [repository-url]/issues
- Documentation: `docs/`
- Architecture Spec: `docs/01-blueprint.md`
