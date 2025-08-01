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
from typing import Any, Callable, Dict, List, Optional, Tuple

import boto3
import requests
from boto3.dynamodb.conditions import Key
from dotenv import load_dotenv
from jose import jwt
from jose.exceptions import ExpiredSignatureError, JWTClaimsError, JWTError
from jsonschema import SchemaError
from jsonschema import validate as json_validate
from jsonschema.exceptions import ValidationError
from requests import Response

from pycommon.api_utils import TokenV1
from pycommon.const import NO_RATE_LIMIT, UNLIMITED, APIAccessType
from pycommon.decorators import required_env_vars
from pycommon.encoders import CustomPydanticJSONEncoder
from pycommon.exceptions import (
    ClaimException,
    HTTPBadRequest,
    HTTPException,
    HTTPUnauthorized,
    UnknownApiUserException,
)

ALGORITHMS = ["RS256"]

# Globals needed by this file
load_dotenv(dotenv_path=".env.local")

# Global state for validation (similar to ops.py pattern)
_validate_rules: Optional[Dict[str, Any]] = None
_permission_checker: Optional[Callable] = None
_access_types: Optional[List[str]] = [APIAccessType.FULL_ACCESS.value]


def setup_validated(
    validate_rules: Dict[str, Any],
    permission_checker: Callable,
):
    """
    Setup validation rules and permission checker for the validated decorator.

    Args:
        validate_rules: Dictionary containing validation rules for operations
        permission_checker: Function to check permissions, should accept
                          (user, type, op, data) and return a callable that
                          accepts (user, data)
    """
    global _validate_rules, _permission_checker
    _validate_rules = validate_rules
    _permission_checker = permission_checker


def set_validate_rules(validate_rules: Dict[str, Any]):
    """
    Set validation rules for the validated decorator.

    Args:
        validate_rules: Dictionary containing validation rules for operations
    """
    global _validate_rules
    _validate_rules = validate_rules


def set_permission_checker(permission_checker: Callable):
    """
    Set permission checker for the validated decorator.

    Args:
        permission_checker: Function to check permissions, should accept
                          (user, type, op, data) and return a callable that
                          accepts (user, data)
    """
    global _permission_checker
    _permission_checker = permission_checker


def add_api_access_types(access_types: List[str]):
    """
    Set the access types for the validated decorator.

    Args:
        access_types: List of access types to set.
    """
    global _access_types
    _access_types += access_types


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

    # This datastructure is:
    # { "keys": [ {}, {}, ... ] }
    rsa_key: Optional[dict] = None
    for key in jwks_data.get("keys", []):
        if key.get("kid") == header.get("kid"):
            rsa_key = key
            break

    if not rsa_key:
        print(f"No RSA key found for kid: {header.get('kid')}")
        raise ClaimException("No valid RSA key found in JWKS")

    # Finally, decode
    try:
        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=ALGORITHMS,
            audience=oauth_audience,
            issuer=oauth_issuer_base_url,
        )
    except ExpiredSignatureError as e:
        print(f"JWT token has expired: {e}")
        raise ClaimException("JWT token has expired")
    except JWTClaimsError as e:
        print(f"JWT claims error: {e}")
        raise ClaimException("Invalid JWT claims")
    except JWTError as e:
        print(f"JWT decoding error: {e}")
        raise ClaimException("Invalid JWT token")

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
    rate_limit: Optional[dict] = NO_RATE_LIMIT
    response = table.get_item(Key={"user": user})
    if "Item" not in response:
        print(f"Note: User {user} has no accounts")

    accounts: List[dict] = response.get("Item", {}).get("accounts", [])
    for acct in accounts:
        if acct["isDefault"]:
            account = acct["id"]
            if acct.get("rateLimit"):
                rate_limit = acct["rateLimit"]

    if not account:
        print("setting account to general_account")
        account = "general_account"

    payload["account"] = account
    payload["rate_limit"] = rate_limit
    payload["username"] = user
    # Here we can established the allowed access according to the feature
    # flags in the future. For now it is set to full_access, which says they
    # can do the operation upon entry of the validated function
    # current access types include: asssistants, share, dual_embedding,
    # chat, file_upload
    payload["allowed_access"] = [APIAccessType.FULL_ACCESS.value]
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
    print(
        f"_validate_data called with name={name}, op={op}, api_accessed={api_accessed}"
    )

    validator: dict = validator_rules.get(
        "api_validators" if api_accessed else "validators", None
    )
    print(f"Using {'api_validators' if api_accessed else 'validators'} from rules")

    if not validator:
        print("No validator found, raising ValidationError")
        raise ValidationError("No validator found for the operation")

    if name in validator and op in validator[name]:
        print(f"Found validator for {name}/{op}")
        schema: dict = validator[name][op]
        validate_data = data
        if schema != {}:
            validate_data = data["data"]
        try:
            json_validate(instance=validate_data, schema=schema)
            print("JSON validation passed")
        except ValidationError as e:
            print(f"JSON validation failed: {e.message}")
            print(f"Schema Expected: {schema}")
            print(f"Data Provided: {validate_data}")
            raise ValidationError(f"Invalid data: {e.message}")
        except SchemaError as e:
            print(f"Schema error: {e.message}")
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
    permission_checker: Optional[Callable] = None,
) -> List[Any]:
    """Parse and validate the input event.

    Args:
        current_user (str): The current user performing the operation.
        event (dict): The input event.
        op (str): The operation being performed.
        api_accessed (bool): Whether the API is being accessed.
        validate_body (bool): Whether to validate the request body.
        permission_checker (Callable, optional): Function to check permissions.
            Should accept (user, type, op, data) and return a callable that accepts (user, data).

    Returns:
        list: A list containing the name and validated data.

    Raises:
        HTTPBadRequest: If the input is invalid or the user lacks permissions.
        HTTPUnauthorized: If the user does not have permission to perform the operation.
    """  # noqa: E501
    print("Getting path from event...")
    # Handle both API Gateway and Lambda Function URL events
    name: Optional[str] = None

    # First try API Gateway format
    if "path" in event:
        print("API Gateway format detected")
        name = event.get("path")
    # Then try Lambda Function URL formats
    elif "rawPath" in event:
        print("Lambda Function URL format detected")
        name = event.get("rawPath")
    elif "requestContext" in event and "http" in event["requestContext"]:
        print("Lambda Function URL alternative format detected")
        name = event["requestContext"]["http"].get("path")
    elif "requestContext" in event and "path" in event["requestContext"]:
        print("Container Lambda Function URL format detected")
        name = event["requestContext"].get("path")

    print(
        f"_parse_and_validate started for user: {current_user}, "
        f"op: {op}, path: {name}"
    )
    print(f"api_accessed: {api_accessed}, validate_body: {validate_body}")

    data: dict = {}
    print("Parsing request body...")
    try:
        data = json.loads(event["body"]) if event.get("body") else {}
        print("Body parsed successfully")
    except json.decoder.JSONDecodeError:
        print("JSON decode error in body parsing")
        raise HTTPBadRequest("Unable to parse JSON body.")

    if not name:
        print("No path found in event")
        raise HTTPBadRequest("Unable to perform the operation, invalid request.")

    if validate_body:
        print("Validating data...")
        try:
            _validate_data(name, op, data, api_accessed, validator_rules)
            print("Data validation completed successfully")
        except ValidationError as e:
            print(f"Validation error: {e}")
            raise HTTPBadRequest(e.message)

    print("Checking permissions...")
    try:
        # If the permission checker exists, is callable, returns a callabe and
        # that callable returns False, then we raise an HTTPUnauthorized
        if permission_checker is not None:
            print("Permission checker exists, calling it...")
            permission_result = permission_checker(current_user, name, op, data)
            print("Permission checker returned, calling result function...")
            if not permission_result(current_user, data):
                print("User does not have permission to perform the operation.")
                raise HTTPUnauthorized(
                    "User does not have permission to perform the operation."
                )
            print("Permission check passed")
        else:
            print("No permission checker set")
    except (NameError, TypeError) as e:
        # This  means our permission checker is not defined
        print(f"Permission checker error (expected): {e}")
        pass

    print(f"_parse_and_validate completed successfully, returning name={name}")
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

    # determine if we have a new or old key type
    lookup_value: str = token
    if lookup_value[:7] == "amp-v1-":
        # this is a new key, we need to look up the hash
        token_v1 = TokenV1(lookup_value)
        lookup_value = token_v1.key  # hash

    # Retrieve item from DynamoDB
    response = table.query(
        IndexName="ApiKeyIndex",
        KeyConditionExpression="apiKey = :apiKeyVal",
        ExpressionAttributeValues={":apiKeyVal": lookup_value},
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
    if not any(access_type in access for access_type in _access_types):
        print("API key doesn't have access to the functionality.")
        raise PermissionError(
            "API key does not have access to the required functionality."
        )

    # Determine API user
    current_user = _determine_api_user(item)

    # Check rate limits
    rate_limit = item.get("rateLimit", {})

    limited, msg = is_rate_limited(current_user, rate_limit)
    if limited:
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
        "rate_limit": rate_limit,
        "api_key_id": item["api_owner_id"],
        "purpose": item.get("purpose"),
    }


def _determine_api_user(data: Dict[str, Any]) -> str:
    """
    Determines the API user based on the api_owner_id field in the provided data.

    The function inspects the 'api_owner_id' to extract the key type (owner, delegate, or system)
    and returns the corresponding user identifier from the data dictionary.

    Args:
        data (Dict[str, Any]): The dictionary containing API key metadata, including 'api_owner_id'.

    Returns:
        str: The user identifier associated with the API key.

    Raises:
        Exception: If the key type is invalid, unrecognized, or the expected user field is missing.

    Security Considerations:
        - Assumes 'api_owner_id' is trusted and well-formed. If user input can control this field,
          additional validation/sanitization may be required.
        - Raises a generic Exception on error; consider using a more specific exception type for production.
    """  # noqa: E501
    # Precompile regex for efficiency and safety;
    # pattern is non-greedy and safe for typical short strings.
    key_type_pattern = re.compile(r"/(.*?)Key/")
    match: Optional[re.Match] = key_type_pattern.search(data.get("api_owner_id", ""))
    key_type: Optional[str] = match.group(1) if match else None

    if key_type == "owner":
        user = data.get("owner")
    elif key_type == "delegate":
        user = data.get("delegate")
    elif key_type == "system":
        user = data.get("systemId")
    else:
        print("Unknown or missing key type in api_owner_id:", key_type)
        raise UnknownApiUserException("Invalid or unrecognized key type.")

    if not user or not isinstance(user, str):
        raise UnknownApiUserException(
            f"Missing or invalid user identifier for key type '{key_type}'."
        )

    return user


@required_env_vars("COST_CALCULATIONS_DYNAMO_TABLE")
def is_rate_limited(current_user: str, rate_limit: dict) -> Tuple[bool, str]:
    """
    Checks if the current user has exceeded their rate limit based on usage data stored in DynamoDB.

    Args:
        current_user (str): The identifier for the user whose rate limit is being checked.
        rate_limit (dict): A dictionary containing rate limit configuration, including 'period' and 'rate'.

    Returns:
        Tuple[bool, str]: A tuple containing a boolean indicating if the user is rate limited and a message.
                          The message indicates the reason for the boolean and may include details that the
                          end-user should not see.
    """  # noqa: E501

    print(rate_limit)
    period: Optional[str] = rate_limit.get("period")
    if period is None:
        return False, "Rate limit period is not specified in the rate_limit data"
    if period == UNLIMITED:
        return False, "No rate limit set"

    cost_calc_table: str = os.getenv("COST_CALCULATIONS_DYNAMO_TABLE")  # type: ignore

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(cost_calc_table)
    try:
        print("Query cost calculation table")
        response = table.query(KeyConditionExpression=Key("id").eq(current_user))
        items = response.get("Items", [])
        if not items:
            return False, "Table entry does not exist. Cannot verify if rate limited."

        rate_data: dict = items[0]

        col_name = f"{period.lower()}Cost"
        spent = rate_data.get(col_name)
        if spent is None:
            return False, f"Column {col_name} not found in rate data"

        if period == "Hourly":
            current_hour = datetime.now().hour
            if not isinstance(spent, list) or current_hour >= len(spent):
                return False, "Hourly cost data is missing or malformed."
            spent = spent[current_hour]  # Get the current hour's usage

        print(f"Amount spent {spent}")
        rate_val: Optional[str] = rate_limit.get("rate")
        if rate_val is None:
            return False, "Rate value missing in rate_limit."

        rate: float = float(rate_limit.get("rate", 0))
        period = rate_limit.get("period", None)
        is_limited: bool = spent >= rate
        if is_limited:
            return True, f"rate limit exceeded (${rate:.2f}/{period})"

        return False, "Rate limit not exceeded"

    except boto3.exceptions.Boto3Error as error:
        print(f"Boto3 error during rate limit DynamoDB operation: {error}")
        return False, "Error accessing DynamoDB for rate limit check"
    except Exception as error:
        print(f"Unexpected error during rate limit DynamoDB operation: {error}")
        return False, "Unexpected error during rate limit check"


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
    op: str,
    validate_body: bool = True,
) -> Callable:
    """Decorator to validate input data and permissions for an API operation.

    Args:
        op (str): The operation being performed.
        validate_body (bool): Whether to validate the request body.

    Returns:
        Callable: The decorated function.

    Note:
        Uses global _validate_rules and _permission_checker set
        via setup_validated()
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

                print("Prior to call _parse_and_validate...")
                print(f"Validation rules available: {_validate_rules is not None}")
                print(
                    f"Permission checker available: {_permission_checker is not None}"
                )

                [name, data] = _parse_and_validate(
                    current_user,
                    event,
                    op,
                    api_accessed,
                    _validate_rules or {},
                    validate_body,
                    _permission_checker,
                )
                print(f"_parse_and_validate completed successfully. name={name}")

                print("Setting up data dictionary...")
                data["access_token"] = token
                data["account"] = claims["account"]
                data["api_key_id"] = claims.get("api_key_id")
                data["rate_limit"] = claims["rate_limit"]
                data["api_accessed"] = api_accessed
                data["allowed_access"] = claims["allowed_access"]
                data["purpose"] = claims.get(
                    "purpose"
                )  # helps identify group system users for ex.
                print("Data dictionary setup complete, calling main function...")

                result = f(event, context, current_user, name, data)
                print("Main function completed successfully")

                return {
                    "statusCode": 200,
                    "body": json.dumps(result, cls=CustomPydanticJSONEncoder),
                }
            except HTTPException as e:
                print(f"HTTPException caught: {e.status_code} - {e}")
                return {
                    "statusCode": e.status_code,
                    "body": json.dumps({"error": f"Error: {e.status_code} - {e}"}),
                }
            except Exception as e:
                print(f"Unexpected exception caught: {type(e).__name__} - {e}")
                import traceback

                print(f"Traceback: {traceback.format_exc()}")
                raise

        return wrapper

    return decorator
