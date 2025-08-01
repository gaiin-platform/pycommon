# Copyright (c) 2025 Vanderbilt University
# Authors: Jules White, Allen Karns, Karely Rodriguez, Max Moundas, Sam Hays

import json
import os
from typing import List, Optional

import requests


def get_email_suggestions(
    access_token: str, email_prefix: str = "*"
) -> Optional[List[str]]:
    """
    Fetch email suggestions based on a query prefix.

    Args:
        access_token: Bearer token for authentication
        email_prefix: Email prefix to search for, * defaults to get all emails

    Returns:
        Optional[List[str]]: List of email addresses matching the prefix,
                            or None if the request fails
    """
    print("Initiate get email suggestions call")

    endpoint = os.environ["API_BASE_URL"] + "/utilities/emails"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }

    params = {"emailprefix": email_prefix}

    try:
        response = requests.get(endpoint, headers=headers, params=params)
        print("Response: ", response.content)

        if response.status_code == 200:
            response_content = response.json()
            # Handle nested JSON structure where actual data is in "body" field
            if "body" in response_content:
                # Parse the body field as JSON
                body_data = json.loads(response_content["body"])
                return body_data.get("emails", [])
            else:
                # Fallback for direct structure
                return response_content.get("emails", [])

        print(f"Request failed with status code: {response.status_code}")

    except requests.RequestException as e:
        print(f"Network error getting email suggestions: {e}")
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON response: {e}")
    except Exception as e:
        print(f"Unexpected error getting email suggestions: {e}")
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
    print("Initiate get system IDs call")

    endpoint = os.environ["API_BASE_URL"] + "/apiKeys/get_system_ids"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }

    try:
        response = requests.get(endpoint, headers=headers)
        print("Response: ", response.content)

        if response.status_code == 200:
            response_content = response.json()
            if response_content.get("success", False):
                return response_content.get("data", [])

        print(f"Request failed with status code: {response.status_code}")

    except requests.RequestException as e:
        print(f"Network error getting system IDs: {e}")
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON response: {e}")
    except Exception as e:
        print(f"Unexpected error getting system IDs: {e}")
    return None


def are_valid_amplify_users(
    access_token: str, user_emails: List[str]
) -> tuple[List[str], List[str]]:
    """
    Check if given emails are valid Amplify users.

    Args:
        access_token: Bearer token for authentication
        user_emails: Email addresses to validate

    Returns:
        tuple[List[str], List[str]]: A tuple containing
        (valid_users, invalid_users) where each list
        contains lowercase email addresses
    """
    print(f"Checking if {user_emails} are valid Amplify users")

    # Get all emails from the system
    all_emails = get_email_suggestions(access_token, "*")
    if all_emails is None:
        print("Failed to retrieve email list")
        all_emails = []

    # Get system users
    system_data = get_system_ids(access_token)
    system_users = []
    if system_data is not None:
        # Extract owner emails from system data
        system_users = [
            item.get("owner", "") for item in system_data if item.get("owner")
        ]
    else:
        print("Failed to retrieve system users list")

    # Combine both lists and check if the user email exists
    all_valid_emails = all_emails + system_users
    valid = []
    invalid = []
    for user in user_emails:
        lower_user = user.lower()
        is_valid = lower_user in [email.lower() for email in all_valid_emails]
        if is_valid:
            valid.append(lower_user)
        else:
            invalid.append(lower_user)

    print(f"Valid Users: {valid}")
    print(f"Invalid Users: {invalid}")
    return valid, invalid
