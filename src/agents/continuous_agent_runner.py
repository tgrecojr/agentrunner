"""
Continuous Agent Runner

Manages continuous agents that process events with persistent state.

Features:
- Dedicated queue per agent
- Persistent conversation state with history
- Crash recovery and state restoration
- Idle agent optimization
- Continuous event processing loop
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from portia_sdk.agent import Agent as PortiaAgent

from ..config.configuration_service import ConfigurationService
from ..config.models import AgentConfig
from ..messaging.event_bus import EventBus
from ..messaging.events import Event, EventType
from ..state.state_manager import StateManager
from ..utils.logger import StructuredLogger


@dataclass
class ContinuousAgentState:
    """State for a continuous agent."""
    agent_id: str
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    memory: Dict[str, Any] = field(default_factory=dict)
    last_event_time: float = field(default_factory=time.time)
    event_count: int = 0
    last_saved_at: float = field(default_factory=time.time)


@dataclass
class ContinuousAgentInstance:
    """Continuous agent instance."""
    agent_name: str
    agent_config: AgentConfig
    portia_agent: PortiaAgent
    state: ContinuousAgentState
    queue_name: str
    is_running: bool = False
    last_activity: float = field(default_factory=time.time)


class ContinuousAgentRunner:
    """
    Manages continuous agents with persistent state.

    Features:
    - Each agent has a dedicated queue: agent.input.{agent_id}
    - Maintains conversation history and memory
    - Periodic state saves and crash recovery
    - Idle agent optimization (flush after 10 minutes)
    - Continuous event processing
    """

    def __init__(
        self,
        config_service: ConfigurationService,
        state_manager: StateManager,
        event_bus: EventBus,
        save_interval_seconds: int = 300,  # 5 minutes
        idle_timeout_seconds: int = 600,  # 10 minutes
        prefetch_count: int = 1
    ):
        """
        Initialize Continuous Agent Runner.

        Args:
            config_service: Configuration service
            state_manager: State manager for persistence
            event_bus: Event bus for coordination
            save_interval_seconds: Interval for periodic state saves
            idle_timeout_seconds: Timeout for idle agent optimization
            prefetch_count: Prefetch count per agent
        """
        self.config_service = config_service
        self.state_manager = state_manager
        self.event_bus = event_bus
        self.save_interval_seconds = save_interval_seconds
        self.idle_timeout_seconds = idle_timeout_seconds
        self.prefetch_count = prefetch_count

        # Agent instances
        self.agent_instances: Dict[str, ContinuousAgentInstance] = {}

        # Processing tasks
        self.processing_tasks: Dict[str, asyncio.Task] = {}

        # Logger
        self.logger = StructuredLogger("ContinuousAgentRunner")

        self.logger.info(
            "ContinuousAgentRunner initialized",
            metadata={
                "save_interval_seconds": save_interval_seconds,
                "idle_timeout_seconds": idle_timeout_seconds,
                "prefetch_count": prefetch_count
            }
        )

    async def initialize(self) -> None:
        """Initialize the continuous agent runner."""
        trace_id = StructuredLogger.generate_trace_id()

        self.logger.info(
            "Initializing ContinuousAgentRunner",
            trace_id=trace_id
        )

        # Get all continuous agents
        continuous_agents = self.config_service.get_agents_by_type("continuous")

        # Start continuous agents
        for agent_config in continuous_agents:
            await self.start_continuous_agent(agent_config, trace_id)

        # Start idle agent monitor
        asyncio.create_task(self._idle_agent_monitor())

        self.logger.info(
            f"ContinuousAgentRunner initialized with {len(continuous_agents)} agents",
            trace_id=trace_id
        )

    async def start_continuous_agent(
        self,
        agent_config: AgentConfig,
        trace_id: Optional[str] = None
    ) -> None:
        """
        Start a continuous agent.

        Args:
            agent_config: Agent configuration
            trace_id: Optional trace ID for logging
        """
        trace_id = trace_id or StructuredLogger.generate_trace_id()

        agent_name = agent_config.name

        self.logger.info(
            f"Starting continuous agent: {agent_name}",
            trace_id=trace_id,
            metadata={"agent_name": agent_name}
        )

        try:
            # Load or initialize state
            state = await self.load_agent_state(agent_name, trace_id)

            # Create Portia AI agent
            portia_agent = PortiaAgent(
                name=agent_name,
                model=agent_config.llm_config.model,
                system_prompt=agent_config.system_prompt,
                api_key=self.config_service.get_secret(
                    f"{agent_config.llm_config.provider.upper()}_API_KEY"
                )
            )

            # Create agent instance
            queue_name = f"agent.input.{agent_name}"
            instance = ContinuousAgentInstance(
                agent_name=agent_name,
                agent_config=agent_config,
                portia_agent=portia_agent,
                state=state,
                queue_name=queue_name,
                is_running=True
            )

            self.agent_instances[agent_name] = instance

            # Subscribe to dedicated queue
            self.event_bus.subscribe(
                queue_name=queue_name,
                routing_patterns=[f"continuous.task.{agent_name}", f"agent.input.{agent_name}"],
                callback=lambda event: self._process_event(agent_name, event),
                auto_ack=False,
                enable_dlq=True
            )

            # Start continuous processing loop
            task = asyncio.create_task(
                self.run_continuous_agent(agent_name)
            )
            self.processing_tasks[agent_name] = task

            self.logger.info(
                f"Continuous agent started: {agent_name}",
                trace_id=trace_id,
                metadata={
                    "agent_name": agent_name,
                    "queue_name": queue_name,
                    "conversation_history_length": len(state.conversation_history)
                }
            )

        except Exception as e:
            self.logger.error(
                f"Failed to start continuous agent {agent_name}: {str(e)}",
                trace_id=trace_id
            )

    async def load_agent_state(
        self,
        agent_id: str,
        trace_id: Optional[str] = None
    ) -> ContinuousAgentState:
        """
        Load agent state from StateManager (for crash recovery).

        Args:
            agent_id: Agent ID
            trace_id: Optional trace ID for logging

        Returns:
            Agent state (new or restored)
        """
        trace_id = trace_id or StructuredLogger.generate_trace_id()

        try:
            # Try to load existing state
            state_data = await self.state_manager.load_latest_agent_state(
                agent_id=agent_id,
                trace_id=trace_id
            )

            if state_data:
                self.logger.info(
                    f"Restored state for agent {agent_id}",
                    trace_id=trace_id,
                    metadata={
                        "agent_id": agent_id,
                        "conversation_length": len(state_data.get("conversation_history", [])),
                        "event_count": state_data.get("event_count", 0)
                    }
                )

                return ContinuousAgentState(
                    agent_id=agent_id,
                    conversation_history=state_data.get("conversation_history", []),
                    memory=state_data.get("memory", {}),
                    last_event_time=state_data.get("last_event_time", time.time()),
                    event_count=state_data.get("event_count", 0),
                    last_saved_at=time.time()
                )

        except Exception as e:
            self.logger.warning(
                f"Could not load state for {agent_id}, starting fresh: {str(e)}",
                trace_id=trace_id
            )

        # Return new state
        return ContinuousAgentState(agent_id=agent_id)

    async def process_event(
        self,
        agent_name: str,
        event_payload: Dict[str, Any],
        trace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process an event with persistent state management.

        Args:
            agent_name: Name of the agent
            event_payload: Event payload
            trace_id: Optional trace ID for logging

        Returns:
            Processing result
        """
        trace_id = trace_id or StructuredLogger.generate_trace_id()

        if agent_name not in self.agent_instances:
            raise ValueError(f"Agent not found: {agent_name}")

        instance = self.agent_instances[agent_name]
        state = instance.state

        self.logger.info(
            f"Processing event for {agent_name}",
            trace_id=trace_id,
            metadata={
                "agent_name": agent_name,
                "event_count": state.event_count + 1
            }
        )

        try:
            # Add event to conversation history
            state.conversation_history.append({
                "role": "user",
                "content": event_payload.get("prompt", ""),
                "timestamp": datetime.utcnow().isoformat(),
                "event_data": event_payload
            })

            # Execute with Portia AI agent including conversation history
            result = await instance.portia_agent.execute(
                prompt=event_payload.get("prompt", ""),
                context={
                    "conversation_history": state.conversation_history[-10:],  # Last 10 messages
                    "memory": state.memory,
                    "event_count": state.event_count
                }
            )

            # Add response to conversation history
            state.conversation_history.append({
                "role": "assistant",
                "content": result.get("response", ""),
                "timestamp": datetime.utcnow().isoformat()
            })

            # Update state
            state.event_count += 1
            state.last_event_time = time.time()
            instance.last_activity = time.time()

            # Update memory if agent provided updates
            if "memory_updates" in result:
                state.memory.update(result["memory_updates"])

            # Periodic state save
            if time.time() - state.last_saved_at >= self.save_interval_seconds:
                await self.save_agent_state(agent_name, trace_id)

            # Publish result
            response_event = Event(
                event_type=EventType.TASK_COMPLETED,
                payload={
                    "agent_name": agent_name,
                    "result": result,
                    "event_count": state.event_count
                },
                trace_id=trace_id
            )

            self.event_bus.publish(
                event=response_event,
                routing_key=f"agent.output.{agent_name}"
            )

            self.logger.info(
                f"Event processed successfully",
                trace_id=trace_id,
                metadata={
                    "agent_name": agent_name,
                    "event_count": state.event_count
                }
            )

            return result

        except Exception as e:
            self.logger.error(
                f"Failed to process event: {str(e)}",
                trace_id=trace_id,
                metadata={"agent_name": agent_name}
            )
            raise

    async def save_agent_state(
        self,
        agent_name: str,
        trace_id: Optional[str] = None
    ) -> None:
        """
        Save agent state to StateManager.

        Args:
            agent_name: Name of the agent
            trace_id: Optional trace ID for logging
        """
        trace_id = trace_id or StructuredLogger.generate_trace_id()

        if agent_name not in self.agent_instances:
            return

        instance = self.agent_instances[agent_name]
        state = instance.state

        try:
            state_data = {
                "conversation_history": state.conversation_history,
                "memory": state.memory,
                "last_event_time": state.last_event_time,
                "event_count": state.event_count
            }

            await self.state_manager.save_agent_state(
                agent_id=agent_name,
                state_data=state_data,
                trace_id=trace_id
            )

            state.last_saved_at = time.time()

            self.logger.debug(
                f"Saved state for agent {agent_name}",
                trace_id=trace_id,
                metadata={
                    "agent_name": agent_name,
                    "conversation_length": len(state.conversation_history),
                    "event_count": state.event_count
                }
            )

        except Exception as e:
            self.logger.error(
                f"Failed to save state for {agent_name}: {str(e)}",
                trace_id=trace_id
            )

    async def flush_idle_agent(
        self,
        agent_name: str,
        trace_id: Optional[str] = None
    ) -> None:
        """
        Flush idle agent to reduce resource consumption.

        Args:
            agent_name: Name of the agent
            trace_id: Optional trace ID for logging
        """
        trace_id = trace_id or StructuredLogger.generate_trace_id()

        if agent_name not in self.agent_instances:
            return

        instance = self.agent_instances[agent_name]

        self.logger.info(
            f"Flushing idle agent: {agent_name}",
            trace_id=trace_id,
            metadata={
                "agent_name": agent_name,
                "idle_time_seconds": time.time() - instance.last_activity
            }
        )

        # Save final state
        await self.save_agent_state(agent_name, trace_id)

        # Trim conversation history to last 100 messages
        if len(instance.state.conversation_history) > 100:
            instance.state.conversation_history = instance.state.conversation_history[-100:]

        self.logger.info(
            f"Agent flushed: {agent_name}",
            trace_id=trace_id
        )

    async def run_continuous_agent(self, agent_name: str) -> None:
        """
        Run continuous processing loop for an agent.

        Args:
            agent_name: Name of the agent
        """
        if agent_name not in self.agent_instances:
            return

        instance = self.agent_instances[agent_name]

        self.logger.info(
            f"Starting continuous processing for {agent_name}",
            metadata={"agent_name": agent_name}
        )

        try:
            # Start consuming from dedicated queue
            self.event_bus.start_consuming(
                queue_name=instance.queue_name,
                blocking=True
            )

        except Exception as e:
            self.logger.error(
                f"Continuous processing stopped for {agent_name}: {str(e)}",
                metadata={"agent_name": agent_name}
            )

            instance.is_running = False

    async def _process_event(self, agent_name: str, event: Event) -> None:
        """
        Internal event processor.

        Args:
            agent_name: Name of the agent
            event: Event to process
        """
        try:
            await self.process_event(
                agent_name=agent_name,
                event_payload=event.payload,
                trace_id=str(event.trace_id) if event.trace_id else None
            )

        except Exception as e:
            self.logger.error(
                f"Failed to process event for {agent_name}: {str(e)}",
                trace_id=str(event.trace_id) if event.trace_id else None
            )

    async def _idle_agent_monitor(self) -> None:
        """Background task to monitor and flush idle agents."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute

                for agent_name, instance in self.agent_instances.items():
                    idle_time = time.time() - instance.last_activity

                    if idle_time >= self.idle_timeout_seconds:
                        await self.flush_idle_agent(agent_name)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(
                    f"Error in idle agent monitor: {str(e)}"
                )

    async def stop(self) -> None:
        """Stop all continuous agents."""
        trace_id = StructuredLogger.generate_trace_id()

        self.logger.info(
            "Stopping all continuous agents",
            trace_id=trace_id
        )

        # Cancel all processing tasks
        for agent_name, task in self.processing_tasks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

            # Save final state
            await self.save_agent_state(agent_name, trace_id)

        # Mark all as not running
        for instance in self.agent_instances.values():
            instance.is_running = False

        self.logger.info(
            "All continuous agents stopped",
            trace_id=trace_id
        )
