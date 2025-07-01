# Copyright (c) 2024 Vanderbilt University
# Authors: Jules White, Allen Karns, Karely Rodriguez, Max Moundas

import json
import os

import requests


def get_all_ast_admin_groups(access_token: str) -> dict:
    """
    Retrieve all AST (Assistant) admin groups.

    Args:
        access_token: Bearer token for authentication

    Returns:
        dict: Response containing all AST admin groups or error information
    """
    print("Initiate get ast admin call")

    endpoint = os.environ["API_BASE_URL"] + "/groups/list_all"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }

    try:
        response = requests.get(
            endpoint,
            headers=headers,
        )
        print("Response: ", response.content)
        response_content = (
            response.json()
        )  # to adhere to object access return response dict

        if response.status_code == 200 and response_content.get("success", False):
            return response_content
        else:
            return {"success": False, "data": None}

    except Exception as e:
        print(f"Error getting ast admin groups: {e}")

    return {"success": False, "data": None}


def update_ast_admin_groups(access_token: str, data: dict) -> dict:
    """
    Update AST (Assistant) admin groups with new configuration.

    Args:
        access_token: Bearer token for authentication
        data: Dictionary containing the update data for AST admin groups

    Returns:
        dict: Response containing success status and any relevant data or error messages
    """
    print("Initiate update ast admin groups call")

    endpoint = os.environ["API_BASE_URL"] + "/groups/update"

    request = {"data": data}

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
            return response_content
        else:
            return {
                "success": False,
                "message": response_content.get(
                    "message", "Failed to update supported models"
                ),
            }

    except Exception as e:
        print(f"Error updating supported Models: {e}")

    return {"success": False, "message": "Failed to make request"}
