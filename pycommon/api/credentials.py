# Copyright (c) 2024 Vanderbilt University
# Authors: Jules White, Allen Karns, Karely Rodriguez, Max Moundas

import json
import logging
import random

import boto3
from botocore.exceptions import ClientError


def get_credentials(secret_name: str) -> str:
    """
    Retrieve credentials from AWS Secrets Manager.

    Args:
        secret_name: Name of the secret to retrieve from Secrets Manager

    Returns:
        str: The secret string value

    Raises:
        ClientError: If there's an error retrieving the secret
    """
    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(service_name="secretsmanager")
    try:
        # Retrieve the secret from Secrets Manager
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
    except ClientError as e:
        raise e
    else:
        # Return the secret string directly
        return get_secret_value_response["SecretString"]


def get_json_credentials(secret_arn: str) -> dict:
    """
    Retrieve and parse JSON credentials from AWS Secrets Manager.

    Args:
        secret_arn: ARN of the secret containing JSON credentials

    Returns:
        dict: Parsed JSON credentials as a dictionary

    Raises:
        ClientError: If there's an error retrieving the secret
    """
    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(service_name="secretsmanager")
    try:
        # Retrieve the secret from Secrets Manager
        get_secret_value_response = client.get_secret_value(SecretId=secret_arn)
    except ClientError as e:
        raise e
    else:
        # Parse and return the secret JSON string
        secret = get_secret_value_response["SecretString"]
        return json.loads(secret)


def get_endpoint(model_name: str, endpoint_arn: str) -> tuple[str, str]:
    """
    Retrieve a random endpoint and API key for a specified model from AWS
    Secrets Manager.

    Args:
        model_name: Name of the model to get endpoint for
        endpoint_arn: ARN of the secret containing endpoint configuration

    Returns:
        tuple[str, str]: Tuple containing (endpoint_url, api_key)

    Raises:
        ClientError: If there's an error retrieving the secret
        ValueError: If the specified model is not found in the secret
    """
    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(service_name="secretsmanager")

    # Retrieve the secret from Secrets Manager
    try:
        get_secret_value_response = client.get_secret_value(SecretId=endpoint_arn)
        secret = get_secret_value_response["SecretString"]
        secret_dict = json.loads(secret)
    except ClientError as e:
        logging.error(f"Error retrieving secret: {e}")
        raise e

    # Parse the secret JSON to find the model
    for model_dict in secret_dict["models"]:
        if model_name in model_dict:
            # Select a random endpoint from the model's endpoints
            random_endpoint = random.choice(model_dict[model_name]["endpoints"])
            endpoint = random_endpoint["url"]
            api_key = random_endpoint["key"]
            return endpoint, api_key

    raise ValueError(f"Model named '{model_name}' not found in secret")
