# Copyright (c) 2024 Vanderbilt University
# Authors: Jules White, Allen Karns, Karely Rodriguez, Max Moundas

import json
import os
from typing import List

import requests


def verify_member_of_ast_admin_group(access_token: str, group_id: str) -> bool:
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

        if response.status_code != 200 or not response_content.get("success", False):
            return False
        elif response.status_code == 200 and response_content.get("success", False):
            return response_content.get("isMember", False)

    except Exception as e:
        print(f"Error verifying amp group membership: {e}")

    return False


def verify_user_in_amp_group(access_token: str, groups: List[str]) -> bool:
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

        if response.status_code != 200 or not response_content.get("success", False):
            return False
        elif response.status_code == 200 and response_content.get("success", False):
            return response_content.get("isMember", False)

    except Exception as e:
        print(f"Error verifying amp group membership: {e}")

    return False
