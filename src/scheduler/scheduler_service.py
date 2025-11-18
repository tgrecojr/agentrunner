"""
Scheduler Service

Manages scheduled agent executions using Celery.

Features:
- Cron-based scheduling
- Interval-based scheduling
- Task timeout handling
- Dynamic schedule registration
- Integration with EventBus for task publishing
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from celery import Celery
from celery.schedules import crontab, schedule
from celery.signals import task_failure, task_success

from ..config.configuration_service import ConfigurationService
from ..config.models import AgentConfig
from ..messaging.event_bus import EventBus
from ..messaging.events import Event, EventType
from ..state.state_manager import StateManager
from ..utils.logger import StructuredLogger


class SchedulerService:
    """
    Manages scheduled agent executions using Celery.

    Features:
    - Supports cron and interval schedules
    - Dynamic schedule registration from ConfigurationService
    - Task timeout and retry handling
    - EventBus integration for task publishing
    """

    def __init__(
        self,
        config_service: ConfigurationService,
        state_manager: StateManager,
        event_bus: EventBus,
        broker_url: str = "amqp://guest:guest@rabbitmq:5672//",
        backend_url: str = "redis://redis:6379/0",
        task_timeout_seconds: int = 300
    ):
        """
        Initialize Scheduler Service.

        Args:
            config_service: Configuration service
            state_manager: State manager for persistence
            event_bus: Event bus for coordination
            broker_url: Celery broker URL
            backend_url: Celery result backend URL
            task_timeout_seconds: Default task timeout
        """
        self.config_service = config_service
        self.state_manager = state_manager
        self.event_bus = event_bus
        self.task_timeout_seconds = task_timeout_seconds

        # Celery app
        self.celery_app = Celery(
            "scheduler",
            broker=broker_url,
            backend=backend_url
        )

        # Celery configuration
        self.celery_app.conf.update(
            task_serializer="json",
            accept_content=["json"],
            result_serializer="json",
            timezone="UTC",
            enable_utc=True,
            task_track_started=True,
            task_time_limit=task_timeout_seconds,
            task_soft_time_limit=task_timeout_seconds - 30,
            worker_prefetch_multiplier=1,
            worker_max_tasks_per_child=1000
        )

        # Schedule registry
        self.schedules: Dict[str, Dict[str, Any]] = {}

        # Logger
        self.logger = StructuredLogger("SchedulerService")

        # Register Celery task
        self._register_celery_task()

        # Register Celery signal handlers
        self._register_signal_handlers()

        self.logger.info(
            "SchedulerService initialized",
            metadata={
                "broker_url": broker_url,
                "backend_url": backend_url,
                "task_timeout_seconds": task_timeout_seconds
            }
        )

    def _register_celery_task(self) -> None:
        """Register the scheduled task execution function."""

        @self.celery_app.task(name="scheduler.execute_scheduled_task", bind=True)
        def execute_scheduled_task(
            celery_task,
            agent_name: str,
            task_data: Dict[str, Any],
            schedule_name: str
        ) -> Dict[str, Any]:
            """
            Execute a scheduled task.

            Args:
                celery_task: Celery task instance
                agent_name: Name of the agent
                task_data: Task data payload
                schedule_name: Name of the schedule

            Returns:
                Execution result
            """
            trace_id = StructuredLogger.generate_trace_id()
            execution_id = f"scheduled_{schedule_name}_{datetime.utcnow().isoformat()}"

            self.logger.info(
                f"Executing scheduled task: {schedule_name}",
                trace_id=trace_id,
                metadata={
                    "agent_name": agent_name,
                    "schedule_name": schedule_name,
                    "execution_id": execution_id,
                    "task_id": celery_task.request.id
                }
            )

            try:
                # Publish task to EventBus
                event = Event(
                    event_type=EventType.TASK_SUBMITTED,
                    payload={
                        "agent_name": agent_name,
                        "execution_id": execution_id,
                        "task_data": task_data,
                        "schedule_name": schedule_name,
                        "scheduled_at": datetime.utcnow().isoformat()
                    },
                    trace_id=trace_id
                )

                # Publish to appropriate queue based on agent config
                agent_config = self.config_service.get_agent_config(agent_name)
                if agent_config:
                    routing_key = self._get_routing_key(agent_config)
                else:
                    routing_key = "task.submitted"

                self.event_bus.publish(event=event, routing_key=routing_key)

                # Record execution
                asyncio.run(self._record_execution(
                    agent_name=agent_name,
                    schedule_name=schedule_name,
                    execution_id=execution_id,
                    status="submitted",
                    trace_id=trace_id
                ))

                self.logger.info(
                    f"Scheduled task published successfully",
                    trace_id=trace_id,
                    metadata={
                        "agent_name": agent_name,
                        "schedule_name": schedule_name,
                        "execution_id": execution_id
                    }
                )

                return {
                    "status": "submitted",
                    "execution_id": execution_id,
                    "agent_name": agent_name,
                    "schedule_name": schedule_name
                }

            except Exception as e:
                self.logger.error(
                    f"Failed to execute scheduled task: {str(e)}",
                    trace_id=trace_id,
                    metadata={
                        "agent_name": agent_name,
                        "schedule_name": schedule_name
                    }
                )

                # Record failure
                asyncio.run(self._record_execution(
                    agent_name=agent_name,
                    schedule_name=schedule_name,
                    execution_id=execution_id,
                    status="failed",
                    error=str(e),
                    trace_id=trace_id
                ))

                raise

        self.execute_scheduled_task = execute_scheduled_task

    def _register_signal_handlers(self) -> None:
        """Register Celery signal handlers."""

        @task_success.connect
        def task_success_handler(sender=None, result=None, **kwargs):
            """Handle task success."""
            self.logger.debug(
                f"Task succeeded: {sender.name}",
                metadata={"result": result}
            )

        @task_failure.connect
        def task_failure_handler(sender=None, task_id=None, exception=None, **kwargs):
            """Handle task failure."""
            self.logger.error(
                f"Task failed: {sender.name}",
                metadata={
                    "task_id": task_id,
                    "exception": str(exception)
                }
            )

    def _get_routing_key(self, agent_config: AgentConfig) -> str:
        """
        Get routing key for agent based on execution mode.

        Args:
            agent_config: Agent configuration

        Returns:
            Routing key
        """
        execution_mode = agent_config.execution_mode
        agent_name = agent_config.name

        if execution_mode == "collaborative":
            return "collaborative.task.submitted"
        elif execution_mode == "autonomous":
            return "autonomous.task.submitted"
        elif execution_mode == "continuous":
            return f"continuous.task.{agent_name}"
        else:
            return "task.submitted"

    async def initialize(self) -> None:
        """Initialize the scheduler service."""
        trace_id = StructuredLogger.generate_trace_id()

        self.logger.info(
            "Initializing SchedulerService",
            trace_id=trace_id
        )

        # Load scheduled agents from ConfigurationService
        scheduled_agents = self.config_service.get_agents_by_type("scheduled")

        # Register schedules
        for agent_config in scheduled_agents:
            await self.register_schedule_from_config(agent_config, trace_id)

        # Update Celery beat schedule
        self._update_celery_beat_schedule()

        self.logger.info(
            f"SchedulerService initialized with {len(self.schedules)} schedules",
            trace_id=trace_id
        )

    async def register_schedule_from_config(
        self,
        agent_config: AgentConfig,
        trace_id: Optional[str] = None
    ) -> None:
        """
        Register a schedule from agent configuration.

        Args:
            agent_config: Agent configuration
            trace_id: Optional trace ID for logging
        """
        trace_id = trace_id or StructuredLogger.generate_trace_id()

        agent_name = agent_config.name
        schedule_config = agent_config.schedule_config

        if not schedule_config:
            self.logger.warning(
                f"No schedule_config found for agent {agent_name}",
                trace_id=trace_id
            )
            return

        schedule_type = schedule_config.get("type")  # "cron" or "interval"

        if schedule_type == "cron":
            # Cron schedule
            cron_expr = schedule_config.get("cron")
            if not cron_expr:
                self.logger.error(
                    f"Missing cron expression for agent {agent_name}",
                    trace_id=trace_id
                )
                return

            # Parse cron expression (minute hour day month day_of_week)
            cron_parts = cron_expr.split()
            if len(cron_parts) != 5:
                self.logger.error(
                    f"Invalid cron expression for agent {agent_name}: {cron_expr}",
                    trace_id=trace_id
                )
                return

            celery_schedule = crontab(
                minute=cron_parts[0],
                hour=cron_parts[1],
                day_of_month=cron_parts[2],
                month_of_year=cron_parts[3],
                day_of_week=cron_parts[4]
            )

        elif schedule_type == "interval":
            # Interval schedule
            interval_seconds = schedule_config.get("interval_seconds")
            if not interval_seconds:
                self.logger.error(
                    f"Missing interval_seconds for agent {agent_name}",
                    trace_id=trace_id
                )
                return

            celery_schedule = schedule(run_every=interval_seconds)

        else:
            self.logger.error(
                f"Unsupported schedule type for agent {agent_name}: {schedule_type}",
                trace_id=trace_id
            )
            return

        # Register schedule
        schedule_name = f"schedule_{agent_name}"
        task_data = schedule_config.get("task_data", {})

        self.schedules[schedule_name] = {
            "task": "scheduler.execute_scheduled_task",
            "schedule": celery_schedule,
            "args": [agent_name, task_data, schedule_name],
            "options": {
                "expires": schedule_config.get("timeout_seconds", self.task_timeout_seconds)
            }
        }

        self.logger.info(
            f"Registered schedule: {schedule_name}",
            trace_id=trace_id,
            metadata={
                "agent_name": agent_name,
                "schedule_type": schedule_type,
                "schedule_config": schedule_config
            }
        )

    async def register_custom_schedule(
        self,
        schedule_name: str,
        agent_name: str,
        schedule_type: str,
        schedule_config: Dict[str, Any],
        task_data: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Register a custom schedule.

        Args:
            schedule_name: Unique schedule name
            agent_name: Name of the agent
            schedule_type: "cron" or "interval"
            schedule_config: Schedule configuration (cron or interval_seconds)
            task_data: Optional task data payload
            trace_id: Optional trace ID for logging

        Returns:
            Registration result
        """
        trace_id = trace_id or StructuredLogger.generate_trace_id()

        self.logger.info(
            f"Registering custom schedule: {schedule_name}",
            trace_id=trace_id,
            metadata={
                "agent_name": agent_name,
                "schedule_type": schedule_type
            }
        )

        if schedule_type == "cron":
            cron_expr = schedule_config.get("cron")
            cron_parts = cron_expr.split()
            celery_schedule = crontab(
                minute=cron_parts[0],
                hour=cron_parts[1],
                day_of_month=cron_parts[2],
                month_of_year=cron_parts[3],
                day_of_week=cron_parts[4]
            )
        elif schedule_type == "interval":
            interval_seconds = schedule_config.get("interval_seconds")
            celery_schedule = schedule(run_every=interval_seconds)
        else:
            raise ValueError(f"Unsupported schedule type: {schedule_type}")

        # Register schedule
        self.schedules[schedule_name] = {
            "task": "scheduler.execute_scheduled_task",
            "schedule": celery_schedule,
            "args": [agent_name, task_data or {}, schedule_name],
            "options": {
                "expires": schedule_config.get("timeout_seconds", self.task_timeout_seconds)
            }
        }

        # Update Celery beat schedule
        self._update_celery_beat_schedule()

        self.logger.info(
            f"Custom schedule registered: {schedule_name}",
            trace_id=trace_id
        )

        return {
            "schedule_name": schedule_name,
            "agent_name": agent_name,
            "status": "registered"
        }

    async def unregister_schedule(
        self,
        schedule_name: str,
        trace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Unregister a schedule.

        Args:
            schedule_name: Schedule name
            trace_id: Optional trace ID for logging

        Returns:
            Unregistration result
        """
        trace_id = trace_id or StructuredLogger.generate_trace_id()

        if schedule_name not in self.schedules:
            raise ValueError(f"Schedule not found: {schedule_name}")

        self.logger.info(
            f"Unregistering schedule: {schedule_name}",
            trace_id=trace_id
        )

        # Remove schedule
        del self.schedules[schedule_name]

        # Update Celery beat schedule
        self._update_celery_beat_schedule()

        self.logger.info(
            f"Schedule unregistered: {schedule_name}",
            trace_id=trace_id
        )

        return {
            "schedule_name": schedule_name,
            "status": "unregistered"
        }

    def _update_celery_beat_schedule(self) -> None:
        """Update Celery beat schedule."""
        self.celery_app.conf.beat_schedule = self.schedules
        self.logger.debug(
            f"Updated Celery beat schedule with {len(self.schedules)} schedules"
        )

    def get_schedules(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all registered schedules.

        Returns:
            Dictionary of schedules
        """
        return {
            name: {
                "task": info["task"],
                "schedule": str(info["schedule"]),
                "args": info["args"]
            }
            for name, info in self.schedules.items()
        }

    async def _record_execution(
        self,
        agent_name: str,
        schedule_name: str,
        execution_id: str,
        status: str,
        error: Optional[str] = None,
        trace_id: Optional[str] = None
    ) -> None:
        """
        Record scheduled execution to StateManager.

        Args:
            agent_name: Agent name
            schedule_name: Schedule name
            execution_id: Execution ID
            status: Execution status
            error: Optional error message
            trace_id: Optional trace ID for logging
        """
        try:
            await self.state_manager.save_execution_result(
                agent_id=agent_name,
                execution_id=execution_id,
                status=status,
                result={
                    "schedule_name": schedule_name,
                    "error": error
                } if error else {"schedule_name": schedule_name},
                execution_time=0.0,
                trace_id=trace_id or StructuredLogger.generate_trace_id()
            )
        except Exception as e:
            self.logger.error(
                f"Failed to record execution: {str(e)}",
                metadata={
                    "agent_name": agent_name,
                    "execution_id": execution_id
                }
            )

    async def stop(self) -> None:
        """Stop the scheduler service."""
        trace_id = StructuredLogger.generate_trace_id()

        self.logger.info(
            "Stopping SchedulerService",
            trace_id=trace_id
        )

        # Clear schedules
        self.schedules.clear()
        self._update_celery_beat_schedule()

        self.logger.info(
            "SchedulerService stopped",
            trace_id=trace_id
        )
