"""
Structured Logger for Multi-Agent Orchestration Platform

Provides JSON-formatted logging to stdout with trace ID support for request correlation.
All components use this logger to ensure consistent log format and traceability.
"""

import json
import logging
import sys
import traceback
import uuid
from datetime import datetime
from typing import Any, Dict, Optional


class StructuredLogger:
    """
    Structured logger that outputs JSON-formatted log messages to stdout.

    Each log entry includes:
    - timestamp: ISO 8601 formatted timestamp
    - level: Log level (INFO, WARNING, ERROR, etc.)
    - component: Name of the component generating the log
    - message: Log message
    - trace_id: Unique identifier for request/event correlation
    - metadata: Additional contextual information
    """

    def __init__(self, component_name: str, log_level: str = "INFO"):
        """
        Initialize the structured logger.

        Args:
            component_name: Name of the component using this logger
            log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        self.component_name = component_name
        self.logger = logging.getLogger(component_name)

        # Set log level
        level = getattr(logging, log_level.upper(), logging.INFO)
        self.logger.setLevel(level)

        # Remove existing handlers to avoid duplicates
        self.logger.handlers = []

        # Create stdout handler with JSON formatter
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)

        # Custom formatter for JSON output
        handler.setFormatter(self._json_formatter())

        self.logger.addHandler(handler)

        # Prevent propagation to root logger
        self.logger.propagate = False

    def _json_formatter(self) -> logging.Formatter:
        """Create a custom JSON formatter."""

        class JSONFormatter(logging.Formatter):
            """Custom formatter that outputs JSON."""

            def format(self, record: logging.LogRecord) -> str:
                """Format log record as JSON."""
                log_data = {
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "level": record.levelname,
                    "component": record.name,
                    "message": record.getMessage(),
                }

                # Add trace_id if present
                if hasattr(record, "trace_id"):
                    log_data["trace_id"] = record.trace_id

                # Add metadata if present
                if hasattr(record, "metadata"):
                    log_data["metadata"] = record.metadata

                # Add exception info if present
                if record.exc_info:
                    log_data["exception"] = self.formatException(record.exc_info)
                    log_data["stack_trace"] = traceback.format_exc()

                return json.dumps(log_data)

        return JSONFormatter()

    @staticmethod
    def generate_trace_id() -> str:
        """
        Generate a unique trace ID for request/event correlation.

        Returns:
            UUID string to be used as trace_id
        """
        return str(uuid.uuid4())

    def _log(
        self,
        level: int,
        message: str,
        trace_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        exc_info: bool = False
    ) -> None:
        """
        Internal method to log a message with structured data.

        Args:
            level: Log level (logging.INFO, logging.WARNING, etc.)
            message: Log message
            trace_id: Optional trace ID for correlation
            metadata: Optional dictionary of additional context
            exc_info: Whether to include exception information
        """
        extra = {}

        if trace_id:
            extra["trace_id"] = trace_id

        if metadata:
            extra["metadata"] = metadata

        self.logger.log(level, message, extra=extra, exc_info=exc_info)

    def debug(
        self,
        message: str,
        trace_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log a debug message.

        Args:
            message: Log message
            trace_id: Optional trace ID for correlation
            metadata: Optional dictionary of additional context
        """
        self._log(logging.DEBUG, message, trace_id, metadata)

    def info(
        self,
        message: str,
        trace_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log an info message.

        Args:
            message: Log message
            trace_id: Optional trace ID for correlation
            metadata: Optional dictionary of additional context
        """
        self._log(logging.INFO, message, trace_id, metadata)

    def warning(
        self,
        message: str,
        trace_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log a warning message.

        Args:
            message: Log message
            trace_id: Optional trace ID for correlation
            metadata: Optional dictionary of additional context
        """
        self._log(logging.WARNING, message, trace_id, metadata)

    def error(
        self,
        message: str,
        trace_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        exc_info: bool = True
    ) -> None:
        """
        Log an error message with optional exception information.

        Args:
            message: Log message
            trace_id: Optional trace ID for correlation
            metadata: Optional dictionary of additional context
            exc_info: Whether to include exception stack trace (default: True)
        """
        self._log(logging.ERROR, message, trace_id, metadata, exc_info)

    def critical(
        self,
        message: str,
        trace_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        exc_info: bool = True
    ) -> None:
        """
        Log a critical message with optional exception information.

        Args:
            message: Log message
            trace_id: Optional trace ID for correlation
            metadata: Optional dictionary of additional context
            exc_info: Whether to include exception stack trace (default: True)
        """
        self._log(logging.CRITICAL, message, trace_id, metadata, exc_info)


# Example usage and documentation
if __name__ == "__main__":
    # Initialize logger for a component
    logger = StructuredLogger("ExampleComponent", log_level="DEBUG")

    # Generate a trace ID for this workflow
    trace_id = StructuredLogger.generate_trace_id()

    # Log messages with trace ID
    logger.info("Processing started", trace_id=trace_id)

    logger.info(
        "Processing data",
        trace_id=trace_id,
        metadata={"record_count": 100, "source": "slack"}
    )

    try:
        # Simulate an error
        raise ValueError("Example error")
    except ValueError:
        logger.error(
            "Processing failed",
            trace_id=trace_id,
            metadata={"error_type": "validation"},
            exc_info=True
        )

    logger.info("Processing completed", trace_id=trace_id)
