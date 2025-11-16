# Future Considerations - Advanced Monitoring and Observability

## Overview

This document captures advanced monitoring and observability infrastructure that was deferred from the initial implementation (Version 1.2) to keep the system simpler and faster to deploy. The initial version uses structured JSON logging with trace IDs, which provides sufficient observability for debugging and request correlation.

This document preserves the complete design and implementation plan for when the system is ready to scale to production with centralized monitoring, metrics collection, and advanced alerting.

**Note**: Pluggable LLM provider support was originally planned for this section but has been included in the main specification (Version 1.2) as Requirement 13. See the design document for the LLMProviderFactory component specification.

---

## Deferred Capabilities

The following monitoring and observability capabilities were removed from the initial implementation to simplify deployment:

- **MonitoringCollector Component**: Centralized metrics collection and aggregation service
- **Prometheus Integration**: Time-series metrics database with scraping endpoints
- **Grafana Dashboards**: Real-time visualization of system health and performance
- **Advanced Alerting**: Threshold-based alerts with notification channels
- **Log Aggregation**: Centralized log collection platforms (ELK, Loki, etc.)
- **Distributed Tracing**: Integration with OpenTelemetry, Jaeger, or Zipkin

---

## Original Requirement 10: Monitoring and Observability

**Description**: The system SHALL expose metrics, logs, and traces to enable real-time monitoring, debugging, and alerting through Prometheus and Grafana.

### Original Acceptance Criteria

**10.1.** WHEN any component performs an operation, THE component SHALL emit structured JSON logs to stdout with fields including timestamp, level (INFO/WARNING/ERROR), component name, message, and trace_id for request correlation.

**10.2.** WHEN the **MonitoringCollector** starts, THE service SHALL initialize Prometheus metrics (Counter, Histogram, Gauge) and expose them on `/metrics` endpoint for scraping with metrics including:
- `agent_task_duration_seconds` (Histogram) - Task execution time by agent_id and status
- `agent_task_success_total` (Counter) - Successful task count by agent_id
- `agent_task_failure_total` (Counter) - Failed task count by agent_id and error_type
- `agent_queue_depth` (Gauge) - Current queue depth by queue_name

**10.3.** WHEN an event enters the system, THE entry point (SlackGateway, SchedulerService, or EventBus) SHALL generate a unique trace_id (UUID) and propagate it through all subsequent operations, logging, and metrics to enable distributed tracing.

**10.4.** WHEN Grafana queries Prometheus, THE system SHALL provide real-time dashboards showing:
- Agent health status and uptime
- Task throughput and error rates (last 5 minutes, 1 hour, 24 hours)
- Queue depth and latency by agent type
- Resource utilization (CPU, memory, RabbitMQ connections)

**10.5.** WHEN a metric exceeds threshold limits, THE **MonitoringCollector** SHALL trigger alerts (e.g., >5 failures in 5 minutes, queue depth >100) and send notifications to configured channels (Slack webhook, email, PagerDuty).

---

## MonitoringCollector Component Specification

### Purpose
Centralized service for collecting metrics, managing alerts, and coordinating observability across all system components.

### Location
`src/monitoring/monitoring_collector.py`

### Interface

```python
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, start_http_server
from typing import Dict, Any, Optional
import json
import logging
from datetime import datetime

class MonitoringCollector:
    """
    Implements Req 10.1, 10.2, 10.3, 10.4, 10.5
    Centralized monitoring and observability service
    """

    def __init__(self, port: int = 9090):
        """
        Initialize Prometheus metrics and start HTTP server for /metrics endpoint

        Args:
            port: Port for Prometheus metrics endpoint (default 9090)
        """
        self.registry = CollectorRegistry()
        self.port = port

        # Initialize Prometheus metrics
        self.task_duration = Histogram(
            'agent_task_duration_seconds',
            'Task execution duration in seconds',
            ['agent_id', 'status'],
            registry=self.registry
        )

        self.task_success = Counter(
            'agent_task_success_total',
            'Total successful task executions',
            ['agent_id'],
            registry=self.registry
        )

        self.task_failure = Counter(
            'agent_task_failure_total',
            'Total failed task executions',
            ['agent_id', 'error_type'],
            registry=self.registry
        )

        self.queue_depth = Gauge(
            'agent_queue_depth',
            'Current queue depth',
            ['queue_name'],
            registry=self.registry
        )

        # Alert thresholds
        self.alert_thresholds = {
            'failure_rate_5min': 5,
            'queue_depth_max': 100,
            'task_duration_p95_seconds': 60
        }

        # Initialize structured logging
        self.logger = logging.getLogger('MonitoringCollector')
        self.logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            '{"timestamp":"%(asctime)s","level":"%(levelname)s",'
            '"component":"%(name)s","message":"%(message)s","metadata":%(metadata)s}'
        ))
        self.logger.addHandler(handler)

    def start(self) -> None:
        """
        Start Prometheus HTTP server for /metrics endpoint
        Implements Req 10.2
        """
        start_http_server(self.port, registry=self.registry)
        self.log_event('Monitoring service started', trace_id=None, port=self.port)

    def log_event(self, message: str, trace_id: Optional[str], **metadata) -> None:
        """
        Emit structured JSON log with trace_id
        Implements Req 10.1, 10.3

        Args:
            message: Log message
            trace_id: Request trace ID for correlation
            **metadata: Additional metadata fields
        """
        log_data = {
            'trace_id': trace_id,
            **metadata
        }
        self.logger.info(message, extra={'metadata': json.dumps(log_data)})

    def log_error(self, message: str, trace_id: Optional[str],
                  error: Optional[Exception] = None, **metadata) -> None:
        """
        Log error with stack trace and trace_id
        Implements Req 10.1, 10.3

        Args:
            message: Error message
            trace_id: Request trace ID
            error: Exception object (optional)
            **metadata: Additional context
        """
        log_data = {
            'trace_id': trace_id,
            'error_type': type(error).__name__ if error else None,
            'error_message': str(error) if error else None,
            **metadata
        }
        self.logger.error(message, extra={'metadata': json.dumps(log_data)},
                         exc_info=error)

    def record_task_duration(self, agent_id: str, duration: float,
                            status: str, trace_id: str) -> None:
        """
        Record task execution duration metric
        Implements Req 10.2

        Args:
            agent_id: Agent identifier
            duration: Execution time in seconds
            status: 'success' or 'failure'
            trace_id: Request trace ID
        """
        self.task_duration.labels(agent_id=agent_id, status=status).observe(duration)
        self.log_event(
            f'Task completed: {status}',
            trace_id=trace_id,
            agent_id=agent_id,
            duration=duration,
            status=status
        )

    def record_task_success(self, agent_id: str, trace_id: str) -> None:
        """
        Increment successful task counter
        Implements Req 10.2
        """
        self.task_success.labels(agent_id=agent_id).inc()

    def record_task_failure(self, agent_id: str, error_type: str, trace_id: str) -> None:
        """
        Increment failed task counter and check alert thresholds
        Implements Req 10.2, 10.5
        """
        self.task_failure.labels(agent_id=agent_id, error_type=error_type).inc()
        self._check_failure_threshold(agent_id, trace_id)

    def update_queue_depth(self, queue_name: str, depth: int) -> None:
        """
        Update queue depth gauge and check alert thresholds
        Implements Req 10.2, 10.5
        """
        self.queue_depth.labels(queue_name=queue_name).set(depth)
        if depth > self.alert_thresholds['queue_depth_max']:
            self._trigger_alert(
                severity='warning',
                message=f'Queue depth exceeded threshold: {depth}',
                queue_name=queue_name,
                current_depth=depth,
                threshold=self.alert_thresholds['queue_depth_max']
            )

    def _check_failure_threshold(self, agent_id: str, trace_id: str) -> None:
        """
        Check if failure rate exceeds threshold and trigger alert
        Implements Req 10.5
        """
        # This would query Prometheus for failure rate in last 5 minutes
        # Simplified implementation - actual would use PromQL query
        # Example PromQL: rate(agent_task_failure_total[5m]) > 1
        pass

    def _trigger_alert(self, severity: str, message: str, **metadata) -> None:
        """
        Trigger alert notification
        Implements Req 10.5

        Args:
            severity: 'info', 'warning', 'critical'
            message: Alert message
            **metadata: Alert context
        """
        alert_data = {
            'severity': severity,
            'message': message,
            'timestamp': datetime.utcnow().isoformat(),
            **metadata
        }

        # Log the alert
        self.logger.warning(f'ALERT: {message}', extra={'metadata': json.dumps(alert_data)})

        # Send to notification channels (Slack, PagerDuty, etc.)
        # Implementation would integrate with alerting services
        pass

    @staticmethod
    def generate_trace_id() -> str:
        """
        Generate UUID for request tracing
        Implements Req 10.3
        """
        import uuid
        return str(uuid.uuid4())
```

### Data Structures

```python
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class MetricRecord:
    """Single metric observation"""
    metric_name: str
    value: float
    labels: Dict[str, str]
    timestamp: datetime
    trace_id: Optional[str] = None

@dataclass
class Alert:
    """Alert notification"""
    severity: str  # 'info', 'warning', 'critical'
    message: str
    triggered_at: datetime
    metric_name: str
    current_value: float
    threshold_value: float
    metadata: Dict[str, Any]
```

### Dependencies

- `prometheus_client` (Python Prometheus client library)
- `StateManager` (for alert history persistence)
- `ConfigurationService` (for alert threshold configuration)

---

## Implementation Tasks (Removed from Version 1.1)

### Phase 5: Monitoring and Observability

**Prerequisites**: Phase 1 (Infrastructure)

#### Task 5.1: Implement MonitoringCollector Class
**File**: `src/monitoring/monitoring_collector.py`
- Create `MonitoringCollector` class
- Initialize Prometheus metrics registry
- Set up structured JSON logging to stdout
- **Requirements**: 10.1, 10.2

#### Task 5.2: Implement Structured Logging
**File**: `src/monitoring/monitoring_collector.py`
- Add `log_event()` method with trace_id propagation
- Add `log_error()` method with stack trace capture
- Implement log formatting with component, level, timestamp, message, metadata
- **Requirements**: 10.1, 10.3

#### Task 5.3: Implement Prometheus Metrics
**File**: `src/monitoring/monitoring_collector.py`
- Define metrics: `agent_task_duration_seconds`, `agent_task_success_total`, `agent_task_failure_total`, `agent_queue_depth`
- Add `record_metric()` method with label support
- Expose `/metrics` endpoint for Prometheus scraping
- **Requirements**: 10.2

#### Task 5.4: Implement Distributed Tracing
**File**: `src/monitoring/monitoring_collector.py`
- Add `start_trace()` method generating UUID trace_id
- Implement trace_id propagation through Event objects
- Add trace correlation in logs and metrics
- **Requirements**: 10.3

#### Task 5.5: Implement Alerting System
**File**: `src/monitoring/monitoring_collector.py`
- Add `trigger_alert()` method with severity levels
- Implement threshold-based alerting (e.g., >5 failures in 5 minutes)
- Add alert notification to monitoring dashboard
- **Requirements**: 10.5

#### Task 5.6: Create Prometheus Configuration
**File**: `config/prometheus.yml`
- Create Prometheus configuration with scrape configs for all services
- Define scrape intervals (15s for high-frequency metrics)
- Configure retention (15 days) and storage settings
- **Requirements**: 10.2, 10.4

#### Task 5.7: Create Grafana Dashboards
**Files**: `config/grafana/dashboards/*.json`
- Create `agent-overview.json` with agent health metrics
- Create dashboard for task throughput and error rates
- Add dashboard for queue depth and latency metrics
- **Requirements**: 10.4

---

## Configuration Files

### Prometheus Configuration (`config/prometheus.yml`)

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    cluster: 'agent-orchestration'
    environment: 'production'

scrape_configs:
  # AgentOrchestrator metrics
  - job_name: 'agent-orchestrator'
    static_configs:
      - targets: ['agent-orchestrator:9090']

  # MonitoringCollector metrics
  - job_name: 'monitoring-collector'
    static_configs:
      - targets: ['monitoring-collector:9090']

  # EventBus metrics
  - job_name: 'event-bus'
    static_configs:
      - targets: ['event-bus:9090']

  # StateManager metrics
  - job_name: 'state-manager'
    static_configs:
      - targets: ['state-manager:9090']

  # Agent Pools
  - job_name: 'collaborative-agent-pool'
    static_configs:
      - targets: ['collaborative-agent-pool:9090']

  - job_name: 'autonomous-agent-pool'
    static_configs:
      - targets: ['autonomous-agent-pool:9090']

  - job_name: 'continuous-agent-runner'
    static_configs:
      - targets: ['continuous-agent-runner:9090']

  # Integrations
  - job_name: 'scheduler-service'
    static_configs:
      - targets: ['scheduler-service:9090']

  - job_name: 'slack-gateway'
    static_configs:
      - targets: ['slack-gateway:9090']

  # RabbitMQ exporter
  - job_name: 'rabbitmq'
    static_configs:
      - targets: ['rabbitmq-exporter:9419']

  # PostgreSQL exporter
  - job_name: 'postgresql'
    static_configs:
      - targets: ['postgres-exporter:9187']

  # Redis exporter
  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']

# Alerting rules
rule_files:
  - 'alerts.yml'

# Alert manager configuration
alerting:
  alertmanagers:
    - static_configs:
        - targets: ['alertmanager:9093']
```

### Prometheus Alert Rules (`config/prometheus/alerts.yml`)

```yaml
groups:
  - name: agent_alerts
    interval: 30s
    rules:
      # High failure rate
      - alert: HighAgentFailureRate
        expr: rate(agent_task_failure_total[5m]) > 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High failure rate for agent {{ $labels.agent_id }}"
          description: "Agent {{ $labels.agent_id }} has failed {{ $value }} tasks/sec in the last 5 minutes"

      # Queue depth critical
      - alert: QueueDepthCritical
        expr: agent_queue_depth > 100
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Queue {{ $labels.queue_name }} depth critical"
          description: "Queue {{ $labels.queue_name }} has {{ $value }} pending messages"

      # Slow task execution
      - alert: SlowTaskExecution
        expr: histogram_quantile(0.95, agent_task_duration_seconds) > 60
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "95th percentile task duration exceeds 60s"
          description: "Agent {{ $labels.agent_id }} tasks are taking {{ $value }}s at p95"

      # Agent down
      - alert: AgentDown
        expr: up{job=~".*agent.*"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Agent service {{ $labels.job }} is down"
          description: "{{ $labels.job }} has been unreachable for 1 minute"
```

### Grafana Dashboard Configuration (`config/grafana/dashboards/agent-overview.json`)

```json
{
  "dashboard": {
    "title": "Agent Orchestration - Overview",
    "tags": ["agents", "orchestration"],
    "timezone": "browser",
    "panels": [
      {
        "id": 1,
        "title": "Task Success Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(agent_task_success_total[5m])",
            "legendFormat": "{{agent_id}}"
          }
        ]
      },
      {
        "id": 2,
        "title": "Task Failure Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(agent_task_failure_total[5m])",
            "legendFormat": "{{agent_id}} - {{error_type}}"
          }
        ]
      },
      {
        "id": 3,
        "title": "Task Duration (p95)",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, agent_task_duration_seconds)",
            "legendFormat": "{{agent_id}}"
          }
        ]
      },
      {
        "id": 4,
        "title": "Queue Depth",
        "type": "graph",
        "targets": [
          {
            "expr": "agent_queue_depth",
            "legendFormat": "{{queue_name}}"
          }
        ]
      },
      {
        "id": 5,
        "title": "Active Agents",
        "type": "stat",
        "targets": [
          {
            "expr": "count(up{job=~\".*agent.*\"} == 1)"
          }
        ]
      }
    ]
  }
}
```

---

## Docker Compose Integration

### Additional Services for Monitoring

```yaml
# Add to docker-compose.yml

services:
  # ... existing services ...

  # Monitoring Collector
  monitoring-collector:
    build:
      context: .
      dockerfile: Dockerfile.monitoring-collector
    container_name: monitoring-collector
    environment:
      - METRICS_PORT=9090
    ports:
      - "9090:9090"
    networks:
      - agent-network
    depends_on:
      - state-manager
      - config-service
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9090/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Prometheus
  prometheus:
    image: prom/prometheus:v2.45.0
    container_name: prometheus
    volumes:
      - ./config/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - ./config/prometheus/alerts.yml:/etc/prometheus/alerts.yml:ro
      - prometheus-data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=15d'
      - '--web.enable-lifecycle'
    ports:
      - "9091:9090"
    networks:
      - agent-network
    restart: unless-stopped

  # Grafana
  grafana:
    image: grafana/grafana:10.0.0
    container_name: grafana
    volumes:
      - ./config/grafana/dashboards:/etc/grafana/provisioning/dashboards:ro
      - ./config/grafana/datasources:/etc/grafana/provisioning/datasources:ro
      - grafana-data:/var/lib/grafana
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD:-admin}
      - GF_USERS_ALLOW_SIGN_UP=false
      - GF_SERVER_ROOT_URL=http://localhost:3000
    ports:
      - "3000:3000"
    networks:
      - agent-network
    depends_on:
      - prometheus
    restart: unless-stopped

  # RabbitMQ Exporter (for Prometheus)
  rabbitmq-exporter:
    image: kbudde/rabbitmq-exporter:v1.0.0-RC19
    container_name: rabbitmq-exporter
    environment:
      - RABBIT_URL=http://rabbitmq:15672
      - RABBIT_USER=${RABBITMQ_USER}
      - RABBIT_PASSWORD=${RABBITMQ_PASSWORD}
    ports:
      - "9419:9419"
    networks:
      - agent-network
    depends_on:
      - rabbitmq

  # PostgreSQL Exporter
  postgres-exporter:
    image: prometheuscommunity/postgres-exporter:v0.13.0
    container_name: postgres-exporter
    environment:
      - DATA_SOURCE_NAME=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}?sslmode=disable
    ports:
      - "9187:9187"
    networks:
      - agent-network
    depends_on:
      - postgres

  # Redis Exporter
  redis-exporter:
    image: oliver006/redis_exporter:v1.52.0
    container_name: redis-exporter
    environment:
      - REDIS_ADDR=redis://redis:6379
    ports:
      - "9121:9121"
    networks:
      - agent-network
    depends_on:
      - redis

volumes:
  prometheus-data:
    driver: local
  grafana-data:
    driver: local
```

### Grafana Datasource Configuration (`config/grafana/datasources/prometheus.yml`)

```yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false
```

---

## Migration Path from Simple Logging to Full Monitoring

### Phase 1: Preparation (1-2 weeks)
1. Review current structured logging implementation
2. Identify key metrics to track (task duration, failure rates, queue depths)
3. Define alert thresholds and notification channels
4. Design Grafana dashboards based on operational needs

### Phase 2: MonitoringCollector Implementation (1 week)
1. Implement `MonitoringCollector` class with Prometheus metrics
2. Update all components to inject `MonitoringCollector` dependency
3. Add metric recording calls to critical paths (task execution, event processing)
4. Test `/metrics` endpoint locally

### Phase 3: Infrastructure Deployment (1 week)
1. Add Prometheus, Grafana, and exporter services to docker-compose.yml
2. Create Prometheus configuration with scrape targets
3. Deploy and verify metrics collection
4. Configure persistent volumes for time-series data

### Phase 4: Dashboard and Alerting (1 week)
1. Create Grafana dashboards for agent health, throughput, errors
2. Implement Prometheus alert rules
3. Configure alert notifications (Slack, email, PagerDuty)
4. Test end-to-end alerting workflow

### Phase 5: Validation and Tuning (1 week)
1. Run load tests and validate metrics accuracy
2. Tune scrape intervals and retention policies
3. Refine alert thresholds based on baseline behavior
4. Document operational runbooks for common alerts

**Total Estimated Time**: 5-6 weeks

---

## Benefits of Adding Full Monitoring

1. **Real-time Visibility**: See system health at a glance through Grafana dashboards
2. **Proactive Alerting**: Get notified of issues before they impact users
3. **Performance Analysis**: Identify bottlenecks and optimization opportunities through metrics
4. **Capacity Planning**: Use historical metrics to predict scaling needs
5. **Debugging Support**: Correlate logs with metrics using trace IDs
6. **Compliance**: Meet observability requirements for production systems

---

## Alternative Monitoring Solutions

If Prometheus/Grafana is not preferred, consider these alternatives:

### Datadog
- **Pros**: SaaS, minimal infrastructure, AI-powered anomaly detection
- **Cons**: Cost scales with volume, vendor lock-in
- **Integration**: Replace `prometheus_client` with `datadog` SDK

### New Relic
- **Pros**: APM + infrastructure monitoring, distributed tracing built-in
- **Cons**: Expensive at scale, complex pricing model
- **Integration**: Use New Relic Python agent

### ELK Stack (Elasticsearch, Logstash, Kibana)
- **Pros**: Excellent for log analysis, full-text search, free and open-source
- **Cons**: Resource-intensive, complex to operate
- **Integration**: Ship structured JSON logs to Logstash

### Loki + Grafana
- **Pros**: Lightweight, designed for logs (not metrics), integrates with Grafana
- **Cons**: Less mature than ELK, limited query language
- **Integration**: Replace Prometheus with Loki for log aggregation

---

## Summary

This document preserves the complete design for advanced monitoring infrastructure that was deferred from Version 1.2. When the system is ready to scale to production, this document provides:

- Complete component specification for `MonitoringCollector`
- 7 implementation tasks with file paths and requirements traceability
- Production-ready Prometheus and Grafana configurations
- Docker Compose integration with exporters for RabbitMQ, PostgreSQL, Redis
- Migration path from simple logging to full observability
- Alternative monitoring solutions for different operational needs

**Current State (Version 1.2)**:
- StructuredLogger utility with trace IDs for observability
- Pluggable LLM provider architecture (AWS Bedrock, OpenAI, Anthropic, Ollama) - **Implemented in main spec**

**Future State (After Monitoring Enhancement)**:
- Full observability with Prometheus metrics, Grafana dashboards, and proactive alerting
- Centralized log aggregation and distributed tracing

**Estimated Implementation Effort**: 5-6 weeks (part-time) or 3-4 weeks (full-time)
