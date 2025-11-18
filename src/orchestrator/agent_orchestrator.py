"""
Agent Orchestrator

Central orchestration component that manages all agents in the platform.

Features:
- Agent registration and lifecycle management
- Routing to appropriate pools based on execution mode
- Health monitoring and automatic restart
- Graceful shutdown with timeout
- Agent registry query and filtering
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from ..config.configuration_service import ConfigurationService
from ..config.models import AgentConfig
from ..messaging.event_bus import EventBus
from ..messaging.events import Event, EventType
from ..state.state_manager import StateManager
from ..utils.logger import StructuredLogger


class AgentStatus(Enum):
    """Agent status enumeration."""
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"
    SHUTDOWN = "shutdown"


@dataclass
class AgentMetadata:
    """Metadata for an agent."""
    agent_name: str
    agent_type: str
    execution_mode: str
    status: AgentStatus
    capabilities: List[str] = field(default_factory=list)
    event_subscriptions: List[str] = field(default_factory=list)
    last_heartbeat: Optional[float] = None
    restart_count: int = 0
    error_message: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


@dataclass
class AgentRegistration:
    """Complete agent registration including config and metadata."""
    config: AgentConfig
    metadata: AgentMetadata


class AgentOrchestrator:
    """
    Central orchestrator for managing all agents in the platform.

    Features:
    - Loads agent configurations from ConfigurationService
    - Maintains agent registry with status and metadata
    - Routes agents to appropriate pools based on execution_mode
    - Monitors agent health and restarts failed agents
    - Provides graceful shutdown with timeout
    """

    def __init__(
        self,
        config_service: ConfigurationService,
        state_manager: StateManager,
        event_bus: EventBus,
        max_restart_attempts: int = 3,
        health_check_interval: int = 60,
        shutdown_timeout: int = 30
    ):
        """
        Initialize Agent Orchestrator.

        Args:
            config_service: Configuration service for loading agent configs
            state_manager: State manager for persisting execution data
            event_bus: Event bus for publishing events
            max_restart_attempts: Maximum restart attempts for failed agents
            health_check_interval: Health check interval in seconds
            shutdown_timeout: Graceful shutdown timeout in seconds
        """
        self.config_service = config_service
        self.state_manager = state_manager
        self.event_bus = event_bus
        self.max_restart_attempts = max_restart_attempts
        self.health_check_interval = health_check_interval
        self.shutdown_timeout = shutdown_timeout

        # Agent registry
        self.agent_registry: Dict[str, AgentRegistration] = {}

        # Shutdown flag
        self._shutdown_requested = False

        # Health monitoring task
        self._health_monitor_task: Optional[asyncio.Task] = None

        # Logger
        self.logger = StructuredLogger("AgentOrchestrator")

        self.logger.info(
            "AgentOrchestrator initialized",
            metadata={
                "max_restart_attempts": max_restart_attempts,
                "health_check_interval": health_check_interval,
                "shutdown_timeout": shutdown_timeout
            }
        )

    async def initialize(self) -> None:
        """
        Initialize orchestrator by loading all agent configurations.

        Loads all enabled agents from ConfigurationService and registers them.
        """
        trace_id = StructuredLogger.generate_trace_id()

        self.logger.info(
            "Initializing AgentOrchestrator",
            trace_id=trace_id
        )

        try:
            # Load all enabled agent configurations
            enabled_agents = self.config_service.get_enabled_agents()

            self.logger.info(
                f"Found {len(enabled_agents)} enabled agent configurations",
                trace_id=trace_id,
                metadata={"agent_count": len(enabled_agents)}
            )

            # Register each agent
            for agent_config in enabled_agents:
                try:
                    await self.register_agent(agent_config, trace_id=trace_id)
                except Exception as e:
                    self.logger.error(
                        f"Failed to register agent {agent_config.name}: {str(e)}",
                        trace_id=trace_id,
                        metadata={"agent_name": agent_config.name}
                    )

            # Start health monitoring
            await self._start_health_monitoring()

            self.logger.info(
                f"AgentOrchestrator initialized with {len(self.agent_registry)} agents",
                trace_id=trace_id,
                metadata={"registered_agents": len(self.agent_registry)}
            )

        except Exception as e:
            self.logger.error(
                f"Failed to initialize AgentOrchestrator: {str(e)}",
                trace_id=trace_id
            )
            raise

    async def register_agent(
        self,
        agent_config: AgentConfig,
        trace_id: Optional[str] = None
    ) -> None:
        """
        Register an agent in the orchestrator.

        Args:
            agent_config: Agent configuration
            trace_id: Optional trace ID for logging
        """
        trace_id = trace_id or StructuredLogger.generate_trace_id()

        # Validate agent configuration
        if not agent_config.enabled:
            self.logger.warning(
                f"Attempted to register disabled agent: {agent_config.name}",
                trace_id=trace_id,
                metadata={"agent_name": agent_config.name}
            )
            return

        # Create agent metadata
        metadata = AgentMetadata(
            agent_name=agent_config.name,
            agent_type=agent_config.agent_type,
            execution_mode=agent_config.execution_mode,
            status=AgentStatus.INITIALIZING,
            capabilities=agent_config.tags or [],
            event_subscriptions=agent_config.event_subscriptions or []
        )

        # Create agent registration
        registration = AgentRegistration(
            config=agent_config,
            metadata=metadata
        )

        # Add to registry
        self.agent_registry[agent_config.name] = registration

        self.logger.info(
            f"Registered agent: {agent_config.name}",
            trace_id=trace_id,
            metadata={
                "agent_name": agent_config.name,
                "agent_type": agent_config.agent_type,
                "execution_mode": agent_config.execution_mode,
                "event_subscriptions": agent_config.event_subscriptions
            }
        )

        # Start the agent
        await self.start_agent(agent_config.name, trace_id=trace_id)

    async def start_agent(
        self,
        agent_name: str,
        trace_id: Optional[str] = None
    ) -> bool:
        """
        Start an agent.

        Args:
            agent_name: Name of the agent to start
            trace_id: Optional trace ID for logging

        Returns:
            True if agent started successfully, False otherwise
        """
        trace_id = trace_id or StructuredLogger.generate_trace_id()

        if agent_name not in self.agent_registry:
            self.logger.error(
                f"Agent not found in registry: {agent_name}",
                trace_id=trace_id,
                metadata={"agent_name": agent_name}
            )
            return False

        registration = self.agent_registry[agent_name]

        try:
            self.logger.info(
                f"Starting agent: {agent_name}",
                trace_id=trace_id,
                metadata={
                    "agent_name": agent_name,
                    "execution_mode": registration.config.execution_mode
                }
            )

            # Update status to ready
            registration.metadata.status = AgentStatus.READY
            registration.metadata.updated_at = time.time()
            registration.metadata.last_heartbeat = time.time()

            # Subscribe to events if event-driven
            if registration.config.execution_mode == "event_driven":
                await self._subscribe_agent_to_events(registration, trace_id=trace_id)

            # For continuous agents, start the runner
            elif registration.config.execution_mode == "continuous":
                await self._start_continuous_agent(registration, trace_id=trace_id)

            self.logger.info(
                f"Agent started successfully: {agent_name}",
                trace_id=trace_id,
                metadata={"agent_name": agent_name}
            )

            return True

        except Exception as e:
            self.logger.error(
                f"Failed to start agent {agent_name}: {str(e)}",
                trace_id=trace_id,
                metadata={"agent_name": agent_name}
            )

            # Mark agent as failed
            registration.metadata.status = AgentStatus.FAILED
            registration.metadata.error_message = str(e)
            registration.metadata.updated_at = time.time()

            return False

    async def invoke_agent(
        self,
        agent_name: str,
        task_data: Dict,
        trace_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Invoke an agent to execute a task.

        Args:
            agent_name: Name of the agent to invoke
            task_data: Task data payload
            trace_id: Optional trace ID for logging

        Returns:
            Execution ID if successful, None otherwise
        """
        trace_id = trace_id or StructuredLogger.generate_trace_id()

        if agent_name not in self.agent_registry:
            self.logger.error(
                f"Agent not found: {agent_name}",
                trace_id=trace_id,
                metadata={"agent_name": agent_name}
            )
            return None

        registration = self.agent_registry[agent_name]

        # Check if agent is ready
        if registration.metadata.status not in [AgentStatus.READY, AgentStatus.RUNNING]:
            self.logger.warning(
                f"Agent not ready: {agent_name} (status: {registration.metadata.status})",
                trace_id=trace_id,
                metadata={
                    "agent_name": agent_name,
                    "status": registration.metadata.status.value
                }
            )
            return None

        try:
            # Generate execution ID
            execution_id = f"{agent_name}_{int(time.time() * 1000)}"

            self.logger.info(
                f"Invoking agent: {agent_name}",
                trace_id=trace_id,
                metadata={
                    "agent_name": agent_name,
                    "execution_id": execution_id,
                    "execution_mode": registration.config.execution_mode
                }
            )

            # Update agent status
            registration.metadata.status = AgentStatus.RUNNING
            registration.metadata.updated_at = time.time()

            # Route to appropriate pool based on execution mode
            await self._route_to_pool(
                registration,
                task_data,
                execution_id,
                trace_id
            )

            # Record execution start in state manager
            await self.state_manager.save_execution_result(
                agent_id=agent_name,
                execution_id=execution_id,
                status="started",
                result={},
                execution_time=0.0,
                trace_id=trace_id
            )

            return execution_id

        except Exception as e:
            self.logger.error(
                f"Failed to invoke agent {agent_name}: {str(e)}",
                trace_id=trace_id,
                metadata={"agent_name": agent_name}
            )

            # Reset agent status back to ready
            registration.metadata.status = AgentStatus.READY
            registration.metadata.updated_at = time.time()

            return None

    async def health_check_agent(
        self,
        agent_name: str,
        trace_id: Optional[str] = None
    ) -> bool:
        """
        Check health of an agent.

        Args:
            agent_name: Name of the agent
            trace_id: Optional trace ID for logging

        Returns:
            True if agent is healthy, False otherwise
        """
        trace_id = trace_id or StructuredLogger.generate_trace_id()

        if agent_name not in self.agent_registry:
            return False

        registration = self.agent_registry[agent_name]

        # Check if agent has sent heartbeat within 60 seconds
        if registration.metadata.last_heartbeat is None:
            return True  # Agent just started, give it time

        time_since_heartbeat = time.time() - registration.metadata.last_heartbeat

        if time_since_heartbeat > self.health_check_interval:
            self.logger.warning(
                f"Agent unresponsive: {agent_name} (last heartbeat {time_since_heartbeat:.1f}s ago)",
                trace_id=trace_id,
                metadata={
                    "agent_name": agent_name,
                    "time_since_heartbeat": time_since_heartbeat
                }
            )
            return False

        return True

    async def restart_agent(
        self,
        agent_name: str,
        trace_id: Optional[str] = None
    ) -> bool:
        """
        Restart a failed agent.

        Args:
            agent_name: Name of the agent to restart
            trace_id: Optional trace ID for logging

        Returns:
            True if agent restarted successfully, False otherwise
        """
        trace_id = trace_id or StructuredLogger.generate_trace_id()

        if agent_name not in self.agent_registry:
            return False

        registration = self.agent_registry[agent_name]

        # Check restart count
        if registration.metadata.restart_count >= self.max_restart_attempts:
            self.logger.error(
                f"Agent exceeded max restart attempts: {agent_name}",
                trace_id=trace_id,
                metadata={
                    "agent_name": agent_name,
                    "restart_count": registration.metadata.restart_count,
                    "max_restart_attempts": self.max_restart_attempts
                }
            )

            # Mark as failed
            registration.metadata.status = AgentStatus.FAILED
            registration.metadata.updated_at = time.time()

            return False

        self.logger.info(
            f"Restarting agent: {agent_name} (attempt {registration.metadata.restart_count + 1})",
            trace_id=trace_id,
            metadata={
                "agent_name": agent_name,
                "restart_count": registration.metadata.restart_count
            }
        )

        # Increment restart count
        registration.metadata.restart_count += 1

        # Reset status
        registration.metadata.status = AgentStatus.INITIALIZING
        registration.metadata.updated_at = time.time()

        # Attempt restart
        success = await self.start_agent(agent_name, trace_id=trace_id)

        if success:
            self.logger.info(
                f"Agent restarted successfully: {agent_name}",
                trace_id=trace_id,
                metadata={"agent_name": agent_name}
            )
        else:
            self.logger.error(
                f"Failed to restart agent: {agent_name}",
                trace_id=trace_id,
                metadata={"agent_name": agent_name}
            )

        return success

    async def shutdown(self, timeout: Optional[int] = None) -> None:
        """
        Gracefully shutdown all agents.

        Args:
            timeout: Shutdown timeout in seconds (uses default if None)
        """
        timeout = timeout or self.shutdown_timeout
        trace_id = StructuredLogger.generate_trace_id()

        self.logger.info(
            f"Initiating graceful shutdown (timeout: {timeout}s)",
            trace_id=trace_id,
            metadata={"timeout": timeout}
        )

        # Set shutdown flag
        self._shutdown_requested = True

        # Stop health monitoring
        if self._health_monitor_task:
            self._health_monitor_task.cancel()
            try:
                await self._health_monitor_task
            except asyncio.CancelledError:
                pass

        # Notify all agents to complete current tasks
        shutdown_tasks = []
        for agent_name, registration in self.agent_registry.items():
            if registration.metadata.status in [AgentStatus.RUNNING, AgentStatus.READY]:
                shutdown_tasks.append(
                    self._shutdown_agent(agent_name, trace_id)
                )

        if shutdown_tasks:
            # Wait for agents to shutdown with timeout
            try:
                await asyncio.wait_for(
                    asyncio.gather(*shutdown_tasks, return_exceptions=True),
                    timeout=timeout
                )
                self.logger.info(
                    "All agents shut down gracefully",
                    trace_id=trace_id
                )
            except asyncio.TimeoutError:
                self.logger.warning(
                    f"Shutdown timeout exceeded ({timeout}s), forcing termination",
                    trace_id=trace_id
                )

                # Force termination of remaining agents
                for agent_name, registration in self.agent_registry.items():
                    if registration.metadata.status != AgentStatus.SHUTDOWN:
                        registration.metadata.status = AgentStatus.SHUTDOWN
                        registration.metadata.updated_at = time.time()

        self.logger.info(
            "AgentOrchestrator shutdown complete",
            trace_id=trace_id
        )

    def get_agent_registry(
        self,
        status: Optional[str] = None,
        agent_type: Optional[str] = None,
        execution_mode: Optional[str] = None
    ) -> Dict[str, Dict]:
        """
        Get agent registry snapshot with optional filtering.

        Args:
            status: Filter by agent status
            agent_type: Filter by agent type
            execution_mode: Filter by execution mode

        Returns:
            Dictionary of agent name -> agent info
        """
        registry = {}

        for agent_name, registration in self.agent_registry.items():
            # Apply filters
            if status and registration.metadata.status.value != status:
                continue
            if agent_type and registration.config.agent_type != agent_type:
                continue
            if execution_mode and registration.config.execution_mode != execution_mode:
                continue

            # Build agent info
            registry[agent_name] = {
                "name": agent_name,
                "type": registration.config.agent_type,
                "execution_mode": registration.config.execution_mode,
                "status": registration.metadata.status.value,
                "capabilities": registration.metadata.capabilities,
                "event_subscriptions": registration.metadata.event_subscriptions,
                "last_heartbeat": registration.metadata.last_heartbeat,
                "restart_count": registration.metadata.restart_count,
                "error_message": registration.metadata.error_message,
                "created_at": registration.metadata.created_at,
                "updated_at": registration.metadata.updated_at
            }

        return registry

    # Private helper methods

    async def _subscribe_agent_to_events(
        self,
        registration: AgentRegistration,
        trace_id: str
    ) -> None:
        """Subscribe agent to event bus topics."""
        if not registration.config.event_subscriptions:
            return

        try:
            # Create callback for this agent
            def event_callback(event: Event):
                # Use asyncio to run the async invoke_agent method
                import asyncio
                asyncio.create_task(
                    self.invoke_agent(
                        registration.config.name,
                        event.payload,
                        trace_id=str(event.trace_id) if event.trace_id else None
                    )
                )

            # Subscribe to all topic patterns for this agent
            queue_name = f"agent.{registration.config.name}"
            self.event_bus.subscribe(
                queue_name=queue_name,
                routing_patterns=registration.config.event_subscriptions,
                callback=event_callback,
                auto_ack=False,
                enable_dlq=True
            )

            self.logger.info(
                f"Subscribed agent {registration.config.name} to topics",
                trace_id=trace_id,
                metadata={
                    "agent_name": registration.config.name,
                    "topic_patterns": registration.config.event_subscriptions,
                    "queue_name": queue_name
                }
            )

        except Exception as e:
            self.logger.error(
                f"Failed to subscribe agent {registration.config.name}: {str(e)}",
                trace_id=trace_id
            )

    async def _start_continuous_agent(
        self,
        registration: AgentRegistration,
        trace_id: str
    ) -> None:
        """Start a continuous agent runner."""
        self.logger.info(
            f"Starting continuous agent: {registration.config.name}",
            trace_id=trace_id,
            metadata={"agent_name": registration.config.name}
        )

        # Publish event to start continuous agent
        event = Event(
            event_type=EventType.AGENT_STARTED,
            payload={
                "agent_name": registration.config.name,
                "config": registration.config.model_dump(mode="json")
            },
            trace_id=trace_id
        )

        self.event_bus.publish(
            event=event,
            routing_key=f"continuous.start.{registration.config.name}"
        )

    async def _route_to_pool(
        self,
        registration: AgentRegistration,
        task_data: Dict,
        execution_id: str,
        trace_id: str
    ) -> None:
        """Route agent execution to appropriate pool."""
        execution_mode = registration.config.execution_mode
        agent_name = registration.config.name

        if execution_mode == "collaborative":
            routing_key = "collaborative.task.submitted"
        elif execution_mode == "autonomous":
            routing_key = "autonomous.task.submitted"
        elif execution_mode == "continuous":
            routing_key = f"continuous.task.{agent_name}"
        else:
            routing_key = "task.submitted"

        # Create event
        event = Event(
            event_type=EventType.TASK_SUBMITTED,
            payload={
                "agent_name": agent_name,
                "execution_id": execution_id,
                "task_data": task_data,
                "config": registration.config.model_dump(mode="json")
            },
            trace_id=trace_id
        )

        # Publish task to appropriate pool
        self.event_bus.publish(event=event, routing_key=routing_key)

    async def _start_health_monitoring(self) -> None:
        """Start background health monitoring task."""
        self._health_monitor_task = asyncio.create_task(
            self._health_monitoring_loop()
        )

    async def _health_monitoring_loop(self) -> None:
        """Background task for monitoring agent health."""
        while not self._shutdown_requested:
            try:
                trace_id = StructuredLogger.generate_trace_id()

                # Check health of all agents
                for agent_name in list(self.agent_registry.keys()):
                    is_healthy = await self.health_check_agent(agent_name, trace_id)

                    if not is_healthy:
                        # Attempt restart
                        await self.restart_agent(agent_name, trace_id)

                # Sleep until next check
                await asyncio.sleep(self.health_check_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(
                    f"Error in health monitoring loop: {str(e)}",
                    metadata={"error": str(e)}
                )
                await asyncio.sleep(self.health_check_interval)

    async def _shutdown_agent(self, agent_name: str, trace_id: str) -> None:
        """Shutdown a specific agent."""
        if agent_name not in self.agent_registry:
            return

        registration = self.agent_registry[agent_name]

        self.logger.info(
            f"Shutting down agent: {agent_name}",
            trace_id=trace_id,
            metadata={"agent_name": agent_name}
        )

        # Update status
        registration.metadata.status = AgentStatus.SHUTDOWN
        registration.metadata.updated_at = time.time()

        # Publish shutdown event
        event = Event(
            event_type=EventType.AGENT_STOPPED,
            payload={
                "agent_name": agent_name,
                "shutdown_time": datetime.utcnow().isoformat()
            },
            trace_id=trace_id
        )

        self.event_bus.publish(
            event=event,
            routing_key=f"agent.shutdown.{agent_name}"
        )
