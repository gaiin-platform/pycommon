# Copyright (c) 2025 Vanderbilt University
# Authors: Jules White, Allen Karns, Karely Rodriguez, Max Moundas

"""
critical_logging.py

This module provides a centralized logging mechanism for critical errors across
all Lambda functions. It allows any service to record critical failures to a
dedicated DynamoDB table for admin monitoring and resolution.

The log_critical_error function can be imported and used in any Lambda to record
critical errors without requiring admin privileges or special permissions.
"""

import os
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError

from pycommon.dal.providers.aws.resource_perms import SQSOperation
from pycommon.decorators import required_env_vars
from pycommon.encoders import dumps_smart
from pycommon.exceptions import EnvVarError
from pycommon.logger import getLogger

logger = getLogger("critical_logging")


# Constants
STATUS_ACTIVE = "ACTIVE"
SEVERITY_CRITICAL = "CRITICAL"
SEVERITY_HIGH = "HIGH"
SEVERITY_MEDIUM = "MEDIUM"
SEVERITY_LOW = "LOW"


@required_env_vars({"CRITICAL_ERRORS_SQS_QUEUE_NAME": [SQSOperation.SEND_MESSAGE]})
def _log_critical_error_internal(
    function_name: str,
    error_type: str,
    error_message: str,
    current_user: Optional[str] = None,
    severity: str = SEVERITY_CRITICAL,
    stack_trace: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    service_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Internal function with environment variable resolution and tracking.
    This function assumes CRITICAL_ERRORS_SQS_QUEUE_NAME is available.
    """
    logger.error(error_message)
    # Auto-detect service name if not provided
    if service_name is None:
        service_name = os.getenv("SERVICE_NAME", "unknown")

    # Get SQS queue URL (guaranteed to be available due to decorator)
    queue_url = os.environ["CRITICAL_ERRORS_SQS_QUEUE_NAME"]

    # Create SQS client when needed (lazy initialization)
    sqs_client = boto3.client("sqs")

    # Prepare message payload
    message_body = {
        "service_name": service_name,
        "function_name": function_name,
        "error_type": error_type,
        "error_message": error_message,
        "current_user": current_user,
        "severity": severity,
        "stack_trace": stack_trace,
        "context": context,
    }

    # Send to SQS
    sqs_client.send_message(
        QueueUrl=queue_url,
        MessageBody=dumps_smart(message_body),
        MessageAttributes={
            "severity": {"StringValue": severity, "DataType": "String"},
            "service_name": {"StringValue": service_name, "DataType": "String"},
        },
    )

    logger.info(
        "Critical error queued: %s.%s | Type: %s",
        service_name,
        function_name,
        error_type,
    )

    return {"success": True, "message": "Critical error queued for processing"}


def log_critical_error(
    function_name: str,
    error_type: str,
    error_message: str,
    current_user: Optional[str] = None,
    severity: str = SEVERITY_CRITICAL,
    stack_trace: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    service_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Log a critical error by sending it to an SQS queue for processing.

    This function is FAIL-SAFE and will never throw exceptions or block the caller.
    Errors are sent to SQS asynchronously for processing by amplify-lambda-admin.

    This function is intentionally NOT decorated with @validated because it needs
    to be called from internal service code, not via API endpoints.

    Args:
        function_name (str): Specific function/handler name
                            Example: "update_configs", "process_payment"
        error_type (str): Classification of the error
                         Example: "DatabaseConnectionFailure", "S3UploadError"
        error_message (str): Detailed error message describing what went wrong
        current_user (Optional[str]): Username/email of the user who triggered the error
                                     Example: "user@example.com"
                                     If None, will be recorded as "system"
        severity (str): Error severity level. Defaults to "CRITICAL"
                       Options: "CRITICAL", "HIGH", "MEDIUM", "LOW"
        stack_trace (Optional[str]): Full stack trace for debugging
                                     Can be captured via traceback.format_exc()
        context (Optional[Dict[str, Any]]): Additional metadata as dictionary
                                           Can include: user_id, request_id,
                                           aws_region, custom fields, etc.
        service_name (Optional[str]): Name of the service where error occurred.
                                     If None, automatically uses SERVICE_NAME env var.
                                     Example: "amplify-lambda-admin",
                                     "amplify-lambda-api"

    Returns:
        Dict[str, Any]: Response dictionary with structure:
            {
                "success": True,
                "message": "Critical error queued for processing"
            }
            Always returns success=True to indicate fail-safe operation.

    Example:
        >>> from pycommon.api.critical_logging import log_critical_error
        >>> import traceback
        >>>
        >>> try:
        >>>     process_payment(order_id, current_user)
        >>> except Exception as e:
        >>>     log_critical_error(
        >>>         function_name="process_payment",
        >>>         error_type="PaymentProcessingFailure",
        >>>         error_message=str(e),
        >>>         current_user=current_user,
        >>>         severity="CRITICAL",
        >>>         stack_trace=traceback.format_exc(),
        >>>         context={"order_id": order_id}
        >>>     )

    Environment Variables Required:
        CRITICAL_ERRORS_SQS_QUEUE_NAME: SQS queue URL for critical errors
        SERVICE_NAME (optional): Auto-detected service name

    Note: This function uses @required_env_vars decorator internally for Parameter
    Store fallback and usage tracking, but maintains fail-safe behavior.
    """
    # FAIL-SAFE: Try to use the decorated internal function with all benefits
    try:
        return _log_critical_error_internal(
            function_name=function_name,
            error_type=error_type,
            error_message=error_message,
            current_user=current_user,
            severity=severity,
            stack_trace=stack_trace,
            context=context,
            service_name=service_name,
        )

    except EnvVarError:
        # Environment variable not available (no Parameter Store fallback worked)
        # Fall back to graceful handling
        logger.warning(
            "CRITICAL_ERRORS_SQS_QUEUE_NAME not available, cannot log: %s.%s - %s",
            service_name or "unknown",
            function_name,
            error_type,
        )
        return {
            "success": True,
            "message": "Queue URL not configured, error not logged",
        }

    except ClientError as e:
        # SQS-specific errors (queue doesn't exist, no permissions, etc.)
        logger.error("SQS error logging critical error (fail-safe mode): %s", str(e))
        return {"success": True, "message": "SQS error, logged locally only"}

    except Exception as e:
        # Any other unexpected errors
        logger.error(
            "Unexpected error logging critical error (fail-safe mode): %s", str(e)
        )
        return {"success": True, "message": "Unexpected error, logged locally only"}
