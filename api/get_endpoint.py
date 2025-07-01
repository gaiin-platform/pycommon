# Copyright (c) 2024 Vanderbilt University
# Authors: Jules White, Allen Karns, Karely Rodriguez, Max Moundas

import json
import os
from enum import Enum

import boto3
from botocore.exceptions import ClientError


class EndpointType(Enum):
    CHAT_ENDPOINT = "CHAT_ENDPOINT"
    API_BASE_URL = "API_BASE_URL"


def get_endpoint(endpoint_type: EndpointType) -> str:
    """
    Retrieve an endpoint URL from AWS Secrets Manager based on the endpoint type.

    Args:
        endpoint_type: Type of endpoint to retrieve (CHAT_ENDPOINT or API_BASE_URL)

    Returns:
        str: The endpoint URL for the specified type

    Raises:
        ValueError: If the endpoint type is not found in secrets manager
        ClientError: If there's an error retrieving the secret
    """
    secret_name = os.environ["APP_ARN_NAME"]
    region_name = os.environ.get("AWS_REGION", "us-east-1")
    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(service_name="secretsmanager", region_name=region_name)
    try:
        print(f"Retrieving {endpoint_type.value}")
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
        secret_string = get_secret_value_response["SecretString"]
        secret_dict = json.loads(secret_string)
        if endpoint_type.value in secret_dict:
            return secret_dict[endpoint_type.value]
        print(f"{endpoint_type.value} Not Found")
    except ClientError as e:
        print(f"Error getting secret: {e}")
    raise ValueError(f"Couldnt retrieve '{endpoint_type.value}' from secrets manager.")
