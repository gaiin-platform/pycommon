import json
from unittest.mock import MagicMock, patch

import pytest
from jsonschema import ValidationError
from requests import ConnectionError, HTTPError

from authz import _parse_and_validate, api_claims, get_claims, verify_user_as_admin
from exceptions import ClaimException, EnvVarError, HTTPBadRequest, HTTPUnauthorized

share_schema = {
    "type": "object",
    "properties": {
        "key": {"type": "string"},
        "value": {"type": "integer"},
    },
    "required": ["key", "value"],
}

share_load_schema = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
    },
    "required": ["id"],
}

# Example validator_rules
rules = {
    "validators": {
        "/state/share": {"append": share_schema, "read": {}},
        "/state/share/load": {"load": share_load_schema},
    }
}


@patch("authz.requests.post")
@patch("authz.os.environ.get")
def test_verify_user_as_admin_success(mock_get_env, mock_post):
    # Mock environment variable
    mock_get_env.return_value = "http://mock-api.com"

    # Mock successful response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True, "isAdmin": True}
    mock_post.return_value = mock_response

    # Call the function
    result = verify_user_as_admin("mock_token", "mock_purpose")

    # Assertions
    assert result is True
    mock_post.assert_called_once_with(
        "http://mock-api.com/amplifymin/auth",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer mock_token",
        },
        data=json.dumps({"data": {"purpose": "mock_purpose"}}),
    )


@patch("authz.requests.post")
@patch("authz.os.environ.get")
def test_verify_user_as_admin_failure(mock_get_env, mock_post):
    # Mock environment variable
    mock_get_env.return_value = "http://mock-api.com"

    # Mock failed response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": False}
    mock_post.return_value = mock_response

    # Call the function
    result = verify_user_as_admin("mock_token", "mock_purpose")

    # Assertions
    assert result is False


@patch("authz.requests.post")
@patch("authz.os.environ.get")
def test_verify_user_as_admin_http_error(mock_get_env, mock_post):
    # Mock environment variable
    mock_get_env.return_value = "http://mock-api.com"

    # Mock network error
    mock_post.side_effect = HTTPError("HTTP error")

    # Call the function
    result = verify_user_as_admin("mock_token", "mock_purpose")

    # Assertions
    assert result is False


@patch("authz.requests.post")
@patch("authz.os.environ.get")
def test_verify_user_as_admin_connection_error(mock_get_env, mock_post):
    # Mock environment variable
    mock_get_env.return_value = "http://mock-api.com"

    # Mock network error
    mock_post.side_effect = ConnectionError("Connection error")

    # Call the function
    result = verify_user_as_admin("mock_token", "mock_purpose")

    # Assertions
    assert result is False


@patch("authz.requests.post")
@patch("authz.os.environ.get")
def test_verify_user_as_admin_json_decode_error(mock_get_env, mock_post):
    # Mock environment variable
    mock_get_env.return_value = "http://mock-api.com"

    # Mock JSON decode error
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.side_effect = json.JSONDecodeError("Expecting value", "", 0)
    mock_post.return_value = mock_response

    # Call the function
    result = verify_user_as_admin("mock_token", "mock_purpose")

    # Assertions
    assert result is False


# Tests for get_claims
@patch("authz.requests.get")
@patch("authz.os.environ.get")
@patch("authz.boto3.resource")
@patch("authz.jwt.get_unverified_header")
@patch("authz.jwt.decode")
def test_get_claims_success(
    mock_decode, mock_get_header, mock_boto3, mock_get_env, mock_requests_get
):
    # Mock environment variables
    mock_get_env.side_effect = lambda key, default: {
        "OAUTH_ISSUER_BASE_URL": "http://mock-issuer.com",
        "OAUTH_AUDIENCE": "mock-audience",
        "ACCOUNTS_DYNAMO_TABLE": "mock-accounts-table",
        "IDP_PREFIX": "mockprefix",
    }.get(key, default)

    # Mock JWKS response
    mock_requests_get.return_value = MagicMock(
        ok=True,
        json=MagicMock(return_value={"Keys": {"mock_kid": {"key": "mock_key"}}}),
    )

    # Mock JWT header and payload
    mock_get_header.return_value = {"kid": "mock_kid"}
    mock_decode.return_value = {"username": "mockprefix_mockuser"}

    # Mock DynamoDB response
    mock_table = MagicMock()
    mock_table.get_item.return_value = {
        "Item": {
            "accounts": [{"id": "mock_account", "isDefault": True}],
        }
    }
    mock_boto3.return_value.Table.return_value = mock_table

    # Call the function
    result = get_claims("mock_token")

    # Assertions
    assert result["username"] == "mockuser"
    assert result["account"] == "mock_account"
    assert result["allowed_access"] == ["full_access"]


@patch("authz.requests.get")
@patch("authz.os.environ.get")
def test_get_claims_missing_env(mock_get_env, mock_requests_get):
    # Test for each required environment variable being missing
    required_env_vars = [
        "OAUTH_ISSUER_BASE_URL",
        "OAUTH_AUDIENCE",
        "ACCOUNTS_DYNAMO_TABLE",
    ]

    for missing_var in required_env_vars:
        mock_get_env.side_effect = lambda key, default, missing_var=missing_var: (
            None if key == missing_var else "mock_value"
        )

        with pytest.raises(EnvVarError, match=f"Env Var: '{missing_var}' is not set"):
            get_claims("mock_token")


@patch("authz.os.environ.get")
def test_get_claims_token_is_none(mock_get_env):
    mock_get_env.side_effect = lambda key, default: {
        "OAUTH_ISSUER_BASE_URL": "http://mock-issuer.com",
        "OAUTH_AUDIENCE": "mock-audience",
        "ACCOUNTS_DYNAMO_TABLE": "mock-accounts-table",
        "IDP_PREFIX": "mockprefix",
    }.get(key, default)
    with pytest.raises(ClaimException, match="No Valid Access Token Found"):
        get_claims(None)


@patch("authz.requests.get")
@patch("authz.os.environ.get")
def test_get_claims_invalid_jwks(mock_get_env, mock_requests_get):
    mock_get_env.side_effect = lambda key, default: {
        "OAUTH_ISSUER_BASE_URL": "http://mock-issuer.com",
        "OAUTH_AUDIENCE": "mock-audience",
        "ACCOUNTS_DYNAMO_TABLE": "mock-accounts-table",
    }.get(key, default)

    # Mock JWKS response with invalid JSON
    mock_requests_get.return_value = MagicMock(
        ok=True,
        json=MagicMock(side_effect=json.JSONDecodeError("Expecting value", "", 0)),
    )

    with pytest.raises(ClaimException, match="Invalid JWKS response"):
        get_claims("mock_token")


@patch("authz.requests.get")
@patch("authz.os.environ.get")
@patch("authz.jwt.get_unverified_header")
def test_get_claims_missing_rsa_key(mock_get_header, mock_get_env, mock_requests_get):
    mock_get_env.side_effect = lambda key, default: {
        "OAUTH_ISSUER_BASE_URL": "http://mock-issuer.com",
        "OAUTH_AUDIENCE": "mock-audience",
        "ACCOUNTS_DYNAMO_TABLE": "mock-accounts-table",
    }.get(key, default)

    # Mock JWKS response without the required key
    mock_requests_get.return_value = MagicMock(
        ok=True, json=MagicMock(return_value={"Keys": {}})
    )

    # Mock JWT header
    mock_get_header.return_value = {"kid": "mock_kid"}

    with pytest.raises(ClaimException, match="No valid RSA key found in JWKS"):
        get_claims("mock_token")


@patch("authz.requests.get")
@patch("authz.os.environ.get")
@patch("authz.boto3.resource")
@patch("authz.jwt.get_unverified_header")
@patch("authz.jwt.decode")
def test_get_claims_no_dynamodb_item(
    mock_decode, mock_get_header, mock_boto3, mock_get_env, mock_requests_get
):
    mock_get_env.side_effect = lambda key, default: {
        "OAUTH_ISSUER_BASE_URL": "http://mock-issuer.com",
        "OAUTH_AUDIENCE": "mock-audience",
        "ACCOUNTS_DYNAMO_TABLE": "mock-accounts-table",
    }.get(key, default)

    # Mock JWKS response
    mock_requests_get.return_value = MagicMock(
        ok=True,
        json=MagicMock(return_value={"Keys": {"mock_kid": {"key": "mock_key"}}}),
    )

    # Mock JWT header and payload
    mock_get_header.return_value = {"kid": "mock_kid"}
    mock_decode.return_value = {"username": "mockuser"}

    # Mock DynamoDB response with no item
    mock_table = MagicMock()
    mock_table.get_item.return_value = {}
    mock_boto3.return_value.Table.return_value = mock_table

    with pytest.raises(ClaimException, match="No item found for user: mockuser"):
        get_claims("mock_token")


@patch("authz.requests.get")
@patch("authz.os.environ.get")
def test_get_claims_jwks_request_failed(mock_get_env, mock_requests_get):
    # Mock environment variables
    mock_get_env.side_effect = lambda key, default: {
        "OAUTH_ISSUER_BASE_URL": "http://mock-issuer.com",
        "OAUTH_AUDIENCE": "mock-audience",
        "ACCOUNTS_DYNAMO_TABLE": "mock-accounts-table",
    }.get(key, default)

    # Mock JWKS response with a failed status
    mock_requests_get.return_value = MagicMock(ok=False, status_code=500)

    with pytest.raises(
        ClaimException,
        match="Failed to retrieve JWKS from http://mock-issuer.com/.well-known/jwks.json, status code: 500",  # noqa: E501
    ):
        get_claims("mock_token")


@patch("authz.requests.get")
@patch("authz.os.environ.get")
@patch("authz.boto3.resource")
@patch("authz.jwt.get_unverified_header")
@patch("authz.jwt.decode")
def test_get_claims_default_account(
    mock_decode, mock_get_header, mock_boto3, mock_get_env, mock_requests_get
):
    # Mock environment variables
    mock_get_env.side_effect = lambda key, default: {
        "OAUTH_ISSUER_BASE_URL": "http://mock-issuer.com",
        "OAUTH_AUDIENCE": "mock-audience",
        "ACCOUNTS_DYNAMO_TABLE": "mock-accounts-table",
    }.get(key, None)

    # Mock JWKS response
    mock_requests_get.return_value = MagicMock(
        ok=True,
        json=MagicMock(return_value={"Keys": {"mock_kid": {"key": "mock_key"}}}),
    )

    # Mock JWT header and payload
    mock_get_header.return_value = {"kid": "mock_kid"}
    mock_decode.return_value = {"username": "mockuser"}

    # Mock DynamoDB response with a default account
    mock_table = MagicMock()
    mock_table.get_item.return_value = {
        "Item": {
            "accounts": [
                {"id": "mock_account_1", "isDefault": False},
                {"id": "mock_account_2", "isDefault": True},
            ],
        }
    }
    mock_boto3.return_value.Table.return_value = mock_table

    # Call the function
    result = get_claims("mock_token")

    # Assertions
    assert result["username"] == "mockuser"
    assert result["account"] == "mock_account_2"
    assert result["allowed_access"] == ["full_access"]


@patch("authz.requests.get")
@patch("authz.os.environ.get")
@patch("authz.boto3.resource")
@patch("authz.jwt.get_unverified_header")
@patch("authz.jwt.decode")
def test_get_claims_no_default_account(
    mock_decode, mock_get_header, mock_boto3, mock_get_env, mock_requests_get
):
    # Mock environment variables
    mock_get_env.side_effect = lambda key, default: {
        "OAUTH_ISSUER_BASE_URL": "http://mock-issuer.com",
        "OAUTH_AUDIENCE": "mock-audience",
        "ACCOUNTS_DYNAMO_TABLE": "mock-accounts-table",
    }.get(key, default)

    # Mock JWKS response
    mock_requests_get.return_value = MagicMock(
        ok=True,
        json=MagicMock(return_value={"Keys": {"mock_kid": {"key": "mock_key"}}}),
    )

    # Mock JWT header and payload
    mock_get_header.return_value = {"kid": "mock_kid"}
    mock_decode.return_value = {"username": "mockuser"}

    # Mock DynamoDB response with no default account
    mock_table = MagicMock()
    mock_table.get_item.return_value = {
        "Item": {
            "accounts": [
                {"id": "mock_account_1", "isDefault": False},
                {"id": "mock_account_2", "isDefault": False},
            ],
        }
    }
    mock_boto3.return_value.Table.return_value = mock_table

    # Call the function
    result = get_claims("mock_token")

    # Assertions
    assert result["username"] == "mockuser"
    assert result["account"] == "general_account"
    assert result["allowed_access"] == ["full_access"]


@patch("authz.get_permission_checker")
def test_parse_and_validate_success(mock_permission_checker):
    # Mock permission checker to return True
    mock_permission_checker.return_value = lambda user, data: True

    current_user = "mock_user"
    event = {"path": "/state/share", "body": '{"key": "test", "value": 123}'}
    op = "append"
    api_accessed = False

    # Call the function
    result = _parse_and_validate(current_user, event, op, api_accessed, rules)
    print(f"our result =  {result}")

    # Assertions
    assert result == ["/state/share", {"key": "test", "value": 123}]


def test_parse_and_validate_invalid_json_body():
    current_user = "mock_user"
    event = {"path": "mock_path", "body": "invalid_json"}
    op = "mock_op"
    api_accessed = False

    with pytest.raises(HTTPBadRequest, match="Unable to parse JSON body."):
        _parse_and_validate(current_user, event, op, api_accessed, rules)


def test_parse_and_validate_missing_path():
    current_user = "mock_user"
    event = {"body": '{"key": "value"}'}
    op = "mock_op"
    api_accessed = False

    with pytest.raises(
        HTTPBadRequest, match="Unable to perform the operation, invalid request."
    ):
        _parse_and_validate(current_user, event, op, api_accessed, rules)


@patch("authz._validate_data")
def test_parse_and_validate_validation_error(mock_validate_data):
    # Mock validation to raise ValidationError
    mock_validate_data.side_effect = ValidationError("Invalid data")

    current_user = "mock_user"
    event = {"path": "mock_path", "body": '{"key": "value"}'}
    op = "mock_op"
    api_accessed = False

    with pytest.raises(HTTPBadRequest, match="Invalid data"):
        _parse_and_validate(current_user, event, op, api_accessed, rules)


@patch("authz.get_permission_checker")
def test_parse_and_validate_permission_denied(mock_permission_checker):
    mock_permission_checker.return_value = lambda user, data: False

    current_user = "mock_user"
    event = {"path": "/state/share", "body": '{"key": "test", "value": 123}'}
    op = "append"
    api_accessed = False

    with pytest.raises(
        HTTPUnauthorized,
        match="User does not have permission to perform the operation.",
    ):
        _parse_and_validate(current_user, event, op, api_accessed, rules)


@patch("authz._validate_data")
@patch("authz.get_permission_checker")
def test_parse_and_validate_no_body(mock_permission_checker, mock_validate_data):
    # Mock permission checker to return True
    mock_permission_checker.return_value = lambda user, data: True

    current_user = "mock_user"
    event = {"path": "mock_path"}
    op = "mock_op"
    api_accessed = False

    # Call the function
    result = _parse_and_validate(
        current_user, event, op, api_accessed, rules, validate_body=False
    )

    # Assertions
    assert result == ["mock_path", {}]
    mock_validate_data.assert_not_called()


@patch("authz.get_permission_checker")
def test_parse_and_validate_valid_input(mock_permission_checker):
    # Mock permission checker to return True
    mock_permission_checker.return_value = lambda user, data: True

    # Input data
    current_user = "mock_user"
    event = {"path": "/state/share", "body": '{"key": "test", "value": 123}'}
    op = "append"
    api_accessed = False

    # Call the function
    result = _parse_and_validate(current_user, event, op, api_accessed, rules)

    # Assertions
    assert result == ["/state/share", {"key": "test", "value": 123}]


@patch("authz.boto3.resource")
@patch("authz.os.getenv")
def test_api_claims_success(mock_getenv, mock_boto3):
    # Mock environment variables
    mock_getenv.side_effect = lambda key: {
        "API_KEYS_DYNAMODB_TABLE": "mock_api_keys_table",
        "COST_CALCULATIONS_DYNAMO_TABLE": "mock_cost_calculations_table",
    }.get(key)

    # Mock API Keys DynamoDB table and query response
    mock_api_keys_table = MagicMock()
    mock_api_keys_table.query.return_value = {
        "Items": [
            {
                "apiKey": "mock_token",
                "active": True,
                "expirationDate": "2099-12-31",
                "accessTypes": ["file_upload", "share"],
                "account": {"id": "mock_account_id"},
                "api_owner_id": "user/ownerKey/mock_owner",
                "rateLimit": {"rate": 100, "period": "Hourly"},
                "owner": "mock_owner",
            }
        ]
    }

    # Mock Cost Calculations DynamoDB table and query response
    mock_cost_calculations_table = MagicMock()
    mock_cost_calculations_table.query.return_value = {
        "Items": [
            {
                "id": "mock_owner",
                "hourlyCost": [0] * 24,  # Simulate no cost for all hours
            }
        ]
    }

    # Mock boto3 resource to return the appropriate table
    mock_boto3.return_value.Table.side_effect = lambda table_name: {
        "mock_api_keys_table": mock_api_keys_table,
        "mock_cost_calculations_table": mock_cost_calculations_table,
    }[table_name]

    # Call the function
    event = {}
    context = {}
    token = "mock_token"
    result = api_claims(event, context, token)

    # Assertions
    assert result["username"] == "mock_owner"
    assert result["account"] == "mock_account_id"
    assert result["allowed_access"] == ["file_upload", "share"]


@patch("authz.boto3.resource")
@patch("authz.os.getenv")
def test_api_claims_key_not_found(mock_getenv, mock_boto3):
    mock_getenv.side_effect = lambda key: {
        "API_KEYS_DYNAMODB_TABLE": "mock_api_keys_table",
    }.get(key)

    mock_table = MagicMock()
    mock_table.query.return_value = {"Items": []}
    mock_boto3.return_value.Table.return_value = mock_table

    with pytest.raises(LookupError, match="API key not found."):
        api_claims({}, {}, "mock_token")


@patch("authz.boto3.resource")
@patch("authz.os.getenv")
def test_api_claims_inactive_key(mock_getenv, mock_boto3):
    # Mock environment variables
    mock_getenv.side_effect = lambda key: {
        "API_KEYS_DYNAMODB_TABLE": "mock_api_keys_table",
    }.get(key)

    # Mock DynamoDB table and query response with an inactive key
    mock_table = MagicMock()
    mock_table.query.return_value = {
        "Items": [{"apiKey": "mock_token", "active": False}]
    }
    mock_boto3.return_value.Table.return_value = mock_table

    # Call the function and expect a PermissionError
    with pytest.raises(PermissionError, match="API key is inactive."):
        api_claims({}, {}, "mock_token")


@patch("authz.boto3.resource")
@patch("authz.os.getenv")
def test_api_claims_expired_key(mock_getenv, mock_boto3):
    # Mock environment variables
    mock_getenv.side_effect = lambda key: {
        "API_KEYS_DYNAMODB_TABLE": "mock_api_keys_table",
    }.get(key)

    # Mock DynamoDB table and query response with an expired key
    mock_table = MagicMock()
    mock_table.query.return_value = {
        "Items": [
            {"apiKey": "mock_token", "active": True, "expirationDate": "2000-01-01"}
        ]
    }
    mock_boto3.return_value.Table.return_value = mock_table

    # Call the function and expect a PermissionError
    with pytest.raises(PermissionError, match="API key has expired."):
        api_claims({}, {}, "mock_token")


@patch("authz.boto3.resource")
@patch("authz.os.getenv")
def test_api_claims_no_access_rights(mock_getenv, mock_boto3):
    # Mock environment variables
    mock_getenv.side_effect = lambda key: {
        "API_KEYS_DYNAMODB_TABLE": "mock_api_keys_table",
    }.get(key)

    # Mock DynamoDB table and query response with no access rights
    mock_table = MagicMock()
    mock_table.query.return_value = {
        "Items": [{"apiKey": "mock_token", "active": True, "accessTypes": []}]
    }
    mock_boto3.return_value.Table.return_value = mock_table

    # Call the function and expect a PermissionError
    with pytest.raises(
        PermissionError,
        match="API key does not have access to the required functionality.",
    ):
        api_claims({}, {}, "mock_token")


@patch("authz.boto3.resource")
@patch("authz.os.getenv")
def test_api_claims_rate_limit_exceeded(mock_getenv, mock_boto3):
    # Mock environment variables
    mock_getenv.side_effect = lambda key: {
        "API_KEYS_DYNAMODB_TABLE": "mock_api_keys_table",
        "COST_CALCULATIONS_DYNAMO_TABLE": "mock_cost_calculations_table",
    }.get(key)

    # Mock DynamoDB table and query response with rate limit exceeded
    mock_table = MagicMock()
    mock_table.query.return_value = {
        "Items": [
            {
                "apiKey": "mock_token",
                "active": True,
                "rateLimit": {"rate": 0, "period": "Hourly"},
                "api_owner_id": "header/ownerKey/mock_owner",
                "owner": "mock_owner",
                "accessTypes": ["file_upload", "share"],
            }
        ]
    }
    mock_boto3.return_value.Table.return_value = mock_table

    # Mock _is_rate_limited to return True
    with patch("authz._is_rate_limited", return_value=True):
        with pytest.raises(HTTPUnauthorized, match="rate limit exceeded"):
            api_claims({}, {}, "mock_token")
