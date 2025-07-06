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
    """Upload a file to the cloud storage service.

    This function handles the complete file upload process by first obtaining
    a presigned URL and then uploading the file content to that URL. It also
    manages file metadata and optional RAG pipeline integration.

    Args:
        access_token (str): Bearer token for API authentication.
        file_name (str): Name of the file to upload. Spaces will be replaced
            with underscores.
        file_contents (Union[str, bytes]): The content of the file to upload.
        file_type (str): MIME type of the file (e.g., 'text/plain',
            'application/pdf').
        tags (List[str]): List of tags to associate with the file for
            categorization.
        data_props (dict, optional): Additional metadata properties for the
            file. Defaults to None.
        enter_rag_pipeline (bool, optional): Whether to process the file
            through RAG pipeline. Defaults to False.
        groupId (str, optional): ID of the group to associate the file with.
            Defaults to None.

    Returns:
        dict or None: Dictionary containing file ID and metadata if successful,
            None if failed. Success response includes: {"id": key, "name":
            clean_name, "type": file_type, "tags": tags, "data": data_props,
            "ragOn": enter_rag_pipeline, "knowledgeBase": "default",
            "groupId": groupId}
    """
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
    """Obtain a presigned URL for file upload from the API.

    This function makes an API call to get a presigned URL that can be used to
    upload a file directly to cloud storage. The presigned URL provides
    temporary, secure access to upload without exposing permanent credentials.

    Args:
        access_token (str): Bearer token for API authentication.
        payload (dict): Dictionary containing file metadata and upload
            parameters. Expected structure: {"data": {"name": str, "type":
            str, "tags": List[str], "data": dict, "ragOn": bool,
            "knowledgeBase": str, "groupId": str}}

    Returns:
        dict: Dictionary containing the response status and upload information.
            Success response: {"success": True, "uploadUrl": str,
            "metadataUrl": str, "key": str} Failure response: {"success":
            False}

    Raises:
        Exception: Any network or API errors are caught and logged, returning
            failure response.
    """
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
            print(f"[✗] API call failed: {response.status_code} " f"{response.text}")
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
    """Upload file content to a presigned URL.

    This function performs the actual file upload to cloud storage using a
    presigned URL. It handles both string and binary content types and sets
    the appropriate Content-Type header.

    Args:
        upload_url (str): The presigned URL obtained from the API for
            uploading.
        file_content (Union[str, bytes]): The content to upload. Strings are
            automatically encoded to UTF-8 bytes.
        content_type (str): MIME type of the content (e.g., 'text/plain',
            'application/pdf').

    Returns:
        bool: True if upload was successful (HTTP 200), False otherwise.

    Raises:
        Exception: Any network errors during upload are caught and logged,
            returning False.
    """
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


def delete_file(access_token: str, key: str):
    """Delete a file from the cloud storage service.

    This function makes an API call to delete a file using its key identifier.
    The file will be permanently removed from the storage service.

    Args:
        access_token (str): Bearer token for API authentication.
        key (str): The unique identifier key of the file to delete.

    Returns:
        dict: Dictionary containing the response status and message.
            Success response: {"success": True, "message": str}
            Failure response: {"success": False, "message": str}

    Raises:
        Exception: Any network or API errors are caught and logged, returning
            failure response.
    """
    delete_endpoint = os.environ["API_BASE_URL"] + "/files/delete"

    payload = {"key": key}

    try:
        response = requests.post(
            url=delete_endpoint,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json=payload,
        )

        if response.status_code != 200:
            print(f"[✗] Delete API call failed: {response.status_code} {response.text}")
            return {
                "success": False,
                "message": f"API call failed with status {response.status_code}",
            }

        response_data = response.json()

        success = response_data.get("success", False)
        message = response_data.get("message", "")

        if success:
            print(f"[✓] Successfully deleted file with key: {key}")
        else:
            print(f"[✗] Failed to delete file with key: {key} - {message}")

        return {"success": success, "message": message}

    except Exception as e:
        print(f"[✗] Error calling delete file API: {e}")

    return {"success": False, "message": f"Failed to delete file with key: {key}"}
