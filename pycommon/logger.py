import logging
import os
from datetime import datetime
from threading import local
from typing import Optional

import boto3

# Configure logging format once at module level
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# Thread-local storage for request context (tracks polling state per request)
_request_context = local()


class PollStatusHandler(logging.Handler):
    """
    Custom logging handler that writes to DynamoDB poll_status table
    when pollRequestId is active in the request context.

    This handler automatically updates the poll status table with:
    - Log messages (for progress tracking)
    - Status changes (processing -> completed/failed)
    - Timestamps for each update

    Updates are rate-limited to avoid excessive DynamoDB writes.
    """

    def __init__(self, table_name: str, min_interval_seconds: int = 5):
        """
        Initialize the poll status handler.

        Args:
            table_name: Name of the DynamoDB poll_status table
            min_interval_seconds: Minimum seconds between updates (default: 5)
        """
        super().__init__()
        self.dynamodb = boto3.resource("dynamodb")
        self.table = self.dynamodb.Table(table_name)
        self.last_update_time = {}  # Track last update per requestId
        self.min_interval = min_interval_seconds

    def emit(self, record):
        """
        Called whenever a log message is emitted.
        Updates DynamoDB if polling is active for this request.
        """
        try:
            # Check if polling is active for this request
            poll_request_id = getattr(_request_context, "poll_request_id", None)
            user = getattr(_request_context, "user", None)
            operation = getattr(_request_context, "operation", None)

            if not poll_request_id or not user:
                return  # No polling active, skip

            # Rate limit: Only update every N seconds
            now = datetime.utcnow().timestamp()
            last_update = self.last_update_time.get(poll_request_id, 0)

            if now - last_update < self.min_interval and record.levelno < logging.ERROR:
                return  # Skip this update (unless it's an error)

            # Determine status from log level
            if record.levelno >= logging.ERROR:
                status = "failed"
            else:
                status = "processing"

            # Update poll status table
            update_expr = (
                "SET #status = :status, lastLog = :log, "
                "lastLogLevel = :level, updatedAt = :time, operation = :op"
            )
            self.table.update_item(
                Key={"requestId": poll_request_id, "user": user},
                UpdateExpression=update_expr,
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={
                    ":status": status,
                    ":log": record.getMessage()[:500],
                    ":level": record.levelname,
                    ":time": datetime.utcnow().isoformat(),
                    ":op": operation or "unknown",
                },
            )

            # Update last update time
            self.last_update_time[poll_request_id] = now

        except Exception as e:
            # Never let logging errors break the application
            # Just log to stderr and continue
            import sys

            print(f"Error updating poll status: {e}", file=sys.stderr)


def getLogger(log_stack: str):
    """
    Logger module for pycommon package.

    This module provides a centralized logging configuration for pycommon.
    It creates loggers with consistent naming and formatting, and supports
    environment-based configuration for service names and log levels.

    When POLL_STATUS_TABLE environment variable is set, the logger will
    automatically update the poll status table with log messages when
    polling is active for a request.

    Environment Variables:
        SERVICE_NAME: The name of the service (default: 'amplify')
        LOG_LEVEL: The logging level (default: 'INFO')
            Supported levels: DEBUG, INFO, WARNING/WARN, ERROR, CRITICAL/FATAL
        POLL_STATUS_TABLE: DynamoDB table name for poll status tracking (optional)

    Example:
        >>> from pycommon.logger import getLogger
        >>> logger = getLogger('my_module')
        >>> logger.info('This is a test message')
    """
    service = os.getenv("SERVICE_NAME", "amplify")
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "WARN": logging.WARNING,  # alias
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
        "FATAL": logging.CRITICAL,  # alias
    }

    logger = logging.getLogger(f"{service}-{log_stack}")
    logger.setLevel(level_map.get(log_level, logging.INFO))

    # Add poll status handler if table configured
    poll_status_table = os.getenv("POLL_STATUS_TABLE")
    if poll_status_table and not any(
        isinstance(h, PollStatusHandler) for h in logger.handlers
    ):
        try:
            handler = PollStatusHandler(poll_status_table)
            handler.setLevel(logging.INFO)  # Only track INFO and above
            logger.addHandler(handler)
        except Exception as e:
            # If handler setup fails, continue without it
            import sys

            print(f"Warning: Could not add poll status handler: {e}", file=sys.stderr)

    return logger


def activate_poll_tracking(poll_request_id: str, user: str, operation: str = None):
    """
    Activate poll status tracking for the current request.

    This makes all subsequent logger calls within this request update
    the poll status table with progress information.

    Args:
        poll_request_id: Unique identifier for this polling request
        user: User making the request (from auth claims)
        operation: Optional operation name (e.g., 'create_assistant')

    Example:
        >>> activate_poll_tracking(
        ...     'req-123-abc', 'user@example.com', 'create_assistant'
        ... )
        >>> logger.info("Starting processing...")  # Updates poll status
    """
    _request_context.poll_request_id = poll_request_id
    _request_context.user = user
    _request_context.operation = operation


def deactivate_poll_tracking():
    """
    Deactivate poll status tracking for the current request.

    Call this when the request completes to stop tracking.
    The @validated decorator handles this automatically in a finally block.
    """
    _request_context.poll_request_id = None
    _request_context.user = None
    _request_context.operation = None


def get_active_poll_request_id() -> Optional[str]:
    """
    Get the currently active poll request ID, if any.

    Returns:
        str: The poll request ID if polling is active, None otherwise
    """
    return getattr(_request_context, "poll_request_id", None)
