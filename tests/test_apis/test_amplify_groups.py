# =============================================================================
# Tests for api/amplify_groups.py
# =============================================================================

import os
from unittest.mock import MagicMock, patch

from api.amplify_groups import (
    verify_member_of_ast_admin_group,
    verify_user_in_amp_group,
)


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("api.amplify_groups.requests.post")
def test_verify_member_of_ast_admin_group_success(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True, "isMember": True}
    mock_post.return_value = mock_response

    result = verify_member_of_ast_admin_group("test_token", "group123")

    assert result is True


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("api.amplify_groups.requests.post")
def test_verify_member_of_ast_admin_group_not_member(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True, "isMember": False}
    mock_post.return_value = mock_response

    result = verify_member_of_ast_admin_group("test_token", "group123")

    assert result is False


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("api.amplify_groups.requests.post")
def test_verify_user_in_amp_group_empty_groups(mock_post):
    result = verify_user_in_amp_group("test_token", [])
    assert result is False
    mock_post.assert_not_called()

    result = verify_user_in_amp_group("test_token", None)
    assert result is False
    mock_post.assert_not_called()


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("api.amplify_groups.requests.post")
def test_verify_user_in_amp_group_success(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True, "isMember": True}
    mock_post.return_value = mock_response

    result = verify_user_in_amp_group("test_token", ["group1", "group2"])

    assert result is True


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("api.amplify_groups.requests.post")
def test_verify_user_in_amp_group_not_member(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True, "isMember": False}
    mock_post.return_value = mock_response

    result = verify_user_in_amp_group("test_token", ["group1", "group2"])

    assert result is False


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("api.amplify_groups.requests.post")
def test_verify_member_of_ast_admin_group_failure(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.return_value = {"success": False}
    mock_post.return_value = mock_response

    result = verify_member_of_ast_admin_group("test_token", "group123")

    assert result is False


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("api.amplify_groups.requests.post")
def test_verify_member_of_ast_admin_group_exception(mock_post):
    mock_post.side_effect = Exception("Network error")

    result = verify_member_of_ast_admin_group("test_token", "group123")

    assert result is False


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("api.amplify_groups.requests.post")
def test_verify_user_in_amp_group_failure(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.return_value = {"success": False}
    mock_post.return_value = mock_response

    result = verify_user_in_amp_group("test_token", ["group1", "group2"])

    assert result is False


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("api.amplify_groups.requests.post")
def test_verify_user_in_amp_group_exception(mock_post):
    mock_post.side_effect = Exception("Network error")

    result = verify_user_in_amp_group("test_token", ["group1", "group2"])

    assert result is False
