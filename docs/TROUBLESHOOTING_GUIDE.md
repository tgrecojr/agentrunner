# Troubleshooting Guide
**Multi-Agent Orchestration Platform**

Comprehensive troubleshooting guide for common issues, debugging techniques, and resolution steps.

---

## Table of Contents

1. [Quick Diagnosis](#quick-diagnosis)
2. [Service Health Checks](#service-health-checks)
3. [Common Issues](#common-issues)
4. [Component-Specific Issues](#component-specific-issues)
5. [Performance Issues](#performance-issues)
6. [Debugging Techniques](#debugging-techniques)
7. [Log Analysis](#log-analysis)
8. [Recovery Procedures](#recovery-procedures)

---

## Quick Diagnosis

### Health Check Script

Run this script to quickly diagnose system health:

```bash
#!/bin/bash
# health_check.sh

echo "=== Platform Health Check ==="

# Check all services
services=(
    "postgres:5432"
    "redis:6379"
    "rabbitmq:5672"
    "state-manager:8001"
    "config-service:8002"
    "agent-orchestrator:8003"
    "scheduler-service:8004"
    "slack-gateway:8005"
)

for service in "${services[@]}"; do
    IFS=':' read -r name port <<< "$service"
    if nc -z localhost $port 2>/dev/null; then
        echo "✓ $name is running on port $port"
    else
        echo "✗ $name is NOT reachable on port $port"
    fi
done

# Check API health endpoints
echo ""
echo "=== API Health Endpoints ==="
for port in 8001 8002 8003 8004 8005; do
    response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:$port/health/live 2>/dev/null)
    if [ "$response" = "200" ]; then
        echo "✓ Service on port $port is healthy"
    else
        echo "✗ Service on port $port returned $response"
    fi
done

# Check Docker containers
echo ""
echo "=== Docker Containers ==="
docker-compose ps
```

**Usage**:
```bash
chmod +x health_check.sh
./health_check.sh
```

---

## Service Health Checks

### StateManager (Port 8001)

```bash
# Liveness probe
curl http://localhost:8001/health/live

# Readiness probe
curl http://localhost:8001/health/ready

# Detailed health with metrics
curl http://localhost:8001/health | jq
```

**Expected Response**:
```json
{
  "status": "healthy",
  "timestamp": "2025-11-18T10:30:00Z",
  "checks": {
    "database": "ok",
    "cache": "ok"
  },
  "metrics": {
    "active_agents": 5,
    "cache_hit_rate": 0.92
  }
}
```

### ConfigurationService (Port 8002)

```bash
# Health check
curl http://localhost:8002/health/live

# List loaded configurations
curl http://localhost:8002/configs | jq '.[] | .name'

# Check specific agent config
curl http://localhost:8002/configs/agent-name | jq
```

### AgentOrchestrator (Port 8003)

```bash
# Health check
curl http://localhost:8003/health/live

# List registered agents
curl http://localhost:8003/agents | jq

# Check agent status
curl http://localhost:8003/agents/agent-name/status | jq
```

### SchedulerService (Port 8004)

```bash
# Health check
curl http://localhost:8004/health/live

# List schedules
curl http://localhost:8004/schedules | jq

# Check Celery workers
docker-compose exec scheduler-service celery -A src.scheduler.scheduler_service:scheduler_service.celery_app inspect active
```

### SlackGateway (Port 8005)

```bash
# Health check
curl http://localhost:8005/health/live

# Test message sending (requires valid token)
curl -X POST http://localhost:8005/slack/send-message \
  -H "Content-Type: application/json" \
  -d '{"channel": "#test", "text": "Hello from API"}'
```

---

## Common Issues

### Issue 1: Service Won't Start

**Symptoms**:
- Container exits immediately after starting
- Health check endpoint not responding
- Connection refused errors

**Diagnosis**:
```bash
# Check container logs
docker-compose logs [service-name]

# Check container status
docker-compose ps

# Check port conflicts
lsof -i :[port]

# Check environment variables
docker-compose config | grep -A 10 [service-name]
```

**Common Causes & Solutions**:

#### Missing Environment Variables
```bash
# Symptom: Service crashes with "KeyError" or "NoneType"
# Solution: Check .env file
cat .env | grep REQUIRED_VAR

# Copy from template if missing
cp .env.example .env
nano .env  # Fill in required values
```

#### Port Already in Use
```bash
# Symptom: "address already in use"
# Solution: Find and kill process using port
lsof -i :8001
kill -9 [PID]

# Or change port in docker-compose.yml
```

#### Database Migration Needed
```bash
# Symptom: "table does not exist"
# Solution: Run migrations
docker-compose exec state-manager alembic upgrade head
```

### Issue 2: Database Connection Failures

**Symptoms**:
- "connection refused" errors
- "authentication failed" errors
- Services waiting for database indefinitely

**Diagnosis**:
```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Check PostgreSQL logs
docker-compose logs postgres

# Test connection manually
docker-compose exec postgres psql -U agentrunner -d agentrunner -c "SELECT 1;"

# Verify credentials
echo $POSTGRES_USER
echo $POSTGRES_PASSWORD
```

**Solutions**:

#### PostgreSQL Not Ready
```bash
# Wait for PostgreSQL to initialize (first startup)
docker-compose logs -f postgres | grep "database system is ready"

# Or use wait-for script
./scripts/wait-for-postgres.sh
```

#### Wrong Credentials
```bash
# Check .env file
cat .env | grep POSTGRES

# Reset PostgreSQL password
docker-compose down
docker volume rm agentrunner_postgres-data
docker-compose up -d postgres
```

#### Connection Pool Exhausted
```bash
# Check active connections
docker-compose exec postgres psql -U agentrunner -c \
  "SELECT count(*) FROM pg_stat_activity;"

# Increase pool size in .env
POSTGRES_MAX_POOL_SIZE=50

# Restart services
docker-compose restart
```

### Issue 3: Redis Connection Issues

**Symptoms**:
- Cache operations failing
- "READONLY" errors
- Connection timeouts

**Diagnosis**:
```bash
# Check Redis is running
docker-compose ps redis

# Test Redis connection
docker-compose exec redis redis-cli ping

# Check Redis info
docker-compose exec redis redis-cli info

# Monitor Redis commands
docker-compose exec redis redis-cli monitor
```

**Solutions**:

#### Redis Not Responding
```bash
# Restart Redis
docker-compose restart redis

# Check Redis logs
docker-compose logs redis

# Verify Redis config
docker-compose exec redis redis-cli CONFIG GET maxmemory
```

#### Memory Full (Eviction)
```bash
# Check memory usage
docker-compose exec redis redis-cli info memory

# Clear cache if needed
docker-compose exec redis redis-cli FLUSHDB

# Increase maxmemory in docker-compose.yml
command: redis-server --maxmemory 2gb --maxmemory-policy allkeys-lru
```

### Issue 4: RabbitMQ Connection/Queue Issues

**Symptoms**:
- Events not being delivered
- Queue buildup
- Consumer not receiving messages
- "connection refused" errors

**Diagnosis**:
```bash
# Check RabbitMQ is running
docker-compose ps rabbitmq

# Access RabbitMQ Management UI
open http://localhost:15672
# Login: guest/guest

# Check queues via CLI
docker-compose exec rabbitmq rabbitmqctl list_queues name messages consumers

# Check exchanges
docker-compose exec rabbitmq rabbitmqctl list_exchanges name type

# Check bindings
docker-compose exec rabbitmq rabbitmqctl list_bindings
```

**Solutions**:

#### Queue Buildup
```bash
# Check queue depth
docker-compose exec rabbitmq rabbitmqctl list_queues name messages

# Purge queue if needed
docker-compose exec rabbitmq rabbitmqctl purge_queue [queue_name]

# Increase consumer count
docker-compose up -d --scale autonomous-agent-pool=3
```

#### Connection Refused
```bash
# Wait for RabbitMQ to fully start
docker-compose logs rabbitmq | grep "Server startup complete"

# Check credentials
echo $RABBITMQ_USER
echo $RABBITMQ_PASSWORD

# Verify AMQP URL
echo $RABBITMQ_URL
```

#### Dead Letter Queue Issues
```bash
# Check DLQ depth
curl -u guest:guest http://localhost:15672/api/queues/%2F/[queue_name].dlq

# Inspect DLQ messages
docker-compose exec rabbitmq rabbitmqadmin get queue=[queue_name].dlq requeue=false

# Requeue messages from DLQ
# Manual intervention required - see docs/OPERATIONS_GUIDE.md
```

### Issue 5: Agent Not Responding

**Symptoms**:
- Tasks submitted but not executed
- Agent shows as "unresponsive"
- No logs from agent

**Diagnosis**:
```bash
# Check agent registration
curl http://localhost:8003/agents | jq '.[] | select(.name == "agent-name")'

# Check agent health
curl http://localhost:8003/agents/agent-name/status | jq

# Check agent logs
docker-compose logs -f [agent-pool-service]

# Check agent queue
curl -u guest:guest http://localhost:15672/api/queues/%2F/agent.agent-name.events
```

**Solutions**:

#### Agent Not Registered
```bash
# Check agent config exists
ls -la config/agents/agent-name.yml

# Validate agent config
python -c "
import yaml
with open('config/agents/agent-name.yml') as f:
    config = yaml.safe_load(f)
    print(f'Loaded config for: {config[\"name\"]}')"

# Restart ConfigurationService to reload
docker-compose restart config-service
```

#### Agent Execution Failing
```bash
# Check LLM API credentials
echo $OPENAI_API_KEY

# Test LLM provider directly
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"

# Check agent error logs
docker-compose logs [pool-service] 2>&1 | grep -i error
```

#### Wrong Execution Mode Routing
```bash
# Verify execution mode in config
cat config/agents/agent-name.yml | grep execution_mode

# Check routing key subscription
curl -u guest:guest http://localhost:15672/api/bindings | \
  jq '.[] | select(.source == "agent.exchange")'
```

### Issue 6: LLM API Errors

**Symptoms**:
- "401 Unauthorized" errors
- "429 Rate Limit" errors
- "500 Internal Server Error" from LLM

**Diagnosis**:
```bash
# Check API key is set
echo $OPENAI_API_KEY
echo $ANTHROPIC_API_KEY

# Test API key validity
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"

# Check rate limit headers
curl -I https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"

# Check agent logs for LLM errors
docker-compose logs [pool-service] 2>&1 | grep -i "llm\|api"
```

**Solutions**:

#### Invalid API Key
```bash
# Verify API key format
# OpenAI: sk-...
# Anthropic: sk-ant-...

# Update .env file
nano .env

# Restart services to pick up new key
docker-compose restart
```

#### Rate Limiting
```bash
# Reduce concurrent requests
# In docker-compose.yml, reduce replicas:
docker-compose up -d --scale autonomous-agent-pool=1

# Add retry logic (already built-in)
# Check retry config in agent YAML:
retry_config:
  max_retries: 3
  retry_delay_seconds: 5
  exponential_backoff: true
```

#### Model Not Available
```bash
# Check model name in agent config
cat config/agents/agent-name.yml | grep model

# Update to available model
nano config/agents/agent-name.yml
# Change: model: gpt-4-turbo-preview

# Verify model availability
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY" | \
  jq '.data[] | .id'
```

---

## Component-Specific Issues

### StateManager Issues

#### State Not Persisting

**Symptoms**: Agent state lost after restart

**Diagnosis**:
```bash
# Check database has records
docker-compose exec postgres psql -U agentrunner -c \
  "SELECT agent_name, updated_at FROM agent_state;"

# Check state save interval
cat config/agents/agent-name.yml | grep save_interval_seconds
```

**Solution**:
```bash
# Ensure auto-save is enabled
nano config/agents/agent-name.yml

continuous_config:
  save_interval_seconds: 180
  auto_save_on_shutdown: true

# Restart agent
docker-compose restart continuous-agent-runner
```

#### Cache Miss Rate High

**Symptoms**: Slow response times, high database load

**Diagnosis**:
```bash
# Check cache hit rate
curl http://localhost:8001/health | jq '.metrics.cache_hit_rate'

# Monitor Redis keys
docker-compose exec redis redis-cli KEYS "state:*" | wc -l
```

**Solution**:
```bash
# Increase cache TTL
nano .env
REDIS_STATE_TTL=3600

# Increase Redis memory
docker-compose.yml:
  redis:
    command: redis-server --maxmemory 4gb

docker-compose up -d redis
```

### ConfigurationService Issues

#### Hot-Reload Not Working

**Symptoms**: Config changes not detected

**Diagnosis**:
```bash
# Check watchdog is enabled
cat .env | grep CONFIG_HOT_RELOAD

# Check ConfigurationService logs
docker-compose logs config-service | grep -i watch
```

**Solution**:
```bash
# Enable hot-reload
nano .env
CONFIG_HOT_RELOAD=true

# Restart config service
docker-compose restart config-service

# Manually trigger reload via API
curl -X POST http://localhost:8002/reload
```

#### Invalid Agent Configuration

**Symptoms**: Agent not loading, validation errors

**Diagnosis**:
```bash
# Validate YAML syntax
yamllint config/agents/agent-name.yml

# Check for required fields
python -c "
import yaml
with open('config/agents/agent-name.yml') as f:
    config = yaml.safe_load(f)
    required = ['name', 'execution_mode', 'llm_config', 'system_prompt']
    for field in required:
        if field not in config:
            print(f'Missing required field: {field}')"
```

**Solution**:
```bash
# Fix YAML syntax
nano config/agents/agent-name.yml

# Use validation script
python scripts/validate_agent_config.py config/agents/agent-name.yml

# Check logs for detailed error
docker-compose logs config-service | grep -i error
```

### AgentOrchestrator Issues

#### Task Routing Failures

**Symptoms**: Tasks not reaching agent pools

**Diagnosis**:
```bash
# Check routing configuration
curl http://localhost:8003/agents | jq '.[] | {name, execution_mode}'

# Check EventBus bindings
curl -u guest:guest http://localhost:15672/api/bindings | \
  jq '.[] | select(.source == "agent.exchange")'

# Monitor task submissions
docker-compose logs -f agent-orchestrator | grep "task.submitted"
```

**Solution**:
```bash
# Verify execution mode matches pool
cat config/agents/agent-name.yml | grep execution_mode

# Check pool is running
docker-compose ps | grep pool

# Restart orchestrator
docker-compose restart agent-orchestrator
```

### SchedulerService Issues

#### Scheduled Tasks Not Running

**Symptoms**: Cron/interval tasks not executing

**Diagnosis**:
```bash
# Check schedule is registered
curl http://localhost:8004/schedules | jq

# Check Celery beat is running
docker-compose exec scheduler-service ps aux | grep "celery.*beat"

# Check Celery worker is active
docker-compose exec scheduler-service celery -A src.scheduler.scheduler_service:scheduler_service.celery_app inspect active

# Check schedule logs
docker-compose logs scheduler-service | grep -i schedule
```

**Solution**:
```bash
# Verify cron expression
python -c "
from croniter import croniter
from datetime import datetime
cron = '0 9 * * *'
print(f'Next run: {croniter(cron, datetime.now()).get_next(datetime)}')"

# Check schedule is enabled
curl http://localhost:8004/schedules/schedule-name | jq '.enabled'

# Manually trigger task
curl -X POST http://localhost:8004/schedules/schedule-name/trigger

# Restart scheduler
docker-compose restart scheduler-service
```

### SlackGateway Issues

#### Webhook Signature Verification Failing

**Symptoms**: "Invalid signature" errors

**Diagnosis**:
```bash
# Check signing secret is set
echo $SLACK_SIGNING_SECRET

# Check gateway logs
docker-compose logs slack-gateway | grep -i signature

# Verify Slack app configuration
# Go to: https://api.slack.com/apps -> Your App -> Basic Information
```

**Solution**:
```bash
# Update signing secret in .env
nano .env
SLACK_SIGNING_SECRET=your-signing-secret

# Restart gateway
docker-compose restart slack-gateway

# Disable verification for testing (NOT production)
nano .env
SLACK_VERIFY_SIGNATURE=false
```

#### Events Not Reaching Agents

**Symptoms**: Slack messages not triggering agents

**Diagnosis**:
```bash
# Check event subscriptions in agent config
cat config/agents/agent-name.yml | grep -A 5 event_subscriptions

# Check SlackGateway is publishing events
docker-compose logs slack-gateway | grep "publish"

# Check RabbitMQ routing
curl -u guest:guest http://localhost:15672/api/exchanges/%2F/agent.exchange/bindings/source
```

**Solution**:
```bash
# Add event subscription to agent
nano config/agents/agent-name.yml

event_subscriptions:
  - "slack.command.*"
  - "slack.event.message"

# Restart to reload config
docker-compose restart config-service agent-orchestrator
```

---

## Performance Issues

### High CPU Usage

**Diagnosis**:
```bash
# Check container CPU usage
docker stats

# Check process CPU usage
docker-compose exec [service] top
```

**Solutions**:
```bash
# Reduce worker concurrency
nano .env
WORKER_PROCESSES=2
CELERY_WORKER_CONCURRENCY=2

# Scale down agent pools
docker-compose up -d --scale autonomous-agent-pool=1

# Enable request throttling
nano .env
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=30
```

### High Memory Usage

**Diagnosis**:
```bash
# Check container memory
docker stats

# Check memory leaks
docker-compose exec [service] ps aux --sort=-rss
```

**Solutions**:
```bash
# Reduce conversation history
nano config/agents/agent-name.yml

continuous_config:
  max_conversation_history: 50  # Reduce from 100

# Enable state compression
nano .env
STATE_COMPRESSION_ENABLED=true
STATE_COMPRESSION_THRESHOLD=512

# Restart workers periodically
nano .env
CELERY_WORKER_MAX_TASKS_PER_CHILD=50  # Reduce from 100
```

### Slow Response Times

**Diagnosis**:
```bash
# Check cache hit rate
curl http://localhost:8001/health | jq '.metrics.cache_hit_rate'

# Check database query performance
docker-compose exec postgres psql -U agentrunner -c \
  "SELECT query, mean_exec_time FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;"

# Check RabbitMQ queue depths
docker-compose exec rabbitmq rabbitmqctl list_queues name messages
```

**Solutions**:
```bash
# Increase cache TTL
nano .env
REDIS_STATE_TTL=3600
REDIS_CONFIG_TTL=7200

# Add database indexes
docker-compose exec postgres psql -U agentrunner -c \
  "CREATE INDEX idx_agent_state_updated ON agent_state(updated_at);"

# Scale up agent pools
docker-compose up -d --scale autonomous-agent-pool=3
```

---

## Debugging Techniques

### Enable Debug Logging

```bash
# Set debug level for all services
nano .env
LOG_LEVEL=DEBUG

# Or per-service
STATE_MANAGER_LOG_LEVEL=DEBUG
ORCHESTRATOR_LOG_LEVEL=DEBUG

# Restart services
docker-compose restart
```

### Interactive Debugging

```bash
# Attach to running container
docker-compose exec [service] bash

# Run Python REPL with imports
docker-compose exec state-manager python
>>> from src.state.state_manager import StateManager
>>> manager = StateManager()
>>> # Test components interactively
```

### Network Debugging

```bash
# Check service connectivity
docker-compose exec agent-orchestrator curl http://state-manager:8001/health/live

# Check DNS resolution
docker-compose exec agent-orchestrator nslookup state-manager

# Monitor network traffic
docker-compose exec agent-orchestrator tcpdump -i any port 8001
```

### Database Debugging

```bash
# Enable query logging
docker-compose exec postgres psql -U agentrunner -c \
  "ALTER SYSTEM SET log_statement = 'all';"
docker-compose restart postgres

# Watch live queries
docker-compose exec postgres tail -f /var/log/postgresql/postgresql-*.log

# Analyze slow queries
docker-compose exec postgres psql -U agentrunner -c \
  "SELECT query, calls, mean_exec_time FROM pg_stat_statements WHERE mean_exec_time > 100 ORDER BY mean_exec_time DESC;"
```

---

## Log Analysis

### Log Locations

```bash
# Docker Compose logs
docker-compose logs [service-name]

# Follow logs in real-time
docker-compose logs -f [service-name]

# Last 100 lines
docker-compose logs --tail=100 [service-name]

# Logs since timestamp
docker-compose logs --since="2025-11-18T10:00:00" [service-name]

# Container logs
docker logs [container-id]
```

### Common Log Patterns

#### Successful Task Execution
```
INFO: Task submitted: execution_id=exec_123, agent=my-agent
INFO: Task routed to autonomous pool
INFO: Agent executing task: exec_123
INFO: Task completed successfully: exec_123, duration=2.3s
```

#### Failed Task Execution
```
ERROR: Task execution failed: exec_123
ERROR: LLM API error: 429 Rate Limit Exceeded
INFO: Retrying task: exec_123, attempt 2/3
```

#### Database Connection Issues
```
ERROR: Database connection failed: connection refused
ERROR: Unable to acquire connection from pool
WARNING: Retrying database connection, attempt 2/3
```

#### Agent Registration
```
INFO: Agent registered: name=my-agent, mode=autonomous
INFO: Subscribed to events: ['autonomous.task.submitted']
INFO: Agent health check: my-agent is healthy
```

### Log Filtering

```bash
# Filter by log level
docker-compose logs [service] 2>&1 | grep ERROR

# Filter by keyword
docker-compose logs [service] 2>&1 | grep "task.submitted"

# Filter by time range and save to file
docker-compose logs --since="2025-11-18T10:00:00" --until="2025-11-18T11:00:00" \
  [service] > error_logs.txt

# Count occurrences
docker-compose logs [service] 2>&1 | grep ERROR | wc -l
```

### Log Aggregation

```bash
# Collect logs from all services
for service in state-manager config-service agent-orchestrator; do
  echo "=== $service ===" >> all_logs.txt
  docker-compose logs $service >> all_logs.txt
done

# Search across all services
grep -r "execution_id=exec_123" all_logs.txt
```

---

## Recovery Procedures

### Restart Individual Service

```bash
# Restart single service
docker-compose restart [service-name]

# Force recreate container
docker-compose up -d --force-recreate [service-name]

# Rebuild and restart
docker-compose up -d --build [service-name]
```

### Restart All Services

```bash
# Graceful restart
docker-compose restart

# Full restart with rebuild
docker-compose down
docker-compose up -d --build

# Clean restart (removes volumes - DATA LOSS!)
docker-compose down -v
docker-compose up -d
```

### Database Recovery

```bash
# Restore from backup
docker-compose stop state-manager
docker-compose exec postgres psql -U agentrunner < backup.sql
docker-compose start state-manager

# Reset database (DATA LOSS!)
docker-compose down
docker volume rm agentrunner_postgres-data
docker-compose up -d postgres
docker-compose exec state-manager alembic upgrade head
```

### RabbitMQ Recovery

```bash
# Clear all queues
docker-compose exec rabbitmq rabbitmqctl reset

# Or clear specific queue
docker-compose exec rabbitmq rabbitmqctl purge_queue [queue-name]

# Restart RabbitMQ
docker-compose restart rabbitmq
```

### Redis Recovery

```bash
# Clear Redis cache
docker-compose exec redis redis-cli FLUSHDB

# Or clear specific pattern
docker-compose exec redis redis-cli --scan --pattern "state:*" | \
  xargs docker-compose exec redis redis-cli DEL

# Restart Redis
docker-compose restart redis
```

### Complete System Reset

```bash
# Stop all services
docker-compose down

# Remove all volumes (DATA LOSS!)
docker volume rm $(docker volume ls -q | grep agentrunner)

# Remove all containers
docker rm $(docker ps -a -q)

# Rebuild and start fresh
docker-compose up -d --build

# Wait for services to be ready
./scripts/wait-for-services.sh

# Verify all services healthy
./health_check.sh
```

---

## Getting Help

### Check Documentation

1. [Operations Guide](OPERATIONS_GUIDE.md) - Deployment and operations
2. [Agent Development Guide](AGENT_DEVELOPMENT_GUIDE.md) - Creating agents
3. [Configuration Reference](CONFIGURATION_REFERENCE.md) - Configuration options
4. [API Reference](API_REFERENCE.md) - API documentation

### Collect Diagnostic Information

Before seeking help, collect this information:

```bash
#!/bin/bash
# collect_diagnostics.sh

# Service status
docker-compose ps > diagnostics/docker-ps.txt

# Logs from all services
for service in postgres redis rabbitmq state-manager config-service \
               agent-orchestrator collaborative-agent-pool \
               autonomous-agent-pool continuous-agent-runner \
               scheduler-service slack-gateway; do
  docker-compose logs --tail=1000 $service > diagnostics/$service.log
done

# Configuration
docker-compose config > diagnostics/docker-compose-resolved.yml
env | grep -E '(POSTGRES|REDIS|RABBITMQ|OPENAI|ANTHROPIC)' > diagnostics/env-vars.txt

# Health checks
for port in 8001 8002 8003 8004 8005; do
  curl http://localhost:$port/health > diagnostics/health-$port.json
done

# Resource usage
docker stats --no-stream > diagnostics/docker-stats.txt

# RabbitMQ status
curl -u guest:guest http://localhost:15672/api/overview > diagnostics/rabbitmq-overview.json

# Create tarball
tar -czf diagnostics-$(date +%Y%m%d-%H%M%S).tar.gz diagnostics/
```

### Enable Verbose Logging

```bash
# Set debug level
nano .env
LOG_LEVEL=DEBUG
STATE_MANAGER_LOG_LEVEL=DEBUG
CONFIG_SERVICE_LOG_LEVEL=DEBUG
ORCHESTRATOR_LOG_LEVEL=DEBUG
SCHEDULER_LOG_LEVEL=DEBUG
SLACK_GATEWAY_LOG_LEVEL=DEBUG

# Enable SQL query logging
POSTGRES_ECHO_SQL=true

# Restart with debug logging
docker-compose restart
```

---

## Appendix: Error Reference

### HTTP Status Codes

| Code | Meaning | Typical Cause |
|------|---------|---------------|
| 400 | Bad Request | Invalid request parameters |
| 401 | Unauthorized | Missing/invalid API key |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Agent/resource doesn't exist |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server-side error |
| 502 | Bad Gateway | Service unavailable |
| 503 | Service Unavailable | Service overloaded |
| 504 | Gateway Timeout | Request timeout |

### Common Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| "connection refused" | Service not running | Start service: `docker-compose up -d [service]` |
| "authentication failed" | Wrong credentials | Check .env file credentials |
| "table does not exist" | Missing migrations | Run: `alembic upgrade head` |
| "address already in use" | Port conflict | Change port or kill process |
| "no such file or directory" | Missing config file | Create agent YAML in config/agents/ |
| "invalid YAML" | Syntax error | Validate with: `yamllint [file]` |
| "timeout" | Service too slow | Increase timeout, check performance |
| "rate limit exceeded" | Too many API calls | Reduce concurrency, add delays |

---

**Last Updated**: 2025-11-18
**Version**: 1.0
