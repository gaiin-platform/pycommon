# Copyright (c) 2024 Vanderbilt University
# Authors: Jules White, Allen Karns, Karely Rodriguez, Max Moundas

import json
import os
from typing import List

import requests


def verify_member_of_ast_admin_group(access_token: str, group_id: str) -> bool:
    """
    Verify if the authenticated user is a member of a specific AST admin group.

    Args:
        access_token: Bearer token for authentication
        group_id: ID of the AST admin group to check membership for

    Returns:
        bool: True if user is a member of the group, False otherwise
    """
    print("Initiate verify in ast admin group call")

    endpoint = os.environ["API_BASE_URL"] + "/groups/verify_ast_group_member"

    request = {"data": {"groupId": group_id}}

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
            return response_content.get("isMember", False)

    except Exception as e:
        print(f"Error verifying amp group membership: {e}")

    return False


def verify_user_in_amp_group(access_token: str, groups: List[str]) -> bool:
    """
    Verify if the authenticated user is a member of any of the specified Amplify groups.

    Args:
        access_token: Bearer token for authentication
        groups: List of Amplify group names to check membership for

    Returns:
        bool: True if user is a member of at least one group, False otherwise
    """
    if not groups or len(groups) == 0:
        return False
    print("Initiate verify in amp group call")

    endpoint = os.environ["API_BASE_URL"] + "/amplifymin/verify_amp_member"

    request = {"data": {"groups": groups}}

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
            return response_content.get("isMember", False)

    except Exception as e:
        print(f"Error verifying amp group membership: {e}")

    return False
