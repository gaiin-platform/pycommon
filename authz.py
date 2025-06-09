"""authz.py

This module provides utilities and functions for performing authorization checks
across various projects. It centralizes the logic for determining user permissions
and access control, ensuring consistency and security throughout the codebase.

The module is designed to be extensible and reusable, allowing for integration
with different authentication and authorization systems.

Copyright (c) 2025 Vanderbilt University
Authors: Jules White, Allen Karns, Karely Rodriguez, Max Moundas, Sam Hays
"""

import json
import os
import re
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import boto3
import requests
from boto3.dynamodb.conditions import Key
from dotenv import load_dotenv
from jose import jwt
from jsonschema import SchemaError
from jsonschema import validate as json_validate
from jsonschema.exceptions import ValidationError
from requests import Response

from decorators import required_env_vars
from encoders import CustomPydanticJSONEncoder
from exceptions import ClaimException, HTTPBadRequest, HTTPException, HTTPUnauthorized
from permissions import get_permission_checker

ALGORITHMS = ["RS256"]

# Globals needed by this file
load_dotenv(dotenv_path=".env.local")


@required_env_vars("API_BASE_URL")
def verify_user_as_admin(access_token: str, purpose: str) -> bool:
    """Verifies if a user is an admin based on the provided token and purpose.

    Args:
        access_token (str): The access token for authentication.
        purpose (str): The purpose of the authorization check.

    Returns:
        bool: True if the user is an admin, False otherwise.
    """
    print("Initiating authentication of user as admin.")

    api_base_url = os.environ.get("API_BASE_URL")

    endpoint = f"{api_base_url}/amplifymin/auth"

    request_payload = {"data": {"purpose": purpose}}

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }

    try:
        response: Response = requests.post(
            endpoint, headers=headers, data=json.dumps(request_payload)
        )

        print("Response received:", response.content)
        response_content: dict = response.json()

        if (
            response.status_code != 200
            or response_content.get("success", False) is False
        ):
            return False
        return response_content.get("isAdmin", False)
    except requests.RequestException as e:
        print(f"Network error during authentication: {e}")
        return False
    except json.JSONDecodeError as e:
        # Handle JSON parsing errors
        print(f"Error decoding JSON response: {e}")
        return False


@required_env_vars("OAUTH_ISSUER_BASE_URL", "OAUTH_AUDIENCE", "ACCOUNTS_DYNAMO_TABLE")
def get_claims(token: str) -> dict:
    """Retrieve and validate claims from a JSON Web Token (JWT).

    This function decodes a JWT, validates it against the JWKS (JSON Web Key Set)
    retrieved from the OAuth issuer, and retrieves user claims. It also determines
    the user's default account and allowed access types.

    Args:
        token (str): The JWT access token to validate and decode.

    Returns:
        dict: A dictionary containing the user's claims, including:
            - `username` (str): The validated username.
            - `account` (str): The user's default account.
            - `allowed_access` (list): A list of allowed access types.

    Raises:
        ClaimException: If the token is invalid, the JWKS cannot be retrieved,
                        the RSA key for the token is not found, or the user's
                        claims cannot be validated.
    """

    # https://cognito-idp.<Region>.amazonaws.com/<userPoolId>/.well-known/jwks.json

    if token is None or not isinstance(token, str):
        print("No valid access token found.")
        raise ClaimException("No Valid Access Token Found")

    # Guaranteed by required_env_vars decorator
    oauth_issuer_base_url: str = os.getenv("OAUTH_ISSUER_BASE_URL")  # type: ignore
    oauth_audience: str = os.getenv("OAUTH_AUDIENCE")  # type: ignore
    accounts_table_name: str = os.getenv("ACCOUNTS_DYNAMO_TABLE")  # type: ignore

    idp_prefix: str = (os.getenv("IDP_PREFIX") or "").lower()

    jwks_url: str = f"{oauth_issuer_base_url}/.well-known/jwks.json"

    # Try to get the jwks here and fail otherwise
    try:
        jwks: Response = requests.get(jwks_url)
        if not jwks.ok:
            raise ClaimException(
                f"Failed to retrieve JWKS from {jwks_url}, status code: {jwks.status_code}"  # noqa: E501
            )
        jwks_data: dict = jwks.json()
        header = jwt.get_unverified_header(token)
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON response from JWKS: {e}")
        raise ClaimException("Invalid JWKS response")

    rsa_key: Optional[dict] = jwks_data.get("Keys", {}).get(header.get("kid"), None)
    if not rsa_key:
        print(f"No RSA key found for kid: {header.get('kid')}")
        raise ClaimException("No valid RSA key found in JWKS")

    # Finally, decode
    payload = jwt.decode(
        token,
        rsa_key,
        algorithms=ALGORITHMS,
        audience=oauth_audience,
        issuer=oauth_issuer_base_url,
    )

    print(f"IDP_PREFIX from env: {idp_prefix}")
    print(f"Original username: {payload['username']}")
    user = payload["username"]
    if len(idp_prefix) > 0 and user.startswith(idp_prefix + "_"):
        user = user.split(idp_prefix + "_", 1)[1]
        print(f"User matched pattern, updated to: {user}")
    print(f"Final user value: {user}")

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(accounts_table_name)
    account: Optional[str] = None
    response = table.get_item(Key={"user": user})
    if "Item" not in response:
        raise ClaimException(f"No item found for user: {user}")

    accounts: List[dict] = response["Item"].get("accounts", [])
    for acct in accounts:
        if acct["isDefault"]:
            account = acct["id"]

    if not account:
        print("setting account to general_account")
        account = "general_account"

    payload["account"] = account
    payload["username"] = user
    # Here we can established the allowed access according to the feature
    # flags in the future. For now it is set to full_access, which says they
    # can do the operation upon entry of the validated function
    # current access types include: asssistants, share, dual_embedding,
    # chat, file_upload
    payload["allowed_access"] = ["full_access"]
    return payload


def _validate_data(
    name: str,
    op: str,
    data: Dict[str, Any],
    api_accessed: bool,
    validator_rules: Dict[str, Any],
) -> None:
    """Validate the input data against a JSON schema.

    Args:
        name (str): The name of the operation.
        op (str): The operation being performed.
        data (dict): The input data to validate.
        api_accessed (bool): Whether the API is being accessed.
        validator_rules (dict): The validation rules.

    Raises:
        ValidationError: If the data does not conform to the schema.
    """
    validator: dict = validator_rules.get(
        "api_validators" if api_accessed else "validators", None
    )
    if not validator:
        raise ValidationError("No validator found for the operation")

    if name in validator and op in validator[name]:
        schema: dict = validator[name][op]
        try:
            json_validate(instance=data, schema=schema)
        except ValidationError as e:
            raise ValidationError(f"Invalid data: {e.message}")
        except SchemaError as e:
            raise ValidationError(f"Invalid schema: {e.message}")
    else:
        print(f"Invalid data or path: {name} - op:{op} - data: {data}")
        raise ValidationError("Invalid data or path")


def _parse_and_validate(
    current_user: str,
    event: Dict[str, Any],
    op: str,
    api_accessed: bool,
    validator_rules: dict,
    validate_body: bool = True,
) -> List[Any]:
    """Parse and validate the input event.

    Args:
        current_user (str): The current user performing the operation.
        event (dict): The input event.
        op (str): The operation being performed.
        api_accessed (bool): Whether the API is being accessed.
        validate_body (bool): Whether to validate the request body.

    Returns:
        list: A list containing the name and validated data.

    Raises:
        HTTPBadRequest: If the input is invalid or the
                        user lacks permissions.
    """
    data: dict = {}
    if validate_body:
        try:
            data = json.loads(event["body"]) if event.get("body") else {}
        except json.decoder.JSONDecodeError:
            raise HTTPBadRequest("Unable to parse JSON body.")

    name: Optional[str] = event.get("path")
    if not name:
        raise HTTPBadRequest("Unable to perform the operation, invalid request.")

    if validate_body:
        try:
            _validate_data(name, op, data, api_accessed, validator_rules)
        except ValidationError as e:
            raise HTTPBadRequest(e.message)

    permission_checker = get_permission_checker(current_user, name, op, data)
    if not permission_checker(current_user, data):
        print("User does not have permission to perform the operation.")
        raise HTTPUnauthorized(
            "User does not have permission to perform the operation."
        )

    return [name, data]


@required_env_vars("API_KEYS_DYNAMODB_TABLE")
def api_claims(event: Dict[str, Any], context: dict, token: str) -> Dict[str, Any]:
    """Retrieve and validate API claims based on the provided token.

    Args:
        event (Dict[str, Any]): The input event containing request details.
        context (Any): The execution context of the Lambda function.
        token (str): The API key token to validate.

    Returns:
        Dict[str, Any]: A dictionary containing the username,
                        account ID, and allowed access types.

    Raises:
        ValueError: If the API keys table name is not provided in the environment variables.
        LookupError: If the API key is not found in the database.
        PermissionError: If the API key is inactive, expired, or lacks required access rights.
        HTTPUnauthorized: If the rate limit is exceeded.
        RuntimeError: If an internal server error occurs during the database operation.
    """  # noqa: E501
    print("API route was taken")
    api_keys_table_name: str = os.getenv("API_KEYS_DYNAMODB_TABLE")  # type: ignore

    # Set up DynamoDB connection
    dynamodb = boto3.resource("dynamodb")

    table = dynamodb.Table(api_keys_table_name)

    # Retrieve item from DynamoDB
    response = table.query(
        IndexName="ApiKeyIndex",
        KeyConditionExpression="apiKey = :apiKeyVal",
        ExpressionAttributeValues={":apiKeyVal": token},
    )
    items = response.get("Items", [])

    if not items:
        print("API key does not exist.")
        raise LookupError("API key not found.")

    item = items[0]

    # Check if the API key is active
    if not item.get("active", False):
        print("API key is inactive.")
        raise PermissionError("API key is inactive.")

    # Optionally check the expiration date if applicable
    expiration_date = item.get("expirationDate")
    if (
        expiration_date
        and datetime.strptime(expiration_date, "%Y-%m-%d") <= datetime.now()
    ):
        print("API key has expired.")
        raise PermissionError("API key has expired.")

    # Check for access rights
    access = item.get("accessTypes", [])
    if not any(
        access_type in access
        for access_type in ["file_upload", "share", "chat", "full_access"]
    ):
        print("API key doesn't have access to the functionality.")
        raise PermissionError(
            "API key does not have access to the required functionality."
        )

    # Determine API user
    current_user = _determine_api_user(item)

    # Check rate limits
    rate_limit = item.get("rateLimit", {})

    # TODO: Maybe add these calculations in that function?
    if _is_rate_limited(current_user, rate_limit):
        rate: float = float(rate_limit.get("rate", 0))
        period = rate_limit.get("period", None)
        if period:
            msg = f"rate limit exceeded (${rate:.2f}/{period})"
        else:
            msg = "rate limit exceeded (no period specified)"
        print(msg)
        raise HTTPUnauthorized(msg)

    # Update last accessed timestamp
    table.update_item(
        Key={"api_owner_id": item["api_owner_id"]},
        UpdateExpression="SET lastAccessed = :now",
        ExpressionAttributeValues={":now": datetime.now().isoformat()},
    )
    print("Last Access updated.")

    return {
        "username": current_user,
        "account": item["account"]["id"],
        "allowed_access": access,
    }


def _determine_api_user(data):
    key_type_pattern = r"/(.*?)Key/"
    match = re.search(key_type_pattern, data["api_owner_id"])
    key_type = match.group(1) if match else None

    if key_type == "owner":
        return data.get("owner")
    elif key_type == "delegate":
        return data.get("delegate")
    elif key_type == "system":
        return data.get("systemId")
    else:
        print("Unknown or missing key type in api_owner_id:", key_type)
        raise Exception("Invalid or unrecognized key type.")


def _is_rate_limited(current_user, rate_limit):
    print(rate_limit)
    if rate_limit["period"] == "Unlimited":
        return False

    cost_calc_table = os.getenv("COST_CALCULATIONS_DYNAMO_TABLE")
    if not cost_calc_table:
        raise ValueError("COST_CALCULATIONS_DYNAMO_TABLE is not provided in env var.")

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(cost_calc_table)

    try:
        print("Query cost calculation table")
        response = table.query(KeyConditionExpression=Key("id").eq(current_user))
        items = response["Items"]
        if not items:
            print("Table entry does not exist. Cannot verify if rate limited.")
            return False

        rate_data = items[0]

        period = rate_limit["period"]
        col_name = f"{period.lower()}Cost"

        spent = rate_data[col_name]
        if period == "Hourly":
            spent = spent[
                datetime.now().hour
            ]  # Get the current hour as a number from 0 to 23
        print(f"Amount spent {spent}")
        return spent >= rate_limit["rate"]

    except Exception as error:
        print(f"Error during rate limit DynamoDB operation: {error}")
        return False


def _parse_token(event: Dict[str, Any]) -> str:
    """Parse the authorization token from the event headers.

    Args:
        event (Dict[str, Any]): The input event.

    Returns:
        str: The parsed token.

    Raises:
        HTTPUnauthorized: If no valid token is found.
    """
    token: Optional[str] = None
    normalized_headers: Dict[str, str] = {
        k.lower(): v for k, v in event["headers"].items()
    }
    authorization_key: str = "authorization"

    if authorization_key in normalized_headers:
        parts: List[str] = normalized_headers[authorization_key].split()
        if len(parts) == 2:
            scheme: str
            scheme, token = parts
            if scheme.lower() != "bearer":
                token = None

    if token is None:
        raise HTTPUnauthorized("No Access Token Found")

    return token


def validated(
    op: str, validate_rules: Dict[str, Any], validate_body: bool = True
) -> Callable:
    """Decorator to validate input data and permissions for an API operation.

    Args:
        op (str): The operation being performed.
        validate_rules (dict): The validation rules.
        validate_body (bool): Whether to validate the request body.

    Returns:
        Callable: The decorated function.
    """

    def decorator(f: Callable) -> Callable:
        def wrapper(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
            try:
                token = _parse_token(event)
                api_accessed = token[:4] == "amp-"

                claims = (
                    api_claims(event, context, token)
                    if api_accessed
                    else get_claims(token)
                )

                current_user = claims["username"]
                print(f"User: {current_user}")
                if current_user is None:
                    raise HTTPUnauthorized("User not found.")

                [name, data] = _parse_and_validate(
                    current_user, event, op, api_accessed, validate_rules, validate_body
                )

                data["access_token"] = token
                data["account"] = claims["account"]
                data["api_accessed"] = api_accessed
                data["allowed_access"] = claims["allowed_access"]

                result = f(event, context, current_user, name, data)

                return {
                    "statusCode": 200,
                    "body": json.dumps(result, cls=CustomPydanticJSONEncoder),
                }
            except HTTPException as e:
                return {
                    "statusCode": e.status_code,
                    "body": json.dumps({"error": f"Error: {e.status_code} - {e}"}),
                }

        return wrapper

    return decorator
