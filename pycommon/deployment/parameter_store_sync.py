"""
Parameter Store Synchronization Utilities

Core logic for automatically populating AWS Parameter Store with locally
defined environment variables from serverless deployments.

This module is used by per-service Lambda functions to sync their
environment variables to Parameter Store for cross-service access.
"""

import logging
from typing import Dict, Optional

import boto3

logger = logging.getLogger(__name__)


def extract_locally_defined_vars(
    env_vars: Dict[str, str], service_name: str, stage: str
) -> Dict[str, str]:
    """
    Extract locally-defined variables by checking if their VALUES match the pattern:
    ${service_name}-${stage}-*

    This is SAFE because:
    1. Only syncs vars whose VALUES start with the service-stage prefix
    2. Won't sync imported SSM parameters (they're paths like /amplify/...)
    3. Won't sync AWS-managed vars (like AWS_REGION, AWS_LAMBDA_FUNCTION_NAME, etc.)
    4. Automatic - no hardcoded list to maintain

    Example:
        POLL_STATUS_TABLE = "amplify-v6-lambda-dev-poll-status"  ✓ SYNC
        API_KEYS_DYNAMODB_TABLE = "/amplify/dev/amplify-v6-lambda/KEY"
            ✗ SKIP (imported)
        AWS_REGION = "us-east-1"  ✗ SKIP (AWS-managed)
        AWS_LAMBDA_FUNCTION_NAME = "amplify-v6-lambda-dev-xxx"
            ✗ SKIP (AWS-managed, even though value matches pattern)

    Args:
        env_vars: Environment variables from Lambda function
        service_name: Service name (e.g., "amplify-v6-lambda")
        stage: Deployment stage (e.g., "dev")

    Returns:
        Dict of locally-defined variable names to their resolved values
    """
    # AWS-managed environment variables to exclude
    AWS_MANAGED_VARS = {
        "AWS_LAMBDA_FUNCTION_NAME",
        "AWS_LAMBDA_FUNCTION_VERSION",
        "AWS_LAMBDA_FUNCTION_MEMORY_SIZE",
        "AWS_LAMBDA_LOG_GROUP_NAME",
        "AWS_LAMBDA_LOG_STREAM_NAME",
        "AWS_REGION",
        "AWS_DEFAULT_REGION",
        "AWS_EXECUTION_ENV",
        "AWS_LAMBDA_RUNTIME_API",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "TZ",
        "LAMBDA_TASK_ROOT",
        "LAMBDA_RUNTIME_DIR",
        "_HANDLER",
        "_X_AMZN_TRACE_ID",
    }

    locally_defined = {}
    prefix = f"{service_name}-{stage}-"

    logger.info(f"Looking for locally-defined variables with prefix: {prefix}")

    for var_name, var_value in env_vars.items():
        # Skip AWS-managed variables
        if var_name in AWS_MANAGED_VARS or var_name.startswith("AWS_"):
            logger.debug(f"✗ Skipping AWS-managed variable: {var_name}")
            continue

        # Skip empty values
        if not var_value:
            continue

        # Check if value starts with our service-stage prefix
        if var_value.startswith(prefix):
            locally_defined[var_name] = var_value
            logger.info(f"✓ Found locally defined variable: {var_name} = {var_value}")
        else:
            # Log skipped variables for debugging
            preview = var_value[:50] if len(var_value) > 50 else var_value
            logger.debug(
                f"✗ Skipping non-local variable: {var_name} = " f"{preview}..."
            )

    logger.info(f"Extracted {len(locally_defined)} locally-defined variables")
    return locally_defined


def create_or_update_parameter(
    parameter_name: str,
    value: str,
    description: str,
    ssm_client: Optional[object] = None,
) -> Dict[str, str]:
    """
    Create or update a parameter in AWS Parameter Store.

    Args:
        parameter_name: Full parameter path (e.g., /amplify/dev/service/VAR_NAME)
        value: Parameter value
        description: Parameter description
        ssm_client: Optional boto3 SSM client (for testing/dependency injection)

    Returns:
        Dict with status and message
    """
    if ssm_client is None:
        ssm_client = boto3.client("ssm")

    try:
        # Check if parameter exists
        try:
            existing = ssm_client.get_parameter(Name=parameter_name)
            existing_value = existing["Parameter"]["Value"]

            # Update if different
            if existing_value != value:
                ssm_client.put_parameter(
                    Name=parameter_name,
                    Value=value,
                    Type="String",
                    Overwrite=True,
                    Description=description,
                )
                logger.info(f"Updated: {parameter_name} = {value}")
                return {
                    "status": "updated",
                    "message": f"Updated from {existing_value} to {value}",
                }
            else:
                logger.info(f"No change: {parameter_name}")
                return {"status": "unchanged", "message": "Value already correct"}

        except ssm_client.exceptions.ParameterNotFound:
            # Create new parameter
            ssm_client.put_parameter(
                Name=parameter_name, Value=value, Type="String", Description=description
            )
            logger.info(f"Created: {parameter_name} = {value}")
            return {"status": "created", "message": f"Created with value {value}"}

    except Exception as e:
        error_msg = f"Error managing parameter {parameter_name}: {e}"
        logger.error(error_msg)
        return {"status": "error", "message": error_msg}


def populate_parameters(
    service_name: str,
    stage: str,
    env_vars: Dict[str, str],
    ssm_client: Optional[object] = None,
) -> Dict:
    """
    Populate Parameter Store with locally defined variables.

    Args:
        service_name: Service name
        stage: Deployment stage
        env_vars: Environment variables from stack
        ssm_client: Optional boto3 SSM client (for testing/dependency injection)

    Returns:
        Dict with results containing:
            - totalVariables: Number of variables processed
            - created: Number of parameters created
            - updated: Number of parameters updated
            - unchanged: Number of parameters unchanged
            - errors: Number of errors
            - variables: Dict of variable names to results
    """
    # Extract locally defined variables
    locally_defined = extract_locally_defined_vars(env_vars, service_name, stage)

    if not locally_defined:
        logger.info("No locally defined variables found")
        return {
            "totalVariables": 0,
            "created": 0,
            "updated": 0,
            "unchanged": 0,
            "errors": 0,
            "variables": {},
        }

    logger.info(f"Found {len(locally_defined)} locally defined variables to populate")

    # Process each variable
    results = {
        "totalVariables": len(locally_defined),
        "created": 0,
        "updated": 0,
        "unchanged": 0,
        "errors": 0,
        "variables": {},
    }

    for var_name, resolved_value in locally_defined.items():
        # Create parameter path: /amplify/{stage}/{service_name}/{var_name}
        parameter_name = f"/amplify/{stage}/{service_name}/{var_name}"

        # Create or update the parameter
        result = create_or_update_parameter(
            parameter_name=parameter_name,
            value=resolved_value,
            description=f"Locally defined variable from {service_name} service",
            ssm_client=ssm_client,
        )

        # Track results
        results["variables"][var_name] = result
        if result["status"] == "created":
            results["created"] += 1
        elif result["status"] == "updated":
            results["updated"] += 1
        elif result["status"] == "unchanged":
            results["unchanged"] += 1
        elif result["status"] == "error":
            results["errors"] += 1
        else:
            # Unexpected status - log warning but continue
            logger.warning(f"Unexpected status '{result['status']}' for {var_name}")
            results["errors"] += 1

    logger.info(
        f"Parameter Store population complete: "
        f"{results['created']} created, {results['updated']} updated, "
        f"{results['unchanged']} unchanged, {results['errors']} errors"
    )

    return results
