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


def is_valid_amplify_user(access_token: str, user_email: str) -> bool:
    """
    Check if a given email is a valid Amplify user.

    Args:
        access_token: Bearer token for authentication
        user_email: Email address to validate

    Returns:
        bool: True if the user email exists in the system
        or system users, False otherwise
    """
    print(f"Checking if {user_email} is a valid Amplify user")

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
    is_valid = user_email.lower() in [email.lower() for email in all_valid_emails]

    print(f"User {user_email} is {'valid' if is_valid else 'not valid'}")
    return is_valid
