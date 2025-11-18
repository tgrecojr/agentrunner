# Future Performance and Scale Testing

**Status**: Deferred from Phase 14
**Estimated Effort**: 1-2 weeks
**Priority**: Medium (post-MVP)

## Overview

This document outlines performance and scale testing requirements that were moved from Phase 14 to future implementation. These tests validate the platform's ability to handle production-scale workloads.

## Deferred Test: 20+ Agent Scaling

**Original Requirement (14.4)**: Test agent scaling to 20+ agents with <5 second startup time

**Why Deferred**:
- Core functionality complete and validated
- Requires dedicated performance testing infrastructure
- Better suited for pre-production validation
- Docker environment needed for accurate testing

## Performance Testing Scope

### 1. Agent Scaling Tests

#### 1.1 Startup Time Benchmark
**Target**: All agents registered and healthy in <5 seconds

**Test Methodology**:
```python
# Test startup with varying agent counts
agent_counts = [5, 10, 15, 20, 25, 30]

for count in agent_counts:
    # Create N agent configurations
    # Start AgentOrchestrator
    # Measure time until all agents registered
    # Record memory and CPU usage
```

**Metrics to Collect**:
- Total startup time
- Per-agent registration time
- Memory consumption (RSS, heap)
- CPU utilization during startup
- Database connection pool usage
- RabbitMQ queue creation time

**Acceptance Criteria**:
- ✅ 20 agents: <5 seconds
- ✅ 30 agents: <7 seconds
- ✅ Memory growth: Linear O(n)
- ✅ No connection pool exhaustion

#### 1.2 Concurrent Execution Scaling
**Target**: Handle concurrent task execution across all agent pools

**Test Scenarios**:
```python
# Concurrent collaborative tasks
test_scenarios = [
    ("collaborative", 10, "complex_research"),
    ("autonomous", 50, "data_analysis"),
    ("continuous", 20, "customer_support"),
    ("scheduled", 15, "periodic_reports")
]
```

**Metrics to Collect**:
- Tasks per second (throughput)
- Average latency per execution mode
- P95/P99 latency
- Error rate under load
- Resource utilization (CPU, memory, network)

**Acceptance Criteria**:
- ✅ Collaborative: 5 tasks/sec sustained
- ✅ Autonomous: 20 tasks/sec sustained
- ✅ Continuous: 10 msgs/sec per agent
- ✅ Error rate: <1% under load

#### 1.3 Horizontal Scaling Validation
**Target**: Verify `docker-compose --scale` works correctly

**Test Commands**:
```bash
# Scale autonomous pool to 5 instances
docker-compose up -d --scale autonomous-agent-pool=5

# Verify load distribution
# Send 100 tasks, each instance should handle ~20

# Scale down to 2 instances
docker-compose up -d --scale autonomous-agent-pool=2

# Verify graceful handling of in-flight tasks
```

**Metrics to Collect**:
- Task distribution across instances
- Load balancing effectiveness (variance)
- Scale-up time
- Scale-down graceful shutdown time
- Lost tasks during scaling operations

**Acceptance Criteria**:
- ✅ Even distribution (±10% variance)
- ✅ Scale-up: <30 seconds
- ✅ Scale-down: No task loss
- ✅ Auto-recovery on instance failure

---

### 2. State Manager Performance

#### 2.1 Redis Cache Hit Rate
**Target**: >90% cache hit rate for agent state

**Test Methodology**:
```python
# Simulate 1000 state reads
# Measure Redis hits vs PostgreSQL fallbacks
cache_hit_rate = redis_hits / total_reads
```

**Metrics**:
- Cache hit rate
- Redis latency (avg, p95, p99)
- PostgreSQL latency when cache misses
- Eviction rate

**Acceptance Criteria**:
- ✅ Hit rate: >90%
- ✅ Redis latency: <5ms (p95)
- ✅ PG latency: <50ms (p95)

#### 2.2 State Persistence Under Load
**Target**: Handle continuous agent state saves without blocking

**Test Scenarios**:
- 20 continuous agents
- Each saves state every 3 minutes
- Simulate 8-hour workday (160 saves/agent)

**Metrics**:
- Write throughput (saves/second)
- Write latency
- Database connection pool saturation
- Lock contention

**Acceptance Criteria**:
- ✅ No blocking on state saves
- ✅ Write latency: <100ms (p95)
- ✅ No connection pool exhaustion

---

### 3. EventBus Throughput

#### 3.1 Message Publishing Rate
**Target**: Handle peak load from all agent types

**Test Methodology**:
```python
# Simulate peak load scenario
publish_rates = {
    "slack_events": 100/sec,
    "task_submissions": 50/sec,
    "agent_results": 50/sec,
    "scheduled_tasks": 10/sec
}
# Total: 210 messages/second
```

**Metrics**:
- Messages published/second
- Message delivery latency
- Queue depth over time
- Consumer lag
- RabbitMQ memory usage

**Acceptance Criteria**:
- ✅ Sustained: 200 msgs/sec
- ✅ Burst: 500 msgs/sec for 1 minute
- ✅ Delivery latency: <100ms (p95)
- ✅ No queue buildup

#### 3.2 Event Delivery Guarantees
**Target**: Verify at-least-once delivery under failure scenarios

**Test Scenarios**:
1. Consumer crashes mid-processing
2. Network partition
3. RabbitMQ restart
4. Publisher crashes after send

**Metrics**:
- Message loss rate
- Duplicate delivery rate
- Recovery time after failure

**Acceptance Criteria**:
- ✅ Zero message loss
- ✅ Duplicates handled gracefully
- ✅ Recovery: <60 seconds

---

### 4. Resource Utilization

#### 4.1 Memory Consumption
**Target**: Predictable memory growth with agent count

**Test Methodology**:
```bash
# Baseline
measure_memory baseline

# Add 10 agents
add_agents 10
measure_memory after_10

# Add 10 more agents
add_agents 10
measure_memory after_20

# Calculate per-agent overhead
```

**Metrics**:
- Memory per agent (avg)
- Memory leak detection (long-running)
- Garbage collection frequency

**Acceptance Criteria**:
- ✅ Per-agent overhead: <50MB
- ✅ No memory leaks over 24 hours
- ✅ GC pauses: <50ms

#### 4.2 CPU Utilization
**Target**: Efficient CPU usage under load

**Metrics**:
- CPU % at idle
- CPU % under load
- CPU % during agent startup
- Thread pool saturation

**Acceptance Criteria**:
- ✅ Idle: <5% CPU
- ✅ Load: 50-70% CPU (headroom for bursts)
- ✅ No thread pool exhaustion

---

### 5. Portia AI Integration Performance

#### 5.1 LLM API Latency
**Target**: Track and optimize LLM provider performance

**Metrics by Provider**:
```python
providers = ["openai", "anthropic", "bedrock", "ollama"]
for provider in providers:
    measure_latency(
        "time_to_first_token",
        "total_completion_time",
        "token_throughput"
    )
```

**Metrics**:
- Time to first token (TTFT)
- Total completion time
- Token throughput (tokens/sec)
- Error rate by provider

**Acceptance Criteria**:
- ✅ TTFT: <1 second (OpenAI, Anthropic)
- ✅ TTFT: <500ms (local Ollama)
- ✅ Error rate: <0.1%

#### 5.2 Concurrent LLM Requests
**Target**: Handle multiple simultaneous LLM calls

**Test Scenario**:
```python
# 10 agents, each making LLM call simultaneously
concurrent_requests = 10

# Measure impact on latency
# Verify no rate limit errors
```

**Metrics**:
- Concurrent request handling
- Rate limit errors
- Retry overhead
- Cost tracking accuracy

**Acceptance Criteria**:
- ✅ 10 concurrent: No degradation
- ✅ Rate limits handled gracefully
- ✅ Cost tracking: 100% accurate

---

### 6. End-to-End Performance

#### 6.1 Slack-to-Response Latency
**Target**: <3 seconds for simple queries

**Test Flow**:
```
Slack webhook received
    ↓ (signature verification)
SlackGateway publishes event (<100ms)
    ↓ (EventBus routing)
Agent processes request
    ↓ (LLM call + execution)
Response sent to Slack
    ↓
TOTAL TIME: Target <3 seconds
```

**Metrics**:
- Total end-to-end latency
- Breakdown by component
- P50, P95, P99 latencies

**Acceptance Criteria**:
- ✅ Simple query: <3 seconds (p95)
- ✅ Complex task: <10 seconds (p95)

#### 6.2 Scheduled Task Accuracy
**Target**: Tasks execute within 1 second of schedule

**Test Scenarios**:
- Cron: Daily at specific time
- Interval: Every 5 minutes

**Metrics**:
- Schedule drift over time
- Missed executions
- Duplicate executions

**Acceptance Criteria**:
- ✅ Drift: <1 second
- ✅ Missed: 0%
- ✅ Duplicates: 0%

---

## Testing Tools and Infrastructure

### Recommended Tools

**Load Testing**:
- **Locust**: HTTP load testing (API endpoints)
- **k6**: Performance testing with scripting
- **Artillery**: Complex scenario testing

**Metrics Collection**:
- **Prometheus**: Time-series metrics
- **Grafana**: Visualization and dashboards
- **Jaeger**: Distributed tracing

**Profiling**:
- **py-spy**: Python profiling
- **memory_profiler**: Memory leak detection
- **cProfile**: CPU profiling

### Test Infrastructure Requirements

**Hardware**:
- 8 CPU cores minimum
- 16GB RAM
- SSD storage
- Dedicated network

**Software**:
- Docker with 8GB RAM allocated
- Docker Compose 2.x
- Python 3.11+
- PostgreSQL 15
- Redis 7
- RabbitMQ 3.12

### Test Data Generation

```python
# Generate test agent configurations
def generate_test_agents(count: int):
    """Generate N test agent configs"""
    for i in range(count):
        create_agent_yaml(
            name=f"test-agent-{i}",
            execution_mode=random.choice([
                "collaborative",
                "autonomous",
                "continuous",
                "scheduled"
            ])
        )

# Generate test workload
def generate_workload(duration_seconds: int, rate: int):
    """Generate sustained workload"""
    start_time = time.time()
    while time.time() - start_time < duration_seconds:
        submit_task()
        time.sleep(1.0 / rate)
```

---

## Test Execution Plan

### Phase 1: Baseline Metrics (1 day)
1. Measure single-agent performance
2. Establish baseline resource usage
3. Document current limitations

### Phase 2: Scale Testing (2 days)
1. Test 5, 10, 15, 20, 25, 30 agents
2. Measure startup time and resource growth
3. Identify bottlenecks

### Phase 3: Load Testing (2 days)
1. Simulate production workload patterns
2. Test concurrent execution
3. Validate horizontal scaling

### Phase 4: Stress Testing (1 day)
1. Push beyond expected limits
2. Identify breaking points
3. Verify graceful degradation

### Phase 5: Soak Testing (2 days)
1. Run at 80% capacity for 24 hours
2. Monitor for memory leaks
3. Check for resource exhaustion

### Phase 6: Failure Testing (1 day)
1. Simulate component failures
2. Verify recovery mechanisms
3. Test failover scenarios

---

## Success Criteria

### Minimum Viable Performance

| Metric | Target | Critical |
|--------|--------|----------|
| Agent Count | 20+ | ✅ |
| Startup Time | <5s for 20 agents | ✅ |
| Task Throughput | 100 tasks/sec | ✅ |
| End-to-End Latency | <3s (p95) | ✅ |
| Uptime | 99.9% | ✅ |
| Data Loss | 0% | ✅ |

### Production-Ready Performance

| Metric | Target | Nice-to-Have |
|--------|--------|--------------|
| Agent Count | 50+ | ⭐ |
| Startup Time | <10s for 50 agents | ⭐ |
| Task Throughput | 500 tasks/sec | ⭐ |
| Cache Hit Rate | >95% | ⭐ |
| Memory per Agent | <30MB | ⭐ |

---

## Optimization Opportunities

### Identified Areas for Improvement

**If startup time >5 seconds with 20 agents**:
- Parallel agent initialization
- Lazy loading of agent resources
- Connection pool pre-warming
- Configuration caching

**If throughput <100 tasks/sec**:
- Increase worker processes
- Optimize database queries
- Add Redis caching layers
- Batch event publishing

**If memory >50MB per agent**:
- Conversation history pruning
- State compression
- Shared resource pools
- Garbage collection tuning

---

## Next Steps

1. **Set up test environment** (Docker cluster with monitoring)
2. **Implement test scripts** (Locust scenarios, k6 tests)
3. **Run baseline tests** (Single agent, minimal load)
4. **Execute scale tests** (5, 10, 15, 20, 25, 30 agents)
5. **Analyze results** (Identify bottlenecks, optimization opportunities)
6. **Iterate** (Optimize, retest, validate improvements)
7. **Document findings** (Performance report, tuning guide)

---

## Cost Estimation

**Infrastructure**: $200-500/month for test environment
**LLM API Costs**: $100-300/month for load testing
**Personnel**: 1-2 weeks of engineering time
**Total**: ~$500-1000 for complete performance validation

---

## Conclusion

Performance and scale testing is critical for production readiness but can be deferred until core functionality is validated. The platform architecture supports horizontal scaling and has been designed with performance in mind.

**Recommended Timeline**:
- MVP Launch: Skip performance testing
- Beta Release: Basic scale testing (20 agents)
- Production Launch: Full performance validation
- Ongoing: Continuous performance monitoring

---

**Document Status**: Planning
**Last Updated**: 2025-11-18
**Next Review**: Before production deployment
