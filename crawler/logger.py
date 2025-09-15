"""Structured logging configuration using structlog."""

import logging
import sys
from typing import Any, Dict, List, Literal, Optional, Union
import types

import structlog
from structlog.processors import CallsiteParameter


def setup_logging(
    level: str = "INFO",
    format_type: str = "json",
    enable_colors: bool = True,
    include_timestamp: bool = True,
) -> None:
    """Configure structured logging for the application.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_type: Output format ('json' or 'console')
        enable_colors: Enable colored output for console format
        include_timestamp: Include timestamps in logs
    """
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper()),
    )

    # Build processor chain
    processors: List[Any] = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.CallsiteParameterAdder(
            parameters=[
                CallsiteParameter.FILENAME,
                CallsiteParameter.FUNC_NAME,
                CallsiteParameter.LINENO,
            ]
        ),
    ]

    if include_timestamp:
        processors.insert(0, structlog.processors.TimeStamper(fmt="iso"))

    # Add final renderer based on format type
    if format_type == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        # Console format with optional colors
        if enable_colors:
            processors.append(
                structlog.dev.ConsoleRenderer(
                    colors=True,
                    exception_formatter=structlog.dev.RichTracebackFormatter(
                        show_locals=True
                    ),
                )
            )
        else:
            processors.append(structlog.dev.ConsoleRenderer(colors=False))

    # Configure structlog
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = __name__, **kwargs: Any) -> Any:
    """Get a configured logger instance.

    Args:
        name: Logger name (typically __name__)
        **kwargs: Additional context to bind to the logger

    Returns:
        Configured structlog logger with bound context
    """
    logger = structlog.get_logger(name)
    if kwargs:
        logger = logger.bind(**kwargs)
    return logger


def log_operation(
    operation: str,
    success: bool,
    duration: float | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Create a structured log entry for an operation.

    Args:
        operation: Name of the operation
        success: Whether the operation succeeded
        duration: Operation duration in seconds
        **extra: Additional context

    Returns:
        Structured log data dictionary
    """
    data = {
        "operation": operation,
        "success": success,
        "status": "success" if success else "failure",
    }

    if duration is not None:
        data["duration_seconds"] = round(duration, 3)

    data.update(extra)
    return data


class LogContext:
    """Context manager for structured logging with timing."""

    def __init__(
        self,
        logger: Any,  # structlog.BoundLogger
        operation: str,
        **context: Any,
    ):
        """Initialize log context.

        Args:
            logger: Structlog logger instance
            operation: Name of the operation
            **context: Additional context to log
        """
        self.logger = logger
        self.operation = operation
        self.context = context
        self.start_time: Optional[float] = None

    def __enter__(self) -> "LogContext":
        """Enter context and log operation start."""
        import time

        self.start_time = time.time()
        self.logger.info(
            f"Starting {self.operation}",
            operation=self.operation,
            **self.context,
        )
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[Exception],
        exc_tb: Optional[types.TracebackType],
    ) -> Literal[False]:
        """Exit context and log operation completion."""
        import time

        if self.start_time is not None:
            duration = time.time() - self.start_time
        else:
            duration = 0.0

        if exc_type is None:
            self.logger.info(
                f"Completed {self.operation}",
                **log_operation(
                    self.operation,
                    success=True,
                    duration=duration,
                    **self.context,
                ),
            )
        else:
            self.logger.error(
                f"Failed {self.operation}",
                **log_operation(
                    self.operation,
                    success=False,
                    duration=duration,
                    error=str(exc_val),
                    error_type=exc_type.__name__ if exc_type else "Unknown",
                    **self.context,
                ),
                exc_info=True,
            )
        return False

    async def __aenter__(self) -> "LogContext":
        """Async enter context and log operation start."""
        import time

        self.start_time = time.time()
        self.logger.info(
            f"Starting {self.operation}",
            operation=self.operation,
            **self.context,
        )
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[Exception],
        exc_tb: Optional[types.TracebackType],
    ) -> Literal[False]:
        """Async exit context and log operation completion."""
        import time

        if self.start_time is not None:
            duration = time.time() - self.start_time
        else:
            duration = 0.0

        if exc_type is None:
            self.logger.info(
                f"Completed {self.operation}",
                **log_operation(
                    self.operation,
                    success=True,
                    duration=duration,
                    **self.context,
                ),
            )
        else:
            self.logger.error(
                f"Failed {self.operation}",
                **log_operation(
                    self.operation,
                    success=False,
                    duration=duration,
                    error=str(exc_val),
                    error_type=exc_type.__name__ if exc_type else "Unknown",
                    **self.context,
                ),
                exc_info=True,
            )
        return False
