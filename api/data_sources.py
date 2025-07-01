# Copyright (c) 2024 Vanderbilt University
# Authors: Jules White, Allen Karns, Karely Rodriguez, Max Moundas

import copy
import os
from typing import Any, Dict, List, Union

import boto3
from boto3.dynamodb.types import TypeDeserializer


def extract_key(source: str) -> str:
    """
    Extract the key portion from a source string by removing protocol prefix.

    Args:
        source: Source string that may contain a protocol
            (e.g., "s3://bucket/key")

    Returns:
        str: The key portion after the protocol separator, or the original
            string if no protocol
    """
    # Look for a :// protocol separator and extract everyting after it
    return source.split("://")[1] if "://" in source else source


def translate_user_data_sources_to_hash_data_sources(
    data_sources: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Translate user data sources to hash data sources by looking up hash file
    locations.

    Args:
        data_sources: List of data source dictionaries with id and type
            information

    Returns:
        List[Dict[str, Any]]: List of translated data sources with updated
            location keys
    """
    dynamodb_client = boto3.client("dynamodb")
    hash_files_table_name = os.environ["HASH_FILES_DYNAMO_TABLE"]
    type_deserializer = TypeDeserializer()

    translated_data_sources = []

    for ds in data_sources:
        key = ds["id"]

        try:
            if key.startswith("s3://"):
                key = extract_key(key)

            if "image/" in ds["type"]:
                # overwrite the id and append to list as it
                ds["id"] = key
                translated_data_sources.append(ds)
                continue

            response = dynamodb_client.get_item(
                TableName=hash_files_table_name, Key={"id": {"S": key}}
            )

            item = response.get("Item")
            if item:
                deserialized_item = {
                    k: type_deserializer.deserialize(v) for k, v in item.items()
                }
                ds["id"] = deserialized_item["textLocationKey"]
        except Exception as e:
            print(e)
            pass

        translated_data_sources.append(ds)

    return [ds for ds in translated_data_sources if ds is not None]


def get_data_source_keys(
    data_sources: List[Dict[str, Any]],
) -> Union[List[str], Dict[str, str]]:
    """
    Extract and process keys from data sources, handling different source types
    and formats.

    Args:
        data_sources: List of data source dictionaries containing id, type, and
            other metadata

    Returns:
        Union[List[str], Dict[str, str]]: List of processed data source keys,
            or error dict if processing fails
    """
    print("Get keys from data sources")
    data_sources_keys = []
    for i in range(len(data_sources)):
        ds = data_sources[i]
        if "metadata" in ds and "image/" in ds["type"]:
            data_sources_keys.append(ds["id"])
            continue
        # print("current datasource: ", ds)
        key = ""
        if ds["id"].startswith("global/"):
            key = ds["id"]
        else:
            if ds["id"].startswith("s3://global/"):
                key = extract_key(ds["id"])
            else:
                ds_copy = copy.deepcopy(ds)
                # Assistant attached data sources tends to have id vals of uuids vs
                # they key we need
                if "key" in ds:
                    ds_copy["id"] = ds["key"]

                key = translate_user_data_sources_to_hash_data_sources([ds_copy])[0][
                    "id"
                ]  # cant

            print("Updated Key: ", key)

        if not key:
            return {"success": "False", "error": "Could not extract key"}
        data_sources_keys.append(key)

    print("Datasource Keys: ", data_sources_keys)
    return data_sources_keys
