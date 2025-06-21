# Copyright (c) 2024 Vanderbilt University
# Authors: Jules White, Allen Karns, Karely Rodriguez, Max Moundas

import json
import os
from typing import Any, Dict, List

import requests


def get_all_op(access_token: str) -> dict:
    print("Initiate get ops call")

    endpoint = os.environ["API_BASE_URL"] + "/ops/get_all"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }

    try:
        response = requests.get(
            endpoint,
            headers=headers,
        )
        # print("Response: ", response.content)
        response_content = (
            response.json()
        )  # to adhere to object access return response dict

        if response.status_code != 200 or not response_content.get("success", False):
            return {"success": False, "data": None}
        elif response.status_code == 200 and response_content.get("success", False):
            return response_content

        # Default return if none of the above conditions are met
        return {"success": False, "data": None}

    except Exception as e:
        print(f"Error getting all ops: {e}")
        return {"success": False, "data": None}


def register_ops(
    access_token: str, ops: List[Dict[str, Any]], system_op: bool = False
) -> bool:
    endpoint = os.environ["API_BASE_URL"] + "/ops/register"

    request = {"data": {"ops": ops, "system_op": system_op}}

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

        if response.status_code != 200 or not response_content.get("success", False):
            return False
        elif response.status_code == 200 and response_content.get("success", False):
            return True

    except Exception as e:
        print(f"Error amplify assistants writing ops: {e}")

    return False
