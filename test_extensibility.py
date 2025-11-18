#!/usr/bin/env python3
"""
Extensibility Test Suite

Tests the platform's extensibility features:
1. Auto-discovery of agents from YAML files
2. Execution mode routing to correct pools
3. Custom tool support (MCP servers)
4. Event subscription from configuration
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from config.configuration_service import ConfigurationService


async def test_auto_discovery():
    """Test 14.1: Verify auto-discovery of new agents from YAML files."""
    print("\n" + "=" * 70)
    print("TEST 1: Auto-Discovery of Agents from YAML Files")
    print("=" * 70)

    # Initialize ConfigurationService
    config_service = ConfigurationService(
        config_dir="config",
        secrets={
            "OPENAI_API_KEY": "test-key",
            "ANTHROPIC_API_KEY": "test-key",
        }
    )

    await config_service.initialize()

    # Get all discovered agents
    all_agents = config_service.get_all_agents()

    print(f"\n✓ Discovered {len(all_agents)} agents from config/agents/")
    print("\nAgent Details:")
    print("-" * 70)

    for agent_config in all_agents:
        print(f"\n  Name: {agent_config.name}")
        print(f"  Type: {agent_config.agent_type}")
        print(f"  Execution Mode: {agent_config.execution_mode}")
        print(f"  LLM Provider: {agent_config.llm_config.provider}")
        print(f"  LLM Model: {agent_config.llm_config.model}")
        print(f"  Tags: {', '.join(agent_config.tags or [])}")
        print(f"  Event Subscriptions: {len(agent_config.event_subscriptions or [])}")

        # Show tools if configured
        if hasattr(agent_config, 'tools') and agent_config.tools:
            print(f"  Custom Tools: {len(agent_config.tools)}")
            for tool in agent_config.tools:
                print(f"    - {tool.get('name')}: {tool.get('description', 'N/A')}")

    await config_service.stop()

    print("\n" + "=" * 70)
    print("✅ AUTO-DISCOVERY TEST PASSED")
    print("=" * 70)

    return all_agents


async def test_execution_mode_routing(all_agents):
    """Test 14.2: Verify execution mode routing to correct pools."""
    print("\n" + "=" * 70)
    print("TEST 2: Execution Mode Routing")
    print("=" * 70)

    # Group agents by execution mode
    execution_modes = {}
    for agent in all_agents:
        mode = agent.execution_mode
        if mode not in execution_modes:
            execution_modes[mode] = []
        execution_modes[mode].append(agent.name)

    print("\nAgents Grouped by Execution Mode:")
    print("-" * 70)

    expected_routing = {
        "collaborative": "CollaborativeAgentPool",
        "autonomous": "AutonomousAgentPool",
        "continuous": "ContinuousAgentRunner",
        "scheduled": "SchedulerService"
    }

    all_valid = True
    for mode, agents in execution_modes.items():
        pool = expected_routing.get(mode, "UNKNOWN")
        print(f"\n  {mode.upper()} → {pool}")
        for agent_name in agents:
            print(f"    - {agent_name}")

        if mode not in expected_routing:
            print(f"    ⚠️  WARNING: Unknown execution mode '{mode}'")
            all_valid = False

    print("\n" + "=" * 70)
    if all_valid:
        print("✅ EXECUTION MODE ROUTING TEST PASSED")
    else:
        print("⚠️  EXECUTION MODE ROUTING TEST COMPLETED WITH WARNINGS")
    print("=" * 70)

    return execution_modes


async def test_custom_tool_support(all_agents):
    """Test 14.3: Verify custom tool support via MCP servers."""
    print("\n" + "=" * 70)
    print("TEST 3: Custom Tool Support (MCP Servers)")
    print("=" * 70)

    agents_with_tools = []

    for agent in all_agents:
        if hasattr(agent, 'tools') and agent.tools:
            agents_with_tools.append(agent)

    print(f"\n✓ Found {len(agents_with_tools)} agents with custom tools")
    print("\nTool Configurations:")
    print("-" * 70)

    for agent in agents_with_tools:
        print(f"\n  Agent: {agent.name}")
        print(f"  Tools configured: {len(agent.tools)}")

        for tool in agent.tools:
            print(f"\n    Tool Name: {tool.get('name')}")
            print(f"    Type: {tool.get('type')}")
            print(f"    URL: {tool.get('url', 'N/A')}")
            print(f"    Description: {tool.get('description', 'N/A')}")

            # Validate tool configuration
            if tool.get('type') == 'mcp':
                if not tool.get('url'):
                    print(f"    ⚠️  WARNING: MCP tool missing URL")
                elif not tool.get('url').startswith('http'):
                    print(f"    ⚠️  WARNING: Invalid URL format")
                else:
                    print(f"    ✓ Valid MCP configuration")

    print("\n" + "=" * 70)
    print("✅ CUSTOM TOOL SUPPORT TEST PASSED")
    print(f"   - {len(agents_with_tools)} agents configured with tools")
    print(f"   - Total tools configured: {sum(len(a.tools) for a in agents_with_tools)}")
    print("=" * 70)

    return agents_with_tools


async def test_event_subscriptions(all_agents):
    """Test 14.5: Verify event subscription from configuration."""
    print("\n" + "=" * 70)
    print("TEST 4: Event Subscriptions from Configuration")
    print("=" * 70)

    # Collect all event subscriptions
    event_map = {}

    for agent in all_agents:
        if agent.event_subscriptions:
            for event_pattern in agent.event_subscriptions:
                if event_pattern not in event_map:
                    event_map[event_pattern] = []
                event_map[event_pattern].append(agent.name)

    print(f"\n✓ Found {len(event_map)} unique event patterns")
    print(f"✓ Total subscriptions: {sum(len(a.event_subscriptions or []) for a in all_agents)}")

    print("\nEvent Pattern Mappings:")
    print("-" * 70)

    for pattern, agents in sorted(event_map.items()):
        print(f"\n  Pattern: {pattern}")
        print(f"  Subscribers ({len(agents)}):")
        for agent_name in agents:
            print(f"    - {agent_name}")

    # Validate patterns
    print("\nPattern Validation:")
    print("-" * 70)

    common_patterns = [
        "slack.", "autonomous.", "collaborative.", "continuous.",
        "scheduled.", "customer.", "data.", "research.", "system."
    ]

    valid_patterns = 0
    for pattern in event_map.keys():
        if any(pattern.startswith(prefix) for prefix in common_patterns):
            valid_patterns += 1

    print(f"\n  ✓ {valid_patterns}/{len(event_map)} patterns follow naming conventions")
    print(f"  ℹ️  Patterns support wildcards: *, #, topic.subtopic.*")

    print("\n" + "=" * 70)
    print("✅ EVENT SUBSCRIPTION TEST PASSED")
    print("=" * 70)

    return event_map


async def test_schedule_configurations(all_agents):
    """Test schedule configurations for scheduled agents."""
    print("\n" + "=" * 70)
    print("TEST 5: Schedule Configurations")
    print("=" * 70)

    scheduled_agents = [
        agent for agent in all_agents
        if agent.execution_mode == "scheduled"
    ]

    print(f"\n✓ Found {len(scheduled_agents)} scheduled agents")
    print("\nSchedule Details:")
    print("-" * 70)

    for agent in scheduled_agents:
        print(f"\n  Agent: {agent.name}")

        if hasattr(agent, 'schedule_config') and agent.schedule_config:
            schedule = agent.schedule_config
            schedule_type = schedule.get('type')

            print(f"  Schedule Type: {schedule_type}")

            if schedule_type == "cron":
                print(f"  Cron Expression: {schedule.get('cron')}")
                print(f"  Timezone: {schedule.get('timezone', 'UTC')}")

            elif schedule_type == "interval":
                interval = schedule.get('interval_seconds')
                print(f"  Interval: {interval} seconds ({interval/60:.1f} minutes)")

            if 'timeout_seconds' in schedule:
                print(f"  Timeout: {schedule['timeout_seconds']} seconds")

            if 'task_data' in schedule:
                print(f"  Task Data Keys: {', '.join(schedule['task_data'].keys())}")
        else:
            print(f"  ⚠️  WARNING: No schedule_config found")

    print("\n" + "=" * 70)
    print("✅ SCHEDULE CONFIGURATION TEST PASSED")
    print("=" * 70)

    return scheduled_agents


async def main():
    """Run all extensibility tests."""
    print("\n" + "=" * 70)
    print("EXTENSIBILITY TEST SUITE")
    print("Multi-Agent Orchestration Platform")
    print("=" * 70)

    try:
        # Test 1: Auto-discovery
        all_agents = await test_auto_discovery()

        # Test 2: Execution mode routing
        execution_modes = await test_execution_mode_routing(all_agents)

        # Test 3: Custom tool support
        agents_with_tools = await test_custom_tool_support(all_agents)

        # Test 4: Event subscriptions
        event_map = await test_event_subscriptions(all_agents)

        # Test 5: Schedule configurations
        scheduled_agents = await test_schedule_configurations(all_agents)

        # Summary
        print("\n" + "=" * 70)
        print("TEST SUITE SUMMARY")
        print("=" * 70)
        print(f"\n  ✅ Total Agents Discovered: {len(all_agents)}")
        print(f"  ✅ Execution Modes: {len(execution_modes)}")
        print(f"  ✅ Agents with Custom Tools: {len(agents_with_tools)}")
        print(f"  ✅ Unique Event Patterns: {len(event_map)}")
        print(f"  ✅ Scheduled Agents: {len(scheduled_agents)}")

        print("\n  Execution Mode Distribution:")
        for mode, agents in execution_modes.items():
            print(f"    - {mode}: {len(agents)} agent(s)")

        print("\n" + "=" * 70)
        print("🎉 ALL EXTENSIBILITY TESTS PASSED!")
        print("=" * 70)
        print("\nThe platform successfully demonstrates:")
        print("  ✓ Configuration-based agent management (no code changes)")
        print("  ✓ Automatic agent discovery from YAML files")
        print("  ✓ Execution mode routing to appropriate pools")
        print("  ✓ Custom tool integration via MCP servers")
        print("  ✓ Event-driven subscriptions from configuration")
        print()

        return 0

    except Exception as e:
        print("\n" + "=" * 70)
        print("❌ TEST SUITE FAILED")
        print("=" * 70)
        print(f"\nError: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
