import json
import os
from unittest.mock import Mock, patch

import pytest
import requests

from pycommon.api.user_data import load_user_data


class TestLoadUserData:
    """Test suite for load_user_data function."""

    def setup_method(self):
        """Set up test fixtures."""
        self.access_token = "test_access_token"
        self.app_id = "test_app_id"
        self.entity_type = "test_entity_type"
        self.item_id = "test_item_id"
        self.api_base_url = "https://api.example.com"

    @patch.dict(os.environ, {"API_BASE_URL": "https://api.example.com"})
    @patch("pycommon.api.user_data.requests.post")
    def test_load_user_data_success(self, mock_post):
        """Test successful user data loading."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "data": {"user_id": "123", "name": "Test User"},
        }
        mock_response.content = (
            b'{"success": true, "data": {"user_id": "123", "name": "Test User"}}'
        )
        mock_post.return_value = mock_response

        result = load_user_data(
            self.access_token, self.app_id, self.entity_type, self.item_id
        )

        # Verify the request was made correctly
        expected_endpoint = f"{self.api_base_url}/user-data/get"
        expected_request_data = {
            "data": {
                "appId": self.app_id,
                "entityType": self.entity_type,
                "itemId": self.item_id,
            }
        }
        expected_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.access_token}",
        }

        mock_post.assert_called_once_with(
            expected_endpoint,
            headers=expected_headers,
            data=json.dumps(expected_request_data),
        )

        # Verify the result
        assert result == {"user_id": "123", "name": "Test User"}

    @patch.dict(os.environ, {"API_BASE_URL": "https://api.example.com"})
    @patch("pycommon.api.user_data.requests.post")
    def test_load_user_data_success_false(self, mock_post):
        """Test response with success=False."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": False, "error": "Invalid request"}
        mock_response.content = b'{"success": false, "error": "Invalid request"}'
        mock_post.return_value = mock_response

        result = load_user_data(
            self.access_token, self.app_id, self.entity_type, self.item_id
        )

        assert result is None

    @patch.dict(os.environ, {"API_BASE_URL": "https://api.example.com"})
    @patch("pycommon.api.user_data.requests.post")
    def test_load_user_data_non_200_status(self, mock_post):
        """Test response with non-200 status code."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.json.return_value = {"success": False, "error": "Not found"}
        mock_response.content = b'{"success": false, "error": "Not found"}'
        mock_post.return_value = mock_response

        result = load_user_data(
            self.access_token, self.app_id, self.entity_type, self.item_id
        )

        assert result is None

    @patch.dict(os.environ, {"API_BASE_URL": "https://api.example.com"})
    @patch("pycommon.api.user_data.requests.post")
    def test_load_user_data_success_no_data(self, mock_post):
        """Test successful response but no data field."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True}
        mock_response.content = b'{"success": true}'
        mock_post.return_value = mock_response

        result = load_user_data(
            self.access_token, self.app_id, self.entity_type, self.item_id
        )

        assert result is None

    @patch.dict(os.environ, {"API_BASE_URL": "https://api.example.com"})
    @patch("pycommon.api.user_data.requests.post")
    def test_load_user_data_request_exception(self, mock_post):
        """Test handling of request exceptions."""
        mock_post.side_effect = requests.exceptions.RequestException("Network error")

        result = load_user_data(
            self.access_token, self.app_id, self.entity_type, self.item_id
        )

        assert result is None

    @patch.dict(os.environ, {"API_BASE_URL": "https://api.example.com"})
    @patch("pycommon.api.user_data.requests.post")
    def test_load_user_data_json_decode_error(self, mock_post):
        """Test handling of JSON decode errors."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_response.content = b"invalid json"
        mock_post.return_value = mock_response

        result = load_user_data(
            self.access_token, self.app_id, self.entity_type, self.item_id
        )

        assert result is None

    @patch.dict(os.environ, {"API_BASE_URL": "https://api.example.com"})
    @patch("pycommon.api.user_data.requests.post")
    def test_load_user_data_generic_exception(self, mock_post):
        """Test handling of generic exceptions."""
        mock_post.side_effect = Exception("Unexpected error")

        result = load_user_data(
            self.access_token, self.app_id, self.entity_type, self.item_id
        )

        assert result is None

    @patch.dict(os.environ, {"API_BASE_URL": "https://api.example.com"})
    @patch("pycommon.api.user_data.requests.post")
    @patch("builtins.print")
    def test_load_user_data_prints_messages(self, mock_print, mock_post):
        """Test that appropriate messages are printed."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True, "data": {"test": "data"}}
        mock_response.content = b'{"success": true, "data": {"test": "data"}}'
        mock_post.return_value = mock_response

        load_user_data(self.access_token, self.app_id, self.entity_type, self.item_id)

        # Check that print was called with expected messages
        print_calls = [call.args[0] for call in mock_print.call_args_list]
        assert "Initiate get user data call" in print_calls
        assert any("Response: " in call for call in print_calls)

    @patch.dict(os.environ, {"API_BASE_URL": "https://api.example.com"})
    @patch("pycommon.api.user_data.requests.post")
    @patch("builtins.print")
    def test_load_user_data_prints_error(self, mock_print, mock_post):
        """Test that error messages are printed on exception."""
        mock_post.side_effect = Exception("Test error")

        load_user_data(self.access_token, self.app_id, self.entity_type, self.item_id)

        # Check that error message was printed
        print_calls = [call.args[0] for call in mock_print.call_args_list]
        assert any(
            "Error getting user data: Test error" in call for call in print_calls
        )

    def test_load_user_data_missing_env_var(self):
        """Test behavior when API_BASE_URL environment variable is missing."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(KeyError):
                load_user_data(
                    self.access_token, self.app_id, self.entity_type, self.item_id
                )

    @patch.dict(os.environ, {"API_BASE_URL": "https://api.example.com"})
    @patch("pycommon.api.user_data.requests.post")
    def test_load_user_data_with_empty_parameters(self, mock_post):
        """Test function with empty string parameters."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True, "data": {"result": "test"}}
        mock_response.content = b'{"success": true, "data": {"result": "test"}}'
        mock_post.return_value = mock_response

        result = load_user_data("", "", "", "")

        # Verify the request was made with empty parameters
        expected_request_data = {"data": {"appId": "", "entityType": "", "itemId": ""}}
        expected_headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer ",
        }

        mock_post.assert_called_once_with(
            f"{self.api_base_url}/user-data/get",
            headers=expected_headers,
            data=json.dumps(expected_request_data),
        )

        assert result == {"result": "test"}
