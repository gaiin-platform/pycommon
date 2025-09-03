# =============================================================================
# Tests for api/amplify_groups.py
# =============================================================================

import os
from unittest.mock import MagicMock, patch

from pycommon.api.amplify_groups import (
    get_user_affiliated_groups,
    verify_member_of_ast_admin_group,
    verify_user_in_amp_group,
)


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.amplify_groups.requests.post")
def test_verify_member_of_ast_admin_group_success(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True, "isMember": True}
    mock_post.return_value = mock_response

    result = verify_member_of_ast_admin_group("test_token", "group123")

    assert result is True


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.amplify_groups.requests.post")
def test_verify_member_of_ast_admin_group_not_member(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True, "isMember": False}
    mock_post.return_value = mock_response

    result = verify_member_of_ast_admin_group("test_token", "group123")

    assert result is False


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.amplify_groups.requests.post")
def test_verify_user_in_amp_group_empty_groups(mock_post):
    result = verify_user_in_amp_group("test_token", [])
    assert result is False
    mock_post.assert_not_called()

    result = verify_user_in_amp_group("test_token", None)
    assert result is False
    mock_post.assert_not_called()


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.amplify_groups.requests.post")
def test_verify_user_in_amp_group_success(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True, "isMember": True}
    mock_post.return_value = mock_response

    result = verify_user_in_amp_group("test_token", ["group1", "group2"])

    assert result is True


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.amplify_groups.requests.post")
def test_verify_user_in_amp_group_not_member(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True, "isMember": False}
    mock_post.return_value = mock_response

    result = verify_user_in_amp_group("test_token", ["group1", "group2"])

    assert result is False


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.amplify_groups.requests.post")
def test_verify_member_of_ast_admin_group_failure(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.return_value = {"success": False}
    mock_post.return_value = mock_response

    result = verify_member_of_ast_admin_group("test_token", "group123")

    assert result is False


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.amplify_groups.requests.post")
def test_verify_member_of_ast_admin_group_exception(mock_post):
    mock_post.side_effect = Exception("Network error")

    result = verify_member_of_ast_admin_group("test_token", "group123")

    assert result is False


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.amplify_groups.requests.post")
def test_verify_user_in_amp_group_failure(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.return_value = {"success": False}
    mock_post.return_value = mock_response

    result = verify_user_in_amp_group("test_token", ["group1", "group2"])

    assert result is False


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.amplify_groups.requests.post")
def test_verify_user_in_amp_group_exception(mock_post):
    mock_post.side_effect = Exception("Network error")

    result = verify_user_in_amp_group("test_token", ["group1", "group2"])

    assert result is False


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.amplify_groups.requests.get")
def test_get_user_affiliated_groups_success(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "success": True,
        "data": ["group1", "group2"],
        "all_groups": ["group1", "group2", "group3", "group4"],
    }
    mock_get.return_value = mock_response

    result = get_user_affiliated_groups("test_token")

    assert result is not None
    affiliated_groups, all_groups = result
    assert affiliated_groups == ["group1", "group2"]
    assert all_groups == ["group1", "group2", "group3", "group4"]

    # Verify the correct endpoint was called
    mock_get.assert_called_once_with(
        "http://test-api.com/amplifymin/amplify_groups/affiliated",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer test_token",
        },
    )


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.amplify_groups.requests.get")
def test_get_user_affiliated_groups_api_failure(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "success": False,
        "message": "No Amplify Groups Found",
    }
    mock_get.return_value = mock_response

    result = get_user_affiliated_groups("test_token")

    assert result == (None, None)


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.amplify_groups.requests.get")
def test_get_user_affiliated_groups_http_error(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.return_value = {"success": False, "message": "Bad Request"}
    mock_get.return_value = mock_response

    result = get_user_affiliated_groups("test_token")

    assert result == (None, None)


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.amplify_groups.requests.get")
def test_get_user_affiliated_groups_exception(mock_get):
    mock_get.side_effect = Exception("Network error")

    result = get_user_affiliated_groups("test_token")

    assert result == (None, None)


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.amplify_groups.requests.get")
def test_get_user_affiliated_groups_missing_data_fields(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "success": True
        # Missing "data" and "all_groups" fields
    }
    mock_get.return_value = mock_response

    result = get_user_affiliated_groups("test_token")

    assert result is not None
    affiliated_groups, all_groups = result
    assert affiliated_groups == []  # Should default to empty list
    assert all_groups == []  # Should default to empty list


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.amplify_groups.requests.get")
def test_get_user_affiliated_groups_partial_data(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "success": True,
        "data": ["user_group1"],
        # Missing "all_groups" field
    }
    mock_get.return_value = mock_response

    result = get_user_affiliated_groups("test_token")

    assert result is not None
    affiliated_groups, all_groups = result
    assert affiliated_groups == ["user_group1"]
    assert all_groups == []  # Should default to empty list
