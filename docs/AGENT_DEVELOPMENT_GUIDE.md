# Agent Development Guide
**Multi-Agent Orchestration Platform**

This guide teaches you how to create, configure, and deploy AI agents within the Multi-Agent Orchestration Platform.

## Table of Contents

1. [Introduction](#introduction)
2. [Agent Basics](#agent-basics)
3. [Execution Modes](#execution-modes)
4. [Agent Configuration](#agent-configuration)
5. [LLM Provider Configuration](#llm-provider-configuration)
6. [Custom Tools (MCP)](#custom-tools-mcp)
7. [Event Subscriptions](#event-subscriptions)
8. [Best Practices](#best-practices)
9. [Testing Agents](#testing-agents)
10. [Examples](#examples)

---

## Introduction

### What is an Agent?

In this platform, an **agent** is an AI-powered autonomous entity that:
- Processes tasks based on natural language prompts
- Uses Large Language Models (LLMs) for reasoning and generation
- Can access custom tools and external APIs
- Communicates via event-driven messages
- Operates in one of four execution modes

### How Agents Work

```
1. Agent Configuration (YAML file)
   ↓
2. Auto-Discovery by ConfigurationService
   ↓
3. Registration with AgentOrchestrator
   ↓
4. Routing to Appropriate Pool
   ↓
5. Task Execution with LLM
   ↓
6. Result Publishing via EventBus
```

### Zero-Code Agent Creation

**Key Principle**: You create agents by writing YAML configuration files. No Python coding required!

```yaml
# config/agents/my-agent.yml
name: my-agent
execution_mode: autonomous
llm_config:
  provider: openai
  model: gpt-4
system_prompt: "You are a helpful assistant."
```

Save this file, and the platform automatically discovers and deploys your agent!

---

## Agent Basics

### Directory Structure

```
config/
└── agents/
    ├── my-agent.yml          # Your agent configuration
    ├── another-agent.yml     # Another agent
    └── team-lead.yml         # Yet another agent
```

**Rules**:
- One YAML file per agent
- File name can be anything (conventionally matches agent name)
- Must be valid YAML syntax
- ConfigurationService watches this directory for changes

### Minimal Agent Configuration

```yaml
name: simple-assistant
agent_type: assistant
execution_mode: autonomous
description: "A simple AI assistant"

llm_config:
  provider: openai
  model: gpt-3.5-turbo
  temperature: 0.7

system_prompt: |
  You are a helpful AI assistant.
  Answer questions clearly and concisely.

tags:
  - general
  - qa
```

**Required Fields**:
- `name`: Unique identifier for the agent
- `execution_mode`: How the agent executes (see [Execution Modes](#execution-modes))
- `llm_config`: LLM provider and model settings
- `system_prompt`: Instructions for the AI

**Optional Fields**:
- `agent_type`: Categorization (e.g., "assistant", "analyst", "reporter")
- `description`: Human-readable description
- `tags`: Labels for searching and filtering
- `event_subscriptions`: Events this agent listens to
- `tools`: Custom tool integrations
- `*_config`: Mode-specific configurations

### Agent Lifecycle

1. **Creation**: Write YAML file in `config/agents/`
2. **Discovery**: ConfigurationService detects new file
3. **Loading**: Configuration parsed and validated
4. **Registration**: AgentOrchestrator registers the agent
5. **Active**: Agent ready to receive tasks
6. **Execution**: Processes tasks based on execution mode
7. **Update**: Modify YAML file (hot-reload)
8. **Deletion**: Remove YAML file to unregister

---

## Execution Modes

The platform supports four execution modes, each with different characteristics:

### 1. Autonomous Mode

**Use Case**: Independent, stateless task execution

**Characteristics**:
- ✅ Isolated execution (no state sharing between tasks)
- ✅ Round-robin load balancing across instances
- ✅ Automatic retry on failure (up to 2 retries)
- ✅ Horizontally scalable
- ❌ No conversation history
- ❌ No memory between tasks

**Best For**:
- Data analysis
- One-off computations
- API calls
- Document processing
- Batch jobs

**Example**:
```yaml
name: data-analyzer
execution_mode: autonomous

llm_config:
  provider: anthropic
  model: claude-3-sonnet-20240229
  temperature: 0.3

system_prompt: |
  You are a data analysis expert.
  Analyze provided datasets and generate insights.

retry_config:
  max_retries: 3
  retry_delay_seconds: 5
  exponential_backoff: true

event_subscriptions:
  - "data.analysis.requested"
  - "autonomous.task.submitted"
```

**Invocation**:
```bash
curl -X POST http://localhost:8003/agents/data-analyzer/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "task_data": {
      "prompt": "Analyze this dataset: [data]"
    }
  }'
```

---

### 2. Continuous Mode

**Use Case**: Long-running agents with persistent state

**Characteristics**:
- ✅ Persistent conversation history
- ✅ Memory across interactions
- ✅ Dedicated message queue per agent
- ✅ Crash recovery with state restoration
- ✅ Idle timeout optimization
- ❌ Not horizontally scalable (stateful)

**Best For**:
- Customer support chatbots
- Personal assistants
- Long-running conversations
- Context-dependent interactions
- Learning from interactions

**Example**:
```yaml
name: customer-support
execution_mode: continuous

llm_config:
  provider: openai
  model: gpt-4
  temperature: 0.7

system_prompt: |
  You are a customer support agent.
  Maintain context across conversations.
  Be helpful, professional, and empathetic.

continuous_config:
  # Agent considered idle after 15 minutes
  idle_timeout_seconds: 900

  # Save state every 3 minutes
  save_interval_seconds: 180

  # Keep last 100 conversation turns
  max_conversation_history: 100

event_subscriptions:
  - "slack.command.support"
  - "customer.ticket.created"
```

**Invocation** (via event):
```python
# Published to EventBus
event = {
    "type": "customer.ticket.created",
    "payload": {
        "ticket_id": "TKT-123",
        "prompt": "I need help with my account"
    }
}
```

**State Management**:
```python
# Automatic state saving includes:
{
    "conversation_history": [
        {"role": "user", "content": "Hello", "timestamp": "..."},
        {"role": "assistant", "content": "Hi! How can I help?", "timestamp": "..."}
    ],
    "memory": {
        "customer_id": "CUST-456",
        "previous_issues": ["login", "billing"]
    },
    "event_count": 42
}
```

---

### 3. Collaborative Mode

**Use Case**: Multiple agents working together on complex tasks

**Characteristics**:
- ✅ Multi-agent planning and coordination
- ✅ Shared state via PlanRunState
- ✅ Human-in-the-loop clarifications
- ✅ Step-by-step execution with dependencies
- ✅ Agent specialization and role assignment
- ❌ Higher latency (planning overhead)

**Best For**:
- Complex research tasks
- Multi-step analysis
- Decision-making with multiple perspectives
- Tasks requiring specialized expertise
- Coordinated workflows

**Example**:
```yaml
name: research-team
execution_mode: collaborative

llm_config:
  provider: openai
  model: gpt-4
  temperature: 0.5

system_prompt: |
  You are part of a collaborative research team.
  Work with other agents to solve complex problems.
  Communicate clearly and build on others' findings.

collaborative_config:
  # Other agents to collaborate with
  preferred_collaborators:
    - data-analyzer
    - content-writer
    - fact-checker

  # Planning configuration
  planning_agent:
    model: gpt-4
    temperature: 0.3

  # Maximum steps in execution plan
  max_plan_steps: 10

  # Allow human clarification requests
  allow_human_clarification: true
  clarification_timeout_seconds: 300

event_subscriptions:
  - "collaborative.task.submitted"
  - "research.request.complex"
```

**Invocation**:
```bash
curl -X POST http://localhost:8003/agents/research-team/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "task_data": {
      "prompt": "Research the impact of AI on healthcare and write a comprehensive report"
    }
  }'
```

**Planning Flow**:
```
1. Task received
2. Planning agent creates execution plan:
   - Step 1: data-analyzer finds relevant studies
   - Step 2: research-team synthesizes findings
   - Step 3: content-writer formats report
   - Step 4: fact-checker verifies claims
3. Each step executed by assigned agent
4. Results aggregated into final output
```

---

### 4. Scheduled Mode

**Use Case**: Time-based automated task execution

**Characteristics**:
- ✅ Cron-based or interval-based scheduling
- ✅ Automated execution (no manual trigger)
- ✅ Configurable timeouts
- ✅ Task data templating
- ✅ Integration with Celery Beat
- ❌ Not real-time (scheduled)

**Best For**:
- Daily/weekly reports
- Periodic health checks
- Scheduled data collection
- Automated maintenance tasks
- Time-based alerts

**Example (Cron)**:
```yaml
name: daily-reporter
execution_mode: scheduled

llm_config:
  provider: openai
  model: gpt-3.5-turbo
  temperature: 0.4

system_prompt: |
  You are an automated reporting agent.
  Generate daily summaries of system metrics.

schedule_config:
  type: cron

  # Run daily at 9:00 AM UTC
  # Format: minute hour day month day_of_week
  cron: "0 9 * * *"

  timezone: UTC

  # Data passed to agent on each execution
  task_data:
    report_type: daily
    include_sections:
      - system_health
      - user_activity
      - performance_metrics

  # Timeout for execution
  timeout_seconds: 600

event_subscriptions:
  - "scheduled.task.daily-report"
  - "report.generate.manual"  # Allow manual triggering
```

**Example (Interval)**:
```yaml
name: health-monitor
execution_mode: scheduled

llm_config:
  provider: anthropic
  model: claude-3-haiku-20240307
  temperature: 0.2

system_prompt: |
  You are a system health monitor.
  Check system status and alert on anomalies.

schedule_config:
  type: interval

  # Run every 5 minutes (300 seconds)
  interval_seconds: 300

  task_data:
    checks:
      - database_health
      - cache_health
      - queue_depth

  timeout_seconds: 120

event_subscriptions:
  - "scheduled.task.health-check"
```

**Manual Trigger**:
```bash
# Manually trigger scheduled task
curl -X POST http://localhost:8004/schedules/daily-reporter/trigger
```

---

## Agent Configuration

### Complete Configuration Reference

```yaml
# ============================================
# Basic Information
# ============================================

name: my-agent
# Required. Unique identifier.
# Must be alphanumeric with hyphens/underscores.
# Example: "customer-support", "data_analyzer_v2"

agent_type: assistant
# Optional. Category for organization.
# Common values: "assistant", "analyst", "reporter", "monitor"

execution_mode: autonomous
# Required. How the agent executes.
# Values: "autonomous", "continuous", "collaborative", "scheduled"

description: "A helpful AI assistant for customer inquiries"
# Optional. Human-readable description.

# ============================================
# LLM Configuration
# ============================================

llm_config:
  provider: openai
  # Required. LLM provider to use.
  # Values: "openai", "anthropic", "bedrock", "ollama"

  model: gpt-4
  # Required. Model identifier.
  # Provider-specific (see LLM Provider Configuration)

  temperature: 0.7
  # Optional. Randomness in responses (0.0-1.0).
  # Lower = more deterministic, Higher = more creative

  max_tokens: 2000
  # Optional. Maximum response length.
  # Provider-specific limits apply.

  top_p: 0.9
  # Optional. Nucleus sampling parameter.

  frequency_penalty: 0.0
  # Optional. Penalize repetition (OpenAI only).

  presence_penalty: 0.0
  # Optional. Encourage topic diversity (OpenAI only).

# ============================================
# System Prompt
# ============================================

system_prompt: |
  You are a helpful AI assistant.

  Your responsibilities:
  - Answer questions accurately
  - Be concise and clear
  - Admit when you don't know

  Always maintain a professional tone.
# Required. Instructions for the AI.
# Use | for multi-line strings.
# Be specific about behavior, tone, and constraints.

# ============================================
# Categorization
# ============================================

tags:
  - customer-service
  - support
  - communication
# Optional. Labels for filtering and search.
# Useful for organizing large agent fleets.

# ============================================
# Event Subscriptions
# ============================================

event_subscriptions:
  - "slack.command.help"
  - "customer.ticket.*"
  - "support.request.#"
# Optional. Event patterns this agent listens to.
# Supports wildcards: * (single level), # (multiple levels)

# ============================================
# Custom Tools
# ============================================

tools:
  - name: knowledge_base
    type: mcp
    url: "https://kb.example.com/mcp"
    description: "Search company knowledge base"
    auth:
      type: bearer_token
      token: "${KB_API_TOKEN}"

  - name: ticket_system
    type: mcp
    url: "https://tickets.example.com/mcp"
    description: "Create and update support tickets"
# Optional. Custom tool integrations via MCP.
# See Custom Tools section for details.

# ============================================
# Mode-Specific Configurations
# ============================================

# For Autonomous Mode
retry_config:
  max_retries: 3
  retry_delay_seconds: 5
  exponential_backoff: true

# For Continuous Mode
continuous_config:
  idle_timeout_seconds: 900
  save_interval_seconds: 180
  max_conversation_history: 100

# For Collaborative Mode
collaborative_config:
  preferred_collaborators:
    - data-analyzer
    - content-writer
  planning_agent:
    model: gpt-4
    temperature: 0.3
  max_plan_steps: 10
  allow_human_clarification: true
  clarification_timeout_seconds: 300

# For Scheduled Mode
schedule_config:
  type: cron  # or "interval"
  cron: "0 9 * * *"
  timezone: UTC
  task_data:
    custom_field: value
  timeout_seconds: 600
```

### Configuration Validation

The platform automatically validates your configuration:

```bash
# Check if your YAML is valid
curl http://localhost:8002/configs/my-agent | jq

# Expected response includes validation status
{
  "name": "my-agent",
  "status": "valid",
  "validation_errors": []
}
```

**Common Validation Errors**:
1. **Missing required field**: Add the missing field
2. **Invalid execution_mode**: Use one of: autonomous, continuous, collaborative, scheduled
3. **Invalid provider**: Use one of: openai, anthropic, bedrock, ollama
4. **Invalid YAML syntax**: Check for indentation errors, use a YAML validator

---

## LLM Provider Configuration

### OpenAI

**Models Available**:
- `gpt-4`: Most capable, best for complex tasks
- `gpt-4-turbo`: Faster, cheaper than GPT-4
- `gpt-3.5-turbo`: Fast, cost-effective

**Configuration**:
```yaml
llm_config:
  provider: openai
  model: gpt-4
  temperature: 0.7
  max_tokens: 2000
  top_p: 1.0
  frequency_penalty: 0.0
  presence_penalty: 0.0
```

**Environment Setup**:
```bash
# In .env
OPENAI_API_KEY=sk-your-api-key-here
OPENAI_ORG_ID=org-your-org-id  # Optional
```

**Cost Optimization**:
- Use `gpt-3.5-turbo` for simple tasks
- Set lower `max_tokens` when possible
- Use `temperature: 0` for deterministic outputs

---

### Anthropic (Claude)

**Models Available**:
- `claude-3-opus-20240229`: Most capable
- `claude-3-sonnet-20240229`: Balanced
- `claude-3-haiku-20240307`: Fast and efficient

**Configuration**:
```yaml
llm_config:
  provider: anthropic
  model: claude-3-sonnet-20240229
  max_tokens: 4096
  temperature: 0.7
  top_p: 0.9
```

**Environment Setup**:
```bash
# In .env
ANTHROPIC_API_KEY=sk-ant-your-api-key-here
```

**Best Practices**:
- Claude has a larger context window (200k tokens)
- Excellent at following complex instructions
- Strong at analysis and reasoning tasks

---

### AWS Bedrock

**Models Available**:
- `anthropic.claude-3-sonnet-20240229-v1:0`: Claude via Bedrock
- `anthropic.claude-3-haiku-20240307-v1:0`: Claude Haiku
- `meta.llama2-70b-chat-v1`: Llama 2
- `amazon.titan-text-express-v1`: Titan Text

**Configuration**:
```yaml
llm_config:
  provider: bedrock
  model: anthropic.claude-3-sonnet-20240229-v1:0
  region: us-east-1
  max_tokens: 4096
  temperature: 0.7
```

**Environment Setup**:
```bash
# In .env
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=us-east-1
```

**Benefits**:
- Enterprise security and compliance
- VPC integration
- Lower latency in AWS regions
- Multiple model options

---

### Ollama (Local/Self-Hosted)

**Models Available** (must be pulled first):
- `llama2`: Meta's Llama 2
- `mistral`: Mistral 7B
- `codellama`: Code-specialized Llama
- `phi`: Microsoft Phi models

**Configuration**:
```yaml
llm_config:
  provider: ollama
  model: llama2
  host: http://localhost:11434
  temperature: 0.7
  num_predict: 2000
```

**Environment Setup**:
```bash
# Install Ollama
curl https://ollama.ai/install.sh | sh

# Pull a model
ollama pull llama2

# Start Ollama server
ollama serve

# In .env
OLLAMA_HOST=http://localhost:11434
```

**Benefits**:
- No API costs
- Full data privacy (on-premise)
- No rate limits
- Customizable models

**Limitations**:
- Requires local compute resources
- Generally less capable than GPT-4/Claude
- Slower inference

---

## Custom Tools (MCP)

### What are MCP Tools?

MCP (Model Context Protocol) allows agents to access external tools and APIs. Tools extend agent capabilities beyond text generation.

**Examples**:
- Database queries
- API calls
- File operations
- Web searches
- Custom business logic

### Tool Configuration

```yaml
tools:
  - name: weather_api
    type: mcp
    url: "https://api.weather.com/mcp"
    description: "Get current weather data"
    auth:
      type: bearer_token
      token: "${WEATHER_API_TOKEN}"

  - name: database_query
    type: mcp
    url: "https://db.example.com/mcp"
    description: "Query customer database"
    auth:
      type: api_key
      key: "${DB_API_KEY}"
      header: "X-API-Key"
```

### Authentication Types

**Bearer Token**:
```yaml
auth:
  type: bearer_token
  token: "${API_TOKEN}"
```

**API Key (Header)**:
```yaml
auth:
  type: api_key
  key: "${API_KEY}"
  header: "X-API-Key"
```

**Basic Auth**:
```yaml
auth:
  type: basic
  username: "${USERNAME}"
  password: "${PASSWORD}"
```

**OAuth 2.0**:
```yaml
auth:
  type: oauth2
  token_url: "https://auth.example.com/token"
  client_id: "${CLIENT_ID}"
  client_secret: "${CLIENT_SECRET}"
```

### Tool Discovery

When an agent starts, Portia AI SDK:
1. Fetches tool definitions from MCP URL
2. Parses available functions and parameters
3. Makes tools available to the agent
4. Agent can invoke tools during task execution

### Example MCP Server Response

```json
{
  "tools": [
    {
      "name": "search_knowledge_base",
      "description": "Search company knowledge base for articles",
      "parameters": {
        "query": {
          "type": "string",
          "description": "Search query"
        },
        "limit": {
          "type": "integer",
          "description": "Maximum results",
          "default": 10
        }
      }
    }
  ]
}
```

### Tool Usage by Agent

The LLM automatically determines when to use tools:

```
User: "What's our refund policy?"

Agent thinks:
  - I need to search the knowledge base
  - Use tool: search_knowledge_base(query="refund policy")

Tool returns: [Article: "30-day money-back guarantee..."]

Agent responds: "According to our policy, we offer a 30-day..."
```

---

## Event Subscriptions

### Event-Driven Architecture

Agents communicate via events published to RabbitMQ. Event subscriptions define which events an agent responds to.

### Subscription Patterns

**Exact Match**:
```yaml
event_subscriptions:
  - "customer.ticket.created"
```

**Single-Level Wildcard** (*):
```yaml
event_subscriptions:
  - "customer.ticket.*"
  # Matches: customer.ticket.created, customer.ticket.updated
  # Does NOT match: customer.ticket.comment.added
```

**Multi-Level Wildcard** (#):
```yaml
event_subscriptions:
  - "customer.#"
  # Matches: customer.ticket.created
  # Matches: customer.ticket.comment.added
  # Matches: customer.profile.updated
```

### Common Event Patterns

**Slack Events**:
```yaml
- "slack.command.*"         # All slash commands
- "slack.command.help"      # Specific command
- "slack.event.message"     # All messages
- "slack.interaction.*"     # Button clicks, menus
```

**Task Events**:
```yaml
- "autonomous.task.submitted"
- "collaborative.task.submitted"
- "task.*.completed"        # All completion events
```

**Custom Events**:
```yaml
- "customer.ticket.created"
- "payment.processed"
- "report.requested"
- "alert.triggered"
```

### Publishing Custom Events

From another service:
```python
from messaging.event_bus import EventBus, Event, EventType

event = Event(
    event_type=EventType.CUSTOM,
    payload={
        "prompt": "Process this data",
        "data": {...}
    },
    trace_id="abc-123"
)

event_bus.publish(
    event=event,
    routing_key="data.processing.requested"
)
```

Agents subscribed to `data.processing.requested` will receive this event.

---

## Best Practices

### System Prompt Design

**DO**:
```yaml
system_prompt: |
  You are a customer support specialist for Acme Corp.

  Your responsibilities:
  - Answer product questions accurately
  - Be empathetic and professional
  - Escalate to human if you cannot help

  Product information:
  - We sell widgets in 3 sizes: small, medium, large
  - Standard shipping takes 3-5 business days
  - Returns accepted within 30 days

  If a customer is angry:
  1. Acknowledge their frustration
  2. Apologize for the inconvenience
  3. Offer concrete solutions
```

**DON'T**:
```yaml
system_prompt: "You are helpful."
# Too vague, agent won't know what to do
```

### Choosing Execution Modes

**Use Autonomous when**:
- Each task is independent
- No state needed between tasks
- High throughput required
- Horizontal scaling needed

**Use Continuous when**:
- Conversation context important
- Learning from interactions
- Stateful workflows
- Customer support scenarios

**Use Collaborative when**:
- Task too complex for one agent
- Multiple expertise areas needed
- Step-by-step verification required
- Research and analysis tasks

**Use Scheduled when**:
- Recurring automated tasks
- Time-based triggers
- Periodic reports
- Maintenance jobs

### Naming Conventions

**Agent Names**:
- Use kebab-case: `customer-support`, `data-analyzer`
- Be descriptive: `daily-sales-reporter` not `reporter-1`
- Include version if needed: `chatbot-v2`

**Event Patterns**:
- Use dot notation: `domain.entity.action`
- Be specific: `customer.ticket.created`
- Consistent casing: lowercase

**Tags**:
- Lowercase: `customer-service`, `analytics`
- Singular form: `report` not `reports`
- Descriptive: `high-priority`, `billing`

### Security Considerations

**1. Sensitive Data**:
```yaml
# DON'T hardcode secrets
tools:
  - name: api
    auth:
      token: "hardcoded-secret"  # ❌ BAD

# DO use environment variables
tools:
  - name: api
    auth:
      token: "${API_SECRET}"  # ✅ GOOD
```

**2. System Prompts**:
```yaml
# DON'T expose internal details
system_prompt: |
  You can access our database at postgresql://admin:pass@db

# DO be general
system_prompt: |
  You have access to customer data via the database_query tool
```

**3. Input Validation**:
```yaml
system_prompt: |
  IMPORTANT: Never execute user-provided code.
  Always validate and sanitize inputs.
  If a request seems malicious, decline politely.
```

### Performance Tips

**1. Choose Appropriate Models**:
```yaml
# Fast, cheap tasks → GPT-3.5 or Claude Haiku
llm_config:
  provider: openai
  model: gpt-3.5-turbo

# Complex tasks → GPT-4 or Claude Opus
llm_config:
  provider: anthropic
  model: claude-3-opus-20240229
```

**2. Optimize Token Usage**:
```yaml
# Set reasonable max_tokens
llm_config:
  max_tokens: 500  # For short responses

# Use lower temperature for deterministic tasks
llm_config:
  temperature: 0.0  # Factual answers
```

**3. Continuous Agent Memory**:
```yaml
# Don't keep unlimited history
continuous_config:
  max_conversation_history: 50  # Keep last 50 turns
  save_interval_seconds: 300    # Save every 5 min
```

---

## Testing Agents

### 1. Validate Configuration

```bash
# Check if agent loaded successfully
curl http://localhost:8002/configs/my-agent | jq

# Verify agent registered
curl http://localhost:8003/agents | jq '.[] | select(.name=="my-agent")'
```

### 2. Test Invocation

```bash
# Invoke agent with test prompt
curl -X POST http://localhost:8003/agents/my-agent/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "task_data": {
      "prompt": "Hello, can you hear me?"
    }
  }' | jq
```

### 3. Monitor Logs

```bash
# Watch agent execution
docker-compose logs -f agent-orchestrator | grep "my-agent"

# Check for errors
docker-compose logs | grep "ERROR" | grep "my-agent"
```

### 4. Test Event Subscriptions

```python
# Publish test event
from messaging.event_bus import EventBus, Event

event = Event(
    event_type="CUSTOM",
    payload={"prompt": "Test message"}
)

event_bus.publish(
    event=event,
    routing_key="my.test.event"  # Must match subscription
)
```

### 5. Verify Tool Access

```bash
# Check tool configuration loaded
curl http://localhost:8002/configs/my-agent | jq '.tools'

# Test tool invocation (via agent)
curl -X POST http://localhost:8003/agents/my-agent/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "task_data": {
      "prompt": "Use the weather_api tool to get weather for NYC"
    }
  }'
```

---

## Examples

### Example 1: Simple Q&A Agent

```yaml
name: qa-bot
agent_type: assistant
execution_mode: autonomous
description: "Answers general knowledge questions"

llm_config:
  provider: openai
  model: gpt-3.5-turbo
  temperature: 0.7
  max_tokens: 500

system_prompt: |
  You are a knowledgeable assistant.
  Answer questions accurately and concisely.
  If you don't know, say "I don't know."

tags:
  - qa
  - general

event_subscriptions:
  - "slack.command.ask"
```

### Example 2: Data Analysis Agent with Tools

```yaml
name: sales-analyst
agent_type: analyst
execution_mode: autonomous
description: "Analyzes sales data and generates insights"

llm_config:
  provider: anthropic
  model: claude-3-sonnet-20240229
  temperature: 0.3
  max_tokens: 3000

system_prompt: |
  You are a sales data analyst.

  When analyzing data:
  1. Use the sales_database tool to query data
  2. Calculate key metrics (revenue, growth, trends)
  3. Provide actionable insights
  4. Include visualizations when helpful

tags:
  - analytics
  - sales
  - business-intelligence

event_subscriptions:
  - "sales.analysis.requested"
  - "report.sales.weekly"

tools:
  - name: sales_database
    type: mcp
    url: "https://db.example.com/mcp/sales"
    description: "Query sales database"
    auth:
      type: bearer_token
      token: "${SALES_DB_TOKEN}"

  - name: chart_generator
    type: mcp
    url: "https://viz.example.com/mcp"
    description: "Generate charts and graphs"
```

### Example 3: Conversational Support Agent

```yaml
name: support-chat
agent_type: support_agent
execution_mode: continuous
description: "Conversational customer support with context"

llm_config:
  provider: openai
  model: gpt-4
  temperature: 0.7
  max_tokens: 1000

system_prompt: |
  You are Sarah, a friendly customer support agent for TechCorp.

  Guidelines:
  - Greet customers warmly
  - Remember context from earlier in the conversation
  - Use the knowledge_base tool to find accurate answers
  - Create tickets for issues you cannot resolve
  - End conversations politely

  Common issues:
  - Login problems: Check account status, reset password
  - Billing questions: Use billing tool to check invoices
  - Technical support: Create ticket for engineering team

tags:
  - customer-support
  - conversational
  - help-desk

continuous_config:
  idle_timeout_seconds: 1800  # 30 minutes
  save_interval_seconds: 180  # 3 minutes
  max_conversation_history: 100

event_subscriptions:
  - "slack.event.message"
  - "support.chat.started"

tools:
  - name: knowledge_base
    type: mcp
    url: "https://kb.techcorp.com/mcp"
    description: "Search support articles"

  - name: ticket_system
    type: mcp
    url: "https://tickets.techcorp.com/mcp"
    description: "Create and update support tickets"

  - name: billing_system
    type: mcp
    url: "https://billing.techcorp.com/mcp"
    description: "Query billing and invoices"
```

### Example 4: Collaborative Research Team

```yaml
name: research-coordinator
agent_type: researcher
execution_mode: collaborative
description: "Coordinates multiple agents for complex research"

llm_config:
  provider: openai
  model: gpt-4
  temperature: 0.5
  max_tokens: 4000

system_prompt: |
  You coordinate research tasks across multiple specialized agents.

  Your role:
  - Break down complex research questions
  - Assign sub-tasks to appropriate agents
  - Synthesize findings from all agents
  - Ensure research quality and accuracy

  Available specialist agents:
  - data-analyst: Quantitative analysis
  - literature-reviewer: Academic research
  - fact-checker: Verification
  - report-writer: Documentation

tags:
  - research
  - coordination
  - analysis

collaborative_config:
  preferred_collaborators:
    - data-analyst
    - literature-reviewer
    - fact-checker
    - report-writer

  planning_agent:
    model: gpt-4
    temperature: 0.3

  max_plan_steps: 15
  allow_human_clarification: true
  clarification_timeout_seconds: 600

event_subscriptions:
  - "research.complex.requested"
  - "collaborative.task.submitted"

tools:
  - name: academic_search
    type: mcp
    url: "https://scholar.example.com/mcp"
    description: "Search academic papers and journals"

  - name: web_search
    type: mcp
    url: "https://search.example.com/mcp"
    description: "General web search"
```

### Example 5: Daily Report Generator

```yaml
name: daily-metrics-report
agent_type: reporter
execution_mode: scheduled
description: "Generates automated daily metrics report"

llm_config:
  provider: anthropic
  model: claude-3-haiku-20240307
  temperature: 0.3
  max_tokens: 2000

system_prompt: |
  You generate daily metrics reports.

  Report structure:
  1. Executive Summary (2-3 sentences)
  2. Key Metrics (compare to yesterday and last week)
  3. Notable Events
  4. Recommendations

  Be concise, data-driven, and actionable.

tags:
  - reporting
  - automation
  - metrics

schedule_config:
  type: cron
  cron: "0 8 * * 1-5"  # 8 AM, Monday-Friday
  timezone: America/New_York

  task_data:
    report_type: daily_metrics
    metrics:
      - active_users
      - revenue
      - error_rate
      - response_time
    recipients:
      - ops@example.com
      - management@example.com

  timeout_seconds: 300

event_subscriptions:
  - "scheduled.task.daily-metrics-report"
  - "report.metrics.manual"

tools:
  - name: metrics_api
    type: mcp
    url: "https://metrics.example.com/mcp"
    description: "Fetch system metrics"

  - name: email_service
    type: mcp
    url: "https://mail.example.com/mcp"
    description: "Send email reports"
```

---

## Troubleshooting

### Agent Not Found

**Problem**: `curl http://localhost:8003/agents` doesn't show your agent

**Solutions**:
1. Check YAML file exists in `config/agents/`
2. Validate YAML syntax
3. Check ConfigService logs: `docker-compose logs config-service`
4. Restart ConfigService: `docker-compose restart config-service`

### Agent Not Responding

**Problem**: Agent receives events but doesn't execute

**Solutions**:
1. Check event subscription patterns match
2. Verify agent pool is running: `docker-compose ps`
3. Check logs for errors: `docker-compose logs | grep my-agent`
4. Test direct invocation via API

### LLM Errors

**Problem**: "Invalid API key" or "Rate limit exceeded"

**Solutions**:
1. Verify `.env` has correct API key
2. Check API key is active in provider dashboard
3. Verify sufficient API credits
4. Check rate limits and usage

### Tool Errors

**Problem**: "Tool not available" or "MCP server unreachable"

**Solutions**:
1. Verify MCP server URL is correct and accessible
2. Check authentication credentials
3. Test MCP endpoint directly: `curl https://tool.example.com/mcp`
4. Check tool configuration in YAML

---

## Next Steps

1. **Create Your First Agent**: Start with a simple autonomous agent
2. **Test Thoroughly**: Use the testing section to validate
3. **Iterate**: Refine system prompt and configuration based on results
4. **Scale**: Add more agents as you identify needs
5. **Monitor**: Watch logs and metrics to optimize performance

---

**Document Version**: 1.0
**Last Updated**: 2025-01-18
**Next Review**: 2025-02-18

**Additional Resources**:
- [Operations Guide](./OPERATIONS_GUIDE.md) - Platform deployment and maintenance
- [API Reference](./API_REFERENCE.md) - Complete API documentation
- [Architecture Overview](./01-blueprint.md) - Platform architecture details
