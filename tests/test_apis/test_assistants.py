# =============================================================================
# Tests for api/assistants.py
# =============================================================================

import os
from unittest.mock import MagicMock, patch

from pycommon.api.assistants import (
    add_assistant_path,
    create_assistant,
    delete_assistant,
    list_assistants,
    remove_astp_perms,
    share_assistant,
)


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.assistants.requests.post")
def test_share_assistant_success(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True}
    mock_post.return_value = mock_response

    result = share_assistant("test_token", {"assistant_id": "123"})

    assert result is True


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.assistants.requests.post")
def test_share_assistant_success_elif_branch(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True}
    mock_post.return_value = mock_response

    result = share_assistant("test_token", {"assistant_id": "123"})

    assert result is True


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.assistants.requests.get")
def test_list_assistants_success(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True, "assistants": []}
    mock_get.return_value = mock_response

    result = list_assistants("test_token")

    assert result == {"success": True, "assistants": []}


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.assistants.requests.get")
def test_list_assistants_failure(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.return_value = {"error": "Bad request"}
    mock_get.return_value = mock_response

    result = list_assistants("test_token")

    assert result == {"success": False}


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.assistants.requests.post")
def test_remove_astp_perms_success(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True}
    mock_post.return_value = mock_response

    result = remove_astp_perms("test_token", {"assistant_id": "123"})

    assert result == {"success": True}


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.assistants.requests.post")
def test_delete_assistant_success(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True}
    mock_post.return_value = mock_response

    result = delete_assistant("test_token", {"assistant_id": "123"})

    assert result == {"success": True}


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.assistants.requests.post")
def test_create_assistant_success(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True, "id": "new_assistant_123"}
    mock_post.return_value = mock_response

    result = create_assistant("test_token", {"name": "Test Assistant"})

    assert result == {"success": True, "id": "new_assistant_123"}


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.assistants.requests.post")
def test_add_assistant_path_success(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True, "message": "Path added"}
    mock_post.return_value = mock_response

    result = add_assistant_path("test_token", {"path": "/test/path"})

    assert result == {"success": True, "message": "Path added"}


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.assistants.requests.post")
def test_add_assistant_path_success_elif_branch(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True, "data": {"path_id": "456"}}
    mock_post.return_value = mock_response

    result = add_assistant_path("test_token", {"path": "/test/path"})

    assert result == {"success": True, "data": {"path_id": "456"}}


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.assistants.requests.post")
def test_add_assistant_path_failure(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.return_value = {"success": False, "message": "Bad request"}
    mock_post.return_value = mock_response

    result = add_assistant_path("test_token", {"assistant_id": "123", "path": "/test"})

    assert result == {"success": False, "message": "Bad request"}


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.assistants.requests.post")
def test_share_assistant_failure(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.return_value = {"success": False}
    mock_post.return_value = mock_response

    result = share_assistant("test_token", {"assistant_id": "123"})

    assert result is False


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.assistants.requests.post")
def test_share_assistant_exception(mock_post):
    mock_post.side_effect = Exception("Network error")

    result = share_assistant("test_token", {"assistant_id": "123"})

    assert result is False


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.assistants.requests.get")
def test_list_assistants_exception(mock_get):
    mock_get.side_effect = Exception("Network error")

    result = list_assistants("test_token")

    assert result == {"success": False}


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.assistants.requests.post")
def test_remove_astp_perms_failure(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.return_value = {"success": False}
    mock_post.return_value = mock_response

    result = remove_astp_perms("test_token", {"assistant_id": "123"})

    assert result == {"success": False}


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.assistants.requests.post")
def test_remove_astp_perms_exception(mock_post):
    mock_post.side_effect = Exception("Network error")

    result = remove_astp_perms("test_token", {"assistant_id": "123"})

    assert result == {"success": False}


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.assistants.requests.post")
def test_delete_assistant_failure(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.return_value = {"success": False}
    mock_post.return_value = mock_response

    result = delete_assistant("test_token", {"assistant_id": "123"})

    assert result == {"success": False}


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.assistants.requests.post")
def test_delete_assistant_exception(mock_post):
    mock_post.side_effect = Exception("Network error")

    result = delete_assistant("test_token", {"assistant_id": "123"})

    assert result == {"success": False}


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.assistants.requests.post")
def test_create_assistant_failure(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.return_value = {"success": False}
    mock_post.return_value = mock_response

    result = create_assistant("test_token", {"name": "Test Assistant"})

    assert result == {"success": False}


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.assistants.requests.post")
def test_create_assistant_exception(mock_post):
    mock_post.side_effect = Exception("Network error")

    result = create_assistant("test_token", {"name": "Test Assistant"})

    assert result == {"success": False}


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.assistants.requests.post")
def test_add_assistant_path_exception(mock_post):
    mock_post.side_effect = Exception("Network error")

    result = add_assistant_path("test_token", {"assistant_id": "123", "path": "/test"})

    assert result == {"success": False, "message": "Unexpected error occurred"}


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.assistants.requests.post")
def test_add_assistant_path_final_return(mock_post):
    # Mock a scenario where the function reaches the final return statement
    # This happens when the response is neither successful nor an exception
    mock_response = MagicMock()
    mock_response.status_code = 500  # Server error, but no exception raised
    mock_response.json.return_value = {"success": False}
    mock_post.return_value = mock_response

    result = add_assistant_path("test_token", {"assistant_id": "123", "path": "/test"})
    assert result == {"success": False, "message": "Failed to add path to assistant"}


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.assistants.requests.post")
def test_add_assistant_exception_line_199(mock_post):
    mock_post.side_effect = Exception("Network error")

    result = add_assistant_path("test_token", {})

    assert result == {"success": False, "message": "Unexpected error occurred"}
