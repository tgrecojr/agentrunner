"""
Autonomous Agent Pool

Manages autonomous agents that execute tasks in isolation with load balancing.

Features:
- Isolated task execution (no state sharing)
- Round-robin load balancing across instances
- Automatic retry on failure (max 2 retries)
- Result persistence per agent/execution
- Event-driven task consumption
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from portia_sdk.agent import Agent as PortiaAgent

from ..config.configuration_service import ConfigurationService
from ..config.models import AgentConfig
from ..messaging.event_bus import EventBus
from ..messaging.events import Event, EventType
from ..state.state_manager import StateManager
from ..utils.logger import StructuredLogger


class TaskStatus(Enum):
    """Task execution status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class AutonomousTask:
    """Autonomous task execution."""
    task_id: str
    agent_name: str
    execution_id: str
    task_data: Dict[str, Any]
    status: TaskStatus = TaskStatus.PENDING
    retry_count: int = 0
    max_retries: int = 2
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    trace_id: Optional[str] = None


@dataclass
class AgentInstance:
    """Agent instance for load balancing."""
    instance_id: str
    agent_name: str
    agent_config: AgentConfig
    portia_agent: PortiaAgent
    task_count: int = 0
    last_task_time: Optional[float] = None


class RoundRobinLoadBalancer:
    """
    Round-robin load balancer for agent instances.

    Distributes tasks evenly across multiple instances of the same agent.
    """

    def __init__(self):
        """Initialize load balancer."""
        self.agent_instances: Dict[str, List[AgentInstance]] = {}
        self.current_index: Dict[str, int] = {}
        self.logger = StructuredLogger("RoundRobinLoadBalancer")

    def register_instance(self, instance: AgentInstance) -> None:
        """
        Register an agent instance.

        Args:
            instance: Agent instance to register
        """
        agent_name = instance.agent_name

        if agent_name not in self.agent_instances:
            self.agent_instances[agent_name] = []
            self.current_index[agent_name] = 0

        self.agent_instances[agent_name].append(instance)

        self.logger.info(
            f"Registered instance for agent {agent_name}",
            metadata={
                "agent_name": agent_name,
                "instance_id": instance.instance_id,
                "total_instances": len(self.agent_instances[agent_name])
            }
        )

    def get_agent_instance(self, agent_name: str) -> Optional[AgentInstance]:
        """
        Get next agent instance using round-robin.

        Args:
            agent_name: Name of the agent

        Returns:
            Next agent instance or None
        """
        if agent_name not in self.agent_instances:
            return None

        instances = self.agent_instances[agent_name]
        if not instances:
            return None

        # Get current index
        index = self.current_index[agent_name]

        # Select instance
        instance = instances[index]

        # Update index for next request (round-robin)
        self.current_index[agent_name] = (index + 1) % len(instances)

        return instance

    def get_instance_count(self, agent_name: str) -> int:
        """
        Get number of instances for an agent.

        Args:
            agent_name: Name of the agent

        Returns:
            Number of instances
        """
        if agent_name not in self.agent_instances:
            return 0
        return len(self.agent_instances[agent_name])


class AutonomousAgentPool:
    """
    Manages autonomous agents that execute tasks independently.

    Features:
    - Isolated execution context (no shared state)
    - Round-robin load balancing across instances
    - Automatic retry on failure
    - Event-driven task consumption
    """

    def __init__(
        self,
        config_service: ConfigurationService,
        state_manager: StateManager,
        event_bus: EventBus,
        max_retries: int = 2,
        retry_delay_seconds: int = 5
    ):
        """
        Initialize Autonomous Agent Pool.

        Args:
            config_service: Configuration service
            state_manager: State manager for persistence
            event_bus: Event bus for coordination
            max_retries: Maximum retry attempts per task
            retry_delay_seconds: Delay between retries
        """
        self.config_service = config_service
        self.state_manager = state_manager
        self.event_bus = event_bus
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds

        # Load balancer
        self.load_balancer = RoundRobinLoadBalancer()

        # Active tasks
        self.active_tasks: Dict[str, AutonomousTask] = {}

        # Logger
        self.logger = StructuredLogger("AutonomousAgentPool")

        self.logger.info(
            "AutonomousAgentPool initialized",
            metadata={
                "max_retries": max_retries,
                "retry_delay_seconds": retry_delay_seconds
            }
        )

    async def initialize(self) -> None:
        """Initialize the autonomous agent pool."""
        trace_id = StructuredLogger.generate_trace_id()

        self.logger.info(
            "Initializing AutonomousAgentPool",
            trace_id=trace_id
        )

        # Get all autonomous agents
        autonomous_agents = self.config_service.get_agents_by_type("autonomous")

        # Initialize agent instances
        for agent_config in autonomous_agents:
            await self.initialize_agent_instances(
                agent_config,
                num_instances=1,  # Start with 1 instance per agent
                trace_id=trace_id
            )

        # Subscribe to autonomous task events
        self.event_bus.subscribe(
            queue_name="autonomous_agent_pool",
            routing_patterns=["autonomous.task.submitted"],
            callback=self._handle_autonomous_task,
            auto_ack=False,
            enable_dlq=True
        )

        self.logger.info(
            f"AutonomousAgentPool initialized with {len(autonomous_agents)} agents",
            trace_id=trace_id
        )

    async def initialize_agent_instances(
        self,
        agent_config: AgentConfig,
        num_instances: int = 1,
        trace_id: Optional[str] = None
    ) -> List[AgentInstance]:
        """
        Initialize multiple instances of an agent for load balancing.

        Args:
            agent_config: Agent configuration
            num_instances: Number of instances to create
            trace_id: Optional trace ID for logging

        Returns:
            List of agent instances
        """
        trace_id = trace_id or StructuredLogger.generate_trace_id()

        self.logger.info(
            f"Initializing {num_instances} instances of {agent_config.name}",
            trace_id=trace_id,
            metadata={
                "agent_name": agent_config.name,
                "num_instances": num_instances
            }
        )

        instances = []

        for i in range(num_instances):
            try:
                instance_id = f"{agent_config.name}_instance_{i}"

                # Create Portia AI agent
                portia_agent = PortiaAgent(
                    name=agent_config.name,
                    model=agent_config.llm_config.model,
                    system_prompt=agent_config.system_prompt,
                    api_key=self.config_service.get_secret(
                        f"{agent_config.llm_config.provider.upper()}_API_KEY"
                    )
                )

                # Create instance
                instance = AgentInstance(
                    instance_id=instance_id,
                    agent_name=agent_config.name,
                    agent_config=agent_config,
                    portia_agent=portia_agent
                )

                # Register with load balancer
                self.load_balancer.register_instance(instance)

                instances.append(instance)

                self.logger.info(
                    f"Initialized instance: {instance_id}",
                    trace_id=trace_id,
                    metadata={
                        "agent_name": agent_config.name,
                        "instance_id": instance_id
                    }
                )

            except Exception as e:
                self.logger.error(
                    f"Failed to initialize instance {i} of {agent_config.name}: {str(e)}",
                    trace_id=trace_id
                )

        return instances

    async def execute_autonomous_task(
        self,
        agent_name: str,
        task_data: Dict[str, Any],
        execution_id: Optional[str] = None,
        trace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute an autonomous task with isolated context.

        Args:
            agent_name: Name of the agent
            task_data: Task data payload
            execution_id: Optional execution ID
            trace_id: Optional trace ID for logging

        Returns:
            Task execution result
        """
        trace_id = trace_id or StructuredLogger.generate_trace_id()
        execution_id = execution_id or str(uuid4())
        task_id = str(uuid4())

        # Create task
        task = AutonomousTask(
            task_id=task_id,
            agent_name=agent_name,
            execution_id=execution_id,
            task_data=task_data,
            status=TaskStatus.IN_PROGRESS,
            max_retries=self.max_retries,
            trace_id=trace_id
        )

        self.active_tasks[task_id] = task
        task.started_at = time.time()

        self.logger.info(
            f"Executing autonomous task for {agent_name}",
            trace_id=trace_id,
            metadata={
                "task_id": task_id,
                "execution_id": execution_id,
                "agent_name": agent_name
            }
        )

        try:
            # Get agent instance using load balancer
            instance = self.load_balancer.get_agent_instance(agent_name)
            if not instance:
                raise ValueError(f"No instances available for agent: {agent_name}")

            # Execute with Portia AI in isolated context
            # NOTE: Each execution gets a fresh context - no state sharing
            result = await instance.portia_agent.execute(
                prompt=task_data.get("prompt", ""),
                context={
                    "task_id": task_id,
                    "execution_id": execution_id,
                    "task_data": task_data
                }
            )

            # Update task
            task.result = result
            task.status = TaskStatus.COMPLETED
            task.completed_at = time.time()

            # Update instance stats
            instance.task_count += 1
            instance.last_task_time = time.time()

            # Persist result (isolated - keyed by agent_id and execution_id)
            await self._persist_result(task, trace_id)

            self.logger.info(
                f"Task completed successfully",
                trace_id=trace_id,
                metadata={
                    "task_id": task_id,
                    "execution_id": execution_id,
                    "agent_name": agent_name,
                    "instance_id": instance.instance_id,
                    "duration_seconds": task.completed_at - task.started_at
                }
            )

            # Cleanup
            del self.active_tasks[task_id]

            return {
                "task_id": task_id,
                "execution_id": execution_id,
                "agent_name": agent_name,
                "status": "completed",
                "result": result,
                "duration_seconds": task.completed_at - task.started_at
            }

        except Exception as e:
            self.logger.error(
                f"Task execution failed: {str(e)}",
                trace_id=trace_id,
                metadata={
                    "task_id": task_id,
                    "execution_id": execution_id,
                    "agent_name": agent_name,
                    "retry_count": task.retry_count
                }
            )

            task.error = str(e)
            task.status = TaskStatus.FAILED

            # Attempt retry
            return await self.retry_on_failure(task, trace_id)

    async def retry_on_failure(
        self,
        task: AutonomousTask,
        trace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Retry a failed task with fresh context.

        Args:
            task: Failed task
            trace_id: Optional trace ID for logging

        Returns:
            Retry result
        """
        trace_id = trace_id or task.trace_id or StructuredLogger.generate_trace_id()

        if task.retry_count >= task.max_retries:
            self.logger.error(
                f"Task failed after {task.max_retries} retries",
                trace_id=trace_id,
                metadata={
                    "task_id": task.task_id,
                    "execution_id": task.execution_id,
                    "agent_name": task.agent_name,
                    "error": task.error
                }
            )

            # Persist failed result
            task.completed_at = time.time()
            await self._persist_result(task, trace_id)

            # Cleanup
            if task.task_id in self.active_tasks:
                del self.active_tasks[task.task_id]

            # Publish failure event
            event = Event(
                event_type=EventType.TASK_FAILED,
                payload={
                    "task_id": task.task_id,
                    "execution_id": task.execution_id,
                    "agent_name": task.agent_name,
                    "error": task.error,
                    "retry_count": task.retry_count
                },
                trace_id=trace_id
            )

            self.event_bus.publish(
                event=event,
                routing_key=f"autonomous.task.failed.{task.agent_name}"
            )

            return {
                "task_id": task.task_id,
                "execution_id": task.execution_id,
                "agent_name": task.agent_name,
                "status": "failed",
                "error": task.error,
                "retry_count": task.retry_count
            }

        # Increment retry count
        task.retry_count += 1
        task.status = TaskStatus.RETRYING

        self.logger.info(
            f"Retrying task (attempt {task.retry_count}/{task.max_retries})",
            trace_id=trace_id,
            metadata={
                "task_id": task.task_id,
                "execution_id": task.execution_id,
                "agent_name": task.agent_name
            }
        )

        # Wait before retry
        await asyncio.sleep(self.retry_delay_seconds)

        # Retry with fresh context
        return await self.execute_autonomous_task(
            agent_name=task.agent_name,
            task_data=task.task_data,
            execution_id=task.execution_id,
            trace_id=trace_id
        )

    async def _persist_result(
        self,
        task: AutonomousTask,
        trace_id: str
    ) -> None:
        """
        Persist task result to StateManager.

        Args:
            task: Task to persist
            trace_id: Trace ID for logging
        """
        try:
            # Store result keyed by agent_id and execution_id (no state sharing)
            await self.state_manager.save_execution_result(
                agent_id=task.agent_name,
                execution_id=task.execution_id,
                status=task.status.value,
                result=task.result or {"error": task.error},
                execution_time=(task.completed_at - task.started_at) if task.completed_at and task.started_at else 0.0,
                trace_id=trace_id
            )

            self.logger.debug(
                f"Persisted result for task {task.task_id}",
                trace_id=trace_id
            )

        except Exception as e:
            self.logger.error(
                f"Failed to persist result: {str(e)}",
                trace_id=trace_id,
                metadata={
                    "task_id": task.task_id,
                    "execution_id": task.execution_id
                }
            )

    async def _handle_autonomous_task(self, event: Event) -> None:
        """
        Handle incoming autonomous task event.

        Args:
            event: Task event
        """
        try:
            payload = event.payload
            agent_name = payload.get("agent_name")
            execution_id = payload.get("execution_id")
            task_data = payload.get("task_data", {})

            if not agent_name:
                self.logger.error(
                    "Missing agent_name in task event",
                    trace_id=str(event.trace_id) if event.trace_id else None
                )
                return

            await self.execute_autonomous_task(
                agent_name=agent_name,
                task_data=task_data,
                execution_id=execution_id,
                trace_id=str(event.trace_id) if event.trace_id else None
            )

        except Exception as e:
            self.logger.error(
                f"Failed to handle autonomous task: {str(e)}",
                trace_id=str(event.trace_id) if event.trace_id else None
            )
