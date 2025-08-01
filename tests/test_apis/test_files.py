# =============================================================================
# Tests for api/files.py
# =============================================================================

import os
from unittest.mock import MagicMock, patch

from pycommon.api.files import (
    delete_file,
    get_file_presigned_url,
    upload_file,
    upload_to_presigned_url,
)


class TestUploadFile:
    """Test cases for the upload_file function."""

    @patch("pycommon.api.files.upload_to_presigned_url")
    @patch("pycommon.api.files.get_file_presigned_url")
    def test_upload_file_success_string_content(
        self, mock_get_presigned_url, mock_upload_to_presigned_url
    ):
        """Test successful file upload with string content."""
        mock_get_presigned_url.return_value = {
            "success": True,
            "uploadUrl": "https://s3.amazonaws.com/bucket/key",
            "key": "file_key_123",
        }
        mock_upload_to_presigned_url.return_value = True

        result = upload_file(
            access_token="test_token",
            file_name="test file.txt",
            file_contents="Hello, world!",
            file_type="text/plain",
            tags=["test", "document"],
            data_props={"author": "test_user"},
            enter_rag_pipeline=True,
            groupId="group_123",
        )

        assert result is not None
        assert result["id"] == "file_key_123"
        assert result["name"] == "test_file.txt"
        assert result["type"] == "text/plain"
        assert result["tags"] == ["test", "document"]
        assert result["data"] == {"author": "test_user"}
        assert result["ragOn"] is True
        assert result["knowledgeBase"] == "default"
        assert result["groupId"] == "group_123"

        mock_get_presigned_url.assert_called_once()
        mock_upload_to_presigned_url.assert_called_once_with(
            "https://s3.amazonaws.com/bucket/key", "Hello, world!", "text/plain"
        )

    @patch("pycommon.api.files.upload_to_presigned_url")
    @patch("pycommon.api.files.get_file_presigned_url")
    def test_upload_file_success_bytes_content(
        self, mock_get_presigned_url, mock_upload_to_presigned_url
    ):
        """Test successful file upload with bytes content."""
        mock_get_presigned_url.return_value = {
            "success": True,
            "uploadUrl": "https://s3.amazonaws.com/bucket/key",
            "key": "image_key_456",
        }
        mock_upload_to_presigned_url.return_value = True

        binary_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"  # PNG header

        result = upload_file(
            access_token="test_token",
            file_name="image.png",
            file_contents=binary_content,
            file_type="image/png",
            tags=["image"],
        )

        assert result is not None
        assert result["id"] == "image_key_456"
        assert result["name"] == "image.png"
        assert result["type"] == "image/png"

        mock_upload_to_presigned_url.assert_called_once_with(
            "https://s3.amazonaws.com/bucket/key", binary_content, "image/png"
        )

    @patch("pycommon.api.files.get_file_presigned_url")
    def test_upload_file_presigned_url_failure(self, mock_get_presigned_url):
        """Test upload_file when getting presigned URL fails."""
        mock_get_presigned_url.return_value = {"success": False}

        result = upload_file(
            access_token="test_token",
            file_name="test.txt",
            file_contents="content",
            file_type="text/plain",
            tags=[],
        )

        assert result is None

    @patch("pycommon.api.files.upload_to_presigned_url")
    @patch("pycommon.api.files.get_file_presigned_url")
    def test_upload_file_upload_failure(
        self, mock_get_presigned_url, mock_upload_to_presigned_url
    ):
        """Test upload_file when upload to presigned URL fails."""
        mock_get_presigned_url.return_value = {
            "success": True,
            "uploadUrl": "https://s3.amazonaws.com/bucket/key",
            "key": "file_key",
        }
        mock_upload_to_presigned_url.return_value = False

        result = upload_file(
            access_token="test_token",
            file_name="test.txt",
            file_contents="content",
            file_type="text/plain",
            tags=[],
        )

        assert result is None

    @patch("pycommon.api.files.upload_to_presigned_url")
    @patch("pycommon.api.files.get_file_presigned_url")
    def test_upload_file_with_defaults(
        self, mock_get_presigned_url, mock_upload_to_presigned_url
    ):
        """Test upload_file with default parameters."""
        mock_get_presigned_url.return_value = {
            "success": True,
            "uploadUrl": "https://s3.amazonaws.com/bucket/key",
            "key": "file_key",
        }
        mock_upload_to_presigned_url.return_value = True

        result = upload_file(
            access_token="test_token",
            file_name="test.txt",
            file_contents="content",
            file_type="text/plain",
            tags=[],
        )

        assert result is not None
        assert result["data"] == {}
        assert result["ragOn"] is False
        assert result["groupId"] is None


class TestGetFilePresignedUrl:
    """Test cases for the get_file_presigned_url function."""

    @patch.dict(os.environ, {"API_BASE_URL": "https://api.example.com"})
    @patch("pycommon.api.files.requests.post")
    def test_get_file_presigned_url_success(self, mock_post):
        """Test successful presigned URL retrieval."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "uploadUrl": "https://s3.amazonaws.com/bucket/key",
            "metadataUrl": "https://api.example.com/metadata/key",
            "key": "file_key_123",
        }
        mock_post.return_value = mock_response

        payload = {
            "data": {
                "name": "test.txt",
                "type": "text/plain",
                "tags": ["test"],
                "data": {},
                "ragOn": False,
                "knowledgeBase": "default",
                "groupId": None,
            }
        }

        result = get_file_presigned_url("test_token", payload)

        assert result["success"] is True
        assert result["uploadUrl"] == "https://s3.amazonaws.com/bucket/key"
        assert result["metadataUrl"] == "https://api.example.com/metadata/key"
        assert result["key"] == "file_key_123"

        mock_post.assert_called_once_with(
            url="https://api.example.com/files/upload",
            headers={
                "Authorization": "Bearer test_token",
                "Content-Type": "application/json",
            },
            json=payload,
        )

    @patch.dict(os.environ, {"API_BASE_URL": "https://api.example.com"})
    @patch("pycommon.api.files.requests.post")
    def test_get_file_presigned_url_api_error(self, mock_post):
        """Test presigned URL retrieval with API error."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_post.return_value = mock_response

        payload = {"data": {"name": "test.txt"}}

        result = get_file_presigned_url("test_token", payload)

        assert result["success"] is False

    @patch.dict(os.environ, {"API_BASE_URL": "https://api.example.com"})
    @patch("pycommon.api.files.requests.post")
    def test_get_file_presigned_url_exception(self, mock_post):
        """Test presigned URL retrieval with exception."""
        mock_post.side_effect = Exception("Network error")

        payload = {"data": {"name": "test.txt"}}

        result = get_file_presigned_url("test_token", payload)

        assert result["success"] is False

    @patch.dict(os.environ, {"API_BASE_URL": "https://api.example.com"})
    @patch("pycommon.api.files.requests.post")
    def test_get_file_presigned_url_partial_response(self, mock_post):
        """Test presigned URL retrieval with partial response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "uploadUrl": "https://s3.amazonaws.com/bucket/key",
            # Missing metadataUrl and key
        }
        mock_post.return_value = mock_response

        payload = {"data": {"name": "test.txt"}}

        result = get_file_presigned_url("test_token", payload)

        assert result["success"] is True
        assert result["uploadUrl"] == "https://s3.amazonaws.com/bucket/key"
        assert result["metadataUrl"] is None
        assert result["key"] is None


class TestUploadToPresignedUrl:
    """Test cases for the upload_to_presigned_url function."""

    @patch("pycommon.api.files.requests.put")
    def test_upload_to_presigned_url_success_string(self, mock_put):
        """Test successful upload with string content."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_put.return_value = mock_response

        result = upload_to_presigned_url(
            "https://s3.amazonaws.com/bucket/key", "Hello, world!", "text/plain"
        )

        assert result is True
        mock_put.assert_called_once_with(
            "https://s3.amazonaws.com/bucket/key",
            data=b"Hello, world!",
            headers={"Content-Type": "text/plain"},
        )

    @patch("pycommon.api.files.requests.put")
    def test_upload_to_presigned_url_success_bytes(self, mock_put):
        """Test successful upload with bytes content."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_put.return_value = mock_response

        binary_content = b"\x89PNG\r\n\x1a\n"

        result = upload_to_presigned_url(
            "https://s3.amazonaws.com/bucket/key", binary_content, "image/png"
        )

        assert result is True
        mock_put.assert_called_once_with(
            "https://s3.amazonaws.com/bucket/key",
            data=binary_content,
            headers={"Content-Type": "image/png"},
        )

    @patch("pycommon.api.files.requests.put")
    def test_upload_to_presigned_url_failure(self, mock_put):
        """Test upload failure with non-200 status code."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_put.return_value = mock_response

        result = upload_to_presigned_url(
            "https://s3.amazonaws.com/bucket/key", "content", "text/plain"
        )

        assert result is False

    @patch("pycommon.api.files.requests.put")
    def test_upload_to_presigned_url_exception(self, mock_put):
        """Test upload with exception."""
        mock_put.side_effect = Exception("Network error")

        result = upload_to_presigned_url(
            "https://s3.amazonaws.com/bucket/key", "content", "text/plain"
        )

        assert result is False

    @patch("pycommon.api.files.requests.put")
    def test_upload_to_presigned_url_empty_string(self, mock_put):
        """Test upload with empty string content."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_put.return_value = mock_response

        result = upload_to_presigned_url(
            "https://s3.amazonaws.com/bucket/key", "", "text/plain"
        )

        assert result is True
        mock_put.assert_called_once_with(
            "https://s3.amazonaws.com/bucket/key",
            data=b"",
            headers={"Content-Type": "text/plain"},
        )

    @patch("pycommon.api.files.requests.put")
    def test_upload_to_presigned_url_empty_bytes(self, mock_put):
        """Test upload with empty bytes content."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_put.return_value = mock_response

        result = upload_to_presigned_url(
            "https://s3.amazonaws.com/bucket/key", b"", "application/octet-stream"
        )

        assert result is True
        mock_put.assert_called_once_with(
            "https://s3.amazonaws.com/bucket/key",
            data=b"",
            headers={"Content-Type": "application/octet-stream"},
        )

    @patch("pycommon.api.files.requests.put")
    def test_upload_to_presigned_url_unicode_string(self, mock_put):
        """Test upload with unicode string content."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_put.return_value = mock_response

        unicode_content = "Hello 世界! 🌍"

        result = upload_to_presigned_url(
            "https://s3.amazonaws.com/bucket/key", unicode_content, "text/plain"
        )

        assert result is True
        mock_put.assert_called_once_with(
            "https://s3.amazonaws.com/bucket/key",
            data=unicode_content.encode("utf-8"),
            headers={"Content-Type": "text/plain"},
        )


class TestDeleteFile:
    """Test cases for the delete_file function."""

    @patch.dict(os.environ, {"API_BASE_URL": "https://api.example.com"})
    @patch("pycommon.api.files.extract_key")
    @patch("pycommon.api.files.requests.post")
    def test_delete_file_success(self, mock_post, mock_extract_key):
        """Test successful file deletion."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "message": "File deleted successfully",
        }
        mock_post.return_value = mock_response
        mock_extract_key.return_value = "file_key_123"

        result = delete_file("test_token", "file_key_123")

        assert result["success"] is True
        assert result["message"] == "File deleted successfully"

        mock_extract_key.assert_called_once_with("file_key_123")
        mock_post.assert_called_once_with(
            url="https://api.example.com/files/delete",
            headers={
                "Authorization": "Bearer test_token",
                "Content-Type": "application/json",
            },
            json={"data": {"key": "file_key_123"}},
        )

    @patch.dict(os.environ, {"API_BASE_URL": "https://api.example.com"})
    @patch("pycommon.api.files.extract_key")
    @patch("pycommon.api.files.requests.post")
    def test_delete_file_with_protocol_prefix(self, mock_post, mock_extract_key):
        """Test file deletion with protocol prefix in key."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "message": "File deleted successfully",
        }
        mock_post.return_value = mock_response
        mock_extract_key.return_value = "bucket/path/file_key_123"

        result = delete_file("test_token", "s3://bucket/path/file_key_123")

        assert result["success"] is True
        assert result["message"] == "File deleted successfully"

        mock_extract_key.assert_called_once_with("s3://bucket/path/file_key_123")
        mock_post.assert_called_once_with(
            url="https://api.example.com/files/delete",
            headers={
                "Authorization": "Bearer test_token",
                "Content-Type": "application/json",
            },
            json={"data": {"key": "bucket/path/file_key_123"}},
        )

    @patch.dict(os.environ, {"API_BASE_URL": "https://api.example.com"})
    @patch("pycommon.api.files.extract_key")
    @patch("pycommon.api.files.requests.post")
    def test_delete_file_api_failure(self, mock_post, mock_extract_key):
        """Test file deletion when API returns failure."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": False,
            "message": "File not found",
        }
        mock_post.return_value = mock_response
        mock_extract_key.return_value = "nonexistent_key"

        result = delete_file("test_token", "nonexistent_key")

        assert result["success"] is False
        assert result["message"] == "File not found"

    @patch.dict(os.environ, {"API_BASE_URL": "https://api.example.com"})
    @patch("pycommon.api.files.extract_key")
    @patch("pycommon.api.files.requests.post")
    def test_delete_file_http_error(self, mock_post, mock_extract_key):
        """Test file deletion with HTTP error status."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_post.return_value = mock_response
        mock_extract_key.return_value = "file_key_123"

        result = delete_file("test_token", "file_key_123")

        assert result["success"] is False
        assert "API call failed with status 404" in result["message"]

    @patch.dict(os.environ, {"API_BASE_URL": "https://api.example.com"})
    @patch("pycommon.api.files.extract_key")
    @patch("pycommon.api.files.requests.post")
    def test_delete_file_network_exception(self, mock_post, mock_extract_key):
        """Test file deletion with network exception."""
        mock_post.side_effect = Exception("Network error")
        mock_extract_key.return_value = "file_key_123"

        result = delete_file("test_token", "file_key_123")

        assert result["success"] is False
        assert "Failed to delete file with key: file_key_123" in result["message"]

    @patch.dict(os.environ, {"API_BASE_URL": "https://api.example.com"})
    @patch("pycommon.api.files.extract_key")
    @patch("pycommon.api.files.requests.post")
    def test_delete_file_partial_response(self, mock_post, mock_extract_key):
        """Test file deletion with partial response (missing message)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True
            # Missing message field
        }
        mock_post.return_value = mock_response
        mock_extract_key.return_value = "file_key_123"

        result = delete_file("test_token", "file_key_123")

        assert result["success"] is True
        assert result["message"] == ""

    @patch.dict(os.environ, {"API_BASE_URL": "https://api.example.com"})
    @patch("pycommon.api.files.extract_key")
    @patch("pycommon.api.files.requests.post")
    def test_delete_file_missing_success_field(self, mock_post, mock_extract_key):
        """Test file deletion with missing success field in response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": "Some message"
            # Missing success field
        }
        mock_post.return_value = mock_response
        mock_extract_key.return_value = "file_key_123"

        result = delete_file("test_token", "file_key_123")

        assert result["success"] is False
        assert result["message"] == "Some message"

    @patch.dict(os.environ, {"API_BASE_URL": "https://api.example.com"})
    @patch("pycommon.api.files.extract_key")
    @patch("pycommon.api.files.requests.post")
    def test_delete_file_empty_response(self, mock_post, mock_extract_key):
        """Test file deletion with empty response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_post.return_value = mock_response
        mock_extract_key.return_value = "file_key_123"

        result = delete_file("test_token", "file_key_123")

        assert result["success"] is False
        assert result["message"] == ""

    @patch.dict(os.environ, {"API_BASE_URL": "https://api.example.com"})
    @patch("pycommon.api.files.extract_key")
    @patch("pycommon.api.files.requests.post")
    def test_delete_file_with_special_characters_in_key(
        self, mock_post, mock_extract_key
    ):
        """Test file deletion with special characters in key."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "message": "File deleted successfully",
        }
        mock_post.return_value = mock_response
        mock_extract_key.return_value = "file_key_with-special.chars_123"

        special_key = "file_key_with-special.chars_123"
        result = delete_file("test_token", special_key)

        assert result["success"] is True
        mock_extract_key.assert_called_once_with(special_key)
        mock_post.assert_called_once_with(
            url="https://api.example.com/files/delete",
            headers={
                "Authorization": "Bearer test_token",
                "Content-Type": "application/json",
            },
            json={"data": {"key": special_key}},
        )
