# =============================================================================
# Tests for api/ops_reqs.py
# =============================================================================

import os
from unittest.mock import MagicMock, patch

from pycommon.api.ops_reqs import get_all_op, register_ops


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.ops_reqs.requests.get")
def test_get_all_op_success(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True, "data": ["op1", "op2"]}
    mock_get.return_value = mock_response

    result = get_all_op("test_token")

    assert result == {"success": True, "data": ["op1", "op2"]}


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.ops_reqs.requests.get")
def test_get_all_op_success_elif_branch(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True, "data": ["op3", "op4"]}
    mock_get.return_value = mock_response

    result = get_all_op("test_token")

    assert result == {"success": True, "data": ["op3", "op4"]}


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.ops_reqs.requests.get")
def test_get_all_op_failure(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.return_value = {"success": False}
    mock_get.return_value = mock_response

    result = get_all_op("test_token")

    assert result == {"success": False, "data": None}


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.ops_reqs.requests.post")
def test_register_ops_success(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True}
    mock_post.return_value = mock_response

    result = register_ops("test_token", [{"name": "test_op"}])

    assert result is True


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.ops_reqs.requests.post")
def test_register_ops_success_elif_branch(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True}
    mock_post.return_value = mock_response

    result = register_ops("test_token", [{"name": "test_op2"}], system_op=True)

    assert result is True


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.ops_reqs.requests.post")
def test_register_ops_exception_lines_64_70(mock_post):
    mock_post.side_effect = Exception("Network error")

    result = register_ops("test_token", [{"name": "test_op"}])

    assert result is False


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.ops_reqs.requests.get")
def test_get_all_op_json_decode_error(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.side_effect = ValueError("JSON decode error")
    mock_get.return_value = mock_response

    result = get_all_op("test_token")
    assert result == {"success": False, "data": None}


# Additional coverage tests for ops_reqs.py
@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.ops_reqs.requests.post")
def test_register_ops_exception_lines_64_70_new(mock_post):
    mock_post.side_effect = Exception("Network error")

    result = register_ops("test_token", [{"name": "test_op"}])

    assert result is False


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.ops_reqs.requests.post")
def test_register_ops_failure(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.return_value = {"success": False}
    mock_post.return_value = mock_response

    result = register_ops("test_token", [{"name": "test_op"}])

    assert result is False
