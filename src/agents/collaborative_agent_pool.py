"""
Collaborative Agent Pool

Manages collaborative multi-agent tasks using Portia AI for planning and execution.

Features:
- Multi-agent plan creation with role assignments
- Sequential plan execution with state management
- Human-in-the-loop clarification support
- Result aggregation from multiple agents
- Event-driven coordination via EventBus
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from portia_sdk.agent import Agent as PortiaAgent
from portia_sdk.planning import PlanningAgent, ExecutionPlan, PlanStep

from ..config.configuration_service import ConfigurationService
from ..config.models import AgentConfig
from ..messaging.event_bus import EventBus
from ..messaging.events import Event, EventType
from ..state.state_manager import StateManager
from ..utils.logger import StructuredLogger


class PlanStatus(Enum):
    """Plan execution status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    WAITING_CLARIFICATION = "waiting_clarification"
    COMPLETED = "completed"
    FAILED = "failed"


class StepStatus(Enum):
    """Plan step execution status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class CollaborativePlan:
    """Collaborative execution plan."""
    plan_id: str
    task_description: str
    participating_agents: List[str]
    steps: List[Dict[str, Any]]
    status: PlanStatus = PlanStatus.PENDING
    current_step_index: int = 0
    results: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    trace_id: Optional[str] = None


@dataclass
class AgentExecutor:
    """Agent executor instance."""
    agent_name: str
    agent_config: AgentConfig
    portia_agent: PortiaAgent
    role: str
    capabilities: List[str]


class CollaborativeAgentPool:
    """
    Manages collaborative multi-agent tasks using Portia AI.

    Coordinates multiple agents working together on complex tasks:
    - Creates execution plans with PlanningAgent
    - Initializes ExecutionAgent instances for each participating agent
    - Executes plans step-by-step with state management
    - Handles human-in-the-loop clarifications
    - Aggregates results from all agents
    """

    def __init__(
        self,
        config_service: ConfigurationService,
        state_manager: StateManager,
        event_bus: EventBus
    ):
        """
        Initialize Collaborative Agent Pool.

        Args:
            config_service: Configuration service for agent configs
            state_manager: State manager for persistence
            event_bus: Event bus for coordination
        """
        self.config_service = config_service
        self.state_manager = state_manager
        self.event_bus = event_bus

        # Active plans
        self.active_plans: Dict[str, CollaborativePlan] = {}

        # Agent executors
        self.agent_executors: Dict[str, AgentExecutor] = {}

        # Portia AI planning agent
        self.planning_agent: Optional[PlanningAgent] = None

        # Logger
        self.logger = StructuredLogger("CollaborativeAgentPool")

        self.logger.info("CollaborativeAgentPool initialized")

    async def initialize(self) -> None:
        """Initialize the collaborative agent pool."""
        trace_id = StructuredLogger.generate_trace_id()

        self.logger.info(
            "Initializing CollaborativeAgentPool",
            trace_id=trace_id
        )

        # Initialize Portia AI Planning Agent
        self.planning_agent = PlanningAgent(
            model="anthropic.claude-3-sonnet-20240229-v1:0",
            api_key=self.config_service.get_secret("ANTHROPIC_API_KEY")
        )

        # Subscribe to collaborative task events
        self.event_bus.subscribe(
            queue_name="collaborative_agent_pool",
            routing_patterns=["collaborative.task.submitted"],
            callback=self._handle_collaborative_task,
            auto_ack=False,
            enable_dlq=True
        )

        # Subscribe to plan step completion events
        self.event_bus.subscribe(
            queue_name="collaborative_step_completion",
            routing_patterns=["collaboration.step.completed.#"],
            callback=self._handle_step_completion,
            auto_ack=False,
            enable_dlq=True
        )

        # Subscribe to clarification events
        self.event_bus.subscribe(
            queue_name="collaborative_clarification",
            routing_patterns=["collaboration.clarification.#"],
            callback=self._handle_clarification_response,
            auto_ack=False,
            enable_dlq=True
        )

        self.logger.info(
            "CollaborativeAgentPool initialized successfully",
            trace_id=trace_id
        )

    async def create_execution_plan(
        self,
        task_description: str,
        available_agents: List[str],
        trace_id: Optional[str] = None
    ) -> CollaborativePlan:
        """
        Create a multi-agent execution plan using Portia AI PlanningAgent.

        Args:
            task_description: Description of the task
            available_agents: List of available agent names
            trace_id: Optional trace ID for logging

        Returns:
            Collaborative execution plan
        """
        trace_id = trace_id or StructuredLogger.generate_trace_id()
        plan_id = str(uuid4())

        self.logger.info(
            f"Creating execution plan for task",
            trace_id=trace_id,
            metadata={
                "plan_id": plan_id,
                "task_description": task_description,
                "available_agents": available_agents
            }
        )

        try:
            # Get agent configurations and capabilities
            agent_capabilities = {}
            for agent_name in available_agents:
                config = self.config_service.get_agent_config(agent_name)
                if config:
                    agent_capabilities[agent_name] = {
                        "type": config.agent_type,
                        "capabilities": config.tags or [],
                        "description": config.description
                    }

            # Use Portia AI to create execution plan
            planning_context = {
                "task": task_description,
                "agents": agent_capabilities,
                "constraints": [
                    "Each step should be assigned to one agent",
                    "Steps should be sequential and buildable",
                    "Include clear success criteria for each step"
                ]
            }

            # Note: This is a simplified version - in production, you'd use
            # the actual Portia AI Planning API
            portia_plan = await self._generate_plan_with_portia(
                planning_context,
                trace_id
            )

            # Create collaborative plan
            plan = CollaborativePlan(
                plan_id=plan_id,
                task_description=task_description,
                participating_agents=list(portia_plan["agents"]),
                steps=portia_plan["steps"],
                status=PlanStatus.PENDING,
                trace_id=trace_id
            )

            # Store plan in StateManager
            await self.state_manager.update_plan_run_state(
                plan_id=plan_id,
                current_step=0,
                total_steps=len(plan.steps),
                step_results={},
                trace_id=trace_id
            )

            # Store in active plans
            self.active_plans[plan_id] = plan

            self.logger.info(
                f"Execution plan created successfully",
                trace_id=trace_id,
                metadata={
                    "plan_id": plan_id,
                    "total_steps": len(plan.steps),
                    "participating_agents": plan.participating_agents
                }
            )

            return plan

        except Exception as e:
            self.logger.error(
                f"Failed to create execution plan: {str(e)}",
                trace_id=trace_id
            )
            raise

    async def initialize_agents(
        self,
        plan: CollaborativePlan,
        trace_id: Optional[str] = None
    ) -> Dict[str, AgentExecutor]:
        """
        Initialize ExecutionAgent instances for collaborative task.

        Args:
            plan: Collaborative execution plan
            trace_id: Optional trace ID for logging

        Returns:
            Dictionary of agent name -> AgentExecutor
        """
        trace_id = trace_id or plan.trace_id or StructuredLogger.generate_trace_id()

        self.logger.info(
            f"Initializing agents for plan {plan.plan_id}",
            trace_id=trace_id,
            metadata={
                "plan_id": plan.plan_id,
                "agents": plan.participating_agents
            }
        )

        executors = {}

        for agent_name in plan.participating_agents:
            try:
                # Get agent configuration
                config = self.config_service.get_agent_config(agent_name)
                if not config:
                    self.logger.warning(
                        f"Agent configuration not found: {agent_name}",
                        trace_id=trace_id
                    )
                    continue

                # Determine agent role in this plan
                role = self._determine_agent_role(agent_name, plan)

                # Create Portia AI ExecutionAgent instance
                portia_agent = PortiaAgent(
                    name=agent_name,
                    model=config.llm_config.model,
                    system_prompt=config.system_prompt,
                    api_key=self.config_service.get_secret(
                        f"{config.llm_config.provider.upper()}_API_KEY"
                    )
                )

                # Create executor
                executor = AgentExecutor(
                    agent_name=agent_name,
                    agent_config=config,
                    portia_agent=portia_agent,
                    role=role,
                    capabilities=config.tags or []
                )

                executors[agent_name] = executor
                self.agent_executors[agent_name] = executor

                self.logger.info(
                    f"Initialized agent: {agent_name}",
                    trace_id=trace_id,
                    metadata={
                        "agent_name": agent_name,
                        "role": role,
                        "capabilities": executor.capabilities
                    }
                )

            except Exception as e:
                self.logger.error(
                    f"Failed to initialize agent {agent_name}: {str(e)}",
                    trace_id=trace_id
                )

        return executors

    async def execute_plan_step(
        self,
        plan_id: str,
        step_index: int,
        trace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute a single step of the collaborative plan.

        Args:
            plan_id: Plan ID
            step_index: Step index to execute
            trace_id: Optional trace ID for logging

        Returns:
            Step execution result
        """
        trace_id = trace_id or StructuredLogger.generate_trace_id()

        if plan_id not in self.active_plans:
            raise ValueError(f"Plan not found: {plan_id}")

        plan = self.active_plans[plan_id]
        if step_index >= len(plan.steps):
            raise ValueError(f"Invalid step index: {step_index}")

        step = plan.steps[step_index]
        agent_name = step["assigned_agent"]

        self.logger.info(
            f"Executing plan step {step_index + 1}/{len(plan.steps)}",
            trace_id=trace_id,
            metadata={
                "plan_id": plan_id,
                "step_index": step_index,
                "agent_name": agent_name,
                "step_description": step["description"]
            }
        )

        try:
            # Get agent executor
            if agent_name not in self.agent_executors:
                await self.initialize_agents(plan, trace_id)

            executor = self.agent_executors.get(agent_name)
            if not executor:
                raise ValueError(f"Agent executor not found: {agent_name}")

            # Execute step with Portia AI agent
            step_context = {
                "plan_id": plan_id,
                "step_index": step_index,
                "step_description": step["description"],
                "previous_results": plan.results,
                "success_criteria": step.get("success_criteria", [])
            }

            result = await executor.portia_agent.execute(
                prompt=step["description"],
                context=step_context
            )

            # Store result
            plan.results[f"step_{step_index}"] = {
                "agent": agent_name,
                "description": step["description"],
                "result": result,
                "status": "completed",
                "timestamp": datetime.utcnow().isoformat()
            }

            # Update plan state
            plan.current_step_index = step_index + 1
            plan.updated_at = time.time()

            # Update in StateManager
            await self.state_manager.update_plan_run_state(
                plan_id=plan_id,
                current_step=step_index + 1,
                total_steps=len(plan.steps),
                step_results=plan.results,
                trace_id=trace_id
            )

            # Publish step completion event
            event = Event(
                event_type=EventType.TASK_COMPLETED,
                payload={
                    "plan_id": plan_id,
                    "step_index": step_index,
                    "agent_name": agent_name,
                    "result": result
                },
                trace_id=trace_id
            )

            self.event_bus.publish(
                event=event,
                routing_key=f"collaboration.step.completed.{plan_id}"
            )

            self.logger.info(
                f"Step executed successfully",
                trace_id=trace_id,
                metadata={
                    "plan_id": plan_id,
                    "step_index": step_index,
                    "agent_name": agent_name
                }
            )

            return plan.results[f"step_{step_index}"]

        except Exception as e:
            self.logger.error(
                f"Failed to execute step: {str(e)}",
                trace_id=trace_id,
                metadata={
                    "plan_id": plan_id,
                    "step_index": step_index
                }
            )

            # Mark step as failed
            plan.results[f"step_{step_index}"] = {
                "agent": agent_name,
                "description": step["description"],
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

            plan.status = PlanStatus.FAILED
            plan.updated_at = time.time()

            raise

    async def handle_clarification(
        self,
        plan_id: str,
        clarification_request: str,
        trace_id: Optional[str] = None
    ) -> str:
        """
        Handle human-in-the-loop clarification request.

        Args:
            plan_id: Plan ID
            clarification_request: Clarification question
            trace_id: Optional trace ID for logging

        Returns:
            Clarification ID for tracking
        """
        trace_id = trace_id or StructuredLogger.generate_trace_id()

        if plan_id not in self.active_plans:
            raise ValueError(f"Plan not found: {plan_id}")

        plan = self.active_plans[plan_id]
        clarification_id = str(uuid4())

        self.logger.info(
            f"Requesting clarification for plan {plan_id}",
            trace_id=trace_id,
            metadata={
                "plan_id": plan_id,
                "clarification_id": clarification_id,
                "request": clarification_request
            }
        )

        # Update plan status
        plan.status = PlanStatus.WAITING_CLARIFICATION
        plan.updated_at = time.time()

        # Publish clarification request event
        event = Event(
            event_type=EventType.CUSTOM,
            payload={
                "plan_id": plan_id,
                "clarification_id": clarification_id,
                "request": clarification_request,
                "timestamp": datetime.utcnow().isoformat()
            },
            trace_id=trace_id
        )

        self.event_bus.publish(
            event=event,
            routing_key=f"collaboration.clarification.request.{plan_id}"
        )

        return clarification_id

    async def resume_with_clarification(
        self,
        plan_id: str,
        clarification_id: str,
        response: str,
        trace_id: Optional[str] = None
    ) -> None:
        """
        Resume plan execution with clarification response.

        Args:
            plan_id: Plan ID
            clarification_id: Clarification ID
            response: Clarification response
            trace_id: Optional trace ID for logging
        """
        trace_id = trace_id or StructuredLogger.generate_trace_id()

        if plan_id not in self.active_plans:
            raise ValueError(f"Plan not found: {plan_id}")

        plan = self.active_plans[plan_id]

        self.logger.info(
            f"Resuming plan with clarification",
            trace_id=trace_id,
            metadata={
                "plan_id": plan_id,
                "clarification_id": clarification_id
            }
        )

        # Store clarification in results
        plan.results[f"clarification_{clarification_id}"] = {
            "response": response,
            "timestamp": datetime.utcnow().isoformat()
        }

        # Resume execution
        plan.status = PlanStatus.IN_PROGRESS
        plan.updated_at = time.time()

        # Continue with next step
        if plan.current_step_index < len(plan.steps):
            await self.execute_plan_step(
                plan_id,
                plan.current_step_index,
                trace_id
            )

    async def aggregate_results(
        self,
        plan_id: str,
        trace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Aggregate results from all plan steps.

        Args:
            plan_id: Plan ID
            trace_id: Optional trace ID for logging

        Returns:
            Aggregated results
        """
        trace_id = trace_id or StructuredLogger.generate_trace_id()

        if plan_id not in self.active_plans:
            raise ValueError(f"Plan not found: {plan_id}")

        plan = self.active_plans[plan_id]

        self.logger.info(
            f"Aggregating results for plan {plan_id}",
            trace_id=trace_id,
            metadata={
                "plan_id": plan_id,
                "total_steps": len(plan.steps),
                "completed_steps": plan.current_step_index
            }
        )

        # Compile final results
        aggregated = {
            "plan_id": plan_id,
            "task_description": plan.task_description,
            "status": "completed" if plan.current_step_index == len(plan.steps) else "partial",
            "participating_agents": plan.participating_agents,
            "total_steps": len(plan.steps),
            "completed_steps": plan.current_step_index,
            "step_results": plan.results,
            "created_at": plan.created_at,
            "completed_at": time.time(),
            "duration_seconds": time.time() - plan.created_at
        }

        # Store final results in StateManager
        await self.state_manager.save_execution_result(
            agent_id="collaborative_pool",
            execution_id=plan_id,
            status="completed",
            result=aggregated,
            execution_time=aggregated["duration_seconds"],
            trace_id=trace_id
        )

        # Mark plan as completed
        plan.status = PlanStatus.COMPLETED
        plan.updated_at = time.time()

        # Publish completion event
        event = Event(
            event_type=EventType.TASK_COMPLETED,
            payload={
                "plan_id": plan_id,
                "results": aggregated
            },
            trace_id=trace_id
        )

        self.event_bus.publish(
            event=event,
            routing_key=f"collaboration.completed.{plan_id}"
        )

        self.logger.info(
            f"Results aggregated successfully",
            trace_id=trace_id,
            metadata={
                "plan_id": plan_id,
                "status": aggregated["status"]
            }
        )

        # Remove from active plans
        del self.active_plans[plan_id]

        return aggregated

    # Private helper methods

    async def _generate_plan_with_portia(
        self,
        planning_context: Dict[str, Any],
        trace_id: str
    ) -> Dict[str, Any]:
        """Generate execution plan using Portia AI."""
        # Simplified plan generation - in production, use actual Portia AI API
        agents = list(planning_context["agents"].keys())

        return {
            "agents": agents,
            "steps": [
                {
                    "step_number": 1,
                    "description": f"Analyze task requirements and gather data",
                    "assigned_agent": agents[0] if agents else "default",
                    "success_criteria": ["Data collected", "Requirements documented"]
                },
                {
                    "step_number": 2,
                    "description": f"Process and analyze the gathered data",
                    "assigned_agent": agents[1] if len(agents) > 1 else agents[0],
                    "success_criteria": ["Analysis complete", "Insights generated"]
                },
                {
                    "step_number": 3,
                    "description": f"Generate final recommendations and summary",
                    "assigned_agent": agents[0] if agents else "default",
                    "success_criteria": ["Recommendations provided", "Summary complete"]
                }
            ]
        }

    def _determine_agent_role(
        self,
        agent_name: str,
        plan: CollaborativePlan
    ) -> str:
        """Determine agent role in the plan."""
        # Count steps assigned to this agent
        assigned_steps = [
            step for step in plan.steps
            if step.get("assigned_agent") == agent_name
        ]

        if not assigned_steps:
            return "observer"

        # Determine role based on step types
        if assigned_steps[0]["step_number"] == 1:
            return "initiator"
        elif assigned_steps[-1]["step_number"] == len(plan.steps):
            return "finalizer"
        else:
            return "processor"

    async def _handle_collaborative_task(self, event: Event) -> None:
        """Handle incoming collaborative task."""
        # Implementation for handling collaborative tasks
        pass

    async def _handle_step_completion(self, event: Event) -> None:
        """Handle step completion event."""
        # Implementation for handling step completions
        pass

    async def _handle_clarification_response(self, event: Event) -> None:
        """Handle clarification response."""
        # Implementation for handling clarification responses
        pass
