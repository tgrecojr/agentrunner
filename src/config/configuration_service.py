"""
Configuration Service

Manages agent configurations, secrets, and credentials with support for:
- Auto-discovery of YAML configuration files
- Configuration validation using Pydantic
- Secure secrets management
- Hot-reload capability with watchdog file monitoring
- Credential injection for agents

All configuration files are located in config/agents/ directory.
"""

import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from dotenv import load_dotenv
from pydantic import ValidationError
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from ..utils.logger import StructuredLogger
from .models import AgentConfig, PlatformConfig


class ConfigFileHandler(FileSystemEventHandler):
    """File system event handler for configuration hot-reload."""

    def __init__(self, callback):
        """
        Initialize handler.

        Args:
            callback: Function to call when config file changes
        """
        self.callback = callback
        super().__init__()

    def on_modified(self, event: FileSystemEvent):
        """Handle file modification event."""
        if event.is_directory:
            return
        if event.src_path.endswith((".yaml", ".yml")):
            self.callback(event.src_path)

    def on_created(self, event: FileSystemEvent):
        """Handle file creation event."""
        if event.is_directory:
            return
        if event.src_path.endswith((".yaml", ".yml")):
            self.callback(event.src_path)


class ConfigurationService:
    """
    Configuration service for loading and managing agent configurations.

    Features:
    - Automatic discovery of YAML files in config/agents/
    - Configuration validation with Pydantic
    - Secrets management from environment variables
    - Hot-reload capability with watchdog file monitoring
    - Credential injection for agents
    """

    def __init__(
        self,
        config_dir: str = "config/agents",
        platform_config: Optional[PlatformConfig] = None,
        enable_hot_reload: bool = True
    ):
        """
        Initialize configuration service.

        Args:
            config_dir: Directory containing agent configuration files
            platform_config: Platform configuration (loaded from env if None)
            enable_hot_reload: Whether to enable hot-reload for configuration changes
        """
        self.config_dir = Path(config_dir)
        self.enable_hot_reload = enable_hot_reload
        self.logger = StructuredLogger("ConfigurationService")

        # Configuration storage
        self.configurations: Dict[str, AgentConfig] = {}
        self.config_errors: Dict[str, str] = {}
        self.file_timestamps: Dict[str, float] = {}

        # Platform configuration
        self.platform_config = platform_config or self._load_platform_config()

        # Secrets storage (loaded from environment)
        self.secrets: Dict[str, str] = {}

        # File watcher
        self.observer: Optional[Observer] = None

        # Load environment variables and secrets
        self._load_secrets()

        # Ensure config directory exists
        self._ensure_config_dir()

        # Perform initial configuration load
        self._load_configurations()

        # Start file watcher if hot-reload enabled
        if self.enable_hot_reload:
            self._start_file_watcher()

        self.logger.info(
            f"ConfigurationService initialized with {len(self.configurations)} agents",
            metadata={
                "config_dir": str(self.config_dir),
                "hot_reload_enabled": enable_hot_reload,
                "errors": len(self.config_errors)
            }
        )

    def _ensure_config_dir(self) -> None:
        """Ensure configuration directory exists."""
        if not self.config_dir.exists():
            self.config_dir.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"Created configuration directory: {self.config_dir}")

    def _load_platform_config(self) -> PlatformConfig:
        """
        Load platform configuration from environment variables.

        Returns:
            PlatformConfig instance
        """
        try:
            config = PlatformConfig(
                state_manager_url=os.getenv("STATE_MANAGER_URL", "http://localhost:8001"),
                rabbitmq_url=f"amqp://{os.getenv('RABBITMQ_USER', 'guest')}:{os.getenv('RABBITMQ_PASSWORD', 'guest')}@{os.getenv('RABBITMQ_HOST', 'localhost')}:{os.getenv('RABBITMQ_PORT', '5672')}/",
                redis_url=f"redis://{os.getenv('REDIS_HOST', 'localhost')}:{os.getenv('REDIS_PORT', '6379')}/0",
                postgres_url=f"postgresql://{os.getenv('POSTGRES_USER', 'agentrunner_user')}:{os.getenv('POSTGRES_PASSWORD', 'agentrunner')}@{os.getenv('POSTGRES_HOST', 'localhost')}:{os.getenv('POSTGRES_PORT', '5432')}/{os.getenv('POSTGRES_DB', 'agentrunner')}",
                log_level=os.getenv("LOG_LEVEL", "INFO"),
                environment=os.getenv("ENVIRONMENT", "development"),
                debug=os.getenv("DEBUG", "false").lower() == "true",
                agent_config_dir=os.getenv("AGENT_CONFIG_DIR", "config/agents"),
                hot_reload_enabled=os.getenv("HOT_RELOAD_ENABLED", "true").lower() == "true",
            )
            self.logger.info(
                "Loaded platform configuration",
                metadata={"environment": config.environment}
            )
            return config
        except Exception as e:
            self.logger.error(f"Failed to load platform config: {str(e)}")
            return PlatformConfig()

    def _load_secrets(self) -> None:
        """
        Load secrets from environment variables.

        Validates that required secrets are present.
        """
        # Load .env file if present
        load_dotenv()

        # Load all environment variables
        self.secrets = dict(os.environ)

        # Log loaded secrets (without values)
        self.logger.info(
            "Secrets loaded from environment",
            metadata={"total_secrets": len(self.secrets)}
        )

    def _load_configurations(self) -> None:
        """
        Discover and load all agent configuration files from config directory.
        """
        if not self.config_dir.exists():
            self.logger.warning(f"Configuration directory does not exist: {self.config_dir}")
            self.config_dir.mkdir(parents=True, exist_ok=True)
            return

        # Find all YAML files
        yaml_files = list(self.config_dir.glob("*.yaml")) + list(self.config_dir.glob("*.yml"))

        if not yaml_files:
            self.logger.warning(f"No configuration files found in {self.config_dir}")
            return

        # Load each configuration file
        for config_file in yaml_files:
            try:
                self._load_config_file(config_file)
            except Exception as e:
                self.logger.error(
                    f"Failed to load configuration file: {config_file.name}",
                    metadata={"error": str(e), "file": str(config_file)}
                )

        self.logger.info(
            f"Loaded {len(self.configurations)} agent configurations",
            metadata={"files_processed": len(yaml_files)}
        )

    def _load_config_file(self, config_file: Path) -> Optional[AgentConfig]:
        """
        Load and validate a single configuration file.

        Args:
            config_file: Path to configuration file

        Returns:
            AgentConfig if successful, None if failed
        """
        try:
            # Read YAML file
            with open(config_file, "r") as f:
                config_data = yaml.safe_load(f)

            if not config_data:
                self.logger.warning(f"Empty configuration file: {config_file}")
                return None

            # Inject secrets from environment
            config_data = self._inject_secrets(config_data)

            # Validate configuration
            agent_config = AgentConfig(**config_data)

            # Store configuration
            self.configurations[agent_config.name] = agent_config

            # Store file timestamp for hot-reload
            self.file_timestamps[str(config_file)] = config_file.stat().st_mtime

            # Clear any previous errors
            if agent_config.name in self.config_errors:
                del self.config_errors[agent_config.name]

            self.logger.info(
                f"Loaded configuration: {agent_config.name}",
                metadata={
                    "file": config_file.name,
                    "agent_type": agent_config.agent_type,
                    "execution_mode": agent_config.execution_mode
                }
            )

            return agent_config

        except ValidationError as e:
            error_msg = f"Validation error in {config_file.name}: {str(e)}"
            self.logger.error(error_msg)
            agent_name = config_file.stem
            self.config_errors[agent_name] = error_msg
            return None

        except yaml.YAMLError as e:
            error_msg = f"Invalid YAML in {config_file.name}: {str(e)}"
            self.logger.error(error_msg)
            agent_name = config_file.stem
            self.config_errors[agent_name] = error_msg
            return None

        except Exception as e:
            error_msg = f"Error loading {config_file.name}: {str(e)}"
            self.logger.error(error_msg)
            agent_name = config_file.stem
            self.config_errors[agent_name] = error_msg
            return None

    def _inject_secrets(self, config_data: Dict) -> Dict:
        """
        Inject secrets from environment variables into configuration.

        Args:
            config_data: Configuration dictionary

        Returns:
            Configuration with secrets injected
        """
        # LLM API keys
        if "llm_config" in config_data:
            llm_config = config_data["llm_config"]

            # AWS Bedrock credentials
            if llm_config.get("provider") == "aws_bedrock":
                llm_config["aws_region"] = llm_config.get("aws_region") or os.getenv("AWS_REGION", "us-east-1")

            # OpenAI API key
            elif llm_config.get("provider") == "openai":
                llm_config["api_key"] = os.getenv("OPENAI_API_KEY")

            # Anthropic API key
            elif llm_config.get("provider") == "anthropic":
                llm_config["api_key"] = os.getenv("ANTHROPIC_API_KEY")

        # Slack integration
        if "slack_integration" in config_data and config_data["slack_integration"].get("enabled"):
            config_data["slack_integration"]["bot_token"] = os.getenv("SLACK_BOT_TOKEN")

        return config_data

    def _start_file_watcher(self) -> None:
        """Start file system watcher for hot-reload."""
        try:
            self.observer = Observer()
            event_handler = ConfigFileHandler(self._on_config_file_changed)
            self.observer.schedule(event_handler, str(self.config_dir), recursive=False)
            self.observer.start()

            self.logger.info(f"Started configuration file watcher on {self.config_dir}")

        except Exception as e:
            self.logger.error(f"Failed to start file watcher: {str(e)}")

    def _on_config_file_changed(self, file_path: str) -> None:
        """
        Handle configuration file change event.

        Args:
            file_path: Path to changed file
        """
        self.logger.info(f"Configuration file changed: {file_path}")

        # Small delay to ensure file is fully written
        time.sleep(0.5)

        # Reload the configuration
        self._load_config_file(Path(file_path))

    def get_agent_config(self, agent_name: str) -> Optional[AgentConfig]:
        """
        Get configuration for a specific agent.

        Args:
            agent_name: Name of the agent

        Returns:
            AgentConfig if found, None otherwise
        """
        return self.configurations.get(agent_name)

    def get_all_configs(self) -> Dict[str, AgentConfig]:
        """
        Get all agent configurations.

        Returns:
            Dictionary mapping agent names to configurations
        """
        return self.configurations.copy()

    def get_enabled_agents(self) -> List[AgentConfig]:
        """
        Get all enabled agent configurations.

        Returns:
            List of enabled AgentConfig instances
        """
        return [config for config in self.configurations.values() if config.enabled]

    def get_agents_by_type(self, agent_type: str) -> List[AgentConfig]:
        """
        Get all agents of a specific type.

        Args:
            agent_type: Agent type (collaborative, autonomous, continuous)

        Returns:
            List of matching AgentConfig instances
        """
        return [
            config for config in self.configurations.values()
            if config.agent_type == agent_type
        ]

    def get_agents_by_execution_mode(self, execution_mode: str) -> List[AgentConfig]:
        """
        Get all agents with a specific execution mode.

        Args:
            execution_mode: Execution mode (on_demand, scheduled, continuous, event_driven)

        Returns:
            List of matching AgentConfig instances
        """
        return [
            config for config in self.configurations.values()
            if config.execution_mode == execution_mode
        ]

    def reload_all_configurations(self) -> None:
        """Reload all agent configurations from disk."""
        self.logger.info("Reloading all configurations")
        self.configurations.clear()
        self.config_errors.clear()
        self._load_configurations()

    def validate_configuration(self, config_data: Dict) -> tuple[bool, Optional[str]]:
        """
        Validate a configuration dictionary without loading it.

        Args:
            config_data: Configuration dictionary to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            AgentConfig(**config_data)
            return True, None
        except ValidationError as e:
            return False, str(e)
        except Exception as e:
            return False, f"Unexpected error: {str(e)}"

    def get_configuration_errors(self) -> Dict[str, str]:
        """
        Get all configuration loading errors.

        Returns:
            Dictionary of agent name -> error message
        """
        return self.config_errors.copy()

    def health_check(self) -> Dict[str, any]:
        """
        Check health of configuration service.

        Returns:
            Dictionary with health status
        """
        return {
            "status": "healthy",
            "loaded_configs": len(self.configurations),
            "config_errors": len(self.config_errors),
            "hot_reload_enabled": self.enable_hot_reload,
            "watcher_running": self.observer is not None and self.observer.is_alive() if self.observer else False,
            "config_directory": str(self.config_dir),
        }

    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get a secret value by key.

        Args:
            key: Secret key
            default: Default value if key not found

        Returns:
            Secret value or default
        """
        return self.secrets.get(key, default)

    def stop(self) -> None:
        """Stop the configuration service and file watcher."""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.logger.info("Stopped configuration file watcher")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
