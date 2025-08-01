# Copyright (c) 2024 Vanderbilt University
# Authors: Jules White, Allen Karns, Karely Rodriguez, Max Moundas

import json
import os
from typing import Any, List

import requests


def delete_embeddings(access_token: str, data_sources: List[str]) -> tuple[bool, Any]:
    """
    Check embedding permissions and delete embeddings for specified data sources.

    Args:
        access_token: Bearer token for authentication
        data_sources: List of data source identifiers or single string

    Returns:
        tuple[bool, Any]: Success status and response content/error message
    """
    delete_embeddings_endpoint = os.environ["API_BASE_URL"] + "/embedding-delete"

    # If data_sources is a single string, convert it to a list
    if isinstance(data_sources, str):
        data_sources = [data_sources]

    request = {"data": {"dataSources": data_sources}}

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }

    try:
        response = requests.post(
            delete_embeddings_endpoint, headers=headers, data=json.dumps(request)
        )

        response_content = response.json()
        print("Delete embeddings response: ", response_content)

        if response.status_code != 200:
            print(f"Error deleting embeddings: {response.status_code}")
            return False, response_content
        else:
            return True, response_content["result"]

    except Exception as e:
        print(f"Error deleting embeddings: {e}")
        return False, str(e)


def check_embedding_completion(access_token: str, datasource_ids: List[str]) -> bool:
    """
    Check if embedding processing is complete for the specified data sources.

    Args:
        access_token: Bearer token for authentication
        datasource_ids: List of data source IDs to check

    Returns:
        bool: True if embedding completion check was successful, False otherwise
    """
    print("Checking embedding completion for data sources", datasource_ids)

    endpoint = os.environ.get("API_BASE_URL", "") + "/embedding/check-completion"

    request = {"data": {"dataSources": datasource_ids}}

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
            return True

    except Exception as e:
        print(f"Error checking embedding completion: {e}")

    return False
