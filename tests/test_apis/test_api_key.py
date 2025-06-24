# =============================================================================
# Tests for api/api_key.py
# =============================================================================

import os
from unittest.mock import MagicMock, patch

from api.api_key import deactivate_key, get_api_keys


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("api.api_key.requests.post")
def test_deactivate_key_success(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True}
    mock_post.return_value = mock_response

    result = deactivate_key("test_token", "api_owner_123")

    assert result is True


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("api.api_key.requests.post")
def test_deactivate_key_success_elif_branch(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True}
    mock_post.return_value = mock_response

    result = deactivate_key("test_token", "api_owner_123")

    assert result is True


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("api.api_key.requests.post")
def test_deactivate_key_failure(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.return_value = {"error": "Bad request"}
    mock_post.return_value = mock_response

    result = deactivate_key("test_token", "api_owner_123")

    assert result is False


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("api.api_key.requests.get")
def test_get_api_keys_success(mock_get):
    mock_response = MagicMock()
    mock_response.json.return_value = {"keys": ["key1", "key2"]}
    mock_get.return_value = mock_response

    result = get_api_keys("test_token")

    assert result == {"keys": ["key1", "key2"]}


@patch.dict(os.environ, {"API_BASE_URL": ""})
def test_get_api_keys_no_base_url():
    result = get_api_keys("test_token")
    assert result is None


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("api.api_key.requests.get")
def test_get_api_keys_exception(mock_get):
    mock_get.side_effect = Exception("Network error")

    result = get_api_keys("test_token")

    assert result is None


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("api.api_key.requests.post")
def test_deactivate_key_exception(mock_post):
    mock_post.side_effect = Exception("Network error")

    result = deactivate_key("test_token", "api_owner_123")

    assert result is False
