import os
import time
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import boto3
from boto3.dynamodb.types import TypeSerializer

from pycommon.api.critical_logging import log_critical_error
from pycommon.dal.providers.aws.resource_perms import DynamoDBOperation
from pycommon.decorators import required_env_vars
from pycommon.logger import getLogger

logger = getLogger("accounting")


def _get_dynamodb_client():
    """Lazy initialization of DynamoDB client to avoid import-time boto3 calls."""
    return boto3.client("dynamodb")


@required_env_vars(
    {
        "ADDITIONAL_CHARGES_TABLE": [DynamoDBOperation.PUT_ITEM],
        "MODEL_RATE_TABLE": [DynamoDBOperation.GET_ITEM],
    }
)
def record_additional_charge(
    account: Dict[str, Any],
    model_id: str,
    token_count: int,
    item_type: str,
    request_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ttl_days: Optional[int] = None,
) -> float:
    """Records additional charges (e.g., embeddings, image generation) to DynamoDB.

    This function is a reusable, dynamic way to record additional charges for various
    services beyond regular LLM chat usage. It calculates costs based on model rates
    and stores them in the ADDITIONAL_CHARGES_TABLE.

    Args:
        account (Dict[str, Any]): Account information containing 'user' and
                                   optionally 'account_id' or 'account'
        model_id (str): Model identifier (e.g., 'text-embedding-3-small',
                        'dall-e-3')
        token_count (int): Number of input tokens used (or equivalent units)
        item_type (str): Type of additional charge (e.g., 'embedding',
                         'image_generation', 'fine_tuning')
        request_id (Optional[str]): Unique request identifier. Defaults to
                                    generated UUID if not provided
        details (Optional[Dict[str, Any]]): Additional metadata to store with
                                             the charge record. Defaults to None.
        ttl_days (Optional[int]): Number of days until record expires (TTL).
                                  If None, no TTL is set.

    Returns:
        float: Total cost calculated for this charge in USD.
               Returns 0.0 if recording fails or environment variables are missing.

    Environment Variables Required:
        ADDITIONAL_CHARGES_TABLE: Table name for storing additional charge records
        MODEL_RATE_TABLE: Table name containing model pricing information

    Note:
        Environment variables are validated and resolved by the @required_env_vars
        decorator. Variables can be provided via Lambda environment or Parameter Store.

    Example:
        >>> account = {"user": "user@example.com", "account_id": "acc-123"}
        >>> cost = record_additional_charge(
        ...     account=account,
        ...     model_id="text-embedding-3-small",
        ...     token_count=1500,
        ...     item_type="embedding",
        ...     details={"document_key": "doc-456.pdf"}
        ... )
        >>> print(f"Cost recorded: ${cost:.6f}")
    """
    # Environment variables guaranteed by @required_env_vars decorator
    additional_charges_table_name = os.environ["ADDITIONAL_CHARGES_TABLE"]
    model_rate_table_name = os.environ["MODEL_RATE_TABLE"]

    try:
        # Validate account data
        if not account or not account.get("user"):
            logger.warning(
                "Missing account.user for additional charge tracking: %s", item_type
            )
            return 0.0

        # Get account_id with fallback
        account_id = (
            account.get("account_id") or account.get("account") or "general_account"
        )

        # Query model rate
        model_rate_response = _get_dynamodb_client().query(
            TableName=model_rate_table_name,
            KeyConditionExpression="ModelID = :modelId",
            ExpressionAttributeValues={":modelId": {"S": model_id}},
        )

        if (
            not model_rate_response.get("Items")
            or len(model_rate_response["Items"]) == 0
        ):
            logger.warning(
                "No pricing found for model: %s (item_type: %s)", model_id, item_type
            )
            return 0.0

        model_rate = model_rate_response["Items"][0]
        input_cost_per_thousand = float(
            model_rate.get("InputCostPerThousandTokens", {}).get("N", "0")
        )

        # Calculate cost
        cost = (token_count / 1000.0) * input_cost_per_thousand

        # Generate record ID and timestamp
        record_id = f"{account['user']}#{item_type}#{request_id or str(uuid.uuid4())}"
        timestamp = datetime.now(timezone.utc).isoformat()

        # Build details dictionary
        charge_details = {
            "itemType": {"S": item_type},
            "model_id": {"S": model_id},
            "token_count": {"N": str(token_count)},
        }

        # Add custom details if provided
        if details:
            for key, value in details.items():
                # Check bool first because bool is a subclass of int in Python
                if isinstance(value, bool):
                    charge_details[key] = {"BOOL": value}
                elif isinstance(value, str):
                    charge_details[key] = {"S": value}
                elif isinstance(value, (int, float)):
                    charge_details[key] = {"N": str(value)}
                elif isinstance(value, dict):
                    charge_details[key] = {"M": TypeSerializer().serialize(value)["M"]}
                else:
                    # For other types (lists, None, etc.), convert to string
                    charge_details[key] = {"S": str(value)}

        # Create ADDITIONAL_CHARGES_TABLE item
        item = {
            "id": {"S": record_id},
            "user": {"S": account["user"]},
            "accountId": {"S": account_id},
            "cost": {"N": str(cost)},
            "details": {"M": charge_details},
            "modelId": {"S": model_id},
            "time": {"S": timestamp},
            "requestId": {"S": request_id or f"{item_type}-batch"},
        }

        # Add TTL if specified
        if ttl_days is not None:
            ttl = int(time.time()) + (ttl_days * 24 * 60 * 60)
            item["ttl"] = {"N": str(ttl)}

        _get_dynamodb_client().put_item(
            TableName=additional_charges_table_name, Item=item
        )

        logger.debug(
            "Additional charge recorded: $%.6f for %d tokens using %s (type: %s)",
            cost,
            token_count,
            model_id,
            item_type,
        )

        return cost

    except Exception as e:
        # Never let cost tracking break the main flow
        logger.error("Failed to record additional charge for %s: %s", item_type, str(e))

        # Log critical error for billing data loss
        try:
            log_critical_error(
                function_name="record_additional_charge",
                error_type="AdditionalChargeRecordingFailure",
                error_message=(
                    f"Failed to record {item_type} charge to DynamoDB: "
                    f"{str(e) or 'Unknown error'}"
                ),
                current_user=account.get("user", "unknown") if account else "unknown",
                severity="HIGH",
                stack_trace=traceback.format_exc(),
                context={
                    "item_type": item_type,
                    "model_id": model_id,
                    "token_count": token_count,
                    "account_id": (
                        (
                            account.get("account_id")
                            or account.get("account")
                            or "general_account"
                        )
                        if account
                        else "unknown"
                    ),
                    "request_id": request_id or "unknown",
                    "table_name": additional_charges_table_name,
                },
            )
        except Exception as log_err:
            logger.error("Failed to log critical error: %s", str(log_err))

        return 0.0


@required_env_vars(
    {
        "CHAT_USAGE_DYNAMO_TABLE": [DynamoDBOperation.PUT_ITEM],
        "COST_CALCULATIONS_DYNAMO_TABLE": [
            DynamoDBOperation.PUT_ITEM,
            DynamoDBOperation.UPDATE_ITEM,
        ],
        "MODEL_RATE_TABLE": [DynamoDBOperation.GET_ITEM],
    }
)
def record_usage(
    account: Dict[str, Any],
    request_id: str,
    model_id: str,
    input_tokens: int,
    output_tokens: int,
    cached_tokens: int,
    details: Optional[Dict[str, Any]] = None,
) -> float:
    """Records usage and costs in DynamoDB tables.

    This function records LLM usage to the chat-usage table and calculates
    the cost based on model rates, storing the cost in the cost-calculations table.

    Args:
        account (Dict[str, Any]): Account information containing 'user', 'account_id',
                                   and optionally 'accessToken' and 'api_key_id'
        request_id (str): Unique request identifier for the LLM call
        model_id (str): Model identifier (e.g., 'gpt-4o', 'claude-3-5-sonnet')
        input_tokens (int): Number of input tokens used
        output_tokens (int): Number of output tokens generated
        cached_tokens (int): Number of cached tokens used
        details (Optional[Dict[str, Any]]): Additional metadata to store with
                                             usage record. Defaults to None.

    Returns:
        float: Total cost calculated for this usage (input + output + cached cost).
               Returns 0.0 if recording fails or environment variables are missing.

    Environment Variables Required:
        CHAT_USAGE_DYNAMO_TABLE: Table name for storing usage records
        COST_CALCULATIONS_DYNAMO_TABLE: Table name for storing cost calculations
        MODEL_RATE_TABLE: Table name containing model pricing information

    Note:
        Environment variables are validated and resolved by the @required_env_vars
        decorator. Variables can be provided via Lambda environment or Parameter Store.
    """
    # Environment variables guaranteed by @required_env_vars decorator
    dynamoTableName = os.environ["CHAT_USAGE_DYNAMO_TABLE"]
    costDynamoTableName = os.environ["COST_CALCULATIONS_DYNAMO_TABLE"]
    modelRateDynamoTable = os.environ["MODEL_RATE_TABLE"]

    api_key_id = get_api_key_id(account)

    try:
        account_id = account.get("account_id", "general_account")

        if details is None:
            details = {}

        if api_key_id:
            details = {**details, "api_key_id": api_key_id}

        item = {
            "id": {"S": str(uuid.uuid4())},
            "requestId": {"S": request_id},
            "user": {"S": account["user"]},
            "time": {"S": datetime.now().isoformat()},
            "accountId": {"S": account_id},
            "inputTokens": {"N": str(input_tokens)},
            "outputTokens": {"N": str(output_tokens)},
            "modelId": {"S": model_id},
            "details": {"M": TypeSerializer().serialize(details)["M"]},
        }

        _get_dynamodb_client().put_item(TableName=dynamoTableName, Item=item)
        logger.info(f"Usage recorded for user: {account['user']}")

    except Exception as e:
        logger.error(f"Error recording usage: {e}")

        # CRITICAL: Usage recording failed - billing data loss
        try:
            log_critical_error(
                function_name="record_usage",
                error_type="UsageRecordingFailure",
                error_message=(
                    f"Failed to record usage to DynamoDB: {str(e) or 'Unknown error'}"
                ),
                current_user=account.get("user", "unknown") if account else "unknown",
                severity="HIGH",
                stack_trace=traceback.format_exc(),
                context={
                    "request_id": request_id or "unknown",
                    "model_id": model_id,
                    "account_id": (
                        account.get("account_id", "general_account")
                        if account
                        else "general_account"
                    ),
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "cached_tokens": cached_tokens,
                    "table_name": dynamoTableName,
                },
            )
        except Exception as log_err:
            logger.error(f"Failed to log critical error: {log_err}")

        return 0.0

    try:
        model_rate_response = _get_dynamodb_client().query(
            TableName=modelRateDynamoTable,
            KeyConditionExpression="ModelID = :modelId",
            ExpressionAttributeValues={":modelId": {"S": model_id}},
        )

        if (
            not model_rate_response.get("Items")
            or len(model_rate_response["Items"]) == 0
        ):
            logger.warning(f"No model rate found for ModelID: {model_id}")
            return 0.0

        model_rate = model_rate_response["Items"][0]
        input_cost_per_thousand_tokens = float(
            model_rate["InputCostPerThousandTokens"]["N"]
        )
        output_cost_per_thousand_tokens = float(
            model_rate["OutputCostPerThousandTokens"]["N"]
        )
        cached_cost_per_thousand_tokens = float(
            model_rate["CachedCostPerThousandTokens"]["N"]
        )

        input_cost = (input_tokens / 1000) * input_cost_per_thousand_tokens
        output_cost = (output_tokens / 1000) * output_cost_per_thousand_tokens
        cached_cost = (cached_tokens / 1000) * cached_cost_per_thousand_tokens
        total_cost = input_cost + output_cost + cached_cost

        logger.info(f"Total cost calculated: ${total_cost:.6f}")

        now = datetime.now(timezone.utc)
        current_hour = now.hour

        # Create the accountInfo (secondary key)
        coa_string = account.get("accountId", "general_account")
        apiKeyIdInfo = api_key_id or "NA"
        account_info = f"{coa_string}#{apiKeyIdInfo}"

        # First update: Ensure dailyCost and hourlyCost are initialized
        empty_list = [{"N": "0"} for _ in range(24)]

        _get_dynamodb_client().update_item(
            TableName=costDynamoTableName,
            Key={"id": {"S": account["user"]}, "accountInfo": {"S": account_info}},
            UpdateExpression=(
                "SET dailyCost = if_not_exists(dailyCost, :zero), "
                "hourlyCost = if_not_exists(hourlyCost, :emptyList), "
                "record_type = if_not_exists(record_type, :recordType)"
            ),
            ExpressionAttributeValues={
                ":zero": {"N": "0"},
                ":emptyList": {"L": empty_list},
                ":recordType": {"S": "cost"},
            },
        )

        # Second update: Update dailyCost and the specific hourlyCost index
        _get_dynamodb_client().update_item(
            TableName=costDynamoTableName,
            Key={"id": {"S": account["user"]}, "accountInfo": {"S": account_info}},
            UpdateExpression=(
                f"SET dailyCost = dailyCost + :totalCost "
                f"ADD hourlyCost[{current_hour}] :totalCost"
            ),
            ExpressionAttributeValues={":totalCost": {"N": str(total_cost)}},
        )
        logger.info(f"Updated dailyCost and hourlyCost for user: {account['user']}")
        return total_cost
    except Exception as e:
        logger.error(f"Error calculating or updating cost: {e}")

        # CRITICAL: Cost calculation/update failed - billing/cost tracking data loss
        try:
            log_critical_error(
                function_name="record_usage_costCalculation",
                error_type="CostCalculationFailure",
                error_message=(
                    f"Failed to calculate or update cost in DynamoDB: "
                    f"{str(e) or 'Unknown error'}"
                ),
                current_user=account.get("user", "unknown") if account else "unknown",
                severity="HIGH",
                stack_trace=traceback.format_exc(),
                context={
                    "request_id": request_id or "unknown",
                    "model_id": model_id,
                    "account_id": (
                        account.get("account_id", "general_account")
                        if account
                        else "general_account"
                    ),
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "cached_tokens": cached_tokens,
                    "cost_table_name": costDynamoTableName,
                    "model_rate_table": modelRateDynamoTable,
                },
            )
        except Exception as log_err:
            logger.error(f"Failed to log critical error: {log_err}")

    return 0.0


def get_api_key_id(account: Dict[str, Any]) -> Optional[str]:
    """Returns the API key ID if the access token starts with "amp-" and
    apiKeyId exists.

    Args:
        account (Dict[str, Any]): Account information containing optionally
                                   'accessToken' and 'api_key_id'

    Returns:
        Optional[str]: API key ID if conditions are met, None otherwise
    """
    if account.get("accessToken", "").startswith("amp-") and account.get("api_key_id"):
        return account["api_key_id"]
    return None
