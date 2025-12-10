# Copyright (c) 2024 Vanderbilt University
# Authors: Jules White, Allen Karns, Karely Rodriguez, Max Moundas

import os

import boto3
from botocore.exceptions import ClientError

from pycommon.dal.providers.aws.resource_perms import DynamoDBOperation
from pycommon.decorators import required_env_vars
from pycommon.logger import getLogger

logger = getLogger("request_state")


@required_env_vars({"REQUEST_STATE_DYNAMO_TABLE": [DynamoDBOperation.GET_ITEM]})
def request_killed(user, request_id):
    """
    Check if a request should be killed based on its state in DynamoDB.

    Args:
        user (str): The user identifier
        request_id (str): The unique request identifier

    Returns:
        bool: True if the request should be killed, False otherwise

    Note:
        Environment variables are validated and resolved by the @required_env_vars
        decorator. The REQUEST_STATE_DYNAMO_TABLE variable can be provided via
        Lambda environment or Parameter Store.
    """
    # Environment variable guaranteed by @required_env_vars decorator
    requests_table = os.environ["REQUEST_STATE_DYNAMO_TABLE"]

    dynamodb_client = boto3.client("dynamodb")

    try:
        logger.info("Checking requests table for killswitch state")
        response = dynamodb_client.get_item(
            TableName=requests_table,
            Key={"user": {"S": user}, "requestId": {"S": request_id}},
        )

        if "Item" not in response:
            logger.warning(
                "Request state not found, assuming was killed/deleted in chat js"
            )
            return True

        killswitch = response["Item"]["exit"]["BOOL"]

        logger.info("Killswitch state is %s", "kill" if killswitch else "continue")

        return killswitch

    except ClientError as e:
        logger.error("Error checking killswitch state: %s", e)
        return False
