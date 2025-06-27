import os
from typing import List, Union

import requests


def upload_file(
    access_token: str,
    file_name: str,
    file_contents: Union[str, bytes],
    file_type: str,
    tags: List[str],
    data_props: dict = None,
    enter_rag_pipeline: bool = False,
    groupId: str = None,
):
    if data_props is None:
        data_props = {}

    clean_name = file_name.replace(" ", "_")

    payload = {
        "data": {
            "name": clean_name,
            "type": file_type,
            "tags": tags,
            "data": data_props,
            "ragOn": enter_rag_pipeline,
            "knowledgeBase": "default",
            "groupId": groupId,
        }
    }

    presigned_url_response = get_file_presigned_url(access_token, payload)

    if not presigned_url_response.get("success"):
        print(f"[✗] Failed to get presigned URL for: {file_name}")
        return

    key = presigned_url_response.get("key")
    upload_url = presigned_url_response.get("uploadUrl")

    print(f"[✓] Uploading file: {file_name} to {upload_url}")

    success = upload_to_presigned_url(upload_url, file_contents, file_type)

    if success:
        print(f"[✓] Uploaded file: {file_name} to {upload_url}")
        return {"id": key, **payload["data"]}

    print(f"[✗] Upload failed for: {file_name}")
    return None


def get_file_presigned_url(access_token: str, payload: dict):
    upload_endpoint = os.environ["API_BASE_URL"] + "/files/upload"
    try:
        response = requests.post(
            url=upload_endpoint,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json=payload,
        )

        if response.status_code != 200:
            print(f"[✗] API call failed: {response.status_code} {response.text}")
            return {"success": False}

        response = response.json()

        return {
            "success": True,
            "uploadUrl": response.get("uploadUrl"),
            "metadataUrl": response.get("metadataUrl"),
            "key": response.get("key"),
        }

    except Exception as e:
        print(f"[✗] Error calling get presigned url API: {e}")

    return {"success": False}


def upload_to_presigned_url(
    upload_url: str, file_content: Union[str, bytes], content_type: str
) -> bool:
    try:
        # Handle both string and bytes content
        if isinstance(file_content, str):
            data = file_content.encode("utf-8")
        else:
            data = file_content

        response = requests.put(
            upload_url, data=data, headers={"Content-Type": content_type}
        )
        return response.status_code == 200
    except Exception as e:
        print(f"[✗] Upload failed: {e}")
        return False
