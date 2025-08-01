# =============================================================================
# Tests for api/object_permissions.py
# =============================================================================

import os
from unittest.mock import MagicMock, patch

from pycommon.api.object_permissions import (
    can_access_objects,
    simulate_can_access_objects,
    update_object_permissions,
)


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.object_permissions.requests.post")
def test_update_object_permissions_success(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"statusCode": 200}
    mock_post.return_value = mock_response

    result = update_object_permissions(
        "test_token", ["user1@test.com"], ["key1"], "file"
    )

    assert result is True


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.object_permissions.requests.post")
def test_update_object_permissions_failure(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.return_value = {"statusCode": 400}
    mock_post.return_value = mock_response

    result = update_object_permissions(
        "test_token", ["user1@test.com"], ["key1"], "file"
    )

    assert result is False


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.object_permissions.requests.post")
def test_update_object_permissions_exception(mock_post):
    mock_post.side_effect = Exception("Network error")

    result = update_object_permissions(
        "test_token", ["user1@test.com"], ["key1"], "file"
    )

    assert result is False


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.object_permissions.requests.post")
def test_can_access_objects_empty_data_sources(mock_post):
    result = can_access_objects("test_token", [])
    assert result is True
    mock_post.assert_not_called()


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.object_permissions.requests.post")
def test_can_access_objects_web_sources_only(mock_post):
    data_sources = [
        {"id": "http://example.com", "type": "website/url"},
        {"id": "https://example.com/sitemap.xml", "type": "website/sitemap"},
    ]
    result = can_access_objects("test_token", data_sources)
    assert result is True
    mock_post.assert_not_called()


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.object_permissions.requests.post")
def test_can_access_objects_success(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"statusCode": 200, "success": True}
    mock_post.return_value = mock_response

    data_sources = [{"id": "file://test.txt", "type": "file"}]
    result = can_access_objects("test_token", data_sources)

    assert result is True


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.object_permissions.requests.post")
def test_can_access_objects_success_elif_branch(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"statusCode": 200, "success": True}
    mock_post.return_value = mock_response

    data_sources = [{"id": "s3://bucket/file.txt", "type": "file"}]
    result = can_access_objects("test_token", data_sources)

    assert result is True


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.object_permissions.requests.post")
def test_can_access_objects_failure(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_response.json.return_value = {"statusCode": 403}
    mock_post.return_value = mock_response

    data_sources = [{"id": "s3://bucket/key", "type": "text/plain"}]
    result = can_access_objects("test_token", data_sources)

    assert result is False


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.object_permissions.requests.post")
def test_simulate_can_access_objects_success(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "statusCode": 200,
        "data": {"obj1": {"read": True}},
    }
    mock_post.return_value = mock_response

    result = simulate_can_access_objects("test_token", ["obj1"])

    assert result == {"obj1": {"read": True}}


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.object_permissions.requests.post")
def test_simulate_can_access_objects_success_elif_branch(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "statusCode": 200,
        "data": {"obj2": {"read": False}},
    }
    mock_post.return_value = mock_response

    result = simulate_can_access_objects("test_token", ["obj2"], ["read"])

    assert result == {"obj2": {"read": False}}


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.object_permissions.requests.post")
def test_simulate_can_access_objects_failure(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.return_value = {"statusCode": 400}
    mock_post.return_value = mock_response

    result = simulate_can_access_objects("test_token", ["obj1", "obj2"])

    expected = {"obj1": {"read": False}, "obj2": {"read": False}}
    assert result == expected


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.object_permissions.requests.post")
def test_simulate_can_access_objects_json_decode_error(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.side_effect = ValueError("JSON decode error")
    mock_post.return_value = mock_response

    result = simulate_can_access_objects("test_token", ["obj1"], ["read"])
    # Should return all denied access when JSON decode fails
    assert result == {"obj1": {"read": False}}


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.object_permissions.requests.post")
def test_simulate_can_access_objects_final_return_line_189(mock_post):
    # Mock a scenario where neither success nor exception paths are taken
    mock_response = MagicMock()
    mock_response.status_code = 500  # Server error, but no exception
    mock_response.json.return_value = {"statusCode": 500}
    mock_post.return_value = mock_response

    result = simulate_can_access_objects("test_token", ["obj1"], ["read"])
    # Should return all denied access as final fallback
    assert result == {"obj1": {"read": False}}


# Additional coverage tests for object_permissions.py
@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.object_permissions.requests.post")
def test_can_access_objects_exception_lines_60_64(mock_post):
    mock_post.side_effect = Exception("Network error")

    data_sources = [{"id": "s3://bucket/key", "type": "text/plain"}]
    result = can_access_objects("test_token", data_sources)

    assert result is False


@patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
@patch("pycommon.api.object_permissions.requests.post")
def test_simulate_can_access_objects_final_return(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"statusCode": 200}  # No "data" key
    mock_post.return_value = mock_response

    result = simulate_can_access_objects("test_token", ["obj1"], ["read"])
    # Should return all denied when no data key is present
    assert result == {"obj1": {"read": False}}
