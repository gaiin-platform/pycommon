# Copyright (c) 2025 Vanderbilt University
"""
authz.py

This module provides utilities and functions for performing authorization checks
across various projects. It centralizes the logic for determining user permissions
and access control, ensuring consistency and security throughout the codebase.

The module is designed to be extensible and reusable, allowing for integration
with different authentication and authorization systems.

Copyright (c) 2025 Vanderbilt University
Authors: Jules White, Allen Karns, Karely Rodriguez, Max Moundas, Sam Hays
"""
# Authors: Jules White, Allen Karns, Karely Rodriguez, Max Moundas, Sam Hays

import os
import requests
import json


def verify_user_as_admin(access_token: str, purpose: str) -> bool:
    """
    Verifies if a user is an admin based on the provided access token and purpose.

    Args:
        access_token (str): The access token for authentication.
        purpose (str): The purpose of the authorization check.

    Returns:
        bool: True if the user is an admin, False otherwise.
    """
    print("Initiating authentication of user as admin.")

    # Ensure the API_BASE_URL environment variable is set
    api_base_url = os.environ.get("API_BASE_URL")
    if not api_base_url:
        print("Error: API_BASE_URL environment variable is not set.")
        return False

    endpoint = f"{api_base_url}/amplifymin/auth"

    request_payload = {"data": {"purpose": purpose}}

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }

    try:
        response = requests.post(
            endpoint, headers=headers, data=json.dumps(request_payload)
        )

        print("Response received:", response.content)

        # Parse the response content
        response_content = response.json()

        # Check for success and admin status
        if response.status_code == 200 and response_content.get("success", False):
            return response_content.get("isAdmin", False)
        else:
            return False

    except requests.exceptions.RequestException as e:
        # Handle network-related exceptions
        print(f"Network error during authentication: {e}")
        return False
    except json.JSONDecodeError as e:
        # Handle JSON parsing errors
        print(f"Error decoding JSON response: {e}")
        return False
    except Exception as e:
        # Catch-all for other exceptions
        print(f"Unexpected error during authentication: {e}")
        return False
