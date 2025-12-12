"""decorators.py provides common decorators for amplify services.

This module provides utility functions and decorators for validating data,
parsing tokens, and performing authorization checks. It centralizes logic
for request validation, permission checks, and rate limiting, ensuring
consistency and security across the codebase.

The module integrates with AWS DynamoDB for account and rate limit management,
supports OAuth-based authentication using JSON Web Tokens (JWT), and provides
environment variable tracking for centralized configuration management.

Copyright (c) 2025 Vanderbilt University
Authors: Jules White, Allen Karns, Karely Rodriguez, Max Moundas, Sam Hays
"""

import os
from datetime import datetime
from functools import wraps
from typing import Any, Callable, Dict, List

import boto3

from pycommon.dal.providers.aws.resource_perms import (  # noqa: F401
    BedrockOperation,
    CognitoOperation,
    DynamoDBOperation,
    LambdaOperation,
    S3Operation,
    SecretsManagerOperation,
    SQSOperation,
    SSMOperation,
)
from pycommon.exceptions import EnvVarError
from pycommon.logger import getLogger

logger = getLogger("decorators")


class EnvVarTracker:
    """Handles environment variable tracking and Parameter Store integration"""

    def __init__(self):
        self.stage = os.getenv("STAGE", "dev")
        self.service_name = os.getenv("SERVICE_NAME", "unknown")
        self.tracking_table = os.getenv("ENV_VARS_TRACKING_TABLE")
        self.region = os.getenv("AWS_REGION", "us-east-1")

        # Initialize DynamoDB for tracking
        self.tracking_enabled = False
        if self.tracking_table:
            try:
                self.dynamodb = boto3.resource("dynamodb", region_name=self.region)
                self.table = self.dynamodb.Table(self.tracking_table)
                self.tracking_enabled = True
                logger.debug(f"Environment tracking enabled: {self.tracking_table}")
            except Exception as e:
                logger.warning(f"Environment tracking unavailable: {e}")
        else:
            logger.debug("ENV_VARS_TRACKING_TABLE not set, tracking disabled")

        # Initialize SSM for Parameter Store fallback
        self.ssm_enabled = False
        try:
            self.ssm = boto3.client("ssm", region_name=self.region)
            self.ssm_enabled = True
            logger.debug("Parameter Store integration enabled")
        except Exception as e:
            logger.warning(f"Parameter Store unavailable: {e}")

    def resolve_env_var(self, var_name: str) -> str:
        """
        Resolve environment variable with fallback chain:
        1. Lambda environment variables (fastest)
        2. Parameter Store (if SSM available)
        3. Process environment
        4. Error
        """

        # First try Lambda environment (fastest, set by serverless)
        value = os.getenv(var_name)
        if value:
            logger.debug(f"Resolved {var_name} from Lambda environment")
            return value.strip()

        # Try Parameter Store as fallback
        if self.ssm_enabled:
            try:
                parameter_path = f"/amplify/{self.stage}/{self.service_name}/{var_name}"
                response = self.ssm.get_parameter(Name=parameter_path)
                value = response["Parameter"]["Value"].strip()

                # Cache in Lambda environment for future calls
                os.environ[var_name] = value
                logger.info(
                    f"Resolved {var_name} from Parameter Store: {parameter_path}"
                )
                return value

            except self.ssm.exceptions.ParameterNotFound:
                logger.debug(
                    f"Parameter not found in Parameter Store: {parameter_path}"
                )
            except Exception as e:
                logger.warning(f"Error accessing Parameter Store for {var_name}: {e}")

        # All resolution methods failed
        raise EnvVarError(
            f"Environment variable '{var_name}' not found in Lambda "
            f"environment or Parameter Store"
        )

    def track_env_var(
        self, var_name: str, operations: List[str] = None, resolved_value: str = None
    ):
        """Record environment variable usage in tracking table"""
        if not self.tracking_enabled:
            return

        try:
            service_var_key = f"{self.service_name}#{var_name}"
            parameter_path = f"/amplify/{self.stage}/{self.service_name}/{var_name}"

            # Use provided value or get current value
            if resolved_value is None:
                resolved_value = os.getenv(var_name, "").strip()

            # Convert operations to strings if they're enum values
            if operations is None:
                operations = []
            operation_strings = [
                op.value if hasattr(op, "value") else str(op) for op in operations
            ]

            # Check for version tracking
            version = os.getenv("VERSION")
            if version:
                version = version.strip()

            timestamp = datetime.utcnow().isoformat() + "Z"

            # Try to get existing record and merge operations
            try:
                response = self.table.get_item(Key={"service_var_key": service_var_key})
                if "Item" in response:
                    existing_item = response["Item"]
                    existing_operations = set(existing_item.get("operations", []))
                    new_operations = set(operation_strings)
                    existing_version = existing_item.get("version")

                    # Check if we need to update operations or version
                    operations_to_add = new_operations - existing_operations
                    version_changed = (
                        (version != existing_version) if version is not None else False
                    )
                    version_added = version is not None and existing_version is None

                    if operations_to_add or version_changed or version_added:
                        # Merge operations (existing + new)
                        merged_operations = list(existing_operations | new_operations)

                        # Build update expression dynamically
                        update_expression_parts = ["SET operations = :operations"]
                        expression_attribute_values = {":operations": merged_operations}

                        # Add version to update if it exists
                        if version is not None:
                            update_expression_parts.append("version = :version")
                            expression_attribute_values[":version"] = version

                        update_expression = ", ".join(update_expression_parts)

                        # Update record with merged operations and version
                        try:
                            response = self.table.update_item(
                                Key={"service_var_key": service_var_key},
                                UpdateExpression=update_expression,
                                ExpressionAttributeValues=expression_attribute_values,
                                ReturnValues="ALL_NEW",
                            )

                            version_info = f", version: {version}" if version else ""
                            logger.info(
                                f"ENV_VAR_TRACKING: MERGED {service_var_key} - "
                                f"added {list(operations_to_add)} → "
                                f"now: {response['Attributes']['operations']}"
                                f"{version_info}"
                            )
                            version_status = (
                                "changed"
                                if version_changed
                                else "added" if version_added else "unchanged"
                            )
                            logger.debug(
                                f"Updated {service_var_key}: "
                                f"operations={list(operations_to_add)}, "
                                f"version={version_status}"
                            )
                        except Exception as update_error:
                            logger.error(
                                f"ENV_VAR_TRACKING: MERGE FAILED {service_var_key} - "
                                f"{update_error}"
                            )
                            # Fall through to create new record if update fails
                            raise
                    return
            except Exception:
                pass  # Fall through to create new record

            # Create new tracking record (no last_accessed field)
            record_item = {
                "service_var_key": service_var_key,
                "service_name": self.service_name,
                "var_name": var_name,
                "resolved_value": resolved_value,
                "parameter_path": parameter_path,
                "operations": operation_strings,
                "first_accessed": timestamp,
            }

            # Only add version if it exists
            if version is not None:
                record_item["version"] = version

            self.table.put_item(Item=record_item)

            version_info = f", version: {version}" if version else ""
            logger.info(
                f"ENV_VAR_TRACKING: PUT NEW item for {service_var_key} - "
                f"operations: {operation_strings}{version_info}"
            )
            logger.info(f"Created new tracking record for {service_var_key}")

        except Exception as e:
            # Never fail the function for tracking issues
            logger.warning(f"Failed to track environment variable {var_name}: {e}")


def required_env_vars(env_vars_dict: Dict[str, List]) -> Callable:
    """
    Decorator to declare required environment variables with precise AWS IAM operations.

    Provides:
    - Environment variable resolution (Lambda env → Parameter Store → Error)
    - Usage tracking in DynamoDB with specific AWS operations
    - Precise IAM permission documentation for security auditing

    Works alongside @validated decorator for API Gateway functions.

    Args:
        env_vars_dict: Dictionary mapping env var names to required AWS
                      operations e.g., {
                          "ACCOUNTS_DYNAMO_TABLE": [DynamoDBOperation.GET_ITEM,
                                                   DynamoDBOperation.PUT_ITEM],
                          "S3_SHARE_BUCKET_NAME": [S3Operation.PUT_OBJECT,
                                                  S3Operation.GET_OBJECT]
                      }

    Example:
        @required_env_vars({
            "ACCOUNTS_DYNAMO_TABLE": [DynamoDBOperation.GET_ITEM,
                                     DynamoDBOperation.PUT_ITEM],
            "S3_SHARE_BUCKET_NAME": [S3Operation.PUT_OBJECT,
                                    S3Operation.GET_OBJECT],
            "LLM_ENDPOINTS_SECRETS_NAME_ARN": [
                SecretsManagerOperation.GET_SECRET_VALUE
            ]
        })
        @validated("get")
        def get_accounts(event, context, user, name, data):
            # Environment variables are resolved and tracked automatically
            accounts_table = os.environ["ACCOUNTS_DYNAMO_TABLE"]
            share_bucket = os.environ["S3_SHARE_BUCKET_NAME"]
            return {"statusCode": 200, "body": "Success"}

    Supported Operations:
        - DynamoDBOperation: GET_ITEM, PUT_ITEM, QUERY, SCAN, UPDATE_ITEM,
                           DELETE_ITEM, etc.
        - S3Operation: GET_OBJECT, PUT_OBJECT, DELETE_OBJECT, LIST_BUCKET, etc.
        - SecretsManagerOperation: GET_SECRET_VALUE, PUT_SECRET_VALUE, etc.
        - SQSOperation: SEND_MESSAGE, RECEIVE_MESSAGE, DELETE_MESSAGE, etc.
        - SSMOperation: GET_PARAMETER, PUT_PARAMETER, etc.
        - LambdaOperation: INVOKE_FUNCTION, GET_FUNCTION, etc.
        - BedrockOperation: INVOKE_MODEL, INVOKE_MODEL_WITH_RESPONSE_STREAM, etc.
        - CognitoOperation: ADMIN_GET_USER, ADMIN_CREATE_USER, etc.
    """

    def decorator(func: Callable) -> Callable:
        # Validate environment variable specifications
        if not isinstance(env_vars_dict, dict):
            raise ValueError(
                "required_env_vars expects a dictionary mapping env var names "
                "to operation lists"
            )

        # Parse environment variables and operations
        for var_name, operations in env_vars_dict.items():
            if not isinstance(var_name, str):
                raise ValueError(
                    f"Environment variable name must be a string: {var_name}"
                )
            if not isinstance(operations, list):
                raise ValueError(
                    f"Operations must be a list for {var_name}: {operations}"
                )
            for op in operations:
                if not hasattr(op, "value"):  # Check if it's an enum
                    raise ValueError(
                        f"Invalid operation {op} for {var_name}. Must use AWS "
                        f"operation enums (e.g., DynamoDBOperation.GET_ITEM)"
                    )

        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            tracker = EnvVarTracker()

            # Resolve and track all declared environment variables
            for var_name, operations in env_vars_dict.items():
                try:
                    # Resolve the environment variable (with Parameter Store fallback)
                    resolved_value = tracker.resolve_env_var(var_name)

                    # Ensure it's available in environment for the function
                    os.environ[var_name] = resolved_value

                    # Track usage in DynamoDB (non-blocking)
                    tracker.track_env_var(var_name, operations, resolved_value)

                except EnvVarError:
                    # Re-raise env variable errors - these should fail the function
                    logger.error(
                        f"Required environment variable '{var_name}' " f"not available"
                    )
                    raise
                except Exception as e:
                    # Other errors (tracking, etc.) shouldn't fail the function
                    logger.warning(
                        f"Non-critical error processing env var {var_name}: " f"{e}"
                    )

            # Call the original function with all environment variables resolved
            return func(*args, **kwargs)

        # Store metadata on function for introspection/documentation generation
        wrapper._required_env_vars = env_vars_dict
        wrapper._env_var_operations = {
            var_name: [op.value for op in operations]
            for var_name, operations in env_vars_dict.items()
        }

        return wrapper

    return decorator


def track_execution(
    operation_name: str,
    account: str = "system",
    user: str = "system",
    extract_from_event: bool = True,
) -> Callable:
    """
    Decorator for tracking event-driven Lambda executions (non-HTTP).

    Use this decorator for Lambda functions triggered by:
    - SQS messages
    - EventBridge/CloudWatch Events (scheduled tasks)
    - SNS notifications
    - S3 events
    - DynamoDB Streams
    - Email events (SES)
    - Any non-HTTP Lambda invocation

    This decorator tracks execution metrics including:
    - Duration and cost
    - Success/failure status
    - Event source information
    - Account and user attribution

    Args:
        operation_name: Name of the operation (e.g., "process_email_event",
                       "daily_cleanup_cron", "process_sqs_message")
        account: Default account to attribute costs to. Use "system" for
                system operations, or specify an account ID.
        user: Default user to attribute costs to. Use "system" for system
             operations, or specify a user ID.
        extract_from_event: If True, attempts to extract account/user from
                           the event payload (default: True)

    Example:
        # SQS handler with system account
        @track_execution(operation_name="process_sqs_message", account="system")
        def sqs_handler(event, context):
            for record in event["Records"]:
                # Process SQS message
                pass
            return {"success": True}

        # Scheduled task (cron)
        @track_execution(operation_name="daily_cleanup_cron")
        def daily_cleanup_handler(event, context):
            # Your cleanup logic
            return {"success": True}

        # Email event handler with user extraction
        @track_execution(operation_name="process_email_event", extract_from_event=True)
        def email_handler(event, context):
            # Event should contain {"user": "user123", "account": "acct456"}
            # These will be automatically extracted
            return {"success": True}

    Returns:
        Decorated function with usage tracking

    Note:
        - If tracking fails, the function continues normally (fail-safe)
        - Metrics are recorded to ADDITIONAL_CHARGES_TABLE
        - ADDITIONAL_CHARGES_TABLE environment variable (temporarily optional)
    """

    # TODO: REMOVE LATER - Temporarily commented out to allow fail-safe deployment
    # @required_env_vars(
    #     {
    #         "ADDITIONAL_CHARGES_TABLE": [
    #             DynamoDBOperation.PUT_ITEM
    #         ],  # DynamoDB table for additional charges (Lambda usage tracking)
    #     }
    # )
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(event: Dict[str, Any], context: Any, *args, **kwargs) -> Any:
            # Import here to avoid circular dependencies
            from pycommon.metrics import get_usage_tracker

            tracker = get_usage_tracker()

            # Extract account/user from event if enabled
            actual_account = account
            actual_user = user

            if extract_from_event and isinstance(event, dict):
                # Try various event structures
                actual_account = event.get("account", event.get("accountId", account))
                actual_user = event.get(
                    "user", event.get("currentUser", event.get("userId", user))
                )

                # Check if it's an SQS/SNS message with nested data
                if "Records" in event and event["Records"]:
                    record = event["Records"][0]
                    event_source = record.get("eventSource", "")

                    # Handle SQS messages
                    if "body" in record:
                        import json
                        import urllib.parse

                        try:
                            body = (
                                json.loads(record["body"])
                                if isinstance(record["body"], str)
                                else record["body"]
                            )
                            actual_account = body.get("account", actual_account)
                            actual_user = body.get(
                                "user",
                                body.get(
                                    "currentUser", body.get("username", actual_user)
                                ),
                            )

                            # Check if SQS body contains S3 event (embedding pattern)
                            if "Records" in body and body["Records"]:
                                s3_record = body["Records"][0]
                                if "s3" in s3_record:
                                    # Extract user from S3 key: format is
                                    # typically user/filename or user/date/filename
                                    s3_key = urllib.parse.unquote(
                                        s3_record["s3"]["object"]["key"]
                                    )
                                    key_parts = s3_key.split("/")
                                    if (
                                        len(key_parts) > 0 and actual_user == user
                                    ):  # Only if not already found
                                        # First part of key is usually the user
                                        potential_user = key_parts[0]
                                        # Validate it looks like a user
                                        # (email or UUID format)
                                        if "@" in potential_user or (
                                            "-" in potential_user
                                            and len(potential_user) > 20
                                        ):
                                            actual_user = potential_user
                        except (json.JSONDecodeError, AttributeError, IndexError):
                            pass

                    # Handle DynamoDB Streams
                    elif event_source == "aws:dynamodb" and "dynamodb" in record:
                        dynamodb_data = record["dynamodb"]
                        # Check NewImage for user/account
                        if "NewImage" in dynamodb_data:
                            new_image = dynamodb_data["NewImage"]
                            # DynamoDB format: {"user": {"S": "value"}}
                            if "user" in new_image:
                                actual_user = new_image["user"].get("S", actual_user)
                            elif "user_id" in new_image:
                                actual_user = new_image["user_id"].get("S", actual_user)
                            elif "username" in new_image:
                                actual_user = new_image["username"].get(
                                    "S", actual_user
                                )

                            if "account" in new_image:
                                actual_account = new_image["account"].get(
                                    "S", actual_account
                                )
                            elif "accountId" in new_image:
                                actual_account = new_image["accountId"].get(
                                    "S", actual_account
                                )

                    # Handle direct S3 events (not wrapped in SQS)
                    elif event_source == "aws:s3" and "s3" in record:
                        import urllib.parse

                        try:
                            s3_key = urllib.parse.unquote(record["s3"]["object"]["key"])
                            key_parts = s3_key.split("/")
                            if len(key_parts) > 0:
                                # First part of key is usually the user
                                potential_user = key_parts[0]
                                if "@" in potential_user or (
                                    "-" in potential_user and len(potential_user) > 20
                                ):
                                    actual_user = potential_user
                        except (AttributeError, IndexError):
                            pass

            # Determine event source for better tracking
            event_source = "unknown"

            if isinstance(event, dict):
                # SQS, SNS, S3, DynamoDB Streams
                if "Records" in event and event["Records"]:
                    record = event["Records"][0]
                    event_source = record.get("eventSource", "unknown")
                # EventBridge/CloudWatch Events
                elif "source" in event:
                    event_source = event["source"]
                # API Gateway (shouldn't use decorator, handle gracefully)
                elif "requestContext" in event:
                    event_source = "apigateway"

            # Create endpoint identifier for tracking
            endpoint = f"event://{event_source}/{operation_name}"

            tracking_context = tracker.start_tracking(
                user=actual_user,
                operation=operation_name,
                endpoint=endpoint,
                api_accessed=False,
                context=context,
            )

            try:
                # Execute the wrapped function
                result = f(event, context, *args, **kwargs)

                # Determine success from result
                success = True
                error_type = None

                if isinstance(result, dict):
                    success = result.get("success", True)
                    if not success:
                        error_type = result.get("error", "OperationFailed")

                # Create result dictionary for tracking
                result_dict = {"statusCode": 200 if success else 500}

                # End tracking
                metrics = tracker.end_tracking(
                    tracking_context=tracking_context,
                    result=result_dict,
                    claims={
                        "account": actual_account,
                        "username": actual_user,
                    },
                    error_type=error_type,
                )

                # Record metrics (async/fire-and-forget)
                tracker.record_metrics(metrics)

                return result

            except Exception as e:
                # Track failed execution
                result_dict = {"statusCode": 500}

                metrics = tracker.end_tracking(
                    tracking_context=tracking_context,
                    result=result_dict,
                    claims={
                        "account": actual_account,
                        "username": actual_user,
                    },
                    error_type=type(e).__name__,
                )

                # Record metrics even on failure
                tracker.record_metrics(metrics)

                # Re-raise the exception
                raise

        return wrapper

    return decorator
