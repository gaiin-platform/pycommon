# Copyright (c) 2024 Vanderbilt University
# Authors: Jules White, Allen Karns, Karely Rodriguez, Max Moundas

import json
import os

import requests


def verify_user_as_admin(access_token: str, purpose: str) -> bool:
    """
    Verify if the authenticated user has admin privileges for a specific purpose.

    Args:
        access_token: Bearer token for authentication
        purpose: The purpose/context for which admin verification is needed

    Returns:
        bool: True if user is verified as admin, False otherwise
    """
    print("Initiate authenticate user as admin call")

    endpoint = os.environ["API_BASE_URL"] + "/amplifymin/auth"

    request = {"data": {"purpose": purpose}}

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }

    try:
        response = requests.post(endpoint, headers=headers, data=json.dumps(request))
        print("Response: ", response.content)
        response_content = (
            response.json()
        )  # to adhere to object access return response dict

        if response.status_code == 200 and response_content.get("success", False):
            return response_content.get("isAdmin", False)

    except Exception as e:
        print(f"Error authenticating user as admin: {e}")

    return False
