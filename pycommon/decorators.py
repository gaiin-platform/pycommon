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

import logging
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

logger = logging.getLogger(__name__)


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
            return value

        # Try Parameter Store as fallback
        if self.ssm_enabled:
            try:
                parameter_path = f"/amplify/{self.stage}/{self.service_name}/{var_name}"
                response = self.ssm.get_parameter(Name=parameter_path)
                value = response["Parameter"]["Value"]

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
                resolved_value = os.getenv(var_name, "")

            # Convert operations to strings if they're enum values
            if operations is None:
                operations = []
            operation_strings = [
                op.value if hasattr(op, "value") else str(op) for op in operations
            ]

            timestamp = datetime.utcnow().isoformat() + "Z"

            # Try to update existing record
            try:
                response = self.table.get_item(Key={"service_var_key": service_var_key})
                if "Item" in response:
                    # Update existing record with new access time
                    self.table.update_item(
                        Key={"service_var_key": service_var_key},
                        UpdateExpression="SET last_accessed = :timestamp",
                        ExpressionAttributeValues={":timestamp": timestamp},
                    )
                    print(
                        f"ENV_VAR_TRACKING: UPDATED {service_var_key} - "
                        f"updated last_accessed timestamp"
                    )
                    logger.debug(f"Updated access tracking for {service_var_key}")
                    return
            except Exception:
                pass  # Fall through to create new record

            # Create new tracking record
            self.table.put_item(
                Item={
                    "service_var_key": service_var_key,
                    "service_name": self.service_name,
                    "var_name": var_name,
                    "resolved_value": resolved_value,
                    "parameter_path": parameter_path,
                    "operations": operation_strings,
                    "first_accessed": timestamp,
                    "last_accessed": timestamp,
                }
            )
            print(
                f"ENV_VAR_TRACKING: PUT NEW item for {service_var_key} - "
                f"first time tracking this variable"
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
