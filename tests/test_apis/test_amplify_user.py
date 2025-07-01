# =============================================================================
# Tests for api/amplify_users.py
# =============================================================================

import json
import os
from unittest.mock import MagicMock, patch

import requests

from pycommon.api.amplify_users import (
    get_email_suggestions,
    get_system_ids,
    is_valid_amplify_user,
)


class TestGetEmailSuggestions:
    """Test cases for get_email_suggestions function."""

    @patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
    @patch("pycommon.api.amplify_users.requests.get")
    def test_get_email_suggestions_success_default_prefix(self, mock_get):
        """Test successful email suggestions retrieval with default prefix."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "emails": ["user1@example.com", "user2@example.com"]
        }
        mock_get.return_value = mock_response

        result = get_email_suggestions("test_token")

        assert result == ["user1@example.com", "user2@example.com"]
        mock_get.assert_called_once_with(
            "http://test-api.com/utilities/emails",
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer test_token",
            },
            params={"emailprefix": "*"},
        )

    @patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
    @patch("pycommon.api.amplify_users.requests.get")
    def test_get_email_suggestions_success_custom_prefix(self, mock_get):
        """Test successful email suggestions retrieval with custom prefix."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "emails": ["admin@example.com", "admin2@example.com"]
        }
        mock_get.return_value = mock_response

        result = get_email_suggestions("test_token", "admin")

        assert result == ["admin@example.com", "admin2@example.com"]
        mock_get.assert_called_once_with(
            "http://test-api.com/utilities/emails",
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer test_token",
            },
            params={"emailprefix": "admin"},
        )

    @patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
    @patch("pycommon.api.amplify_users.requests.get")
    def test_get_email_suggestions_empty_response(self, mock_get):
        """Test handling of empty email list in response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"emails": []}
        mock_get.return_value = mock_response

        result = get_email_suggestions("test_token", "nonexistent")

        assert result == []

    @patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
    @patch("pycommon.api.amplify_users.requests.get")
    def test_get_email_suggestions_missing_emails_key(self, mock_get):
        """Test handling of response missing 'emails' key."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"other_key": "value"}
        mock_get.return_value = mock_response

        result = get_email_suggestions("test_token")

        assert result == []

    @patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
    @patch("pycommon.api.amplify_users.requests.get")
    def test_get_email_suggestions_http_error(self, mock_get):
        """Test handling of HTTP error responses."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.content = b"Unauthorized"
        mock_get.return_value = mock_response

        result = get_email_suggestions("invalid_token")

        assert result is None

    @patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
    @patch("pycommon.api.amplify_users.requests.get")
    def test_get_email_suggestions_network_error(self, mock_get):
        """Test handling of network errors."""
        mock_get.side_effect = requests.RequestException("Network error")

        result = get_email_suggestions("test_token")

        assert result is None

    @patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
    @patch("pycommon.api.amplify_users.requests.get")
    def test_get_email_suggestions_json_decode_error(self, mock_get):
        """Test handling of JSON decode errors."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_get.return_value = mock_response

        result = get_email_suggestions("test_token")

        assert result is None

    @patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
    @patch("pycommon.api.amplify_users.requests.get")
    def test_get_email_suggestions_unexpected_error(self, mock_get):
        """Test handling of unexpected errors."""
        mock_get.side_effect = Exception("Unexpected error")

        result = get_email_suggestions("test_token")

        assert result is None


class TestGetSystemIds:
    """Test cases for get_system_ids function."""

    @patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
    @patch("pycommon.api.amplify_users.requests.get")
    def test_get_system_ids_success(self, mock_get):
        """Test successful system IDs retrieval."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "data": [
                {
                    "owner": "system1@example.com",
                    "applicationName": "App1",
                    "systemId": "sys1",
                },
                {
                    "owner": "system2@example.com",
                    "applicationName": "App2",
                    "systemId": "sys2",
                },
            ],
        }
        mock_get.return_value = mock_response

        result = get_system_ids("test_token")

        expected_data = [
            {
                "owner": "system1@example.com",
                "applicationName": "App1",
                "systemId": "sys1",
            },
            {
                "owner": "system2@example.com",
                "applicationName": "App2",
                "systemId": "sys2",
            },
        ]
        assert result == expected_data
        mock_get.assert_called_once_with(
            "http://test-api.com/apiKeys/get_system_ids",
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer test_token",
            },
        )

    @patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
    @patch("pycommon.api.amplify_users.requests.get")
    def test_get_system_ids_success_false(self, mock_get):
        """Test handling when API returns success=False."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": False,
            "message": "No system IDs found",
        }
        mock_get.return_value = mock_response

        result = get_system_ids("test_token")

        assert result is None

    @patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
    @patch("pycommon.api.amplify_users.requests.get")
    def test_get_system_ids_empty_data(self, mock_get):
        """Test handling of empty data array."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True, "data": []}
        mock_get.return_value = mock_response

        result = get_system_ids("test_token")

        assert result == []

    @patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
    @patch("pycommon.api.amplify_users.requests.get")
    def test_get_system_ids_missing_data_key(self, mock_get):
        """Test handling of response missing 'data' key."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True}
        mock_get.return_value = mock_response

        result = get_system_ids("test_token")

        assert result == []

    @patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
    @patch("pycommon.api.amplify_users.requests.get")
    def test_get_system_ids_http_error(self, mock_get):
        """Test handling of HTTP error responses."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.content = b"Forbidden"
        mock_get.return_value = mock_response

        result = get_system_ids("invalid_token")

        assert result is None

    @patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
    @patch("pycommon.api.amplify_users.requests.get")
    def test_get_system_ids_network_error(self, mock_get):
        """Test handling of network errors."""
        mock_get.side_effect = requests.RequestException("Network error")

        result = get_system_ids("test_token")

        assert result is None

    @patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
    @patch("pycommon.api.amplify_users.requests.get")
    def test_get_system_ids_json_decode_error(self, mock_get):
        """Test handling of JSON decode errors."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_get.return_value = mock_response

        result = get_system_ids("test_token")

        assert result is None

    @patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
    @patch("pycommon.api.amplify_users.requests.get")
    def test_get_system_ids_unexpected_error(self, mock_get):
        """Test handling of unexpected errors."""
        mock_get.side_effect = Exception("Unexpected error")

        result = get_system_ids("test_token")

        assert result is None


class TestIsValidAmplifyUser:
    """Test cases for is_valid_amplify_user function."""

    @patch("pycommon.api.amplify_users.get_system_ids")
    @patch("pycommon.api.amplify_users.get_email_suggestions")
    def test_is_valid_amplify_user_valid_email_in_emails(
        self, mock_get_emails, mock_get_systems
    ):
        """Test validation of a valid user email from email suggestions."""
        mock_get_emails.return_value = [
            "user1@example.com",
            "user2@example.com",
            "admin@example.com",
        ]
        mock_get_systems.return_value = [
            {"owner": "system1@example.com", "systemId": "sys1"},
        ]

        result = is_valid_amplify_user("test_token", "user1@example.com")

        assert result is True
        mock_get_emails.assert_called_once_with("test_token", "*")
        mock_get_systems.assert_called_once_with("test_token")

    @patch("pycommon.api.amplify_users.get_system_ids")
    @patch("pycommon.api.amplify_users.get_email_suggestions")
    def test_is_valid_amplify_user_valid_email_in_systems(
        self, mock_get_emails, mock_get_systems
    ):
        """Test validation of a valid user email from system users."""
        mock_get_emails.return_value = ["user1@example.com", "user2@example.com"]
        mock_get_systems.return_value = [
            {"owner": "system1@example.com", "systemId": "sys1"},
            {"owner": "system2@example.com", "systemId": "sys2"},
        ]

        result = is_valid_amplify_user("test_token", "system1@example.com")

        assert result is True

    @patch("pycommon.api.amplify_users.get_system_ids")
    @patch("pycommon.api.amplify_users.get_email_suggestions")
    def test_is_valid_amplify_user_case_insensitive(
        self, mock_get_emails, mock_get_systems
    ):
        """Test validation with case-insensitive matching."""
        mock_get_emails.return_value = ["User1@Example.com"]
        mock_get_systems.return_value = [
            {"owner": "System1@Example.com", "systemId": "sys1"},
        ]

        # Test email case insensitive
        assert is_valid_amplify_user("test_token", "user1@example.com") is True
        # Test system user case insensitive
        assert is_valid_amplify_user("test_token", "system1@example.com") is True

    @patch("pycommon.api.amplify_users.get_system_ids")
    @patch("pycommon.api.amplify_users.get_email_suggestions")
    def test_is_valid_amplify_user_invalid_email(
        self, mock_get_emails, mock_get_systems
    ):
        """Test validation of an invalid user email."""
        mock_get_emails.return_value = ["user1@example.com", "user2@example.com"]
        mock_get_systems.return_value = [
            {"owner": "system1@example.com", "systemId": "sys1"},
        ]

        result = is_valid_amplify_user("test_token", "nonexistent@example.com")

        assert result is False

    @patch("pycommon.api.amplify_users.get_system_ids")
    @patch("pycommon.api.amplify_users.get_email_suggestions")
    def test_is_valid_amplify_user_both_lists_empty(
        self, mock_get_emails, mock_get_systems
    ):
        """Test validation when both email and system lists are empty."""
        mock_get_emails.return_value = []
        mock_get_systems.return_value = []

        result = is_valid_amplify_user("test_token", "user@example.com")

        assert result is False

    @patch("pycommon.api.amplify_users.get_system_ids")
    @patch("pycommon.api.amplify_users.get_email_suggestions")
    def test_is_valid_amplify_user_emails_fail_systems_work(
        self, mock_get_emails, mock_get_systems
    ):
        """Test validation when get_email_suggestions fails but get_system_ids works."""
        mock_get_emails.return_value = None
        mock_get_systems.return_value = [
            {"owner": "system1@example.com", "systemId": "sys1"},
        ]

        result = is_valid_amplify_user("test_token", "system1@example.com")

        assert result is True

    @patch("pycommon.api.amplify_users.get_system_ids")
    @patch("pycommon.api.amplify_users.get_email_suggestions")
    def test_is_valid_amplify_user_systems_fail_emails_work(
        self, mock_get_emails, mock_get_systems
    ):
        """Test validation when get_system_ids fails but get_email_suggestions works."""
        mock_get_emails.return_value = ["user1@example.com"]
        mock_get_systems.return_value = None

        result = is_valid_amplify_user("test_token", "user1@example.com")

        assert result is True

    @patch("pycommon.api.amplify_users.get_system_ids")
    @patch("pycommon.api.amplify_users.get_email_suggestions")
    def test_is_valid_amplify_user_both_fail(self, mock_get_emails, mock_get_systems):
        """Test validation when both API calls fail."""
        mock_get_emails.return_value = None
        mock_get_systems.return_value = None

        result = is_valid_amplify_user("test_token", "user@example.com")

        assert result is False

    @patch("pycommon.api.amplify_users.get_system_ids")
    @patch("pycommon.api.amplify_users.get_email_suggestions")
    def test_is_valid_amplify_user_system_data_without_owner(
        self, mock_get_emails, mock_get_systems
    ):
        """Test validation with system data that has missing or empty owner fields."""
        mock_get_emails.return_value = ["user1@example.com"]
        mock_get_systems.return_value = [
            {"owner": "system1@example.com", "systemId": "sys1"},
            {"systemId": "sys2"},  # Missing owner
            {"owner": "", "systemId": "sys3"},  # Empty owner
            {"owner": "system2@example.com", "systemId": "sys4"},
        ]

        # Should find system1@example.com and system2@example.com but ignore the others
        assert is_valid_amplify_user("test_token", "system1@example.com") is True
        assert is_valid_amplify_user("test_token", "system2@example.com") is True
        assert is_valid_amplify_user("test_token", "nonexistent@example.com") is False

    @patch("pycommon.api.amplify_users.get_system_ids")
    @patch("pycommon.api.amplify_users.get_email_suggestions")
    def test_is_valid_amplify_user_duplicate_emails(
        self, mock_get_emails, mock_get_systems
    ):
        """Test validation with duplicate emails across both sources."""
        mock_get_emails.return_value = ["user1@example.com", "duplicate@example.com"]
        mock_get_systems.return_value = [
            {"owner": "duplicate@example.com", "systemId": "sys1"},
            {"owner": "system1@example.com", "systemId": "sys2"},
        ]

        # Should still work even with duplicates
        assert is_valid_amplify_user("test_token", "duplicate@example.com") is True
        assert is_valid_amplify_user("test_token", "user1@example.com") is True
        assert is_valid_amplify_user("test_token", "system1@example.com") is True
