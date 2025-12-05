# Copyright (c) 2025 Vanderbilt University
# Authors: Jules White, Allen Karns, Karely Rodriguez, Max Moundas, Sam Hays

import json
import os
import re
from typing import Dict, List, Optional

import boto3
import requests
from botocore.exceptions import ClientError

from pycommon.dal.providers.aws.resource_perms import DynamoDBOperation
from pycommon.decorators import required_env_vars
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


@required_env_vars(
    {
        "COGNITO_USERS_DYNAMODB_TABLE": [DynamoDBOperation.GET_ITEM],
        "API_KEYS_DYNAMODB_TABLE": [DynamoDBOperation.GET_ITEM],
    }
)
def are_valid_amplify_users(
    access_token: str, user_emails: List[str]
) -> tuple[List[str], List[str]]:
    """
    Check if given emails and group system IDs are valid Amplify users
    using efficient direct lookups.

    Args:
        access_token: Bearer token for authentication
        user_emails: Email addresses and group system IDs to validate

    Returns:
        tuple[List[str], List[str]]: A tuple containing
        (valid_users, invalid_users) where emails are lowercase
        and group system IDs preserve original case
    """
    logger.info(f"Checking if {user_emails} are valid Amplify users")

    # Regex patterns for system IDs (more comprehensive to avoid unnecessary API calls)
    # Pattern 1: GroupName_UUID format (original group system IDs)
    group_system_id_pattern = re.compile(
        r"^[A-Z][a-zA-Z0-9]*_[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}"
        r"-[a-f0-9]{12}$"
    )

    # Pattern 2: General system ID patterns (includes various dash/number combinations)
    # Matches: GroupName-Numbers, GroupName--Numbers, GroupName-Text-Numbers, etc.
    general_system_id_pattern = re.compile(
        r"^[A-Za-z][A-Za-z0-9]*(?:-+[A-Za-z0-9]+)*-[0-9]+$"
    )

    # Separate checks for different system ID types
    def is_group_system_id(identifier):
        return group_system_id_pattern.match(identifier) is not None

    def is_general_system_id(identifier):
        return general_system_id_pattern.match(identifier) is not None

    # Smart optimization: Skip get_system_ids() unless we have general system IDs
    # - Group system IDs (GroupName_UUID): use direct API keys table lookup
    # - Regular emails/cognito subs: use direct cognito table lookup
    # - General system IDs (THK-265484 style): need system owner data from API
    has_general_system_ids = any(is_general_system_id(email) for email in user_emails)

    system_data = None
    system_users_set = set()

    # Only call API if we have general system IDs (which need system owner lookup)
    if has_general_system_ids:
        system_data = get_system_ids(access_token)

    if system_data is not None:
        # Extract owner emails from system data
        system_users = [
            item.get("owner", "").lower() for item in system_data if item.get("owner")
        ]
        # Convert system users to a set for O(1) lookup
        system_users_set = set(system_users)
    else:
        logger.warning("Failed to retrieve system users list")

    # Initialize DynamoDB client
    dynamodb = boto3.resource("dynamodb")
    cognito_user_table = dynamodb.Table(os.environ["COGNITO_USERS_DYNAMODB_TABLE"])

    valid = []
    invalid = []

    for user_identifier in user_emails:
        # Check if it's a UUID-based group system ID (direct DynamoDB lookup)
        if is_group_system_id(user_identifier):
            # Handle UUID-based group system ID - preserve original case
            try:
                # Parse GroupName_uuid to extract components
                group_name, uuid_part = user_identifier.split("_", 1)
                # Construct api_owner_id: GroupName/systemKey/uuid
                api_owner_id = f"{group_name}/systemKey/{uuid_part}"

                # Initialize API keys table only when needed
                api_keys_table = dynamodb.Table(os.environ["API_KEYS_DYNAMODB_TABLE"])

                # Check API_KEYS_DYNAMODB_TABLE
                response = api_keys_table.get_item(
                    Key={"api_owner_id": api_owner_id},
                    ProjectionExpression="api_owner_id",
                )

                if "Item" in response:
                    # Group system ID exists
                    logger.info(
                        f"Group system ID {user_identifier} validated successfully "
                        f"with api_owner_id: {api_owner_id}"
                    )
                    valid.append(user_identifier)  # Preserve original case
                else:
                    # Group system ID doesn't exist
                    invalid.append(user_identifier)

            except ClientError as e:
                logger.error(
                    f"Error checking group system ID {user_identifier}: "
                    f"{e.response['Error']['Message']}"
                )
                # On error, treat as invalid to be safe
                invalid.append(user_identifier)
            except Exception as e:
                logger.error(f"Error parsing group system ID {user_identifier}: {e}")
                invalid.append(user_identifier)
            continue

        # Check if it's a general system ID pattern (dash-number format)
        elif is_general_system_id(user_identifier):
            if system_data is not None:
                system_id_found = False
                for system_item in system_data:
                    system_id = system_item.get("systemId", "")
                    if (
                        user_identifier == system_id
                        or user_identifier.lower() in system_users_set
                    ):
                        valid.append(user_identifier)  # Preserve case
                        system_id_found = True
                        break

                if system_id_found:
                    continue

            # If not found in system data, it's invalid
            invalid.append(user_identifier)
            continue

        # Handle as email - convert to lowercase
        else:
            lower_user = user_identifier.lower()

            # First check if it's a system user (fast set lookup)
            if lower_user in system_users_set:
                valid.append(lower_user)
                continue

            # Check if it exists in cognito_users table using direct GetItem
            try:
                response = cognito_user_table.get_item(
                    Key={"user_id": lower_user},
                    ProjectionExpression="user_id",
                )

                if "Item" in response:
                    valid.append(lower_user)
                else:
                    invalid.append(lower_user)

            except ClientError as e:
                logger.error(
                    f"Error checking user {lower_user}: "
                    f"{e.response['Error']['Message']}"
                )
                invalid.append(lower_user)

    logger.debug(f"Valid Users: {valid}")
    logger.debug(f"Invalid Users: {invalid}")
    return valid, invalid
