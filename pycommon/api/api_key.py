# Copyright (c) 2024 Vanderbilt University
# Authors: Jules White, Allen Karns, Karely Rodriguez, Max Moundas

import json
import os
from typing import Dict, Union

import requests

from pycommon.logger import getLogger

logger = getLogger("api_key")


def deactivate_key(access_token: str, api_owner_id: str) -> bool:
    """
    Deactivate an API key for a given owner.

    Args:
        access_token: Bearer token for authentication
        api_owner_id: ID of the API key owner

    Returns:
        bool: True if deactivation was successful, False otherwise
    """
    logger.info("Initiate deactivate key call")

    api_key_endpoint = os.environ["API_BASE_URL"] + "/apiKeys/key/deactivate"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }
    data = {"data": {"apiKeyId": api_owner_id}}

    try:
        response = requests.post(
            api_key_endpoint, headers=headers, data=json.dumps(data)
        )
        response_content = response.json()
        logger.debug("Response: %s", response_content)

        if response.status_code == 200 and response_content.get("success", False):
            return True

    except Exception as e:
        logger.error(f"Error deactivating API key: {e}")

    return False


def get_api_keys(token: str) -> Union[Dict, None]:
    """
    Retrieves all API keys for the authenticated user.

    Args:
        token (str): Authorization token.

    Returns:
        dict or None: API response containing API keys, or None if an error occurs.
    """

    api_base = os.environ.get("API_BASE_URL", None)
    if not api_base:
        logger.error("API_BASE_URL is not set.")
        return None

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    try:
        response = requests.get(f"{api_base}/apiKeys/keys/get", headers=headers)
        response.raise_for_status()
        result = response.json()

        logger.debug(f"Retrieved API Keys: {result}")
        return result
    except Exception as e:
        logger.error(f"Failed to retrieve API keys: {str(e)}")
        return None
