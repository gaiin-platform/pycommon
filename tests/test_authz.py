import json
from unittest.mock import MagicMock, patch

from requests import ConnectionError, HTTPError

from authz import verify_user_as_admin


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
    mock_get_env.assert_called_once_with("API_BASE_URL")
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


@patch("authz.os.environ.get")
def test_verify_user_as_admin_missing_env(mock_get_env):
    # Mock missing environment variable
    mock_get_env.return_value = None

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
