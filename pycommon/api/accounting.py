import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import boto3
from boto3.dynamodb.types import TypeSerializer

from pycommon.dal.providers.aws.resource_perms import DynamoDBOperation
from pycommon.decorators import required_env_vars
from pycommon.logger import getLogger

logger = getLogger("accounting")

dynamodb = boto3.client("dynamodb")


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

        dynamodb.put_item(TableName=dynamoTableName, Item=item)
        logger.info(f"Usage recorded for user: {account['user']}")

    except Exception as e:
        logger.error(f"Error recording usage: {e}")
        return 0.0

    try:
        model_rate_response = dynamodb.query(
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

        dynamodb.update_item(
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
        dynamodb.update_item(
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
