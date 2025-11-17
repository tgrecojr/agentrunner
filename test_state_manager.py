"""
Quick test script to verify StateManager functionality.
"""

import json
from uuid import uuid4

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from src.state import StateManager


def main():
    print("=" * 60)
    print("Testing StateManager Implementation")
    print("=" * 60)

    # Initialize StateManager
    print("\n1. Initializing StateManager...")
    state_manager = StateManager()
    print("✓ StateManager initialized")

    # Health check
    print("\n2. Running health check...")
    health = state_manager.health_check()
    print(f"Health status: {json.dumps(health, indent=2)}")

    # Test saving state
    print("\n3. Testing save_state...")
    agent_id = "test_agent_001"
    agent_name = "Test Agent"
    execution_id = uuid4()
    test_state = {
        "conversation_history": [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ],
        "context": {"user_id": "user123", "session_id": "session456"},
        "step": 5
    }

    saved_state = state_manager.save_state(
        agent_id=agent_id,
        agent_name=agent_name,
        execution_id=execution_id,
        state_data=test_state,
        metadata={"test": True}
    )
    print(f"✓ State saved with ID: {saved_state.id}")
    print(f"  - Compressed: {saved_state.compressed}")
    print(f"  - State version: {saved_state.state_version}")

    # Test loading state
    print("\n4. Testing load_state...")
    loaded_state = state_manager.load_state(agent_id, execution_id)
    if loaded_state == test_state:
        print("✓ State loaded successfully and matches original")
    else:
        print("✗ State mismatch!")
        print(f"Expected: {test_state}")
        print(f"Got: {loaded_state}")

    # Test latest state retrieval
    print("\n5. Testing load_latest_agent_state...")
    latest = state_manager.load_latest_agent_state(agent_id)
    if latest:
        latest_exec_id, latest_state = latest
        print(f"✓ Latest state retrieved")
        print(f"  - Execution ID: {latest_exec_id}")
        print(f"  - Matches current: {latest_exec_id == execution_id}")
    else:
        print("✗ No latest state found")

    # Test compression with large state
    print("\n6. Testing compression (large payload)...")
    large_state = {
        "large_data": ["x" * 1000 for _ in range(2000)]  # ~2MB
    }
    large_execution_id = uuid4()

    saved_large = state_manager.save_state(
        agent_id=agent_id,
        agent_name=agent_name,
        execution_id=large_execution_id,
        state_data=large_state,
    )
    print(f"✓ Large state saved")
    print(f"  - Compressed: {saved_large.compressed} (should be True)")
    print(f"  - Size: ~{len(json.dumps(large_state)) / 1024 / 1024:.2f}MB")

    # Load and verify large state
    loaded_large = state_manager.load_state(agent_id, large_execution_id)
    if loaded_large == large_state:
        print("✓ Compressed state loaded successfully")
    else:
        print("✗ Compressed state mismatch!")

    # Test execution result
    print("\n7. Testing save_execution_result...")
    from datetime import datetime, timedelta

    start_time = datetime.utcnow()
    end_time = start_time + timedelta(seconds=5)

    result = state_manager.save_execution_result(
        agent_id=agent_id,
        agent_name=agent_name,
        execution_id=execution_id,
        status="success",
        result_data={"output": "Task completed successfully"},
        execution_started_at=start_time,
        execution_completed_at=end_time,
        execution_duration_ms=5000,
        task_id="task_001",
    )
    print(f"✓ Execution result saved with ID: {result.id}")
    print(f"  - Status: {result.status}")
    print(f"  - Duration: {result.execution_duration_ms}ms")

    # Query execution results
    print("\n8. Testing get_execution_results...")
    results = state_manager.get_execution_results(agent_id=agent_id)
    print(f"✓ Found {len(results)} execution result(s)")
    for r in results:
        print(f"  - {r.status} @ {r.created_at}")

    # Test plan run state
    print("\n9. Testing collaborative plan run...")
    plan_id = uuid4()

    plan_run = state_manager.create_plan_run(
        plan_id=plan_id,
        plan_name="Test Collaborative Plan",
        plan_definition={
            "steps": [
                {"step": 1, "agent": "agent_1", "task": "analyze"},
                {"step": 2, "agent": "agent_2", "task": "process"},
                {"step": 3, "agent": "agent_3", "task": "summarize"}
            ]
        },
        total_steps=3,
        participating_agents=["agent_1", "agent_2", "agent_3"],
    )
    print(f"✓ Plan run created with ID: {plan_run.id}")
    print(f"  - Plan ID: {plan_run.plan_id}")
    print(f"  - Status: {plan_run.status}")
    print(f"  - Total steps: {plan_run.total_steps}")

    # Update plan run
    print("\n10. Testing update_plan_run_state...")
    updated = state_manager.update_plan_run_state(
        plan_id=plan_id,
        status="in_progress",
        current_step=1,
        execution_history=[
            {"step": 1, "agent": "agent_1", "status": "completed", "result": "Analysis done"}
        ]
    )
    if updated:
        print(f"✓ Plan run updated")
        print(f"  - Status: {updated.status}")
        print(f"  - Current step: {updated.current_step}")
        print(f"  - Started at: {updated.started_at}")
    else:
        print("✗ Plan run not found!")

    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
