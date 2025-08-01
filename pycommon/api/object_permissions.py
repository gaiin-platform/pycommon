# Copyright (c) 2024 Vanderbilt University
# Authors: Jules White, Allen Karns, Karely Rodriguez, Max Moundas

import json
import os
from typing import Any, Dict, List, Optional

import requests


def update_object_permissions(
    access_token: str,
    shared_with_users: List[str],
    keys: List[str],
    object_type: str,
    principal_type: str = "user",
    permission_level: str = "read",
    policy: str = "",
) -> bool:
    """
    Update object permissions for specified users and data sources.

    Args:
        access_token: Bearer token for authentication
        shared_with_users: List of user emails to share with
        keys: List of data source keys
        object_type: Type of object being shared
        principal_type: Type of principal (default: "user")
        permission_level: Level of permission to grant (default: "read")
        policy: Additional policy configuration

    Returns:
        bool: True if permissions were updated successfully, False otherwise
    """
    permissions_endpoint = (
        os.environ["API_BASE_URL"] + "/utilities/update_object_permissions"
    )

    request = {
        "data": {
            "emailList": shared_with_users,
            "dataSources": keys,
            "objectType": object_type,
            "principalType": principal_type,
            "permissionLevel": permission_level,
            "policy": policy,
        }
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }

    try:
        response = requests.post(
            permissions_endpoint, headers=headers, data=json.dumps(request)
        )

        response_content = (
            response.json()
        )  # to adhere to object access return response dict

        if (
            response.status_code == 200
            and response_content.get("statusCode", None) == 200
        ):
            return True

    except Exception as e:
        print(f"Error updating permissions: {e}")

    return False


def can_access_objects(
    access_token: str,
    data_sources: List[Dict[str, Any]],
    permission_level: str = "read",
) -> bool:
    """
    Check if the authenticated user can access the specified data sources.

    Args:
        access_token: Bearer token for authentication
        data_sources: List of data source dictionaries with id and type
        permission_level: Required permission level (default: "read")

    Returns:
        bool: True if user has access to all data sources, False otherwise
    """
    print(f"Checking access on data sources: {data_sources}")

    # Skip empty data sources
    if not data_sources:
        return True

    # Separate web and non-web data sources
    non_web_data_sources = []
    for ds in data_sources:
        # Skip websites and sitemaps - they don't need permission checks
        if ds.get("type") in ["website/url", "website/sitemap"] or ds.get(
            "id", ""
        ).startswith(("http://", "https://")):
            continue
        non_web_data_sources.append(ds)

    # If there are no non-web data sources left, return true (all were web URLs)
    if not non_web_data_sources:
        return True

    # Check permissions for non-web data sources
    access_levels = {}
    for ds in non_web_data_sources:
        id_key = ds["id"].split("://")[-1]
        access_levels[id_key] = permission_level

    print(f"Checking access for non-web data sources: {access_levels}")

    request_data = {"data": {"dataSources": access_levels}}
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }

    permissions_endpoint = os.environ["API_BASE_URL"] + "/utilities/can_access_objects"
    try:
        response = requests.post(
            permissions_endpoint, headers=headers, data=json.dumps(request_data)
        )

        response_content = response.json()

        if (
            response.status_code != 200
            or response_content.get("statusCode", None) != 200
        ):
            print(f"User does not have access to data sources: {response.status_code}")
            return False
        else:
            return True

    except Exception as e:
        print(f"Error checking access on data sources: {e}")

    return False


def simulate_can_access_objects(
    access_token: str,
    object_ids: List[str],
    permission_levels: Optional[List[str]] = None,
) -> Dict[str, Dict[str, bool]]:
    """
    Simulate access permissions for specified objects and permission levels.

    Args:
        access_token: Bearer token for authentication
        object_ids: List of object IDs to check access for
        permission_levels: List of permission levels to check (default: ["read"])

    Returns:
        Dict[str, Dict[str, bool]]: Nested dictionary with object IDs as keys and
        permission levels as nested keys, with boolean access values
    """
    if permission_levels is None:
        permission_levels = ["read"]

    print(f"Simulating access on data sources: {object_ids}")

    access_levels = {id: permission_levels for id in object_ids}

    # Set the access levels result for each object to false for every object id
    # and permission level
    all_denied = {id: {pl: False for pl in permission_levels} for id in object_ids}

    print(f"With access levels: {access_levels}")

    request_data = {"data": {"objects": access_levels}}

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }

    # Replace 'permissions_endpoint' with the actual permissions endpoint URL
    permissions_endpoint = (
        os.environ["API_BASE_URL"] + "/utilities/simulate_access_to_objects"
    )

    try:
        response = requests.post(
            permissions_endpoint, headers=headers, data=json.dumps(request_data)
        )

        response_content = (
            response.json()
        )  # to adhere to object access return response dict

        if (
            response.status_code == 200
            and response_content.get("statusCode", None) == 200
        ):
            result = response.json()
            if "data" in result:
                return result["data"]
            else:
                return all_denied
        else:
            print("Error simulating user access")
            return all_denied

    except Exception as e:
        print(f"Error simulating access on data sources: {e}")

    return all_denied
