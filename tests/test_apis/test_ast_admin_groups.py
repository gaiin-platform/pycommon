# =============================================================================
# Tests for api/ast_admin_groups.py
# =============================================================================

import os
from unittest.mock import MagicMock, patch

from pycommon.api.ast_admin_groups import (
    get_all_ast_admin_groups,
    update_ast_admin_groups,
)


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.ast_admin_groups.requests.get")
def test_get_all_ast_admin_groups_success(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True, "data": ["group1", "group2"]}
    mock_get.return_value = mock_response

    result = get_all_ast_admin_groups("test_token")

    assert result == {"success": True, "data": ["group1", "group2"]}


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.ast_admin_groups.requests.get")
def test_get_all_ast_admin_groups_success_elif_branch(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True, "data": ["group3", "group4"]}
    mock_get.return_value = mock_response

    result = get_all_ast_admin_groups("test_token")

    assert result == {"success": True, "data": ["group3", "group4"]}


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.ast_admin_groups.requests.get")
def test_get_all_ast_admin_groups_failure(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.return_value = {"success": False}
    mock_get.return_value = mock_response

    result = get_all_ast_admin_groups("test_token")

    assert result == {"success": False, "data": None}


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.ast_admin_groups.requests.get")
def test_get_all_ast_admin_groups_exception(mock_get):
    mock_get.side_effect = Exception("Network error")

    result = get_all_ast_admin_groups("test_token")

    assert result == {"success": False, "data": None}


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.ast_admin_groups.requests.post")
def test_update_ast_admin_groups_success(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True}
    mock_post.return_value = mock_response

    result = update_ast_admin_groups("test_token", {"group_id": "123"})

    assert result == {"success": True}


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.ast_admin_groups.requests.post")
def test_update_ast_admin_groups_success_elif_branch(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True, "data": {"updated": True}}
    mock_post.return_value = mock_response

    result = update_ast_admin_groups("test_token", {"group_id": "456"})

    assert result == {"success": True, "data": {"updated": True}}


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.ast_admin_groups.requests.post")
def test_update_ast_admin_groups_failure(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.return_value = {"success": False, "message": "Bad request"}
    mock_post.return_value = mock_response

    result = update_ast_admin_groups("test_token", {"group_id": "123"})

    assert result == {"success": False, "message": "Bad request"}


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.ast_admin_groups.requests.post")
def test_update_ast_admin_groups_exception(mock_post):
    mock_post.side_effect = Exception("Network error")

    result = update_ast_admin_groups("test_token", {"group_id": "123"})

    assert result == {"success": False, "message": "Failed to make request"}
