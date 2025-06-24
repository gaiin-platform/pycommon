# =============================================================================
# Tests for api/auth_admin.py
# =============================================================================

import os
from unittest.mock import MagicMock, patch

from api.auth_admin import verify_user_as_admin


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("api.auth_admin.requests.post")
def test_verify_user_as_admin_success(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True, "isAdmin": True}
    mock_post.return_value = mock_response

    result = verify_user_as_admin("test_token", "admin_check")

    assert result is True


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("api.auth_admin.requests.post")
def test_verify_user_as_admin_success_elif_branch(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True, "isAdmin": False}
    mock_post.return_value = mock_response

    result = verify_user_as_admin("test_token", "admin_check")

    assert result is False


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("api.auth_admin.requests.post")
def test_verify_user_as_admin_not_admin(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True, "isAdmin": False}
    mock_post.return_value = mock_response

    result = verify_user_as_admin("test_token", "admin_check")

    assert result is False


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("api.auth_admin.requests.post")
def test_verify_user_as_admin_failure(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.return_value = {"success": False}
    mock_post.return_value = mock_response

    result = verify_user_as_admin("test_token", "admin_check")

    assert result is False


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("api.auth_admin.requests.post")
def test_verify_user_as_admin_exception(mock_post):
    mock_post.side_effect = Exception("Network error")

    result = verify_user_as_admin("test_token", "admin_check")

    assert result is False


@patch.dict(os.environ, {"API_BASE_URL": ""})
def test_verify_user_as_admin_no_base_url():
    result = verify_user_as_admin("test_token", "admin_check")
    assert result is False
