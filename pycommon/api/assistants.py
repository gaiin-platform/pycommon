# Copyright (c) 2024 Vanderbilt University
# Authors: Jules White, Allen Karns, Karely Rodriguez, Max Moundas

import json
import os

import requests

from pycommon.logger import getLogger
from pycommon.lzw import safe_compress

logger = getLogger("assistants")


def share_assistant(access_token: str, data: dict) -> bool:
    """
    Share an assistant with other users or groups.

    Args:
        access_token: Bearer token for authentication
        data: Dictionary containing sharing configuration (recipients,
            permissions, etc.)

    Returns:
        bool: True if assistant was shared successfully, False otherwise
    """
    logger.info("Initiate share assistant call")

    share_assistant_endpoint = os.environ["API_BASE_URL"] + "/assistant/share"

    request = {"data": safe_compress(data)}

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }

    try:
        response = requests.post(
            share_assistant_endpoint, headers=headers, data=json.dumps(request)
        )
        # print("Response: ", response.content)
        response_content = (
            response.json()
        )  # to adhere to object access return response dict

        if response.status_code == 200 and response_content.get("success", False):
            return True

    except Exception as e:
        logger.error(f"Error updating permissions: {e}")

    return False


def list_assistants(access_token: str) -> dict:
    """
    Retrieve a list of all assistants accessible to the authenticated user.

    Args:
        access_token: Bearer token for authentication

    Returns:
        dict: Response containing list of assistants or error information
    """
    logger.info("Initiate list assistant call")

    assistant_endpoint = os.environ["API_BASE_URL"] + "/assistant/list"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }
    try:
        response = requests.get(
            assistant_endpoint,
            headers=headers,
        )
        response_content = (
            response.json()
        )  # to adhere to object access return response dict

        if response.status_code != 200 or "success" not in response_content:
            logger.debug("Response: %s", response.content)
            return {"success": False}
        else:
            return response_content

    except Exception as e:
        logger.error(f"Error listing asts: {e}")
        return {"success": False}


def remove_astp_perms(access_token: str, data: dict) -> dict:
    """
    Remove ASTP (Assistant Template Permissions) permissions from an assistant.

    Args:
        access_token: Bearer token for authentication
        data: Dictionary containing permission removal configuration

    Returns:
        dict: Response containing success status and any relevant data
    """
    logger.info("Initiate remove astp perms assistant call")

    assistant_endpoint = (
        os.environ["API_BASE_URL"] + "/assistant/remove_astp_permissions"
    )

    request = {"data": data}

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }
    try:
        response = requests.post(
            assistant_endpoint, headers=headers, data=json.dumps(request)
        )
        # print("Response: ", response.content)
        response_content = (
            response.json()
        )  # to adhere to object access return response dict

        if response.status_code != 200 or "success" not in response_content:
            return {"success": False}
        else:
            return response_content

    except Exception as e:
        logger.error(f"Error updating permissions: {e}")
        return {"success": False}


def delete_assistant(access_token: str, data: dict) -> dict:
    """
    Delete an assistant.

    Args:
        access_token: Bearer token for authentication
        data: Dictionary containing assistant deletion configuration
            (e.g., assistant ID)

    Returns:
        dict: Response containing success status and any relevant data
    """
    logger.info("Initiate delete assistant call")

    assistant_endpoint = os.environ["API_BASE_URL"] + "/assistant/delete"

    request = {"data": data}

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }
    try:
        response = requests.post(
            assistant_endpoint, headers=headers, data=json.dumps(request)
        )
        # print("Response: ", response.content)
        response_content = (
            response.json()
        )  # to adhere to object access return response dict

        if response.status_code != 200 or "success" not in response_content:
            return {"success": False}
        else:
            return response_content

    except Exception as e:
        logger.error(f"Error deleting ast: {e}")
        return {"success": False}


def create_assistant(access_token: str, data: dict) -> dict:
    """
    Create a new assistant.

    Args:
        access_token: Bearer token for authentication
        data: Dictionary containing assistant configuration (name, description,
            settings, etc.)

    Returns:
        dict: Response containing success status and created assistant data
    """
    logger.info("Initiate create assistant call")

    assistant_endpoint = os.environ["API_BASE_URL"] + "/assistant/create"

    request = {"data": safe_compress(data)}

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }
    try:
        response = requests.post(
            assistant_endpoint, headers=headers, data=json.dumps(request)
        )
        # print("Response: ", response.content)
        response_content = (
            response.json()
        )  # to adhere to object access return response dict
        # print(response_content)

        if response.status_code != 200 or "success" not in response_content:
            return {"success": False}
        else:
            return response_content

    except Exception as e:
        logger.error(f"Error creating ast: {e}")
        return {"success": False}


def add_assistant_path(access_token: str, data: dict) -> dict:
    """
    Add a path/route to an existing assistant.

    Args:
        access_token: Bearer token for authentication
        data: Dictionary containing path configuration (assistant ID, path
            details, etc.)

    Returns:
        dict: Response containing success status and any relevant data or
            error messages
    """
    logger.info("Initiate add assistant path call")

    path_assistant_endpoint = os.environ["API_BASE_URL"] + "/assistant/add_path"

    request = {"data": safe_compress(data)}

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }

    try:
        response = requests.post(
            path_assistant_endpoint, headers=headers, data=json.dumps(request)
        )
        # print("Response: ", response.content)
        response_content = (
            response.json()
        )  # to adhere to object access return response dict

        if response.status_code == 200 and response_content.get("success", False):
            return response_content
        else:
            return {
                "success": False,
                "message": response_content.get(
                    "message", "Failed to add path to assistant"
                ),
            }

    except Exception as e:
        logger.error(f"Error adding path to assistant: {e}")

    return {"success": False, "message": "Unexpected error occurred"}
