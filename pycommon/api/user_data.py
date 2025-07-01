import json
import os

import requests


def load_user_data(access_token, app_id, entity_type, item_id):
    print("Initiate get user data call")

    endpoint = os.environ["API_BASE_URL"] + "/user-data/get"

    request = {"data": {"appId": app_id, "entityType": entity_type, "itemId": item_id}}

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
            return response_content.get("data", None)

    except Exception as e:
        print(f"Error getting user data: {e}")

    return None
