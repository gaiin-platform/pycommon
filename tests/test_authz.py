import json
from unittest.mock import MagicMock, patch

import boto3
import pytest
from jose import ExpiredSignatureError, JWTError
from jose.exceptions import JWTClaimsError
from jsonschema.exceptions import ValidationError
from requests import ConnectionError, HTTPError

from pycommon.authz import (
    _determine_api_user,
    _parse_and_validate,
    _parse_token,
    _validate_data,
    add_api_access_types,
    api_claims,
    get_claims,
    is_rate_limited,
    set_permission_checker,
    set_validate_rules,
    setup_validated,
    validated,
    verify_user_as_admin,
)
from pycommon.exceptions import (
    ClaimException,
    EnvVarError,
    HTTPBadRequest,
    HTTPUnauthorized,
    UnknownApiUserException,
)

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

rules = {
    "validators": {
        "/state/share": {"append": share_schema, "read": {}},
        "/state/share/load": {"load": share_load_schema},
    }
}


def always_allow_permission_checker(user, type, op, data):
    return lambda user, data: True


always_allow_permission_checker(None, None, None, None)


@patch("pycommon.authz.requests.post")
@patch("pycommon.authz.os.environ.get")
def test_verify_user_as_admin_success(mock_get_env, mock_post):
    mock_get_env.return_value = "http://mock-api.com"

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True, "isAdmin": True}
    mock_post.return_value = mock_response

    result = verify_user_as_admin("mock_token", "mock_purpose")

    assert result is True
    mock_post.assert_called_once_with(
        "http://mock-api.com/amplifymin/auth",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer mock_token",
        },
        data=json.dumps({"data": {"purpose": "mock_purpose"}}),
    )


@patch("pycommon.authz.requests.post")
@patch("pycommon.authz.os.environ.get")
def test_verify_user_as_admin_failure(mock_get_env, mock_post):
    mock_get_env.return_value = "http://mock-api.com"

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": False}
    mock_post.return_value = mock_response

    result = verify_user_as_admin("mock_token", "mock_purpose")

    assert result is False


@patch("pycommon.authz.requests.post")
@patch("pycommon.authz.os.environ.get")
def test_verify_user_as_admin_http_error(mock_get_env, mock_post):
    mock_get_env.return_value = "http://mock-api.com"

    mock_post.side_effect = HTTPError("HTTP error")

    result = verify_user_as_admin("mock_token", "mock_purpose")

    assert result is False


@patch("pycommon.authz.requests.post")
@patch("pycommon.authz.os.environ.get")
def test_verify_user_as_admin_connection_error(mock_get_env, mock_post):
    mock_get_env.return_value = "http://mock-api.com"

    mock_post.side_effect = ConnectionError("Connection error")

    result = verify_user_as_admin("mock_token", "mock_purpose")

    assert result is False


@patch("pycommon.authz.requests.post")
@patch("pycommon.authz.os.environ.get")
def test_verify_user_as_admin_json_decode_error(mock_get_env, mock_post):
    mock_get_env.return_value = "http://mock-api.com"

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.side_effect = json.JSONDecodeError("Expecting value", "", 0)
    mock_post.return_value = mock_response

    result = verify_user_as_admin("mock_token", "mock_purpose")

    assert result is False


@patch("pycommon.authz.requests.get")
@patch("pycommon.authz.os.environ.get")
@patch("pycommon.authz.boto3.resource")
@patch("pycommon.authz.jwt.get_unverified_header")
@patch("pycommon.authz.jwt.decode")
def test_get_claims_success(
    mock_decode, mock_get_header, mock_boto3, mock_get_env, mock_requests_get
):
    mock_get_env.side_effect = lambda key, default: {
        "OAUTH_ISSUER_BASE_URL": "http://mock-issuer.com",
        "OAUTH_AUDIENCE": "mock-audience",
        "ACCOUNTS_DYNAMO_TABLE": "mock-accounts-table",
        "IDP_PREFIX": "mockprefix",
    }.get(key, default)

    mock_requests_get.return_value = MagicMock(
        ok=True,
        json=MagicMock(return_value={"keys": [{"kid": "mock_kid", "key": "mock_key"}]}),
    )

    mock_get_header.return_value = {"kid": "mock_kid"}
    mock_decode.return_value = {"username": "mockprefix_mockuser"}

    mock_table = MagicMock()
    mock_table.get_item.return_value = {
        "Item": {
            "accounts": [
                {
                    "id": "mock_account",
                    "isDefault": True,
                    "rateLimit": {"rate": 42, "period": "Hourly"},
                }
            ],
        }
    }
    mock_boto3.return_value.Table.return_value = mock_table

    result = get_claims("mock_token")

    assert result["username"] == "mockuser"
    assert result["account"] == "mock_account"
    assert result["allowed_access"] == ["full_access"]
    assert result["rate_limit"] == {"rate": 42, "period": "Hourly"}


@patch("pycommon.authz.requests.get")
@patch("pycommon.authz.os.environ.get")
def test_get_claims_missing_env(mock_get_env, mock_requests_get):
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


@patch("pycommon.authz.os.environ.get")
def test_get_claims_token_is_none(mock_get_env):
    mock_get_env.side_effect = lambda key, default: {
        "OAUTH_ISSUER_BASE_URL": "http://mock-issuer.com",
        "OAUTH_AUDIENCE": "mock-audience",
        "ACCOUNTS_DYNAMO_TABLE": "mock-accounts-table",
        "IDP_PREFIX": "mockprefix",
    }.get(key, default)
    with pytest.raises(ClaimException, match="No Valid Access Token Found"):
        get_claims(None)


@patch("pycommon.authz.requests.get")
@patch("pycommon.authz.os.environ.get")
def test_get_claims_invalid_jwks(mock_get_env, mock_requests_get):
    mock_get_env.side_effect = lambda key, default: {
        "OAUTH_ISSUER_BASE_URL": "http://mock-issuer.com",
        "OAUTH_AUDIENCE": "mock-audience",
        "ACCOUNTS_DYNAMO_TABLE": "mock-accounts-table",
    }.get(key, default)

    mock_requests_get.return_value = MagicMock(
        ok=True,
        json=MagicMock(side_effect=json.JSONDecodeError("Expecting value", "", 0)),
    )

    with pytest.raises(ClaimException, match="Invalid JWKS response"):
        get_claims("mock_token")


@patch("pycommon.authz.requests.get")
@patch("pycommon.authz.os.environ.get")
@patch("pycommon.authz.jwt.get_unverified_header")
def test_get_claims_missing_rsa_key(mock_get_header, mock_get_env, mock_requests_get):
    mock_get_env.side_effect = lambda key, default: {
        "OAUTH_ISSUER_BASE_URL": "http://mock-issuer.com",
        "OAUTH_AUDIENCE": "mock-audience",
        "ACCOUNTS_DYNAMO_TABLE": "mock-accounts-table",
    }.get(key, default)

    mock_requests_get.return_value = MagicMock(
        ok=True, json=MagicMock(return_value={"keys": {}})
    )

    mock_get_header.return_value = {"kid": "mock_kid"}

    with pytest.raises(ClaimException, match="No valid RSA key found in JWKS"):
        get_claims("mock_token")


@patch("pycommon.authz.requests.get")
@patch("pycommon.authz.os.environ.get")
@patch("pycommon.authz.boto3.resource")
@patch("pycommon.authz.jwt.get_unverified_header")
@patch("pycommon.authz.jwt.decode")
def test_get_claims_with_rsa_key(
    mock_decode, mock_get_header, mock_boto3, mock_get_env, mock_requests_get
):
    mock_get_env.side_effect = lambda key, default: {
        "OAUTH_ISSUER_BASE_URL": "http://mock-issuer.com",
        "OAUTH_AUDIENCE": "mock-audience",
        "ACCOUNTS_DYNAMO_TABLE": "mock-accounts-table",
    }.get(key, default)

    mock_table = MagicMock()
    mock_table.get_item.return_value = {}

    mock_table.get_item.return_value = {
        "Item": {
            "accounts": [
                {"id": "mock_account_1", "isDefault": False},
                {"id": "mock_account_2", "isDefault": True},
            ],
        }
    }

    mock_boto3.return_value.Table.return_value = mock_table

    mock_requests_get.return_value = MagicMock(
        ok=True, json=MagicMock(return_value={"keys": [{"kid": "mock_kid"}]})
    )

    mock_get_header.return_value = {"kid": "mock_kid"}
    mock_decode.return_value = {"username": "mockuser"}

    x = get_claims("mock_token")
    assert x["username"] == "mockuser"
    assert x["account"] == "mock_account_2"
    assert x["allowed_access"] == ["full_access"]
    assert x["rate_limit"] == {"period": "Unlimited", "rate": None}


@patch("pycommon.authz.requests.get")
@patch("pycommon.authz.os.environ.get")
@patch("pycommon.authz.jwt.get_unverified_header")
@patch("pycommon.authz.jwt.decode")
def test_get_claims_with_no_kid_found(
    mock_decode, mock_get_header, mock_get_env, mock_requests_get
):
    mock_get_env.side_effect = lambda key, default: {
        "OAUTH_ISSUER_BASE_URL": "http://mock-issuer.com",
        "OAUTH_AUDIENCE": "mock-audience",
        "ACCOUNTS_DYNAMO_TABLE": "mock-accounts-table",
    }.get(key, default)

    mock_requests_get.return_value = MagicMock(
        ok=True, json=MagicMock(return_value={"keys": [{"kid": "bad_kid"}]})
    )

    mock_get_header.return_value = {"kid": "mock_kid"}
    mock_decode.return_value = {"username": "mockuser"}

    with pytest.raises(ClaimException, match="No valid RSA key found in JWKS"):
        get_claims("mock_token")


@patch("pycommon.authz.requests.get")
@patch("pycommon.authz.os.environ.get")
@patch("pycommon.authz.boto3.resource")
@patch("pycommon.authz.jwt.get_unverified_header")
@patch("pycommon.authz.jwt.decode")
def test_get_claims_no_dynamodb_item(
    mock_decode, mock_get_header, mock_boto3, mock_get_env, mock_requests_get
):
    mock_get_env.side_effect = lambda key, default: {
        "OAUTH_ISSUER_BASE_URL": "http://mock-issuer.com",
        "OAUTH_AUDIENCE": "mock-audience",
        "ACCOUNTS_DYNAMO_TABLE": "mock-accounts-table",
    }.get(key, default)

    mock_requests_get.return_value = MagicMock(
        ok=True,
        json=MagicMock(return_value={"keys": [{"kid": "mock_kid", "key": "mock_key"}]}),
    )

    mock_get_header.return_value = {"kid": "mock_kid"}
    mock_decode.return_value = {"username": "mockuser"}

    mock_table = MagicMock()
    mock_table.get_item.return_value = {}
    mock_boto3.return_value.Table.return_value = mock_table

    # Should no longer raise KeyError, but should handle gracefully
    result = get_claims("mock_token")
    assert result["username"] == "mockuser"
    assert result["account"] == "general_account"
    assert result["allowed_access"] == ["full_access"]
    assert result["rate_limit"] == {"period": "Unlimited", "rate": None}


@patch("pycommon.authz.requests.get")
@patch("pycommon.authz.os.environ.get")
def test_get_claims_jwks_request_failed(mock_get_env, mock_requests_get):
    mock_get_env.side_effect = lambda key, default: {
        "OAUTH_ISSUER_BASE_URL": "http://mock-issuer.com",
        "OAUTH_AUDIENCE": "mock-audience",
        "ACCOUNTS_DYNAMO_TABLE": "mock-accounts-table",
    }.get(key, default)

    mock_requests_get.return_value = MagicMock(ok=False, status_code=500)

    with pytest.raises(
        ClaimException,
        match="Failed to retrieve JWKS from http://mock-issuer.com/.well-known/jwks.json, status code: 500",  # noqa: E501
    ):
        get_claims("mock_token")


@patch("pycommon.authz.requests.get")
@patch("pycommon.authz.os.environ.get")
@patch("pycommon.authz.boto3.resource")
@patch("pycommon.authz.jwt.get_unverified_header")
@patch("pycommon.authz.jwt.decode")
def test_get_claims_default_account(
    mock_decode, mock_get_header, mock_boto3, mock_get_env, mock_requests_get
):
    mock_get_env.side_effect = lambda key, default: {
        "OAUTH_ISSUER_BASE_URL": "http://mock-issuer.com",
        "OAUTH_AUDIENCE": "mock-audience",
        "ACCOUNTS_DYNAMO_TABLE": "mock-accounts-table",
    }.get(key, None)
    mock_requests_get.return_value = MagicMock(
        ok=True,
        json=MagicMock(return_value={"keys": [{"kid": "mock_kid", "key": "mock_key"}]}),
    )
    mock_get_header.return_value = {"kid": "mock_kid"}
    mock_decode.return_value = {"username": "mockuser"}
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
    result = get_claims("mock_token")
    assert result["username"] == "mockuser"
    assert result["account"] == "mock_account_2"
    assert result["allowed_access"] == ["full_access"]
    assert result["rate_limit"] == {"period": "Unlimited", "rate": None}


@patch("pycommon.authz.requests.get")
@patch("pycommon.authz.os.environ.get")
@patch("pycommon.authz.boto3.resource")
@patch("pycommon.authz.jwt.get_unverified_header")
@patch("pycommon.authz.jwt.decode")
def test_get_claims_no_default_account(
    mock_decode, mock_get_header, mock_boto3, mock_get_env, mock_requests_get
):
    mock_get_env.side_effect = lambda key, default: {
        "OAUTH_ISSUER_BASE_URL": "http://mock-issuer.com",
        "OAUTH_AUDIENCE": "mock-audience",
        "ACCOUNTS_DYNAMO_TABLE": "mock-accounts-table",
    }.get(key, default)
    mock_requests_get.return_value = MagicMock(
        ok=True,
        json=MagicMock(return_value={"keys": [{"kid": "mock_kid", "key": "mock_key"}]}),
    )
    mock_get_header.return_value = {"kid": "mock_kid"}
    mock_decode.return_value = {"username": "mockuser"}
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
    result = get_claims("mock_token")
    assert result["username"] == "mockuser"
    assert result["account"] == "general_account"
    assert result["allowed_access"] == ["full_access"]
    assert result["rate_limit"] == {"period": "Unlimited", "rate": None}


@patch("pycommon.authz.requests.get")
@patch("pycommon.authz.os.environ.get")
@patch("pycommon.authz.boto3.resource")
@patch("pycommon.authz.jwt.get_unverified_header")
@patch("pycommon.authz.jwt.decode")
def test_get_claims_no_accounts_list(
    mock_decode, mock_get_header, mock_boto3, mock_get_env, mock_requests_get
):
    """Test the case where no default account is found and the print statement is
    executed."""
    mock_get_env.side_effect = lambda key, default: {
        "OAUTH_ISSUER_BASE_URL": "http://mock-issuer.com",
        "OAUTH_AUDIENCE": "mock-audience",
        "ACCOUNTS_DYNAMO_TABLE": "mock-accounts-table",
    }.get(key, default)
    mock_requests_get.return_value = MagicMock(
        ok=True,
        json=MagicMock(return_value={"keys": [{"kid": "mock_kid", "key": "mock_key"}]}),
    )
    mock_get_header.return_value = {"kid": "mock_kid"}
    mock_decode.return_value = {"username": "mockuser"}
    mock_table = MagicMock()
    mock_table.get_item.return_value = {
        "Item": {
            "accounts": [],  # Empty accounts list
        }
    }
    mock_boto3.return_value.Table.return_value = mock_table
    result = get_claims("mock_token")
    assert result["username"] == "mockuser"
    assert result["account"] == "general_account"
    assert result["allowed_access"] == ["full_access"]
    assert result["rate_limit"] == {"period": "Unlimited", "rate": None}


def test_parse_and_validate_success():
    def mock_permission_checker(user, type, op, data):
        return lambda user, data: True

    current_user = "mock_user"
    event = {"path": "/state/share", "body": '{"data": {"key": "test", "value": 123}}'}
    op = "append"
    api_accessed = False
    result = _parse_and_validate(
        current_user,
        event,
        op,
        api_accessed,
        rules,
        permission_checker=mock_permission_checker,
    )
    assert result == ["/state/share", {"data": {"key": "test", "value": 123}}]


def test_parse_and_validate_bad_permission_checker():
    # This doesn't accept the right number of expect arguments
    def mock_permission_checker(user, type, op):
        return lambda user, data: True

    current_user = "mock_user"
    event = {"path": "/state/share", "body": '{"data": {"key": "test", "value": 123}}'}
    op = "append"
    api_accessed = False
    result = _parse_and_validate(
        current_user,
        event,
        op,
        api_accessed,
        rules,
        permission_checker=mock_permission_checker,
    )
    assert result == ["/state/share", {"data": {"key": "test", "value": 123}}]


def test_parse_and_validate_no_permission_checker_set():
    current_user = "mock_user"
    event = {"path": "/state/share", "body": '{"data": {"key": "test", "value": 123}}'}
    op = "append"
    api_accessed = False
    result = _parse_and_validate(
        current_user,
        event,
        op,
        api_accessed,
        rules,
    )
    assert result == ["/state/share", {"data": {"key": "test", "value": 123}}]


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


@patch("pycommon.authz._validate_data")
def test_parse_and_validate_validation_error(mock_validate_data):
    mock_validate_data.side_effect = ValidationError("Invalid data")

    current_user = "mock_user"
    event = {"path": "mock_path", "body": '{"key": "value"}'}
    op = "mock_op"
    api_accessed = False

    with pytest.raises(HTTPBadRequest, match="Invalid data"):
        _parse_and_validate(current_user, event, op, api_accessed, rules)


def test_parse_and_validate_permission_denied():
    def mock_permission_checker(user, type, op, data):
        return lambda user, data: False

    current_user = "mock_user"
    event = {"path": "/state/share", "body": '{"data": {"key": "test", "value": 123}}'}
    op = "append"
    api_accessed = False

    with pytest.raises(
        HTTPUnauthorized,
        match="User does not have permission to perform the operation.",
    ):
        _parse_and_validate(
            current_user,
            event,
            op,
            api_accessed,
            rules,
            permission_checker=mock_permission_checker,
        )


@patch("pycommon.authz._validate_data")
def test_parse_and_validate_no_body(mock_validate_data):
    def mock_permission_checker(user, type, op, data):
        return lambda user, data: True

    current_user = "mock_user"
    event = {"path": "mock_path"}
    op = "mock_op"
    api_accessed = False
    result = _parse_and_validate(
        current_user,
        event,
        op,
        api_accessed,
        rules,
        validate_body=False,
        permission_checker=mock_permission_checker,
    )
    assert result == ["mock_path", {}]
    mock_validate_data.assert_not_called()


def test_parse_and_validate_valid_input():
    def mock_permission_checker(user, type, op, data):
        return lambda user, data: True

    current_user = "mock_user"
    event = {"path": "/state/share", "body": '{"data": {"key": "test", "value": 123}}'}
    op = "append"
    api_accessed = False
    result = _parse_and_validate(
        current_user,
        event,
        op,
        api_accessed,
        rules,
        permission_checker=mock_permission_checker,
    )
    assert result == ["/state/share", {"data": {"key": "test", "value": 123}}]


def test_parse_and_validate_rawpath_format():
    """Test _parse_and_validate with Lambda Function URL rawPath format."""

    def mock_permission_checker(user, type, op, data):
        return lambda user, data: True

    current_user = "mock_user"
    event = {
        "rawPath": "/state/share",
        "body": '{"data": {"key": "test", "value": 123}}',
    }
    op = "append"
    api_accessed = False
    result = _parse_and_validate(
        current_user,
        event,
        op,
        api_accessed,
        rules,
        permission_checker=mock_permission_checker,
    )
    assert result == ["/state/share", {"data": {"key": "test", "value": 123}}]


def test_parse_and_validate_lambda_function_url_alternative_format():
    """Test _parse_and_validate with Lambda Function URL alternative format."""

    def mock_permission_checker(user, type, op, data):
        return lambda user, data: True

    current_user = "mock_user"
    event = {
        "requestContext": {"http": {"path": "/state/share"}},
        "body": '{"data": {"key": "test", "value": 123}}',
    }
    op = "append"
    api_accessed = False
    result = _parse_and_validate(
        current_user,
        event,
        op,
        api_accessed,
        rules,
        permission_checker=mock_permission_checker,
    )
    assert result == ["/state/share", {"data": {"key": "test", "value": 123}}]


def test_parse_and_validate_container_lambda_function_url_format():
    """Test _parse_and_validate with Container Lambda Function URL format."""

    def mock_permission_checker(user, type, op, data):
        return lambda user, data: True

    current_user = "mock_user"
    event = {
        "requestContext": {"path": "/state/share"},
        "body": '{"data": {"key": "test", "value": 123}}',
    }
    op = "append"
    api_accessed = False
    result = _parse_and_validate(
        current_user,
        event,
        op,
        api_accessed,
        rules,
        permission_checker=mock_permission_checker,
    )
    assert result == ["/state/share", {"data": {"key": "test", "value": 123}}]


@patch("pycommon.authz.boto3.resource")
@patch("pycommon.authz.os.getenv")
def test_api_claims_success(mock_getenv, mock_boto3):
    import pycommon.authz

    # Store original access types to restore later
    original_access_types = pycommon.authz._access_types.copy()

    try:
        # Set access types to include the ones used in this test
        pycommon.authz._access_types = ["full_access", "file_upload", "share"]

        mock_getenv.side_effect = lambda key: {
            "API_KEYS_DYNAMODB_TABLE": "mock_api_keys_table",
            "COST_CALCULATIONS_DYNAMO_TABLE": "mock_cost_calculations_table",
        }.get(key)
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
        mock_cost_calculations_table = MagicMock()
        mock_cost_calculations_table.query.return_value = {
            "Items": [
                {
                    "id": "mock_owner",
                    "hourlyCost": [0] * 24,  # Simulate no cost for all hours
                }
            ]
        }
        mock_boto3.return_value.Table.side_effect = lambda table_name: {
            "mock_api_keys_table": mock_api_keys_table,
            "mock_cost_calculations_table": mock_cost_calculations_table,
        }[table_name]
        event = {}
        context = {}
        token = "mock_token"
        result = api_claims(event, context, token)
        assert result["username"] == "mock_owner"
        assert result["account"] == "mock_account_id"
        assert result["allowed_access"] == ["file_upload", "share"]
        assert result["rate_limit"] == {"period": "Hourly", "rate": 100}
        assert result["api_key_id"] == "user/ownerKey/mock_owner"

    finally:
        # Restore original state
        pycommon.authz._access_types = original_access_types


@patch("pycommon.authz.boto3.resource")
@patch("pycommon.authz.os.getenv")
@patch("pycommon.authz.TokenV1")
def test_api_claims_success_with_v1_token(mock_token_v1, mock_getenv, mock_boto3):
    """Test api_claims with new amp-v1- token format"""
    import pycommon.authz

    # Store original access types to restore later
    original_access_types = pycommon.authz._access_types.copy()

    try:
        # Set access types to include the ones used in this test
        pycommon.authz._access_types = ["full_access", "file_upload", "share"]

        # Mock TokenV1 to return a hash
        mock_token_v1_instance = MagicMock()
        mock_token_v1_instance.key = "hashed_token_value"
        mock_token_v1.return_value = mock_token_v1_instance

        mock_getenv.side_effect = lambda key: {
            "API_KEYS_DYNAMODB_TABLE": "mock_api_keys_table",
            "COST_CALCULATIONS_DYNAMO_TABLE": "mock_cost_calculations_table",
        }.get(key)
        mock_api_keys_table = MagicMock()
        mock_api_keys_table.query.return_value = {
            "Items": [
                {  # This should match the hash from TokenV1
                    "apiKey": "hashed_token_value",
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
        mock_cost_calculations_table = MagicMock()
        mock_cost_calculations_table.query.return_value = {
            "Items": [
                {
                    "id": "mock_owner",
                    "hourlyCost": [0] * 24,  # Simulate no cost for all hours
                }
            ]
        }
        mock_boto3.return_value.Table.side_effect = lambda table_name: {
            "mock_api_keys_table": mock_api_keys_table,
            "mock_cost_calculations_table": mock_cost_calculations_table,
        }[table_name]
        event = {}
        context = {}
        token = "amp-v1-some_token_value"  # New format token
        result = api_claims(event, context, token)

        # Verify TokenV1 was called with the original token
        mock_token_v1.assert_called_once_with("amp-v1-some_token_value")

        # Verify the query used the hashed value
        mock_api_keys_table.query.assert_called_once_with(
            IndexName="ApiKeyIndex",
            KeyConditionExpression="apiKey = :apiKeyVal",
            ExpressionAttributeValues={":apiKeyVal": "hashed_token_value"},
        )

        assert result["username"] == "mock_owner"
        assert result["account"] == "mock_account_id"
        assert result["allowed_access"] == ["file_upload", "share"]
        assert result["rate_limit"] == {"period": "Hourly", "rate": 100}
        assert result["api_key_id"] == "user/ownerKey/mock_owner"

    finally:
        # Restore original state
        pycommon.authz._access_types = original_access_types


@patch("pycommon.authz.boto3.resource")
@patch("pycommon.authz.os.getenv")
def test_api_claims_key_not_found(mock_getenv, mock_boto3):
    mock_getenv.side_effect = lambda key: {
        "API_KEYS_DYNAMODB_TABLE": "mock_api_keys_table",
    }.get(key)

    mock_table = MagicMock()
    mock_table.query.return_value = {"Items": []}
    mock_boto3.return_value.Table.return_value = mock_table

    with pytest.raises(LookupError, match="API key not found."):
        api_claims({}, {}, "mock_token")


@patch("pycommon.authz.boto3.resource")
@patch("pycommon.authz.os.getenv")
def test_api_claims_inactive_key(mock_getenv, mock_boto3):
    mock_getenv.side_effect = lambda key: {
        "API_KEYS_DYNAMODB_TABLE": "mock_api_keys_table",
    }.get(key)
    mock_table = MagicMock()
    mock_table.query.return_value = {
        "Items": [{"apiKey": "mock_token", "active": False}]
    }
    mock_boto3.return_value.Table.return_value = mock_table
    with pytest.raises(PermissionError, match="API key is inactive."):
        api_claims({}, {}, "mock_token")


@patch("pycommon.authz.boto3.resource")
@patch("pycommon.authz.os.getenv")
def test_api_claims_expired_key(mock_getenv, mock_boto3):
    mock_getenv.side_effect = lambda key: {
        "API_KEYS_DYNAMODB_TABLE": "mock_api_keys_table",
    }.get(key)
    mock_table = MagicMock()
    mock_table.query.return_value = {
        "Items": [
            {"apiKey": "mock_token", "active": True, "expirationDate": "2000-01-01"}
        ]
    }
    mock_boto3.return_value.Table.return_value = mock_table
    with pytest.raises(PermissionError, match="API key has expired."):
        api_claims({}, {}, "mock_token")


@patch("pycommon.authz.boto3.resource")
@patch("pycommon.authz.os.getenv")
def test_api_claims_no_access_rights(mock_getenv, mock_boto3):
    mock_getenv.side_effect = lambda key: {
        "API_KEYS_DYNAMODB_TABLE": "mock_api_keys_table",
    }.get(key)
    mock_table = MagicMock()
    mock_table.query.return_value = {
        "Items": [{"apiKey": "mock_token", "active": True, "accessTypes": []}]
    }
    mock_boto3.return_value.Table.return_value = mock_table
    with pytest.raises(
        PermissionError,
        match="API key does not have access to the required functionality.",
    ):
        api_claims({}, {}, "mock_token")


def test_determine_api_user_owner():
    data = {"api_owner_id": "user/ownerKey/mock_owner", "owner": "mock_owner"}
    assert _determine_api_user(data) == "mock_owner"


def test_determine_api_user_delegate():
    data = {
        "api_owner_id": "user/delegateKey/mock_delegate",
        "delegate": "mock_delegate",
    }
    assert _determine_api_user(data) == "mock_delegate"


def test_determine_api_user_system():
    data = {"api_owner_id": "user/systemKey/mock_system", "systemId": "mock_system"}
    assert _determine_api_user(data) == "mock_system"


def test_determine_api_user_invalid_key_type():
    data = {"api_owner_id": "user/unknownKey/mock_user", "owner": "mock_owner"}
    with pytest.raises(
        UnknownApiUserException, match="Invalid or unrecognized key type."
    ):
        _determine_api_user(data)


def test_determine_api_user_unknown_key_type():
    """Test the case where an unknown key type is encountered, triggering the print
    statement."""
    data = {"api_owner_id": "user/invalidKey/mock_user", "owner": "mock_owner"}
    with pytest.raises(
        UnknownApiUserException, match="Invalid or unrecognized key type."
    ):
        _determine_api_user(data)


def test_determine_api_user_missing_api_owner_id():
    data = {"owner": "mock_owner"}
    with pytest.raises(
        UnknownApiUserException, match="Invalid or unrecognized key type."
    ):
        _determine_api_user(data)


def test_determine_api_user_missing_user_field_owner():
    data = {"api_owner_id": "user/ownerKey/mock_owner"}
    with pytest.raises(
        UnknownApiUserException,
        match="Missing or invalid user identifier for key type 'owner'.",
    ):
        _determine_api_user(data)


def test_determine_api_user_missing_user_field_delegate():
    data = {"api_owner_id": "user/delegateKey/mock_delegate"}
    with pytest.raises(
        UnknownApiUserException,
        match="Missing or invalid user identifier for key type 'delegate'.",
    ):
        _determine_api_user(data)


def test_determine_api_user_missing_user_field_system():
    data = {"api_owner_id": "user/systemKey/mock_system"}
    with pytest.raises(
        UnknownApiUserException,
        match="Missing or invalid user identifier for key type 'system'.",
    ):
        _determine_api_user(data)


def test_determine_api_user_user_field_wrong_type():
    data = {"api_owner_id": "user/ownerKey/mock_owner", "owner": 12345}  # not a string
    with pytest.raises(
        UnknownApiUserException,
        match="Missing or invalid user identifier for key type 'owner'.",
    ):
        _determine_api_user(data)


def test_validate_data_success():
    validator_rules = {
        "validators": {
            "/foo": {
                "bar": {
                    "type": "object",
                    "properties": {"x": {"type": "integer"}},
                    "required": ["x"],
                }
            }
        }
    }
    _validate_data("/foo", "bar", {"data": {"x": 1}}, False, validator_rules)


def test_validate_data_no_validator():
    with pytest.raises(ValidationError, match="No validator found for the operation"):
        _validate_data("/foo", "bar", {"data": {"x": 1}}, False, {})


def test_validate_data_invalid_path():
    with pytest.raises(ValidationError, match="Invalid data or path"):
        _validate_data("/foo", "bar", {"data": {"x": 1}}, False, rules)


def test_validate_data_invalid_schema():
    validator_rules = {
        "validators": {
            "/foo": {
                "bar": {
                    "type": "object",
                    "properties": {"x": {"type": "unknown_type"}},
                }
            }
        }
    }
    with pytest.raises(ValidationError, match="Invalid schema"):
        _validate_data("/foo", "bar", {"data": {"x": 1}}, False, validator_rules)


def test_validate_data_invalid_data():
    validator_rules = {
        "validators": {
            "/foo": {
                "bar": {
                    "type": "object",
                    "properties": {"x": {"type": "integer"}},
                    "required": ["x"],
                }
            }
        }
    }
    with pytest.raises(ValidationError, match="Invalid data"):
        _validate_data("/foo", "bar", {"data": {"y": 2}}, False, validator_rules)


def test_validate_data_path_not_found():
    with pytest.raises(ValidationError, match="Invalid data or path"):
        _validate_data("/foo", "bar", {"data": {"x": 1}}, False, rules)


def test_validate_data_empty_schema():
    """Test validation with empty schema - should skip validation and pass"""
    # This tests the uncovered branch where schema == {}
    # Using the 'read' operation which has an empty schema in the rules
    try:
        _validate_data("/state/share", "read", {"data": {"x": 1}}, False, rules)
        # Should not raise any exception since schema is empty
    except Exception as e:
        pytest.fail(f"Validation with empty schema should not raise exception: {e}")


def test_parse_token_success():
    event = {"headers": {"Authorization": "Bearer abc123"}}
    assert _parse_token(event) == "abc123"


def test_parse_token_wrong_scheme():
    event = {"headers": {"Authorization": "Basic abc123"}}
    with pytest.raises(HTTPUnauthorized, match="No Access Token Found"):
        _parse_token(event)


def test_parse_token_missing_header():
    event = {"headers": {}}
    with pytest.raises(HTTPUnauthorized, match="No Access Token Found"):
        _parse_token(event)


def test_parse_token_malformed_header():
    event = {"headers": {"Authorization": "Bearer"}}
    with pytest.raises(HTTPUnauthorized, match="No Access Token Found"):
        _parse_token(event)


def test_parse_token_case_insensitive():
    event = {"headers": {"authorization": "Bearer abc123"}}
    assert _parse_token(event) == "abc123"


def test_parse_token_extra_spaces():
    event = {"headers": {"Authorization": "Bearer   "}}
    with pytest.raises(HTTPUnauthorized):
        _parse_token(event)


@patch("pycommon.authz._parse_token")
@patch("pycommon.authz.api_claims")
@patch("pycommon.authz._parse_and_validate")
@patch("pycommon.authz.get_claims")
@patch("pycommon.authz.os.environ.get")
@patch("pycommon.authz.requests.get")
def test_validated_api_access_success(
    mock_requests_get,
    mock_get_env,
    mock_get_claims,
    mock_parse_and_validate,
    mock_api_claims,
    mock_parse_token,
):
    mock_get_env.side_effect = lambda key, default=None: {
        "OAUTH_ISSUER_BASE_URL": "http://mock-issuer.com",
        "OAUTH_AUDIENCE": "mock-audience",
        "ACCOUNTS_DYNAMO_TABLE": "mock-accounts-table",
    }.get(key, default)
    mock_requests_get.return_value = MagicMock(
        ok=True,
        json=MagicMock(return_value={"keys": [{"kid": "mock_kid", "key": "mock_key"}]}),
    )
    mock_parse_token.return_value = "amp-token"
    mock_api_claims.return_value = {
        "username": "api_user",
        "account": "acc",
        "allowed_access": ["full_access"],
        "rate_limit": {},
        "api_key_id": "user/ownerKey/api_user",
    }
    mock_get_claims.return_value = {
        "username": "api_user",
        "account": "acc",
        "allowed_access": ["full_access"],
        "rate_limit": {},
    }
    mock_parse_and_validate.return_value = ["path", {"foo": "bar"}]

    # Set up global state for validation
    setup_validated({}, always_allow_permission_checker)

    @validated("op", True)
    def test_handler_api_access(event, context, user, name, data):
        return {"ok": True}

    event = {
        "headers": {"Authorization": "Bearer api-token"},
        "body": "{}",
        "path": "path",
    }
    context = {}
    resp = test_handler_api_access(event, context)
    assert resp["statusCode"] == 200
    assert resp["body"] == '{"ok": true}'


@patch("pycommon.authz._parse_token")
@patch("pycommon.authz.get_claims")
@patch("pycommon.authz._parse_and_validate")
def test_validated_user_access_success(
    mock_parse_and_validate, mock_get_claims, mock_parse_token
):
    mock_parse_token.return_value = "user-token"
    mock_get_claims.return_value = {
        "username": "user",
        "account": "acc",
        "allowed_access": ["full_access"],
        "rate_limit": {},
    }
    mock_parse_and_validate.return_value = ["path", {"foo": "bar"}]

    # Set up global state for validation
    setup_validated({}, always_allow_permission_checker)

    @validated("op", True)
    def test_handler_user_access(event, context, user, name, data):
        return {"ok": True}

    event = {
        "headers": {"Authorization": "Bearer user-token"},
        "body": "{}",
        "path": "path",
    }
    context = {}
    resp = test_handler_user_access(event, context)
    assert resp["statusCode"] == 200
    assert resp["body"] == '{"ok": true}'


@patch("pycommon.authz._parse_token")
@patch("pycommon.authz.get_claims")
@patch("pycommon.authz._parse_and_validate")
def test_validated_user_not_found(
    mock_parse_and_validate, mock_get_claims, mock_parse_token
):
    mock_parse_token.return_value = "user-token"
    mock_get_claims.return_value = {
        "username": None,
        "account": "acc",
        "allowed_access": ["full_access"],
        "rate_limit": {},
    }
    mock_parse_and_validate.return_value = ["path", {"foo": "bar"}]

    # Set up global state for validation
    setup_validated({}, always_allow_permission_checker)

    @validated("op", True)
    def test_handler_user_not_found(event, context, user, name, data):
        return {"ok": True}  # pragma: no cover

    event = {
        "headers": {"Authorization": "Bearer user-token"},
        "body": "{}",
        "path": "path",
    }
    context = {}
    resp = test_handler_user_not_found(event, context)
    assert resp["statusCode"] == 401
    assert "User not found" in json.loads(resp["body"])["error"]


@patch("pycommon.authz._parse_token")
@patch("pycommon.authz.get_claims")
@patch("pycommon.authz._parse_and_validate")
def test_validated_http_exception(
    mock_parse_and_validate, mock_get_claims, mock_parse_token
):
    mock_parse_token.return_value = "user-token"
    mock_get_claims.return_value = {
        "username": "user",
        "account": "acc",
        "allowed_access": ["full_access"],
        "rate_limit": {},
    }
    mock_parse_and_validate.side_effect = HTTPBadRequest("bad input")

    # Set up global state for validation
    setup_validated({}, always_allow_permission_checker)

    @validated("op", True)
    def test_handler_http_exception(event, context, user, name, data):
        return {"ok": True}  # pragma: no cover

    event = {
        "headers": {"Authorization": "Bearer user-token"},
        "body": "{}",
        "path": "path",
    }
    context = {}
    resp = test_handler_http_exception(event, context)
    assert resp["statusCode"] == 400
    assert "bad input" in json.loads(resp["body"])["error"]


@patch("pycommon.authz._parse_token")
@patch("pycommon.authz.get_claims")
@patch("pycommon.authz._parse_and_validate")
def test_validated_unexpected_exception(
    mock_parse_and_validate, mock_get_claims, mock_parse_token
):
    """Test the validated decorator handling unexpected exceptions
    (not HTTPException)."""
    mock_parse_token.return_value = "user-token"
    mock_get_claims.return_value = {
        "username": "user",
        "account": "acc",
        "allowed_access": ["full_access"],
        "rate_limit": {},
    }
    mock_parse_and_validate.return_value = ["path", {"foo": "bar"}]

    # Set up global state for validation
    setup_validated({}, always_allow_permission_checker)

    @validated("op", True)
    def test_handler_unexpected_exception(event, context, user, name, data):
        # Raise a non-HTTPException to trigger the Exception handler
        raise ValueError("Unexpected error occurred")

    event = {
        "headers": {"Authorization": "Bearer user-token"},
        "body": "{}",
        "path": "path",
    }
    context = {}

    # This should re-raise the ValueError after printing debug info
    with pytest.raises(ValueError, match="Unexpected error occurred"):
        test_handler_unexpected_exception(event, context)


@patch("pycommon.authz.boto3.resource")
@patch("pycommon.authz.os.getenv")
def test_api_claims_rate_limit_exceeded(mock_getenv, mock_boto3):
    import pycommon.authz

    # Store original access types to restore later
    original_access_types = pycommon.authz._access_types.copy()

    try:
        # Set access types to include the ones used in this test
        pycommon.authz._access_types = ["full_access", "file_upload", "share"]

        mock_getenv.side_effect = lambda key: {
            "API_KEYS_DYNAMODB_TABLE": "mock_api_keys_table",
            "COST_CALCULATIONS_DYNAMO_TABLE": "mock_cost_calculations_table",
        }.get(key)
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
        with patch(
            "pycommon.authz.is_rate_limited", return_value=(True, "rate limit exceeded")
        ):
            with pytest.raises(HTTPUnauthorized, match="rate limit exceeded"):
                api_claims({}, {}, "mock_token")

    finally:
        # Restore original state
        pycommon.authz._access_types = original_access_types


@patch("pycommon.authz.boto3.resource")
@patch("pycommon.authz.os.getenv")
def test_is_rate_limited_unlimited_period(mock_getenv, mock_boto3):
    mock_getenv.return_value = "mock_cost_calc_table"
    assert is_rate_limited("user", {"period": "Unlimited", "rate": 100}) == (
        False,
        "No rate limit set",
    )


@patch("pycommon.authz.boto3.resource")
@patch("pycommon.authz.os.getenv")
def test_is_rate_limited_no_period(mock_getenv, mock_boto3):
    mock_getenv.return_value = "mock_cost_calc_table"
    assert is_rate_limited("user", {"rate": 100}) == (
        False,
        "Rate limit period is not specified in the rate_limit data",
    )


@patch("pycommon.authz.boto3.resource")
@patch("pycommon.authz.os.getenv")
def test_is_rate_limited_no_items(mock_getenv, mock_boto3):
    mock_getenv.return_value = "mock_cost_calc_table"
    mock_table = MagicMock()
    mock_table.query.return_value = {"Items": []}
    mock_boto3.return_value.Table.return_value = mock_table
    assert is_rate_limited("user", {"period": "Hourly", "rate": 100}) == (
        False,
        "Table entry does not exist. Cannot verify if rate limited.",
    )


@patch("pycommon.authz.boto3.resource")
@patch("pycommon.authz.os.getenv")
def test_is_rate_limited_missing_col_name(mock_getenv, mock_boto3):
    mock_getenv.return_value = "mock_cost_calc_table"
    mock_table = MagicMock()
    mock_table.query.return_value = {"Items": [{"id": "user"}]}
    mock_boto3.return_value.Table.return_value = mock_table
    assert is_rate_limited("user", {"period": "Hourly", "rate": 100}) == (
        False,
        "Column hourlyCost not found in rate data",
    )


@patch("pycommon.authz.boto3.resource")
@patch("pycommon.authz.os.getenv")
def test_is_rate_limited_hourly_cost_missing_or_malformed(mock_getenv, mock_boto3):
    mock_getenv.return_value = "mock_cost_calc_table"
    mock_table = MagicMock()
    mock_table.query.return_value = {"Items": [{"hourlyCost": None}]}
    mock_boto3.return_value.Table.return_value = mock_table
    assert is_rate_limited("user", {"period": "Hourly", "rate": 100}) == (
        False,
        "Column hourlyCost not found in rate data",
    )
    mock_table.query.return_value = {"Items": [{"hourlyCost": []}]}
    assert is_rate_limited("user", {"period": "Hourly", "rate": 100}) == (
        False,
        "Hourly cost data is missing or malformed.",
    )


@patch("pycommon.authz.boto3.resource")
@patch("pycommon.authz.os.getenv")
def test_is_rate_limited_hourly_cost_exceeded(mock_getenv, mock_boto3):
    mock_getenv.return_value = "mock_cost_calc_table"
    mock_table = MagicMock()
    mock_table.query.return_value = {"Items": [{"hourlyCost": [10] + [0] * 23}]}
    mock_boto3.return_value.Table.return_value = mock_table
    with patch("pycommon.authz.datetime") as mock_datetime:
        mock_datetime.now.return_value.hour = 0
        assert is_rate_limited("user", {"period": "Hourly", "rate": 5}) == (
            True,
            "rate limit exceeded ($5.00/Hourly)",
        )


@patch("pycommon.authz.boto3.resource")
@patch("pycommon.authz.os.getenv")
def test_is_rate_limited_hourly_cost_not_exceeded(mock_getenv, mock_boto3):
    mock_getenv.return_value = "mock_cost_calc_table"
    mock_table = MagicMock()
    mock_table.query.return_value = {"Items": [{"hourlyCost": [2] + [0] * 23}]}
    mock_boto3.return_value.Table.return_value = mock_table
    with patch("pycommon.authz.datetime") as mock_datetime:
        mock_datetime.now.return_value.hour = 0
        assert is_rate_limited("user", {"period": "Hourly", "rate": 5}) == (
            False,
            "Rate limit not exceeded",
        )


@patch("pycommon.authz.boto3.resource")
@patch("pycommon.authz.os.getenv")
def test_is_rate_limited_daily_cost_exceeded(mock_getenv, mock_boto3):
    mock_getenv.return_value = "mock_cost_calc_table"
    mock_table = MagicMock()
    mock_table.query.return_value = {"Items": [{"dailyCost": 15}]}
    mock_boto3.return_value.Table.return_value = mock_table
    assert is_rate_limited("user", {"period": "Daily", "rate": 10}) == (
        True,
        "rate limit exceeded ($10.00/Daily)",
    )


@patch("pycommon.authz.boto3.resource")
@patch("pycommon.authz.os.getenv")
def test_is_rate_limited_daily_cost_not_exceeded(mock_getenv, mock_boto3):
    mock_getenv.return_value = "mock_cost_calc_table"
    mock_table = MagicMock()
    mock_table.query.return_value = {"Items": [{"dailyCost": 5}]}
    mock_boto3.return_value.Table.return_value = mock_table
    assert is_rate_limited("user", {"period": "Daily", "rate": 10}) == (
        False,
        "Rate limit not exceeded",
    )


@patch("pycommon.authz.boto3.resource")
@patch("pycommon.authz.os.getenv")
def test_is_rate_limited_missing_rate(mock_getenv, mock_boto3):
    mock_getenv.return_value = "mock_cost_calc_table"
    mock_table = MagicMock()
    mock_table.query.return_value = {"Items": [{"dailyCost": 5}]}
    mock_boto3.return_value.Table.return_value = mock_table
    assert is_rate_limited("user", {"period": "Daily"}) == (
        False,
        "Rate value missing in rate_limit.",
    )


@patch("pycommon.authz.boto3.resource")
@patch("pycommon.authz.os.getenv")
def test_is_rate_limited_boto3_error(mock_getenv, mock_boto3):
    mock_getenv.return_value = "mock_cost_calc_table"
    mock_table = MagicMock()
    mock_table.query.side_effect = Exception("boto3 error")
    mock_boto3.return_value.Table.return_value = mock_table
    assert is_rate_limited("user", {"period": "Daily", "rate": 10}) == (
        False,
        "Unexpected error during rate limit check",
    )


@patch("pycommon.authz.boto3.resource")
@patch("pycommon.authz.os.getenv")
def test_is_rate_limited_table_entry_missing(mock_getenv, mock_boto3):
    mock_getenv.return_value = "mock_cost_table"
    mock_table = MagicMock()
    mock_table.query.return_value = {"Items": []}
    mock_boto3.return_value.Table.return_value = mock_table
    rate_limit = {"period": "Hourly", "rate": 100}
    limited, msg = is_rate_limited("mock_user", rate_limit)
    assert limited is False
    assert "Table entry does not exist" in msg


@patch("pycommon.authz.boto3.resource")
@patch("pycommon.authz.os.getenv")
def test_is_rate_limited_column_missing(mock_getenv, mock_boto3):
    mock_getenv.return_value = "mock_cost_table"
    mock_table = MagicMock()
    mock_table.query.return_value = {"Items": [{"id": "mock_user"}]}
    mock_boto3.return_value.Table.return_value = mock_table
    rate_limit = {"period": "Hourly", "rate": 100}
    limited, msg = is_rate_limited("mock_user", rate_limit)
    assert limited is False
    assert "Column hourlyCost not found" in msg


@patch("pycommon.authz.boto3.resource")
@patch("pycommon.authz.os.getenv")
def test_is_rate_limited_hourly_cost_malformed(mock_getenv, mock_boto3):
    mock_getenv.return_value = "mock_cost_table"
    mock_table = MagicMock()
    mock_table.query.return_value = {"Items": [{"id": "mock_user", "hourlyCost": None}]}
    mock_boto3.return_value.Table.return_value = mock_table
    rate_limit = {"period": "Hourly", "rate": 100}
    limited, msg = is_rate_limited("mock_user", rate_limit)
    assert limited is False
    assert "Column hourlyCost not found in rate data" in msg


@patch("pycommon.authz.boto3.resource")
@patch("pycommon.authz.os.getenv")
def test_is_rate_limited_rate_value_missing(mock_getenv, mock_boto3):
    mock_getenv.return_value = "mock_cost_table"
    mock_table = MagicMock()
    mock_table.query.return_value = {
        "Items": [{"id": "mock_user", "hourlyCost": [0] * 24}]
    }
    mock_boto3.return_value.Table.return_value = mock_table
    rate_limit = {"period": "Hourly"}
    limited, msg = is_rate_limited("mock_user", rate_limit)
    assert limited is False
    assert "Rate value missing in rate_limit." in msg


@patch("pycommon.authz.boto3.resource")
@patch("pycommon.authz.os.getenv")
def test_is_rate_limited_exceeded(mock_getenv, mock_boto3):
    mock_getenv.return_value = "mock_cost_table"
    mock_table = MagicMock()
    hourly_cost = [101] + [0] * 23
    mock_table.query.return_value = {
        "Items": [{"id": "mock_user", "hourlyCost": hourly_cost}]
    }
    mock_boto3.return_value.Table.return_value = mock_table
    rate_limit = {"period": "Hourly", "rate": 100}
    with patch("pycommon.authz.datetime") as mock_datetime:
        mock_datetime.now.return_value.hour = 0
        limited, msg = is_rate_limited("mock_user", rate_limit)
        assert limited is True
        assert "rate limit exceeded" in msg


@patch("pycommon.authz.boto3.resource")
@patch("pycommon.authz.os.getenv")
def test_is_rate_limited_not_exceeded(mock_getenv, mock_boto3):
    mock_getenv.return_value = "mock_cost_table"
    mock_table = MagicMock()
    hourly_cost = [10] + [0] * 23
    mock_table.query.return_value = {
        "Items": [{"id": "mock_user", "hourlyCost": hourly_cost}]
    }
    mock_boto3.return_value.Table.return_value = mock_table
    rate_limit = {"period": "Hourly", "rate": 100}
    with patch("pycommon.authz.datetime") as mock_datetime:
        mock_datetime.now.return_value.hour = 0
        limited, msg = is_rate_limited("mock_user", rate_limit)
        assert limited is False
        assert "Rate limit not exceeded" in msg


@patch("pycommon.authz.boto3.resource")
@patch("pycommon.authz.os.getenv")
def test_is_rate_limited_boto3_exception(mock_getenv, mock_boto3):
    mock_getenv.return_value = "mock_cost_table"
    mock_table = MagicMock()
    mock_table.query.side_effect = boto3.exceptions.Boto3Error()
    mock_boto3.return_value.Table.return_value = mock_table
    rate_limit = {"period": "Hourly", "rate": 100}
    limited, msg = is_rate_limited("mock_user", rate_limit)
    assert limited is False
    assert "Error accessing DynamoDB" in msg


@patch("pycommon.authz.boto3.resource")
@patch("pycommon.authz.os.getenv")
def test_is_rate_limited_unexpected_exception(mock_getenv, mock_boto3):
    mock_getenv.return_value = "mock_cost_table"
    mock_table = MagicMock()
    mock_table.query.side_effect = Exception("unexpected")
    mock_boto3.return_value.Table.return_value = mock_table
    rate_limit = {"period": "Hourly", "rate": 100}
    limited, msg = is_rate_limited("mock_user", rate_limit)
    assert limited is False
    assert "Unexpected error during rate limit" in msg


@patch("pycommon.authz.requests.get")
@patch("pycommon.authz.os.environ.get")
def test_get_claims_missing_env_vars(mock_get_env, _):
    required_vars = ["OAUTH_ISSUER_BASE_URL", "OAUTH_AUDIENCE", "ACCOUNTS_DYNAMO_TABLE"]
    mock_get_env.side_effect = lambda key, default=None: (
        None if key == missing else "value"
    )
    for missing in required_vars:

        with pytest.raises(EnvVarError) as exc:
            get_claims("sometoken")
        assert f"Env Var: '{missing}' is not set" in str(exc.value)


@patch("pycommon.authz.requests.get")
@patch("pycommon.authz.os.environ.get")
def test_get_claims_jwks_invalid_json(mock_get_env, mock_requests_get):
    mock_get_env.side_effect = lambda key, default=None: (
        "issuer"
        if key == "OAUTH_ISSUER_BASE_URL"
        else "aud" if key == "OAUTH_AUDIENCE" else "table"
    )
    mock_requests_get.return_value = MagicMock(
        ok=True,
        json=MagicMock(side_effect=json.JSONDecodeError("Expecting value", "", 0)),
    )
    with pytest.raises(ClaimException, match="Invalid JWKS response"):
        get_claims("sometoken")


@patch("pycommon.authz.requests.get")
@patch("pycommon.authz.os.environ.get")
@patch("pycommon.authz.jwt.get_unverified_header")
@patch("pycommon.authz.jwt.decode")
def test_get_claims_jwt_decode_error(
    mock_decode, mock_get_header, mock_get_env, mock_requests_get
):
    mock_get_env.side_effect = lambda key, default=None: (
        "issuer"
        if key == "OAUTH_ISSUER_BASE_URL"
        else "aud" if key == "OAUTH_AUDIENCE" else "table"
    )
    mock_requests_get.return_value = MagicMock(
        ok=True,
        json=MagicMock(return_value={"keys": [{"kid": "kid1"}]}),
    )
    mock_get_header.return_value = {"kid": "kid1"}
    mock_decode.side_effect = JWTError("decode error")
    with pytest.raises(ClaimException, match="Invalid JWT token"):
        get_claims("sometoken")


@patch("pycommon.authz.requests.get")
@patch("pycommon.authz.os.environ.get")
@patch("pycommon.authz.jwt.get_unverified_header")
@patch("pycommon.authz.jwt.decode")
def test_get_claims_jwt_expired_sigs_error(
    mock_decode, mock_get_header, mock_get_env, mock_requests_get
):
    mock_get_env.side_effect = lambda key, default=None: (
        "issuer"
        if key == "OAUTH_ISSUER_BASE_URL"
        else "aud" if key == "OAUTH_AUDIENCE" else "table"
    )
    mock_requests_get.return_value = MagicMock(
        ok=True,
        json=MagicMock(return_value={"keys": [{"kid": "kid1"}]}),
    )
    mock_get_header.return_value = {"kid": "kid1"}
    mock_decode.side_effect = ExpiredSignatureError("JWT token has expired")
    with pytest.raises(ClaimException, match="JWT token has expired"):
        get_claims("sometoken")


@patch("pycommon.authz.requests.get")
@patch("pycommon.authz.os.environ.get")
@patch("pycommon.authz.jwt.get_unverified_header")
@patch("pycommon.authz.jwt.decode")
def test_get_claims_jwt_expired_claims_error(
    mock_decode, mock_get_header, mock_get_env, mock_requests_get
):
    mock_get_env.side_effect = lambda key, default=None: (
        "issuer"
        if key == "OAUTH_ISSUER_BASE_URL"
        else "aud" if key == "OAUTH_AUDIENCE" else "table"
    )
    mock_requests_get.return_value = MagicMock(
        ok=True,
        json=MagicMock(return_value={"keys": [{"kid": "kid1"}]}),
    )
    mock_get_header.return_value = {"kid": "kid1"}
    mock_decode.side_effect = JWTClaimsError("Invalid JWT Claims")
    with pytest.raises(ClaimException, match="Invalid JWT claims"):
        get_claims("sometoken")


def test_setup_validated():
    """Test the setup_validated function sets
    both global variables correctly.
    """
    test_rules = {"test": "rules"}

    def test_checker(u, t, o, d):
        return lambda u, d: True

    setup_validated(test_rules, test_checker)

    # Import the globals to check they were set
    import pycommon.authz

    assert pycommon.authz._validate_rules == test_rules
    assert pycommon.authz._permission_checker == test_checker


def test_set_validate_rules():
    """Test the set_validate_rules function sets the global variable correctly."""
    test_rules = {"individual": "rules"}

    set_validate_rules(test_rules)

    # Import the globals to check they were set
    import pycommon.authz

    assert pycommon.authz._validate_rules == test_rules


def test_set_permission_checker():
    """Test the set_permission_checker function sets the global variable correctly."""

    def test_checker(u, t, o, d):
        return lambda u, d: False

    set_permission_checker(test_checker)

    # Import the globals to check they were set
    import pycommon.authz

    assert pycommon.authz._permission_checker == test_checker


def test_add_api_access_types():
    """Test the add_api_access_types function adds access types to the global list."""
    import pycommon.authz

    # Store original access types to restore later
    original_access_types = pycommon.authz._access_types.copy()

    try:
        # Reset to known state
        pycommon.authz._access_types = ["full_access"]

        # Add new access types
        add_api_access_types(["chat", "file_upload"])

        # Check that the access types were added
        assert "full_access" in pycommon.authz._access_types
        assert "chat" in pycommon.authz._access_types
        assert "file_upload" in pycommon.authz._access_types
        assert len(pycommon.authz._access_types) == 3

    finally:
        # Restore original state
        pycommon.authz._access_types = original_access_types


@patch("pycommon.authz.boto3.resource")
@patch("pycommon.authz.os.getenv")
def test_api_claims_empty_access_types(mock_getenv, mock_boto3):
    """Test api_claims when _access_types is empty - should raise PermissionError."""
    import pycommon.authz

    # Store original access types to restore later
    original_access_types = pycommon.authz._access_types.copy()

    try:
        # Set _access_types to empty list
        pycommon.authz._access_types = []

        mock_getenv.side_effect = lambda key: {
            "API_KEYS_DYNAMODB_TABLE": "mock_api_keys_table",
        }.get(key)

        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [
                {
                    "apiKey": "mock_token",
                    "active": True,
                    "accessTypes": ["chat", "file_upload"],  # API key has access types
                    "account": {"id": "mock_account_id"},
                    "api_owner_id": "user/ownerKey/mock_owner",
                    "owner": "mock_owner",
                }
            ]
        }
        mock_boto3.return_value.Table.return_value = mock_table

        # Should raise PermissionError because _access_types is empty
        with pytest.raises(
            PermissionError,
            match="API key does not have access to the required functionality.",
        ):
            api_claims({}, {}, "mock_token")

    finally:
        # Restore original state
        pycommon.authz._access_types = original_access_types


@patch("pycommon.authz.boto3.resource")
@patch("pycommon.authz.os.getenv")
def test_api_claims_partial_access_match(mock_getenv, mock_boto3):
    """Test api_claims when API key has some matching access types."""
    import pycommon.authz

    # Store original access types to restore later
    original_access_types = pycommon.authz._access_types.copy()

    try:
        # Set specific access types required
        pycommon.authz._access_types = ["chat", "assistants"]

        mock_getenv.side_effect = lambda key: {
            "API_KEYS_DYNAMODB_TABLE": "mock_api_keys_table",
            "COST_CALCULATIONS_DYNAMO_TABLE": "mock_cost_calculations_table",
        }.get(key)

        mock_api_keys_table = MagicMock()
        mock_api_keys_table.query.return_value = {
            "Items": [
                {
                    "apiKey": "mock_token",
                    "active": True,
                    "expirationDate": "2099-12-31",
                    "accessTypes": [
                        "chat",
                        "file_upload",
                    ],  # Has "chat" but not "assistants"
                    "account": {"id": "mock_account_id"},
                    "api_owner_id": "user/ownerKey/mock_owner",
                    "rateLimit": {"rate": 100, "period": "Hourly"},
                    "owner": "mock_owner",
                }
            ]
        }

        mock_cost_calculations_table = MagicMock()
        mock_cost_calculations_table.query.return_value = {
            "Items": [
                {
                    "id": "mock_owner",
                    "hourlyCost": [0] * 24,  # Simulate no cost for all hours
                }
            ]
        }

        mock_boto3.return_value.Table.side_effect = lambda table_name: {
            "mock_api_keys_table": mock_api_keys_table,
            "mock_cost_calculations_table": mock_cost_calculations_table,
        }[table_name]

        # Should succeed because API key has "chat" which matches
        # one of the required access types
        result = api_claims({}, {}, "mock_token")
        assert result["username"] == "mock_owner"
        assert result["account"] == "mock_account_id"
        assert result["allowed_access"] == ["chat", "file_upload"]

    finally:
        # Restore original state
        pycommon.authz._access_types = original_access_types


@patch("pycommon.authz.boto3.resource")
@patch("pycommon.authz.os.getenv")
def test_api_claims_no_matching_access_types(mock_getenv, mock_boto3):
    """Test api_claims when API key has no matching access types."""
    import pycommon.authz

    # Store original access types to restore later
    original_access_types = pycommon.authz._access_types.copy()

    try:
        # Set specific access types required
        pycommon.authz._access_types = ["assistants", "dual_embedding"]

        mock_getenv.side_effect = lambda key: {
            "API_KEYS_DYNAMODB_TABLE": "mock_api_keys_table",
        }.get(key)

        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [
                {
                    "apiKey": "mock_token",
                    "active": True,
                    "accessTypes": ["chat", "file_upload"],  # No matching access types
                    "account": {"id": "mock_account_id"},
                    "api_owner_id": "user/ownerKey/mock_owner",
                    "owner": "mock_owner",
                }
            ]
        }
        mock_boto3.return_value.Table.return_value = mock_table

        # Should raise PermissionError because no access types match
        with pytest.raises(
            PermissionError,
            match="API key does not have access to the required functionality.",
        ):
            api_claims({}, {}, "mock_token")

    finally:
        # Restore original state
        pycommon.authz._access_types = original_access_types
