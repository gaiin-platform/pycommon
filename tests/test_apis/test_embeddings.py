# =============================================================================
# Tests for api/embeddings.py
# =============================================================================

import json
import os
from unittest.mock import MagicMock, patch

from api.embeddings import (
    check_embedding_completion,
    embedding_permission,
)


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("api.embeddings.requests.post")
def test_embedding_permission_success(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True, "result": "deleted"}
    mock_post.return_value = mock_response

    success, result = embedding_permission("test_token", ["datasource1"])

    assert success is True
    assert result == "deleted"


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("api.embeddings.requests.post")
def test_embedding_permission_failure(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.return_value = {"success": False, "error": "Bad request"}
    mock_post.return_value = mock_response

    success, result = embedding_permission("test_token", ["datasource1"])

    assert success is False
    assert result == {"success": False, "error": "Bad request"}


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("api.embeddings.requests.post")
def test_embedding_permission_string_input(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True, "result": "deleted"}
    mock_post.return_value = mock_response

    success, result = embedding_permission("test_token", "single_datasource")

    assert success is True
    expected_data = {"data": {"dataSources": ["single_datasource"]}}
    mock_post.assert_called_once()
    call_args = mock_post.call_args
    assert json.loads(call_args[1]["data"]) == expected_data


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("api.embeddings.requests.post")
def test_check_embedding_completion_success(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True}
    mock_post.return_value = mock_response

    result = check_embedding_completion("test_token", ["datasource1"])

    assert result is True


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("api.embeddings.requests.post")
def test_check_embedding_completion_failure(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.return_value = {"success": False}
    mock_post.return_value = mock_response

    result = check_embedding_completion("test_token", ["datasource1"])

    assert result is False


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("api.embeddings.requests.post")
def test_check_embedding_completion_exception_lines_68_74(mock_post):
    mock_post.side_effect = Exception("Network error")

    result = check_embedding_completion("test_token", ["datasource1"])

    assert result is False


# Additional coverage tests for embeddings.py
@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("api.embeddings.requests.post")
def test_embedding_permission_exception_lines_41_43(mock_post):
    mock_post.side_effect = Exception("Network error")

    success, result = embedding_permission("test_token", ["datasource1"])

    assert success is False
    assert result == "Network error"


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("api.embeddings.requests.post")
def test_check_embedding_completion_exception(mock_post):
    mock_post.side_effect = Exception("Network error")

    result = check_embedding_completion("test_token", ["datasource1"])

    assert result is False


# NEW TEST: Cover elif branch 68->74 (status_code == 200 AND success == True)
@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("api.embeddings.requests.post")
def test_check_embedding_completion_success_elif_branch(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True}
    mock_post.return_value = mock_response

    result = check_embedding_completion("test_token", ["datasource2"])

    assert result is True
