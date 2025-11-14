import json
import os

import requests

from pycommon.logger import getLogger

logger = getLogger("user_data")


def load_user_data(access_token, app_id, entity_type, item_id):
    """Load user data from the API.

    Args:
        access_token (str): Bearer token for authentication
        app_id (str): Application ID
        entity_type (str): Type of entity to retrieve data for
        item_id (str): ID of the specific item

    Returns:
        dict or None: User data if successful, None otherwise
    """
    logger.info("Initiate get user data call")

    endpoint = os.environ["API_BASE_URL"] + "/user-data/get"

    request = {"data": {"appId": app_id, "entityType": entity_type, "itemId": item_id}}

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }

    try:
        response = requests.post(endpoint, headers=headers, data=json.dumps(request))
        logger.debug("Response: %s", response.content)
        response_content = (
            response.json()
        )  # to adhere to object access return response dict

        if response.status_code == 200 and response_content.get("success", False):
            return response_content.get("data", None)

    except Exception as e:
        logger.error(f"Error getting user data: {e}")

    return None


def save_user_data(access_token, app_id, entity_type, item_id, data, range_key=None):
    """Save user data to the API.

    Args:
        access_token (str): Bearer token for authentication
        app_id (str): Application ID
        entity_type (str): Type of entity to save data for
        item_id (str): ID of the specific item
        data (dict): Data to save
        range_key (str, optional): Range key for the item. Defaults to None.

    Returns:
        dict or None: Response data if successful, None otherwise
    """
    logger.info(f"Initiate save user data call for {entity_type}/{item_id}")

    endpoint = os.environ["API_BASE_URL"] + "/user-data/put"

    request_data = {
        "data": {
            "appId": app_id,
            "entityType": entity_type,
            "itemId": item_id,
            "data": data,
        }
    }

    if range_key:
        request_data["data"]["rangeKey"] = range_key

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }

    try:
        response = requests.post(
            endpoint, headers=headers, data=json.dumps(request_data)
        )
        logger.debug("Response: %s", response.content)
        response_content = response.json()

        if response.status_code == 200 and response_content.get("success", False):
            return response_content
        else:
            logger.error(f"Error saving user data: {response_content}")
            return None

    except Exception as e:
        logger.error(f"Error saving user data: {e}")
        return None


def delete_user_data(access_token, app_id, entity_type, item_id, range_key=None):
    """Delete user data from the API.

    Args:
        access_token (str): Bearer token for authentication
        app_id (str): Application ID
        entity_type (str): Type of entity to delete data for
        item_id (str): ID of the specific item
        range_key (str, optional): Range key for the item. Defaults to None.

    Returns:
        dict or None: Response data if successful, None otherwise
    """
    logger.info(f"Initiate delete user data call for {entity_type}/{item_id}")

    endpoint = os.environ["API_BASE_URL"] + "/user-data/delete"

    request_data = {
        "data": {"appId": app_id, "entityType": entity_type, "itemId": item_id}
    }

    if range_key:
        request_data["data"]["rangeKey"] = range_key

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }

    try:
        response = requests.post(
            endpoint, headers=headers, data=json.dumps(request_data)
        )
        logger.debug("Response: %s", response.content)
        response_content = response.json()

        if response.status_code == 200 and response_content.get("success", False):
            return response_content
        else:
            logger.error(f"Error deleting user data: {response_content}")
            return None

    except Exception as e:
        logger.error(f"Error deleting user data: {e}")
        return None
