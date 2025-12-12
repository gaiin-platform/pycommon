"""usage_tracker.py

This module provides classes and utilities for tracking Lambda execution metrics
to enable cost calculation and usage monitoring.

Copyright (c) 2025 Vanderbilt University
Authors: Jules White, Allen Karns, Karely Rodriguez, Max Moundas, Sam Hays
"""

import os
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional

import boto3

from pycommon.logger import getLogger

logger = getLogger("usage_tracker")

# Global flag to detect cold starts
# Lambda containers are reused, so first invocation is cold start
_cold_start = True


@dataclass
class LambdaExecutionMetrics:
    """Metrics for a single Lambda execution.

    This dataclass captures all relevant information needed to calculate
    Lambda execution costs and monitor usage patterns.

    Attributes:
        start_timestamp: When the Lambda execution started
        end_timestamp: When the Lambda execution completed
        duration_ms: Execution duration in milliseconds
        user: Username/user ID performing the operation
        account: Account ID associated with the execution
        api_key_id: API key ID if accessed via API (None for OAuth)
        operation: Operation name/type being performed
        endpoint: API endpoint/path that was called
        api_accessed: Whether this was an API access (True) or OAuth (False)
        status_code: HTTP status code of the response
        success: Whether the execution succeeded (status < 400)
        error_type: Type of error if execution failed (None if successful)
        request_id: Lambda request ID for correlation
        memory_limit_mb: Memory allocated to the Lambda in MB
        purpose: Optional purpose field (e.g., group system ID)
    """

    # Timing
    start_timestamp: datetime
    end_timestamp: datetime
    duration_ms: float

    # Identity
    user: str
    account: str
    api_key_id: Optional[str]

    # Request
    operation: str
    endpoint: str
    api_accessed: bool

    # Response
    status_code: int
    success: bool
    error_type: Optional[str]

    # Lambda context
    request_id: Optional[str]
    memory_limit_mb: Optional[int]
    max_memory_used_mb: Optional[int] = None
    is_cold_start: bool = False

    # Additional context
    purpose: Optional[str] = None
    service_name: Optional[str] = None
    function_name: Optional[str] = None

    def get_padded_duration_ms(self, padding_percent: float = 33.0) -> float:
        """Get duration with padding to account for tracking overhead.

        The tracked duration misses:
        - DynamoDB metrics write time (~50-100ms)
        - Lambda finalization overhead (~20-50ms)
        - Response serialization (~10-20ms)

        Args:
            padding_percent: Percentage to add to duration (default 33%)
                           Based on observed overhead:
                           - Warm starts: 848ms tracked vs 984ms actual = 16% gap
                           - With overhead: 348ms tracked vs 465ms actual = 34% gap
                           Using 33% as balanced estimate

        Returns:
            float: Padded duration in milliseconds
        """
        return self.duration_ms * (1.0 + padding_percent / 100.0)

    def estimated_cost_usd(
        self,
        use_actual_memory: bool = False,
        use_padded_duration: bool = True,
        padding_percent: float = 33.0,
    ) -> Decimal:
        """Calculate estimated AWS Lambda cost in USD.

        AWS Lambda pricing (as of 2025):
        - $0.0000166667 per GB-second (compute)
        - First 1M requests per month are free, then $0.20 per 1M requests
        - First 400,000 GB-seconds of compute per month are free

        This calculation focuses on compute cost only (GB-seconds).
        Request cost is negligible for most use cases.

        Args:
            use_actual_memory: If True and max_memory_used_mb is available,
                             use actual memory for cost calculation (more accurate).
                             If False, use memory_limit_mb (what Lambda bills).
            use_padded_duration: If True, add padding to account for tracking
                               overhead that's not captured in duration_ms.
            padding_percent: Percentage to pad duration (default 33%)

        Returns:
            Decimal: Estimated cost in USD for this execution
        """
        if not self.memory_limit_mb or self.duration_ms <= 0:
            return Decimal("0.0")

        # Use actual memory if requested and available, otherwise use limit
        # Note: AWS bills based on allocated memory, not used memory
        # But tracking actual usage helps identify over-provisioning
        memory_mb = self.memory_limit_mb
        if use_actual_memory and self.max_memory_used_mb:
            memory_mb = self.max_memory_used_mb

        # Convert memory from MB to GB
        memory_gb = Decimal(memory_mb) / Decimal(1024)

        # Use padded duration if requested to account for tracking overhead
        # TODO: REMOVE LATER - temporary fail-safe logging
        duration_ms = self.duration_ms
        if use_padded_duration:
            try:
                duration_ms = self.get_padded_duration_ms(padding_percent)
            except Exception as padding_error:
                logger.warning(
                    f"[REMOVE LATER] Failed to calculate padded duration "
                    f"(using raw duration): {padding_error}"
                )
                duration_ms = self.duration_ms

        # Convert duration from ms to seconds
        duration_seconds = Decimal(str(duration_ms)) / Decimal(1000)

        # Calculate GB-seconds
        gb_seconds = memory_gb * duration_seconds

        # AWS Lambda cost per GB-second
        cost_per_gb_second = Decimal("0.0000166667")

        # Calculate total cost
        cost = gb_seconds * cost_per_gb_second

        return cost.quantize(Decimal("0.0000000001"))  # Round to 10 decimal places

    def to_dynamodb_item(self) -> Dict[str, Any]:
        """Convert metrics to DynamoDB item format.

        Returns:
            Dict[str, Any]: Dictionary formatted for DynamoDB storage
        """
        item = {
            "account": self.account,
            "timestamp": self.start_timestamp.isoformat(),
            "user": self.user,
            "operation": self.operation,
            "endpoint": self.endpoint,
            "duration_ms": Decimal(str(self.duration_ms)),
            "status_code": self.status_code,
            "success": self.success,
            "api_accessed": self.api_accessed,
            "estimated_cost_usd": self.estimated_cost_usd(),
        }

        # Add optional fields only if they exist
        if self.api_key_id:
            item["api_key_id"] = self.api_key_id
        if self.error_type:
            item["error_type"] = self.error_type
        if self.request_id:
            item["request_id"] = self.request_id
        if self.memory_limit_mb:
            item["memory_limit_mb"] = self.memory_limit_mb
        if self.max_memory_used_mb:
            item["max_memory_used_mb"] = self.max_memory_used_mb
        if self.purpose:
            item["purpose"] = self.purpose
        if self.service_name:
            item["service_name"] = self.service_name
        if self.function_name:
            item["function_name"] = self.function_name

        return item


class UsageTracker:
    """Tracks Lambda execution metrics and stores them in DynamoDB.

    This class provides methods to start tracking at Lambda entry,
    end tracking at Lambda exit, and store metrics asynchronously.

    The tracker is designed to be fail-safe - if metrics collection
    fails, it will log the error but not impact the main Lambda execution.
    """

    def __init__(
        self,
        dynamodb_table: Optional[str] = None,
        enabled: bool = True,
    ):
        """Initialize the usage tracker.

        Args:
            dynamodb_table: DynamoDB table name for storing metrics.
                           If None, uses ADDITIONAL_CHARGES_TABLE env var.
            enabled: Whether tracking is enabled. Can be controlled via
                    ENABLE_USAGE_TRACKING env var.
        """
        # TODO: REMOVE LATER - temporary fail-safe logging
        self.table_name = dynamodb_table or os.getenv("ADDITIONAL_CHARGES_TABLE")
        logger.warning(
            f"[REMOVE LATER] UsageTracker init: table_name={self.table_name}, "
            f"enabled={enabled}"
        )

        # Check if tracking is enabled via environment variable
        env_enabled = os.getenv("ENABLE_USAGE_TRACKING", "true").lower()
        self.enabled = enabled and env_enabled in ("true", "1", "yes")

        if not self.enabled:
            logger.warning(
                f"[REMOVE LATER] Usage tracking is disabled "
                f"(enabled={enabled}, env_enabled={env_enabled})"
            )
            return

        if not self.table_name:
            logger.warning(
                "[REMOVE LATER] ADDITIONAL_CHARGES_TABLE not set, "
                "usage tracking will be disabled. This is a temporary fail-safe."
            )
            self.enabled = False
            return

        # TODO: REMOVE LATER - temporary fail-safe for boto3 initialization
        try:
            self.dynamodb = boto3.resource("dynamodb")
            self.table = self.dynamodb.Table(self.table_name)
            logger.warning(
                f"[REMOVE LATER] Usage tracker initialized successfully "
                f"with table: {self.table_name}"
            )
        except Exception as e:
            logger.warning(
                f"[REMOVE LATER] Failed to initialize DynamoDB table "
                f"(failing safe): {e}",
                exc_info=True,
            )
            self.enabled = False

    def start_tracking(
        self,
        user: str,
        operation: str,
        endpoint: str,
        api_accessed: bool,
        context: Any,
        service_name: Optional[str] = None,
        function_name: Optional[str] = None,
        start_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Start tracking a Lambda execution.

        Called at the entry point after authentication and validation.

        Args:
            user: Username/user ID performing the operation
            operation: Operation type/name
            endpoint: API endpoint/path being called
            api_accessed: Whether this is API access (True) or OAuth (False)
            context: Lambda context object
            service_name: Service name (from SERVICE_NAME env var)
            function_name: Lambda function name (from context)
            start_time: Optional start time (use this for accurate Lambda billing)

        Returns:
            Dict[str, Any]: Tracking context to pass to end_tracking()
        """
        if not self.enabled:
            return {}

        tracking_context = {
            "start_time": start_time or datetime.utcnow(),
            "user": user,
            "operation": operation,
            "endpoint": endpoint,
            "api_accessed": api_accessed,
            "request_id": getattr(context, "aws_request_id", None),
            "memory_limit": getattr(context, "memory_limit_in_mb", None),
            "service_name": service_name or os.getenv("SERVICE_NAME"),
            "function_name": function_name or getattr(context, "function_name", None),
        }

        logger.debug(
            f"Started tracking for user={user}, op={operation}, "
            f"endpoint={endpoint}, service={tracking_context['service_name']}"
        )
        return tracking_context

    def end_tracking(
        self,
        tracking_context: Dict[str, Any],
        result: Dict[str, Any],
        claims: Dict[str, Any],
        error_type: Optional[str] = None,
    ) -> Optional[LambdaExecutionMetrics]:
        """End tracking and create metrics object.

        Called at the exit point after the Lambda function completes.

        Args:
            tracking_context: Context returned from start_tracking()
            result: Result dictionary with statusCode
            claims: Claims dictionary with account info
            error_type: Type of error if execution failed (None if successful)

        Returns:
            Optional[LambdaExecutionMetrics]: Metrics object, or None if
            tracking disabled
        """
        if not self.enabled or not tracking_context:
            return None

        try:
            end_time = datetime.utcnow()
            start_time = tracking_context.get("start_time", end_time)
            duration = (end_time - start_time).total_seconds() * 1000

            status_code = result.get("statusCode", 200)

            # Capture memory usage (Python process RSS + 30MB overhead buffer)
            max_memory_used_mb = None
            try:
                import resource

                # Get peak memory usage in KB, convert to MB
                # RUSAGE_SELF gets this process's resource usage
                peak_memory_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                # On Linux, ru_maxrss is in KB; on macOS it's in bytes
                # Lambda runs on Linux, so we expect KB
                import platform

                if platform.system() == "Darwin":  # macOS
                    peak_memory_kb = peak_memory_kb / 1024

                # Convert to MB and add 35MB buffer for Lambda runtime overhead
                # Observed: 111MB tracked vs 133MB actual (22MB diff)
                #          117MB tracked vs 141MB actual (24MB diff)
                # Using 35MB buffer for better accuracy
                python_memory_mb = int(peak_memory_kb / 1024)
                max_memory_used_mb = python_memory_mb + 35
            except Exception as e:
                logger.debug(f"Could not capture memory usage: {e}")

            # Detect if this is a cold start
            # TODO: REMOVE LATER - temporary fail-safe logging
            is_cold = False
            try:
                is_cold = is_cold_start()
                logger.warning(
                    f"[REMOVE LATER] Cold start detection successful: {is_cold}"
                )
            except Exception as cold_start_error:
                logger.warning(
                    f"[REMOVE LATER] Cold start detection failed "
                    f"(failing safe to False): {cold_start_error}",
                    exc_info=True,
                )

            metrics = LambdaExecutionMetrics(
                start_timestamp=start_time,
                end_timestamp=end_time,
                duration_ms=duration,
                user=tracking_context["user"],
                account=claims.get("account", "unknown"),
                api_key_id=claims.get("api_key_id"),
                operation=tracking_context["operation"],
                endpoint=tracking_context["endpoint"],
                api_accessed=tracking_context["api_accessed"],
                status_code=status_code,
                success=status_code < 400,
                error_type=error_type,
                request_id=tracking_context.get("request_id"),
                memory_limit_mb=tracking_context.get("memory_limit"),
                max_memory_used_mb=max_memory_used_mb,
                is_cold_start=is_cold,
                purpose=claims.get("purpose"),
                service_name=tracking_context.get("service_name"),
                function_name=tracking_context.get("function_name"),
            )

            logger.debug(
                f"Ended tracking: duration={duration:.2f}ms, "
                f"memory={max_memory_used_mb or 'unknown'}MB, "
                f"status={status_code}, cold_start={is_cold}, "
                f"cost=${metrics.estimated_cost_usd()}"
            )
            return metrics

        except Exception as e:
            logger.error(f"Error ending tracking: {e}", exc_info=True)
            return None

    def record_metrics(self, metrics: Optional[LambdaExecutionMetrics]) -> None:
        """Store metrics in ADDITIONAL_CHARGES_TABLE.

        Format matches code interpreter pattern with all details in 'details' field.
        This is designed to be fire-and-forget to avoid impacting
        Lambda response times. Errors are logged but not raised.

        Args:
            metrics: Metrics object to store, or None to skip
        """
        if not self.enabled or not metrics:
            logger.warning(
                "[REMOVE LATER] record_metrics skipped: enabled=%s, metrics=%s",
                self.enabled,
                metrics is not None,
            )
            return

        # TODO: REMOVE LATER - temporary fail-safe for ADDITIONAL_CHARGES_TABLE
        table_name = os.getenv("ADDITIONAL_CHARGES_TABLE")
        if not table_name:
            logger.warning(
                "[REMOVE LATER] ADDITIONAL_CHARGES_TABLE not set, "
                "skipping metrics recording. This is a temporary fail-safe. "
                "Metrics would be: user=%s, duration=%.2fms, cost=$%s",
                metrics.user,
                metrics.duration_ms,
                metrics.estimated_cost_usd(),
            )
            return

        try:
            import time
            import uuid
            from datetime import datetime

            # Generate unique ID for this execution record
            execution_id = f"{metrics.user}#lambda#{uuid.uuid4()}"

            # Calculate cost (top-level for easy querying)
            cost = metrics.estimated_cost_usd()

            # Calculate TTL: 90 days from now (Lambda records are temporary)
            ttl = int(time.time()) + (90 * 24 * 60 * 60)

            # Build details object with all execution data
            details = {
                "itemType": "lambda_execution",
                "execution": {
                    "service_name": metrics.service_name,
                    "function_name": metrics.function_name,
                    "operation": metrics.operation,
                    "endpoint": metrics.endpoint,
                    "event_source": getattr(metrics, "event_source", None),
                    "duration_ms": Decimal(str(metrics.duration_ms)),
                    "duration_ms_padded": Decimal(
                        str(metrics.get_padded_duration_ms())
                    ),
                    "memory_limit_mb": metrics.memory_limit_mb,
                    "max_memory_used_mb": metrics.max_memory_used_mb,
                    "is_cold_start": metrics.is_cold_start,
                    "estimated_cost_usd": cost,  # Based on padded duration by default
                    "status_code": metrics.status_code,
                    "success": metrics.success,
                    "api_accessed": metrics.api_accessed,
                    "timestamp": metrics.start_timestamp.isoformat(),
                    "request_id": metrics.request_id,
                },
            }

            # Add optional fields
            if metrics.error_type:
                details["execution"]["error_type"] = metrics.error_type
            if metrics.api_key_id:
                details["execution"]["api_key_id"] = metrics.api_key_id
            if metrics.purpose:
                details["execution"]["purpose"] = metrics.purpose

            # Create ADDITIONAL_CHARGES_TABLE item
            item = {
                "id": execution_id,
                "user": metrics.user,
                "accountId": metrics.account,
                "cost": cost,  # Top-level cost field for easy aggregation
                "ttl": ttl,  # Auto-delete after 90 days
                "details": details,
                "modelId": (
                    f"{metrics.service_name or 'unknown'}/"
                    f"{metrics.function_name or 'unknown'}"
                ),
                "time": datetime.utcnow().isoformat() + "Z",
                "requestId": metrics.request_id or "unknown",
            }

            self.table.put_item(Item=item)

            logger.info(
                f"Recorded metrics to ADDITIONAL_CHARGES: user={metrics.user}, "
                f"service={metrics.service_name}, "
                f"func={metrics.function_name}, "
                f"duration={metrics.duration_ms:.2f}ms, "
                f"cost=${metrics.estimated_cost_usd()}"
            )

        except Exception as e:
            # Log error but don't raise - we never want metrics to break the main flow
            logger.error(f"Failed to record metrics: {e}", exc_info=True)


# Global singleton instance
_usage_tracker: Optional[UsageTracker] = None


def is_cold_start() -> bool:
    """Detect if this is a Lambda cold start.

    Lambda containers are reused across invocations. The first invocation
    after container creation is a "cold start" with significant initialization
    overhead (2000+ ms). Subsequent invocations are "warm starts".

    This function returns True only on the first call per container,
    then False for all subsequent calls.

    Returns:
        bool: True if this is a cold start, False if warm start
    """
    global _cold_start
    if _cold_start:
        _cold_start = False
        return True
    return False


def get_usage_tracker() -> UsageTracker:
    """Get or create the global usage tracker instance.

    Returns:
        UsageTracker: The global usage tracker singleton
    """
    global _usage_tracker
    if _usage_tracker is None:
        _usage_tracker = UsageTracker()
    return _usage_tracker
