"""
Test script for ConfigurationService functionality.
"""

import time
from pathlib import Path

from dotenv import load_dotenv

from src.config import AgentType, ConfigurationService, ExecutionMode

# Load environment variables
load_dotenv()


def main():
    print("=" * 60)
    print("Testing ConfigurationService Implementation")
    print("=" * 60)

    # Test 1: Initialize ConfigurationService
    print("\n1. Initializing ConfigurationService...")
    try:
        config_service = ConfigurationService(
            config_dir="config/agents",
            enable_hot_reload=True
        )
        print("✓ ConfigurationService initialized")
        print(f"  - Config directory: {config_service.config_dir}")
        print(f"  - Hot-reload enabled: {config_service.enable_hot_reload}")
    except Exception as e:
        print(f"✗ Failed to initialize ConfigurationService: {e}")
        return

    # Test 2: Check loaded configurations
    print("\n2. Checking loaded configurations...")
    all_configs = config_service.get_all_configs()
    print(f"✓ Loaded {len(all_configs)} agent configurations:")
    for name, config in all_configs.items():
        print(f"  - {name}")
        print(f"      Type: {config.agent_type}")
        print(f"      Execution Mode: {config.execution_mode}")
        print(f"      LLM: {config.llm_config.provider} / {config.llm_config.model}")
        print(f"      Enabled: {config.enabled}")

    # Test 3: Configuration errors
    print("\n3. Checking configuration errors...")
    errors = config_service.get_configuration_errors()
    if errors:
        print(f"✗ Found {len(errors)} configuration errors:")
        for name, error in errors.items():
            print(f"  - {name}: {error}")
    else:
        print("✓ No configuration errors")

    # Test 4: Get specific agent config
    print("\n4. Testing get_agent_config()...")
    if all_configs:
        agent_name = list(all_configs.keys())[0]
        config = config_service.get_agent_config(agent_name)
        if config:
            print(f"✓ Retrieved configuration for: {agent_name}")
            print(f"  - Description: {config.description}")
            print(f"  - Version: {config.version}")
            print(f"  - Tags: {config.tags}")
        else:
            print(f"✗ Failed to retrieve configuration for: {agent_name}")
    else:
        print("⚠ No configurations to retrieve")

    # Test 5: Filter by agent type
    print("\n5. Testing get_agents_by_type()...")
    for agent_type in [AgentType.AUTONOMOUS, AgentType.COLLABORATIVE, AgentType.CONTINUOUS]:
        agents = config_service.get_agents_by_type(agent_type.value)
        print(f"  - {agent_type.value}: {len(agents)} agent(s)")
        for agent in agents:
            print(f"      • {agent.name}")

    # Test 6: Filter by execution mode
    print("\n6. Testing get_agents_by_execution_mode()...")
    for mode in [ExecutionMode.EVENT_DRIVEN, ExecutionMode.SCHEDULED, ExecutionMode.CONTINUOUS]:
        agents = config_service.get_agents_by_execution_mode(mode.value)
        print(f"  - {mode.value}: {len(agents)} agent(s)")
        for agent in agents:
            print(f"      • {agent.name}")

    # Test 7: Get enabled agents
    print("\n7. Testing get_enabled_agents()...")
    enabled_agents = config_service.get_enabled_agents()
    print(f"✓ Found {len(enabled_agents)} enabled agents")

    # Test 8: Platform configuration
    print("\n8. Testing platform configuration...")
    platform_config = config_service.platform_config
    print("✓ Platform configuration loaded:")
    print(f"  - Environment: {platform_config.environment}")
    print(f"  - Log level: {platform_config.log_level}")
    print(f"  - Debug mode: {platform_config.debug}")
    print(f"  - State Manager URL: {platform_config.state_manager_url}")

    # Test 9: Health check
    print("\n9. Testing health_check()...")
    health = config_service.health_check()
    print(f"✓ ConfigurationService health check:")
    print(f"  - Status: {health['status']}")
    print(f"  - Loaded configs: {health['loaded_configs']}")
    print(f"  - Config errors: {health['config_errors']}")
    print(f"  - Hot-reload enabled: {health['hot_reload_enabled']}")
    print(f"  - Watcher running: {health['watcher_running']}")

    # Test 10: Hot-reload (create a new config file)
    print("\n10. Testing hot-reload functionality...")
    print("  Creating test configuration file...")

    test_config_path = Path("config/agents/test_agent.yaml")
    test_config_content = """
name: test_agent
description: "Test agent for hot-reload"
version: "1.0.0"
agent_type: autonomous
execution_mode: on_demand

llm_config:
  provider: aws_bedrock
  model: "anthropic.claude-3-haiku-20240307-v1:0"
  temperature: 0.7
  max_tokens: 1024

enabled: true
tags:
  - test
"""

    with open(test_config_path, "w") as f:
        f.write(test_config_content)

    print("  Waiting for hot-reload to detect new file...")
    time.sleep(2)  # Wait for file watcher to detect

    # Check if new config was loaded
    test_config = config_service.get_agent_config("test_agent")
    if test_config:
        print("✓ Hot-reload successfully detected new configuration!")
        print(f"  - Agent: {test_config.name}")
        print(f"  - Description: {test_config.description}")
    else:
        print("✗ Hot-reload did not detect new configuration")

    # Clean up test file
    print("  Cleaning up test file...")
    test_config_path.unlink()
    time.sleep(1)

    # Test 11: Validate configuration
    print("\n11. Testing configuration validation...")

    # Valid configuration
    valid_config = {
        "name": "valid_test",
        "agent_type": "autonomous",
        "execution_mode": "on_demand",
        "llm_config": {
            "provider": "aws_bedrock",
            "model": "test-model",
            "temperature": 0.7,
            "max_tokens": 1024
        }
    }

    is_valid, error = config_service.validate_configuration(valid_config)
    if is_valid:
        print("✓ Valid configuration passed validation")
    else:
        print(f"✗ Valid configuration failed: {error}")

    # Invalid configuration (missing required fields)
    invalid_config = {
        "name": "invalid_test",
        "agent_type": "autonomous"
        # Missing execution_mode and llm_config
    }

    is_valid, error = config_service.validate_configuration(invalid_config)
    if not is_valid:
        print("✓ Invalid configuration correctly rejected")
        print(f"  - Error: {str(error)[:100]}...")
    else:
        print("✗ Invalid configuration incorrectly passed")

    # Test 12: Context manager
    print("\n12. Testing context manager...")
    with ConfigurationService(config_dir="config/agents", enable_hot_reload=False) as service:
        print(f"✓ Context manager working")
        print(f"  - Loaded {len(service.get_all_configs())} configs")

    print("\n13. Stopping ConfigurationService...")
    config_service.stop()
    print("✓ ConfigurationService stopped")

    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
