# Copyright (c) 2025 Vanderbilt University
# Authors: Jules White, Allen Karns, Karely Rodriguez, Max Moundas, Sam Hays

import json
import os
from typing import Dict, List, Optional

import boto3
import requests
from botocore.exceptions import ClientError

from pycommon.logger import getLogger

logger = getLogger("amplify_users")


def get_email_suggestions(
    access_token: str, email_prefix: str = "*"
) -> Optional[Dict[str, str]]:
    """
    Fetch user email mapping based on a query prefix.

    Args:
        access_token: Bearer token for authentication
        email_prefix: Email prefix to search for, * defaults to get all emails

    Returns:
        Optional[Dict[str, str]]: Dictionary mapping user_id to email address,
                                  or None if the request fails
    """
    logger.info("Initiate get email suggestions call")

    endpoint = os.environ["API_BASE_URL"] + "/utilities/emails"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }

    params = {"emailprefix": email_prefix}

    try:
        response = requests.get(endpoint, headers=headers, params=params)
        logger.debug("Response: %s", response.content)

        if response.status_code == 200:
            response_content = response.json()
            # Handle nested JSON structure where actual data is in "body" field
            if "body" in response_content:
                # Parse the body field as JSON
                body_data = json.loads(response_content["body"])
                return body_data.get("user_email_map", {})
            else:
                # Fallback for direct structure
                return response_content.get("user_email_map", {})

        logger.warning(f"Request failed with status code: {response.status_code}")

    except requests.RequestException as e:
        logger.error(f"Network error getting email suggestions: {e}")
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON response: {e}")
    except Exception as e:
        logger.error(f"Unexpected error getting email suggestions: {e}")
    return None


def get_system_ids(access_token: str) -> Optional[List[dict]]:
    """
    Fetch all system IDs from the API.

    Args:
        access_token: Bearer token for authentication

    Returns:
        Optional[List[dict]]: List of system API key data,
                             or None if the request fails
    """
    logger.info("Initiate get system IDs call")

    endpoint = os.environ["API_BASE_URL"] + "/apiKeys/get_system_ids"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }

    try:
        response = requests.get(endpoint, headers=headers)
        logger.debug("Response: %s", response.content)

        if response.status_code == 200:
            response_content = response.json()
            if response_content.get("success", False):
                return response_content.get("data", [])

        logger.warning(f"Request failed with status code: {response.status_code}")

    except requests.RequestException as e:
        logger.error(f"Network error getting system IDs: {e}")
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON response: {e}")
    except Exception as e:
        logger.error(f"Unexpected error getting system IDs: {e}")
    return None


def are_valid_amplify_users(
    access_token: str, user_emails: List[str]
) -> tuple[List[str], List[str]]:
    """
    Check if given emails are valid Amplify users using efficient direct lookups.

    Args:
        access_token: Bearer token for authentication
        user_emails: Email addresses to validate

    Returns:
        tuple[List[str], List[str]]: A tuple containing
        (valid_users, invalid_users) where each list
        contains lowercase email addresses
    """
    logger.info(f"Checking if {user_emails} are valid Amplify users")

    system_data = get_system_ids(access_token)
    system_users = []
    if system_data is not None:
        # Extract owner emails from system data
        system_users = [
            item.get("owner", "").lower() for item in system_data if item.get("owner")
        ]
    else:
        logger.warning("Failed to retrieve system users list")

    # Convert system users to a set for O(1) lookup
    system_users_set = set(system_users)

    # Initialize DynamoDB client
    dynamodb = boto3.resource("dynamodb")
    cognito_user_table = dynamodb.Table(os.environ["COGNITO_USERS_DYNAMODB_TABLE"])

    valid = []
    invalid = []

    for user_email in user_emails:
        lower_user = user_email.lower()

        # First check if it's a system user (fast set lookup)
        if lower_user in system_users_set:
            valid.append(lower_user)
            continue

        # Check if it exists in cognito_users table using direct GetItem
        try:
            response = cognito_user_table.get_item(
                Key={"user_id": lower_user},
                ProjectionExpression="user_id",
                # Only get the key back to minimize data transfer
            )

            if "Item" in response:
                # User exists in cognito table
                valid.append(lower_user)
            else:
                # User doesn't exist in either place
                invalid.append(lower_user)

        except ClientError as e:
            logger.error(
                f"Error checking user {lower_user}: {e.response['Error']['Message']}"
            )
            # On error, treat as invalid to be safe
            invalid.append(lower_user)

    logger.debug(f"Valid Users: {valid}")
    logger.debug(f"Invalid Users: {invalid}")
    return valid, invalid
