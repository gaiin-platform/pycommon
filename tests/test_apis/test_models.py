import os
from unittest.mock import Mock, patch

import requests

from pycommon.api.models import get_default_models


class TestGetDefaultModels:
    """Test cases for the get_default_models function."""

    @patch.dict(os.environ, {"API_BASE_URL": "https://api.example.com"})
    @patch("pycommon.api.models.requests.get")
    def test_get_default_models_successful_response(self, mock_get):
        """Test get_default_models with successful response containing all fields."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "data": {
                "user": "gpt-4",
                "cheapest": "gpt-3.5-turbo",
                "agent": "claude-3-sonnet",
                "advanced": "gpt-4-turbo",
            },
        }
        mock_get.return_value = mock_response

        result = get_default_models("test_token")

        expected = {
            "user_model": "gpt-4",
            "cheapest_model": "gpt-3.5-turbo",
            "agent_model": "claude-3-sonnet",
            "advanced_model": "gpt-4-turbo",
        }
        assert result == expected

        mock_get.assert_called_once_with(
            "https://api.example.com/default_models",
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer test_token",
            },
        )

    @patch.dict(os.environ, {"API_BASE_URL": "https://api.example.com"})
    @patch("pycommon.api.models.requests.get")
    def test_get_default_models_with_minimal_data(self, mock_get):
        """Test get_default_models with minimal response data (only user field)."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True, "data": {"user": "gpt-4"}}
        mock_get.return_value = mock_response

        result = get_default_models("test_token")

        expected = {
            "user_model": "gpt-4",
            "cheapest_model": "gpt-4",  # Falls back to user model
            "agent_model": "gpt-4",  # Falls back to cheapest (user model)
            "advanced_model": "gpt-4",  # Falls back to user model
        }
        assert result == expected

    @patch.dict(os.environ, {"API_BASE_URL": "https://api.example.com"})
    @patch("pycommon.api.models.requests.get")
    def test_get_default_models_with_partial_data(self, mock_get):
        """Test get_default_models with partial response data."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "data": {"user": "gpt-4", "cheapest": "gpt-3.5-turbo"},
        }
        mock_get.return_value = mock_response

        result = get_default_models("test_token")

        expected = {
            "user_model": "gpt-4",
            "cheapest_model": "gpt-3.5-turbo",
            "agent_model": "gpt-3.5-turbo",  # Falls back to cheapest
            "advanced_model": "gpt-4",  # Falls back to user model
        }
        assert result == expected

    @patch.dict(os.environ, {"API_BASE_URL": "https://api.example.com"})
    @patch("pycommon.api.models.requests.get")
    @patch("builtins.print")
    def test_get_default_models_response_not_success(self, mock_print, mock_get):
        """Test get_default_models when response success is False."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": False, "data": {}}
        mock_get.return_value = mock_response

        result = get_default_models("test_token")

        assert result == {}
        mock_print.assert_called_once_with("Missing data in default models response")

    @patch.dict(os.environ, {"API_BASE_URL": "https://api.example.com"})
    @patch("pycommon.api.models.requests.get")
    @patch("builtins.print")
    def test_get_default_models_missing_data_field(self, mock_print, mock_get):
        """Test get_default_models when response is missing data field."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True}
        mock_get.return_value = mock_response

        result = get_default_models("test_token")

        assert result == {}
        mock_print.assert_called_once_with("Missing data in default models response")

    @patch.dict(os.environ, {"API_BASE_URL": "https://api.example.com"})
    @patch("pycommon.api.models.requests.get")
    @patch("builtins.print")
    def test_get_default_models_empty_response(self, mock_print, mock_get):
        """Test get_default_models when response is empty."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_get.return_value = mock_response

        result = get_default_models("test_token")

        assert result == {}
        mock_print.assert_called_once_with("Missing data in default models response")

    @patch.dict(os.environ, {"API_BASE_URL": "https://api.example.com"})
    @patch("pycommon.api.models.requests.get")
    @patch("builtins.print")
    def test_get_default_models_none_response(self, mock_print, mock_get):
        """Test get_default_models when response json is None."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = None
        mock_get.return_value = mock_response

        result = get_default_models("test_token")

        assert result == {}
        mock_print.assert_called_once_with("Missing data in default models response")

    @patch.dict(os.environ, {"API_BASE_URL": "https://api.example.com"})
    @patch("pycommon.api.models.requests.get")
    @patch("builtins.print")
    def test_get_default_models_missing_user_model(self, mock_print, mock_get):
        """Test get_default_models when user model is missing from data."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "data": {"cheapest": "gpt-3.5-turbo"},
        }
        mock_get.return_value = mock_response

        result = get_default_models("test_token")

        assert result == {}
        mock_print.assert_called_once_with("Missing default model")

    @patch.dict(os.environ, {"API_BASE_URL": "https://api.example.com"})
    @patch("pycommon.api.models.requests.get")
    @patch("builtins.print")
    def test_get_default_models_empty_user_model(self, mock_print, mock_get):
        """Test get_default_models when user model is empty string."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True, "data": {"user": ""}}
        mock_get.return_value = mock_response

        result = get_default_models("test_token")

        assert result == {}
        mock_print.assert_called_once_with("Missing default model")

    @patch.dict(os.environ, {"API_BASE_URL": "https://api.example.com"})
    @patch("pycommon.api.models.requests.get")
    @patch("builtins.print")
    def test_get_default_models_none_user_model(self, mock_print, mock_get):
        """Test get_default_models when user model is None."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True, "data": {"user": None}}
        mock_get.return_value = mock_response

        result = get_default_models("test_token")

        assert result == {}
        mock_print.assert_called_once_with("Missing default model")

    @patch.dict(os.environ, {"API_BASE_URL": "https://api.example.com"})
    @patch("pycommon.api.models.requests.get")
    @patch("builtins.print")
    def test_get_default_models_http_error(self, mock_print, mock_get):
        """Test get_default_models when HTTP error occurs."""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "404 Not Found"
        )
        mock_get.return_value = mock_response

        result = get_default_models("test_token")

        assert result == {}
        mock_print.assert_called_once_with(
            "Error fetching default models: 404 Not Found"
        )

    @patch.dict(os.environ, {"API_BASE_URL": "https://api.example.com"})
    @patch("pycommon.api.models.requests.get")
    @patch("builtins.print")
    def test_get_default_models_request_exception(self, mock_print, mock_get):
        """Test get_default_models when requests exception occurs."""
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection timeout")

        result = get_default_models("test_token")

        assert result == {}
        mock_print.assert_called_once_with(
            "Error fetching default models: Connection timeout"
        )

    @patch.dict(os.environ, {"API_BASE_URL": "https://api.example.com"})
    @patch("pycommon.api.models.requests.get")
    def test_get_default_models_with_none_cheapest(self, mock_get):
        """Test get_default_models when cheapest model is None."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "data": {"user": "gpt-4", "cheapest": None, "agent": "claude-3-sonnet"},
        }
        mock_get.return_value = mock_response

        result = get_default_models("test_token")

        expected = {
            "user_model": "gpt-4",
            "cheapest_model": "gpt-4",  # Falls back to user model
            "agent_model": "claude-3-sonnet",
            "advanced_model": "gpt-4",
        }
        assert result == expected

    @patch.dict(os.environ, {"API_BASE_URL": "https://api.example.com"})
    @patch("pycommon.api.models.requests.get")
    def test_get_default_models_with_empty_cheapest(self, mock_get):
        """Test get_default_models when cheapest model is empty string."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "data": {"user": "gpt-4", "cheapest": "", "advanced": "gpt-4-turbo"},
        }
        mock_get.return_value = mock_response

        result = get_default_models("test_token")

        expected = {
            "user_model": "gpt-4",
            "cheapest_model": "gpt-4",  # Falls back to user model
            "agent_model": "gpt-4",  # Falls back to cheapest (user model)
            "advanced_model": "gpt-4-turbo",
        }
        assert result == expected
