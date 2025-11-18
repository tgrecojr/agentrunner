# Operations Guide
**Multi-Agent Orchestration Platform**

This guide covers everything you need to deploy, configure, monitor, and maintain the Multi-Agent Orchestration Platform in production.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Starting the Platform](#starting-the-platform)
5. [Monitoring](#monitoring)
6. [Scaling](#scaling)
7. [Backup and Recovery](#backup-and-recovery)
8. [Security](#security)
9. [Troubleshooting](#troubleshooting)
10. [Maintenance](#maintenance)

---

## Prerequisites

### Hardware Requirements

**Minimum (Development)**:
- 4 CPU cores
- 8 GB RAM
- 20 GB disk space (SSD recommended)
- Network connectivity

**Recommended (Production)**:
- 8+ CPU cores
- 16+ GB RAM
- 100+ GB SSD storage
- Redundant network connections

### Software Requirements

**Required**:
- Docker 20.10+ ([Install Docker](https://docs.docker.com/get-docker/))
- Docker Compose 2.0+ (included with Docker Desktop)
- Git 2.0+

**Optional**:
- Make (for automation scripts)
- curl/httpie (for API testing)
- jq (for JSON processing)

### LLM Provider Accounts

At least ONE of the following:
- **OpenAI** account with API key ([Get API key](https://platform.openai.com/api-keys))
- **Anthropic** account with API key ([Get API key](https://console.anthropic.com/))
- **AWS** account with Bedrock access ([AWS Bedrock](https://aws.amazon.com/bedrock/))
- **Ollama** installed locally for offline models ([Install Ollama](https://ollama.ai/))

### Optional Integrations

- **Slack** workspace (for Slack integration)
  - Bot token (xoxb-...)
  - Signing secret
  - App token (xapp-...)

---

## Installation

### Step 1: Clone the Repository

```bash
git clone https://github.com/your-org/agentrunner.git
cd agentrunner
```

### Step 2: Configure Environment Variables

```bash
# Copy the example environment file
cp .env.example .env

# Edit the configuration
nano .env  # or use your preferred editor
```

**Required Variables** (at minimum, set ONE LLM provider):

```bash
# OpenAI (recommended for getting started)
OPENAI_API_KEY=sk-your-api-key-here

# OR Anthropic
ANTHROPIC_API_KEY=sk-ant-your-api-key-here

# OR AWS Bedrock
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=us-east-1

# Postgres password (change in production)
POSTGRES_PASSWORD=your-secure-password-here

# RabbitMQ credentials (change in production)
RABBITMQ_USER=agentrunner
RABBITMQ_PASSWORD=your-secure-password-here
```

**Optional Variables** (for Slack integration):

```bash
SLACK_SIGNING_SECRET=your-signing-secret
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token
```

### Step 3: Create Required Directories

```bash
mkdir -p logs data config/agents
```

### Step 4: Verify Docker Installation

```bash
# Check Docker is running
docker info

# Check Docker Compose version
docker-compose version
```

---

## Configuration

### Directory Structure

```
agentrunner/
├── config/
│   └── agents/          # Agent YAML configurations (auto-discovered)
├── logs/                # Application logs (mounted volume)
├── data/                # Persistent data (mounted volume)
├── .env                 # Environment configuration
└── docker-compose.yml   # Service orchestration
```

### Environment Configuration

The `.env` file controls all platform behavior. Key sections:

#### Database Configuration

```bash
# PostgreSQL
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=agentrunner
POSTGRES_USER=agentrunner
POSTGRES_PASSWORD=change_me_in_production

# Connection pool
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=10
```

#### Cache Configuration

```bash
# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=change_me_in_production

# TTL settings
REDIS_STATE_TTL=3600     # 1 hour
REDIS_CACHE_TTL=300      # 5 minutes
```

#### Message Broker Configuration

```bash
# RabbitMQ
RABBITMQ_HOST=rabbitmq
RABBITMQ_PORT=5672
RABBITMQ_USER=agentrunner
RABBITMQ_PASSWORD=change_me_in_production
RABBITMQ_PREFETCH_COUNT=1
```

#### Application Settings

```bash
# Logging
LOG_LEVEL=INFO          # DEBUG, INFO, WARNING, ERROR
LOG_FORMAT=json         # json or text

# Agent orchestration
AGENT_HEALTH_CHECK_INTERVAL=60  # seconds
AGENT_RESTART_MAX_ATTEMPTS=3
AGENT_SHUTDOWN_TIMEOUT=30       # seconds

# State management
STATE_COMPRESSION_THRESHOLD=1048576  # 1MB
STATE_RETENTION_DAYS=30

# Continuous agents
CONTINUOUS_AGENT_IDLE_TIMEOUT=600  # 10 minutes
```

---

## Starting the Platform

### Quick Start (All Services)

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Check service health
docker-compose ps
```

### Staged Startup (Recommended for First Time)

#### Stage 1: Infrastructure Services

```bash
# Start databases and message broker
docker-compose up -d postgres redis rabbitmq

# Wait for health checks (30-60 seconds)
docker-compose ps

# Verify services are healthy
docker-compose ps | grep "healthy"
```

Expected output:
```
postgres     healthy
redis        healthy
rabbitmq     healthy
```

#### Stage 2: Core Services

```bash
# Start StateManager and ConfigService
docker-compose up -d state-manager config-service

# Monitor startup
docker-compose logs -f state-manager config-service

# Verify health
curl http://localhost:8001/health/live  # StateManager
curl http://localhost:8002/health/live  # ConfigService
```

Expected response: `{"status":"alive"}`

#### Stage 3: Agent Orchestrator

```bash
# Start orchestrator
docker-compose up -d agent-orchestrator

# Check logs
docker-compose logs -f agent-orchestrator

# Verify agent registration
curl http://localhost:8003/agents | jq
```

#### Stage 4: Agent Pools

```bash
# Start all agent pools
docker-compose up -d \
  collaborative-agent-pool \
  autonomous-agent-pool \
  continuous-agent-runner

# Monitor startup
docker-compose logs -f collaborative-agent-pool autonomous-agent-pool continuous-agent-runner
```

#### Stage 5: Integration Services

```bash
# Start scheduler and Slack gateway
docker-compose up -d scheduler-service slack-gateway

# Verify all services
for port in 8001 8002 8003 8004 8005; do
  echo "Port $port: $(curl -s http://localhost:$port/health/live 2>&1 | jq -r .status)"
done
```

Expected output:
```
Port 8001: alive
Port 8002: alive
Port 8003: alive
Port 8004: alive
Port 8005: alive
```

### Verify Complete Startup

```bash
# Check all containers
docker-compose ps

# All services should show "Up" or "Up (healthy)"
# No services should be "Restarting" or "Exit"
```

### Access Management UIs

- **RabbitMQ Management**: http://localhost:15672
  - Username: `guest` (or value from RABBITMQ_USER)
  - Password: `guest` (or value from RABBITMQ_PASSWORD)

- **API Documentation** (Swagger):
  - AgentOrchestrator: http://localhost:8003/docs
  - SchedulerService: http://localhost:8004/docs
  - SlackGateway: http://localhost:8005/docs

---

## Monitoring

### Health Checks

#### Automated Health Monitoring Script

```bash
#!/bin/bash
# health_check.sh

services=("8001:StateManager" "8002:ConfigService" "8003:Orchestrator" "8004:Scheduler" "8005:SlackGateway")

echo "=== Service Health Check ==="
all_healthy=true

for service in "${services[@]}"; do
  port="${service%%:*}"
  name="${service##*:}"

  response=$(curl -s http://localhost:$port/health/live 2>/dev/null | jq -r .status 2>/dev/null)

  if [ "$response" = "alive" ]; then
    echo "✓ $name (port $port): healthy"
  else
    echo "✗ $name (port $port): UNHEALTHY"
    all_healthy=false
  fi
done

if [ "$all_healthy" = true ]; then
  echo "All services healthy!"
  exit 0
else
  echo "Some services are unhealthy!"
  exit 1
fi
```

```bash
chmod +x health_check.sh
./health_check.sh
```

#### Manual Health Checks

```bash
# Check individual services
curl http://localhost:8001/health/ready | jq  # StateManager
curl http://localhost:8002/health/ready | jq  # ConfigService
curl http://localhost:8003/health/ready | jq  # Orchestrator

# Check infrastructure
docker-compose exec postgres pg_isready -U agentrunner
docker-compose exec redis redis-cli ping
docker-compose exec rabbitmq rabbitmq-diagnostics ping
```

### Log Monitoring

#### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f agent-orchestrator

# Last 100 lines
docker-compose logs --tail=100 state-manager

# Follow with timestamps
docker-compose logs -f --timestamps
```

#### Search Logs by Trace ID

```bash
# Find all logs for a specific request
docker-compose logs | grep "trace_id\":\"abc-123-def"

# Search within specific time range
docker-compose logs --since="2025-01-18T10:00:00" --until="2025-01-18T11:00:00" | grep ERROR
```

#### Log Levels

Adjust log verbosity in `.env`:

```bash
# More verbose (development)
LOG_LEVEL=DEBUG

# Standard (production)
LOG_LEVEL=INFO

# Errors only
LOG_LEVEL=ERROR
```

### Resource Monitoring

#### Container Resource Usage

```bash
# Real-time resource usage
docker stats

# One-time snapshot
docker stats --no-stream

# Specific services
docker stats agent-orchestrator collaborative-agent-pool
```

#### Disk Usage

```bash
# Docker volumes
docker system df -v

# Database size
docker-compose exec postgres psql -U agentrunner -c "SELECT pg_size_pretty(pg_database_size('agentrunner'));"

# Redis memory usage
docker-compose exec redis redis-cli info memory | grep used_memory_human

# RabbitMQ queue depth
docker-compose exec rabbitmq rabbitmqctl list_queues
```

### Performance Metrics

#### Agent Registry Status

```bash
# List all agents
curl http://localhost:8003/agents | jq

# Agent count by status
curl http://localhost:8003/agents | jq 'group_by(.status) | map({status: .[0].status, count: length})'

# Agent count by execution mode
curl http://localhost:8003/agents | jq 'group_by(.execution_mode) | map({mode: .[0].execution_mode, count: length})'
```

#### Task Execution Stats

```bash
# Check RabbitMQ queue depths
curl -u guest:guest http://localhost:15672/api/queues | jq '.[] | {name, messages, consumers}'
```

### Alerting Setup

#### Basic Email Alerts

```bash
# Add to crontab for periodic health checks
*/5 * * * * /path/to/health_check.sh || echo "Platform health check failed" | mail -s "Alert: AgentRunner Unhealthy" ops@example.com
```

#### Slack Webhook Alerts

```bash
#!/bin/bash
# alert_to_slack.sh

SLACK_WEBHOOK="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

if ! ./health_check.sh; then
  curl -X POST $SLACK_WEBHOOK \
    -H 'Content-Type: application/json' \
    -d '{"text":"⚠️ AgentRunner Platform Health Check Failed!"}'
fi
```

---

## Scaling

### Horizontal Scaling

#### Scale Autonomous Agent Pool

```bash
# Scale to 3 instances
docker-compose up -d --scale autonomous-agent-pool=3

# Verify scaling
docker-compose ps autonomous-agent-pool

# Check load distribution
curl http://localhost:8003/metrics/pool-stats | jq
```

#### Scale Other Services

```bash
# Scale collaborative pool
docker-compose up -d --scale collaborative-agent-pool=2

# Scale continuous runner
docker-compose up -d --scale continuous-agent-runner=2
```

**Note**: StateManager, ConfigService, and AgentOrchestrator should NOT be scaled (stateful singletons).

### Vertical Scaling

Edit `docker-compose.yml` to adjust resource limits:

```yaml
services:
  autonomous-agent-pool:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          cpus: '1.0'
          memory: 1G
```

### Database Scaling

#### Increase Connection Pool

In `.env`:

```bash
DB_POOL_SIZE=50          # Up from 20
DB_MAX_OVERFLOW=30       # Up from 10
```

#### PostgreSQL Performance Tuning

```bash
# Edit PostgreSQL configuration
docker-compose exec postgres bash

# Edit /var/lib/postgresql/data/postgresql.conf
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 128MB
max_connections = 200
```

### Redis Scaling

```bash
# Increase maxmemory in docker-compose.yml
redis:
  command: redis-server --maxmemory 2gb --maxmemory-policy allkeys-lru
```

---

## Backup and Recovery

### Database Backup

#### Manual Backup

```bash
# Backup PostgreSQL
docker-compose exec -T postgres pg_dump -U agentrunner agentrunner > backup_$(date +%Y%m%d_%H%M%S).sql

# Backup with compression
docker-compose exec -T postgres pg_dump -U agentrunner agentrunner | gzip > backup_$(date +%Y%m%d_%H%M%S).sql.gz
```

#### Automated Daily Backups

```bash
#!/bin/bash
# backup_daily.sh

BACKUP_DIR="/backups/agentrunner"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup PostgreSQL
docker-compose exec -T postgres pg_dump -U agentrunner agentrunner | gzip > $BACKUP_DIR/postgres_$DATE.sql.gz

# Backup Redis (if persistence enabled)
docker-compose exec -T redis redis-cli --rdb /data/dump.rdb
docker cp agentrunner-redis:/data/dump.rdb $BACKUP_DIR/redis_$DATE.rdb

# Backup agent configurations
tar -czf $BACKUP_DIR/configs_$DATE.tar.gz config/

# Keep only last 30 days
find $BACKUP_DIR -name "*.gz" -mtime +30 -delete
find $BACKUP_DIR -name "*.rdb" -mtime +30 -delete

echo "Backup completed: $DATE"
```

Add to crontab:
```bash
0 2 * * * /path/to/backup_daily.sh
```

### Database Restore

#### From SQL Backup

```bash
# Stop services
docker-compose stop

# Restore database
cat backup_20250118_020000.sql | docker-compose exec -T postgres psql -U agentrunner agentrunner

# Or from compressed backup
gunzip -c backup_20250118_020000.sql.gz | docker-compose exec -T postgres psql -U agentrunner agentrunner

# Restart services
docker-compose up -d
```

### Volume Backup

```bash
# Backup all volumes
docker run --rm \
  -v agentrunner_postgres-data:/source \
  -v /backups:/backup \
  alpine tar -czf /backup/postgres-volume_$(date +%Y%m%d).tar.gz -C /source .

# Same for redis and rabbitmq
docker run --rm \
  -v agentrunner_redis-data:/source \
  -v /backups:/backup \
  alpine tar -czf /backup/redis-volume_$(date +%Y%m%d).tar.gz -C /source .
```

### Disaster Recovery

#### Complete System Restoration

```bash
# 1. Stop all services
docker-compose down

# 2. Restore volumes
docker volume create agentrunner_postgres-data
docker run --rm \
  -v agentrunner_postgres-data:/target \
  -v /backups:/backup \
  alpine tar -xzf /backup/postgres-volume_20250118.tar.gz -C /target

# 3. Restore configuration
tar -xzf /backups/configs_20250118.tar.gz

# 4. Start services
docker-compose up -d

# 5. Verify restoration
./health_check.sh
```

---

## Security

### Production Security Checklist

#### 1. Change Default Passwords

```bash
# In .env file
POSTGRES_PASSWORD=<strong-random-password>
RABBITMQ_PASSWORD=<strong-random-password>
REDIS_PASSWORD=<strong-random-password>
```

Generate strong passwords:
```bash
openssl rand -base64 32
```

#### 2. API Authentication

Enable API authentication in `.env`:

```bash
ENABLE_API_AUTH=true
API_SECRET_KEY=$(openssl rand -base64 64)
```

#### 3. TLS/SSL Configuration

```bash
# In .env
ENABLE_TLS=true
TLS_CERT_PATH=/app/certs/tls.crt
TLS_KEY_PATH=/app/certs/tls.key
```

Mount certificates:
```yaml
services:
  agent-orchestrator:
    volumes:
      - ./certs:/app/certs:ro
```

#### 4. Network Security

Use Docker networks with firewall rules:

```bash
# Only expose necessary ports
# Remove from docker-compose.yml for internal services:
ports:
  - "5432:5432"  # Remove - only for development
  - "6379:6379"   # Remove - only for development
```

#### 5. Secrets Management

**Option A: Docker Secrets** (Swarm mode)

```yaml
secrets:
  openai_api_key:
    external: true

services:
  agent-orchestrator:
    secrets:
      - openai_api_key
```

**Option B: AWS Secrets Manager**

```python
# In application code
import boto3

secrets_client = boto3.client('secretsmanager')
api_key = secrets_client.get_secret_value(SecretId='OPENAI_API_KEY')
```

**Option C: HashiCorp Vault**

```bash
vault kv get secret/agentrunner/openai-api-key
```

#### 6. Rate Limiting

Add rate limiting via nginx reverse proxy:

```nginx
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;

server {
    location /api/ {
        limit_req zone=api burst=20 nodelay;
        proxy_pass http://localhost:8003;
    }
}
```

#### 7. Audit Logging

Enable detailed audit logs:

```bash
# In .env
LOG_LEVEL=INFO
ENABLE_AUDIT_LOG=true
AUDIT_LOG_PATH=/app/logs/audit.log
```

### Slack Security

#### Verify Webhook Signatures

The platform automatically verifies Slack webhook signatures. Ensure you have:

```bash
# In .env
SLACK_SIGNING_SECRET=<your-signing-secret>
```

Verification happens in `src/integrations/slack_gateway.py:verify_signature()`

---

## Troubleshooting

### Common Issues

#### Issue: Service Won't Start

**Symptoms**: Container exits immediately or keeps restarting

**Diagnosis**:
```bash
# Check container logs
docker-compose logs <service-name>

# Check container status
docker-compose ps

# Inspect container
docker inspect agentrunner-<service-name>
```

**Common Causes**:
1. **Port already in use**
   ```bash
   # Find process using port
   lsof -i :8001
   # Kill process or change port in docker-compose.yml
   ```

2. **Missing environment variables**
   ```bash
   # Verify .env file exists and has required values
   cat .env | grep API_KEY
   ```

3. **Database connection failure**
   ```bash
   # Verify PostgreSQL is running
   docker-compose ps postgres
   # Check PostgreSQL logs
   docker-compose logs postgres
   ```

#### Issue: Agent Not Registered

**Symptoms**: Agent YAML exists but not showing in registry

**Diagnosis**:
```bash
# Check ConfigService logs
docker-compose logs config-service | grep "agent_name"

# List loaded agents
curl http://localhost:8002/configs | jq '.[] | .name'

# Check YAML syntax
cat config/agents/my-agent.yml | yaml-validator
```

**Solutions**:
1. Verify YAML syntax (use https://www.yamllint.com/)
2. Check file permissions (`chmod 644 config/agents/*.yml`)
3. Restart ConfigService (`docker-compose restart config-service`)

#### Issue: High Memory Usage

**Diagnosis**:
```bash
# Check container memory
docker stats --no-stream

# Check specific service
docker stats agent-orchestrator --no-stream
```

**Solutions**:
1. **Increase memory limits**:
   ```yaml
   deploy:
     resources:
       limits:
         memory: 2G
   ```

2. **Reduce continuous agent history**:
   ```yaml
   continuous_config:
     max_conversation_history: 50  # Reduce from 100
   ```

3. **Enable state compression**:
   ```bash
   STATE_COMPRESSION_THRESHOLD=524288  # 512KB (lower threshold)
   ```

#### Issue: Slow API Response

**Diagnosis**:
```bash
# Measure response time
time curl http://localhost:8003/agents

# Check database connections
docker-compose exec postgres psql -U agentrunner -c "SELECT count(*) FROM pg_stat_activity;"

# Check Redis performance
docker-compose exec redis redis-cli --latency
```

**Solutions**:
1. Increase connection pool size
2. Add Redis caching
3. Scale agent pools horizontally

#### Issue: EventBus Message Backlog

**Diagnosis**:
```bash
# Check queue depths
curl -u guest:guest http://localhost:15672/api/queues | jq '.[] | {name, messages}'

# Check consumer count
curl -u guest:guest http://localhost:15672/api/queues | jq '.[] | {name, consumers}'
```

**Solutions**:
1. Scale agent pools
2. Increase consumer prefetch count
3. Check for stuck consumers

---

## Maintenance

### Routine Maintenance Tasks

#### Daily
- [ ] Monitor service health
- [ ] Check error logs
- [ ] Verify backup completion
- [ ] Review queue depths

#### Weekly
- [ ] Review resource usage trends
- [ ] Clean up old logs
- [ ] Update agent configurations as needed
- [ ] Test disaster recovery procedure

#### Monthly
- [ ] Update Docker images
- [ ] Review and rotate credentials
- [ ] Archive old execution results
- [ ] Performance testing

### Updating the Platform

#### Update Docker Images

```bash
# Pull latest images
docker-compose pull

# Restart with new images
docker-compose up -d

# Verify update
docker-compose ps
```

#### Update Agent Configurations

```bash
# Edit agent YAML
nano config/agents/my-agent.yml

# ConfigService auto-reloads (hot reload enabled)
# Verify update
curl http://localhost:8002/configs/my-agent | jq
```

#### Database Migrations

```bash
# Run migrations
docker-compose exec state-manager alembic upgrade head

# Check migration status
docker-compose exec state-manager alembic current

# Rollback if needed
docker-compose exec state-manager alembic downgrade -1
```

### Log Rotation

```bash
# Add logrotate configuration
sudo nano /etc/logrotate.d/agentrunner

# Configuration:
/path/to/agentrunner/logs/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    create 0644 root root
}
```

### Cleanup Old Data

```bash
# Clean up old execution results (>30 days)
docker-compose exec postgres psql -U agentrunner -c "DELETE FROM execution_results WHERE created_at < NOW() - INTERVAL '30 days';"

# Clean up old agent states (>30 days)
docker-compose exec postgres psql -U agentrunner -c "DELETE FROM agent_states WHERE updated_at < NOW() - INTERVAL '30 days';"

# Clean up Docker resources
docker system prune -a --volumes
```

---

## Appendix

### Service Port Reference

| Service | Port | Purpose |
|---------|------|---------|
| StateManager | 8001 | State persistence API |
| ConfigService | 8002 | Agent configuration API |
| AgentOrchestrator | 8003 | Main orchestration API |
| SchedulerService | 8004 | Scheduled task management |
| SlackGateway | 8005 | Slack webhook endpoint |
| PostgreSQL | 5432 | Primary database |
| Redis | 6379 | Cache layer |
| RabbitMQ (AMQP) | 5672 | Message broker |
| RabbitMQ (Management) | 15672 | Management UI |

### Useful Commands Reference

```bash
# Start everything
docker-compose up -d

# Stop everything
docker-compose down

# Restart a service
docker-compose restart <service-name>

# View logs
docker-compose logs -f <service-name>

# Execute command in container
docker-compose exec <service-name> <command>

# Scale a service
docker-compose up -d --scale <service-name>=<count>

# Check service health
curl http://localhost:<port>/health/live

# List all agents
curl http://localhost:8003/agents | jq

# Backup database
docker-compose exec -T postgres pg_dump -U agentrunner agentrunner > backup.sql

# Monitor resources
docker stats
```

---

**Document Version**: 1.0
**Last Updated**: 2025-01-18
**Next Review**: 2025-02-18
