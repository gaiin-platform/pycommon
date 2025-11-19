# =============================================================================
# Tests for api/amplify_users.py
# =============================================================================

import json
import os
from unittest.mock import MagicMock, patch

import requests
from botocore.exceptions import ClientError

from pycommon.api.amplify_users import (
    are_valid_amplify_users,
    get_email_suggestions,
    get_system_ids,
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
            "user_email_map": {
                "user1@example.com": "user1@example.com",
                "user2@example.com": "user2@example.com",
            }
        }
        mock_get.return_value = mock_response

        result = get_email_suggestions("test_token")

        assert result == {
            "user1@example.com": "user1@example.com",
            "user2@example.com": "user2@example.com",
        }
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
            "user_email_map": {
                "admin@example.com": "admin@example.com",
                "admin2@example.com": "admin2@example.com",
            }
        }
        mock_get.return_value = mock_response

        result = get_email_suggestions("test_token", "admin")

        assert result == {
            "admin@example.com": "admin@example.com",
            "admin2@example.com": "admin2@example.com",
        }
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
    def test_get_email_suggestions_success_nested_structure(self, mock_get):
        """Test successful email suggestions retrieval
        with nested JSON structure."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "statusCode": 200,
            "body": '{"user_email_map": {"user1@example.com": "user1@example.com", \
                 "user2@example.com": "user2@example.com"}}',
        }
        mock_get.return_value = mock_response

        result = get_email_suggestions("test_token")

        assert result == {
            "user1@example.com": "user1@example.com",
            "user2@example.com": "user2@example.com",
        }

    @patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
    @patch("pycommon.api.amplify_users.requests.get")
    def test_get_email_suggestions_nested_structure_empty_user_email_map(
        self, mock_get
    ):
        """Test nested JSON structure with empty user_email_map."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "statusCode": 200,
            "body": '{"user_email_map": {}}',
        }
        mock_get.return_value = mock_response

        result = get_email_suggestions("test_token")

        assert result == {}

    @patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
    @patch("pycommon.api.amplify_users.requests.get")
    def test_get_email_suggestions_nested_structure_missing_user_email_map(
        self, mock_get
    ):
        """Test nested JSON structure with missing user_email_map key."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "statusCode": 200,
            "body": '{"other_key": "value"}',
        }
        mock_get.return_value = mock_response

        result = get_email_suggestions("test_token")

        assert result == {}

    @patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
    @patch("pycommon.api.amplify_users.requests.get")
    def test_get_email_suggestions_nested_structure_invalid_json_body(self, mock_get):
        """Test nested JSON structure with invalid JSON in body field."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_get.return_value = mock_response

        result = get_email_suggestions("test_token")

        assert result is None

    @patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
    @patch("pycommon.api.amplify_users.requests.get")
    def test_get_email_suggestions_empty_response(self, mock_get):
        """Test handling of empty user_email_map in response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"user_email_map": {}}
        mock_get.return_value = mock_response

        result = get_email_suggestions("test_token", "nonexistent")

        assert result == {}

    @patch.dict(os.environ, {"API_BASE_URL": "http://test-api.com"})
    @patch("pycommon.api.amplify_users.requests.get")
    def test_get_email_suggestions_missing_user_email_map_key(self, mock_get):
        """Test handling of response missing 'user_email_map' key."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"other_key": "value"}
        mock_get.return_value = mock_response

        result = get_email_suggestions("test_token")

        assert result == {}

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


class TestAreValidAmplifyUsersOld:
    """Test cases for are_valid_amplify_users function - legacy single email tests."""

    @patch.dict(
        os.environ,
        {
            "COGNITO_USERS_DYNAMODB_TABLE": "test-cognito-table",
            "API_KEYS_DYNAMODB_TABLE": "test-api-keys-table",
        },
    )
    @patch("pycommon.api.amplify_users.boto3.resource")
    @patch("pycommon.api.amplify_users.get_system_ids")
    def test_are_valid_amplify_users_valid_email_in_emails(
        self, mock_get_systems, mock_boto3_resource
    ):
        """Test validation of a valid user email from email suggestions."""
        # Mock DynamoDB table
        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": {"user_id": "user1@example.com"}}
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        mock_get_systems.return_value = [
            {"owner": "system1@example.com", "systemId": "sys1"},
        ]

        valid, invalid = are_valid_amplify_users("test_token", ["user1@example.com"])

        assert valid == ["user1@example.com"]
        assert invalid == []
        mock_get_systems.assert_called_once_with("test_token")

    @patch.dict(
        os.environ,
        {
            "COGNITO_USERS_DYNAMODB_TABLE": "test-cognito-table",
            "API_KEYS_DYNAMODB_TABLE": "test-api-keys-table",
        },
    )
    @patch("pycommon.api.amplify_users.boto3.resource")
    @patch("pycommon.api.amplify_users.get_system_ids")
    @patch("pycommon.api.amplify_users.get_email_suggestions")
    def test_are_valid_amplify_users_valid_email_in_systems(
        self, mock_get_emails, mock_get_systems, mock_boto3_resource
    ):
        """Test validation of a valid user email from system users."""
        # Mock DynamoDB table
        mock_table = MagicMock()
        mock_table.get_item.return_value = {}
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        mock_get_emails.return_value = {
            "user1@example.com": "user1@example.com",
            "user2@example.com": "user2@example.com",
        }
        mock_get_systems.return_value = [
            {"owner": "system1@example.com", "systemId": "sys1"},
            {"owner": "system2@example.com", "systemId": "sys2"},
        ]

        valid, invalid = are_valid_amplify_users("test_token", ["system1@example.com"])

        assert valid == ["system1@example.com"]
        assert invalid == []

    @patch.dict(
        os.environ,
        {
            "COGNITO_USERS_DYNAMODB_TABLE": "test-cognito-table",
            "API_KEYS_DYNAMODB_TABLE": "test-api-keys-table",
        },
    )
    @patch("pycommon.api.amplify_users.boto3.resource")
    @patch("pycommon.api.amplify_users.get_system_ids")
    @patch("pycommon.api.amplify_users.get_email_suggestions")
    def test_are_valid_amplify_users_case_insensitive(
        self, mock_get_emails, mock_get_systems, mock_boto3_resource
    ):
        """Test validation with case-insensitive matching."""
        # Mock DynamoDB table
        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": {"user_id": "user1@example.com"}}
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        mock_get_emails.return_value = {"User1@Example.com": "User1@Example.com"}
        mock_get_systems.return_value = [
            {"owner": "System1@Example.com", "systemId": "sys1"},
        ]

        # Test email case insensitive
        valid, invalid = are_valid_amplify_users("test_token", ["user1@example.com"])
        assert valid == ["user1@example.com"]
        assert invalid == []

        # Test system user case insensitive
        valid, invalid = are_valid_amplify_users("test_token", ["system1@example.com"])
        assert valid == ["system1@example.com"]
        assert invalid == []

    @patch.dict(
        os.environ,
        {
            "COGNITO_USERS_DYNAMODB_TABLE": "test-cognito-table",
            "API_KEYS_DYNAMODB_TABLE": "test-api-keys-table",
        },
    )
    @patch("pycommon.api.amplify_users.boto3.resource")
    @patch("pycommon.api.amplify_users.get_system_ids")
    @patch("pycommon.api.amplify_users.get_email_suggestions")
    def test_are_valid_amplify_users_invalid_email(
        self, mock_get_emails, mock_get_systems, mock_boto3_resource
    ):
        """Test validation of an invalid user email."""
        # Mock DynamoDB table - return empty for nonexistent user
        mock_table = MagicMock()
        mock_table.get_item.return_value = {}
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        mock_get_emails.return_value = {
            "user1@example.com": "user1@example.com",
            "user2@example.com": "user2@example.com",
        }
        mock_get_systems.return_value = [
            {"owner": "system1@example.com", "systemId": "sys1"},
        ]

        valid, invalid = are_valid_amplify_users(
            "test_token", ["nonexistent@example.com"]
        )

        assert valid == []
        assert invalid == ["nonexistent@example.com"]

    @patch.dict(
        os.environ,
        {
            "COGNITO_USERS_DYNAMODB_TABLE": "test-cognito-table",
            "API_KEYS_DYNAMODB_TABLE": "test-api-keys-table",
        },
    )
    @patch("pycommon.api.amplify_users.boto3.resource")
    @patch("pycommon.api.amplify_users.get_system_ids")
    @patch("pycommon.api.amplify_users.get_email_suggestions")
    def test_are_valid_amplify_users_both_lists_empty(
        self, mock_get_emails, mock_get_systems, mock_boto3_resource
    ):
        """Test validation when both email and system lists are empty."""
        # Mock DynamoDB table - return empty for user
        mock_table = MagicMock()
        mock_table.get_item.return_value = {}
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        mock_get_emails.return_value = {}
        mock_get_systems.return_value = []

        valid, invalid = are_valid_amplify_users("test_token", ["user@example.com"])

        assert valid == []
        assert invalid == ["user@example.com"]

    @patch.dict(
        os.environ,
        {
            "COGNITO_USERS_DYNAMODB_TABLE": "test-cognito-table",
            "API_KEYS_DYNAMODB_TABLE": "test-api-keys-table",
        },
    )
    @patch("pycommon.api.amplify_users.boto3.resource")
    @patch("pycommon.api.amplify_users.get_system_ids")
    @patch("pycommon.api.amplify_users.get_email_suggestions")
    def test_are_valid_amplify_users_emails_fail_systems_work(
        self, mock_get_emails, mock_get_systems, mock_boto3_resource
    ):
        """Test validation when get_email_suggestions fails but get_system_ids works."""
        # Mock DynamoDB table
        mock_table = MagicMock()
        mock_table.get_item.return_value = {}
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        mock_get_emails.return_value = None
        mock_get_systems.return_value = [
            {"owner": "system1@example.com", "systemId": "sys1"},
        ]

        valid, invalid = are_valid_amplify_users("test_token", ["system1@example.com"])

        assert valid == ["system1@example.com"]
        assert invalid == []

    @patch.dict(
        os.environ,
        {
            "COGNITO_USERS_DYNAMODB_TABLE": "test-cognito-table",
            "API_KEYS_DYNAMODB_TABLE": "test-api-keys-table",
        },
    )
    @patch("pycommon.api.amplify_users.boto3.resource")
    @patch("pycommon.api.amplify_users.get_system_ids")
    def test_are_valid_amplify_users_systems_fail_emails_work(
        self, mock_get_systems, mock_boto3_resource
    ):
        """Test validation when get_system_ids fails but get_email_suggestions works."""
        # Mock DynamoDB table - return item for valid user
        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": {"user_id": "user1@example.com"}}
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        mock_get_systems.return_value = None

        valid, invalid = are_valid_amplify_users("test_token", ["user1@example.com"])

        assert valid == ["user1@example.com"]
        assert invalid == []

    @patch.dict(
        os.environ,
        {
            "COGNITO_USERS_DYNAMODB_TABLE": "test-cognito-table",
            "API_KEYS_DYNAMODB_TABLE": "test-api-keys-table",
        },
    )
    @patch("pycommon.api.amplify_users.boto3.resource")
    @patch("pycommon.api.amplify_users.get_system_ids")
    @patch("pycommon.api.amplify_users.get_email_suggestions")
    def test_are_valid_amplify_users_both_fail(
        self, mock_get_emails, mock_get_systems, mock_boto3_resource
    ):
        """Test validation when both API calls fail."""
        # Mock DynamoDB table - return empty for user
        mock_table = MagicMock()
        mock_table.get_item.return_value = {}
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        mock_get_emails.return_value = None
        mock_get_systems.return_value = None

        valid, invalid = are_valid_amplify_users("test_token", ["user@example.com"])

        assert valid == []
        assert invalid == ["user@example.com"]

    @patch.dict(
        os.environ,
        {
            "COGNITO_USERS_DYNAMODB_TABLE": "test-cognito-table",
            "API_KEYS_DYNAMODB_TABLE": "test-api-keys-table",
        },
    )
    @patch("pycommon.api.amplify_users.boto3.resource")
    @patch("pycommon.api.amplify_users.get_system_ids")
    def test_are_valid_amplify_users_system_data_without_owner(
        self, mock_get_systems, mock_boto3_resource
    ):
        """Test validation with system data that has missing or empty owner fields."""
        # Mock DynamoDB table
        mock_table = MagicMock()
        mock_table.get_item.return_value = {}
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        mock_get_systems.return_value = [
            {"owner": "system1@example.com", "systemId": "sys1"},
            {"systemId": "sys2"},  # Missing owner
            {"owner": "", "systemId": "sys3"},  # Empty owner
            {"owner": "system2@example.com", "systemId": "sys4"},
        ]

        # Should find system1@example.com and system2@example.com but ignore the others
        valid, invalid = are_valid_amplify_users("test_token", ["system1@example.com"])
        assert valid == ["system1@example.com"]
        assert invalid == []

        valid, invalid = are_valid_amplify_users("test_token", ["system2@example.com"])
        assert valid == ["system2@example.com"]
        assert invalid == []

        valid, invalid = are_valid_amplify_users(
            "test_token", ["nonexistent@example.com"]
        )
        assert valid == []
        assert invalid == ["nonexistent@example.com"]

    @patch.dict(
        os.environ,
        {
            "COGNITO_USERS_DYNAMODB_TABLE": "test-cognito-table",
            "API_KEYS_DYNAMODB_TABLE": "test-api-keys-table",
        },
    )
    @patch("pycommon.api.amplify_users.boto3.resource")
    @patch("pycommon.api.amplify_users.get_system_ids")
    def test_are_valid_amplify_users_duplicate_emails(
        self, mock_get_systems, mock_boto3_resource
    ):
        """Test validation with duplicate emails across both sources."""
        # Mock DynamoDB table
        mock_table = MagicMock()

        def get_item_side_effect(**kwargs):
            user_id = kwargs.get("Key", {}).get("user_id", "")
            if user_id in ["user1@example.com"]:
                return {"Item": {"user_id": user_id}}
            return {}

        mock_table.get_item.side_effect = get_item_side_effect
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        mock_get_systems.return_value = [
            {"owner": "duplicate@example.com", "systemId": "sys1"},
            {"owner": "system1@example.com", "systemId": "sys2"},
        ]

        # Should still work even with duplicates
        valid, invalid = are_valid_amplify_users(
            "test_token", ["duplicate@example.com"]
        )
        assert valid == ["duplicate@example.com"]
        assert invalid == []

        valid, invalid = are_valid_amplify_users("test_token", ["user1@example.com"])
        assert valid == ["user1@example.com"]
        assert invalid == []

        valid, invalid = are_valid_amplify_users("test_token", ["system1@example.com"])
        assert valid == ["system1@example.com"]
        assert invalid == []


class TestAreValidAmplifyUsers:
    """Test cases for are_valid_amplify_users function."""

    @patch.dict(
        os.environ,
        {
            "COGNITO_USERS_DYNAMODB_TABLE": "test-cognito-table",
            "API_KEYS_DYNAMODB_TABLE": "test-api-keys-table",
        },
    )
    @patch("pycommon.api.amplify_users.boto3.resource")
    @patch("pycommon.api.amplify_users.get_system_ids")
    def test_are_valid_amplify_users_all_valid_emails(
        self, mock_get_systems, mock_boto3_resource
    ):
        """Test validation when all emails are valid."""
        # Mock DynamoDB table - return item for valid user
        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": {"user_id": "user1@example.com"}}
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        mock_get_systems.return_value = [
            {"owner": "system1@example.com", "systemId": "sys1"},
        ]

        valid, invalid = are_valid_amplify_users(
            "test_token", ["user1@example.com", "system1@example.com"]
        )

        assert valid == ["user1@example.com", "system1@example.com"]
        assert invalid == []
        mock_get_systems.assert_called_once_with("test_token")

    @patch.dict(
        os.environ,
        {
            "COGNITO_USERS_DYNAMODB_TABLE": "test-cognito-table",
            "API_KEYS_DYNAMODB_TABLE": "test-api-keys-table",
        },
    )
    @patch("pycommon.api.amplify_users.boto3.resource")
    @patch("pycommon.api.amplify_users.get_system_ids")
    def test_are_valid_amplify_users_all_invalid_emails(
        self, mock_get_systems, mock_boto3_resource
    ):
        """Test validation when all emails are invalid."""
        # Mock DynamoDB table - return empty for invalid users
        mock_table = MagicMock()
        mock_table.get_item.return_value = {}
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        mock_get_systems.return_value = [
            {"owner": "system1@example.com", "systemId": "sys1"},
        ]

        valid, invalid = are_valid_amplify_users(
            "test_token", ["invalid1@example.com", "invalid2@example.com"]
        )

        assert valid == []
        assert invalid == ["invalid1@example.com", "invalid2@example.com"]

    @patch.dict(
        os.environ,
        {
            "COGNITO_USERS_DYNAMODB_TABLE": "test-cognito-table",
            "API_KEYS_DYNAMODB_TABLE": "test-api-keys-table",
        },
    )
    @patch("pycommon.api.amplify_users.boto3.resource")
    @patch("pycommon.api.amplify_users.get_system_ids")
    def test_are_valid_amplify_users_mixed_validity(
        self, mock_get_systems, mock_boto3_resource
    ):
        """Test validation with mix of valid and invalid emails."""
        # Mock DynamoDB table - user1 exists, invalid doesn't
        mock_table = MagicMock()

        def get_item_side_effect(**kwargs):
            user_id = kwargs.get("Key", {}).get("user_id", "")
            if user_id in ["user1@example.com"]:
                return {"Item": {"user_id": user_id}}
            return {}

        mock_table.get_item.side_effect = get_item_side_effect
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        mock_get_systems.return_value = [
            {"owner": "system1@example.com", "systemId": "sys1"},
        ]

        valid, invalid = are_valid_amplify_users(
            "test_token",
            ["user1@example.com", "invalid@example.com", "system1@example.com"],
        )

        assert valid == ["user1@example.com", "system1@example.com"]
        assert invalid == ["invalid@example.com"]

    @patch.dict(
        os.environ,
        {
            "COGNITO_USERS_DYNAMODB_TABLE": "test-cognito-table",
            "API_KEYS_DYNAMODB_TABLE": "test-api-keys-table",
        },
    )
    @patch("pycommon.api.amplify_users.boto3.resource")
    @patch("pycommon.api.amplify_users.get_system_ids")
    @patch("pycommon.api.amplify_users.get_email_suggestions")
    def test_are_valid_amplify_users_case_insensitive(
        self, mock_get_emails, mock_get_systems, mock_boto3_resource
    ):
        """Test validation with case-insensitive matching."""
        # Mock DynamoDB table
        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": {"user_id": "user1@example.com"}}
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        mock_get_emails.return_value = {}
        mock_get_systems.return_value = [
            {"owner": "System1@Example.com", "systemId": "sys1"},
        ]

        valid, invalid = are_valid_amplify_users(
            "test_token", ["user1@example.com", "system1@example.com"]
        )

        assert valid == ["user1@example.com", "system1@example.com"]
        assert invalid == []

    @patch.dict(
        os.environ,
        {
            "COGNITO_USERS_DYNAMODB_TABLE": "test-cognito-table",
            "API_KEYS_DYNAMODB_TABLE": "test-api-keys-table",
        },
    )
    @patch("pycommon.api.amplify_users.boto3.resource")
    @patch("pycommon.api.amplify_users.get_system_ids")
    @patch("pycommon.api.amplify_users.get_email_suggestions")
    def test_are_valid_amplify_users_empty_input(
        self, mock_get_emails, mock_get_systems, mock_boto3_resource
    ):
        """Test validation with empty email list."""
        # Mock DynamoDB table
        mock_table = MagicMock()
        mock_table.get_item.return_value = {}
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        mock_get_emails.return_value = {}
        mock_get_systems.return_value = [
            {"owner": "system1@example.com", "systemId": "sys1"},
        ]

        valid, invalid = are_valid_amplify_users("test_token", [])

        assert valid == []
        assert invalid == []

    @patch.dict(
        os.environ,
        {
            "COGNITO_USERS_DYNAMODB_TABLE": "test-cognito-table",
            "API_KEYS_DYNAMODB_TABLE": "test-api-keys-table",
        },
    )
    @patch("pycommon.api.amplify_users.boto3.resource")
    @patch("pycommon.api.amplify_users.get_system_ids")
    @patch("pycommon.api.amplify_users.get_email_suggestions")
    def test_are_valid_amplify_users_emails_fail_systems_work(
        self, mock_get_emails, mock_get_systems, mock_boto3_resource
    ):
        """Test validation when get_email_suggestions fails but get_system_ids works."""
        # Mock DynamoDB table
        mock_table = MagicMock()
        mock_table.get_item.return_value = {}
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        mock_get_systems.return_value = [
            {"owner": "system1@example.com", "systemId": "sys1"},
        ]

        valid, invalid = are_valid_amplify_users(
            "test_token", ["system1@example.com", "invalid@example.com"]
        )

        assert valid == ["system1@example.com"]
        assert invalid == ["invalid@example.com"]

    @patch.dict(
        os.environ,
        {
            "COGNITO_USERS_DYNAMODB_TABLE": "test-cognito-table",
            "API_KEYS_DYNAMODB_TABLE": "test-api-keys-table",
        },
    )
    @patch("pycommon.api.amplify_users.boto3.resource")
    @patch("pycommon.api.amplify_users.get_system_ids")
    def test_are_valid_amplify_users_systems_fail_emails_work(
        self, mock_get_systems, mock_boto3_resource
    ):
        """Test validation when get_system_ids fails but get_email_suggestions works."""
        # Mock DynamoDB table
        mock_table = MagicMock()

        def get_item_side_effect(**kwargs):
            user_id = kwargs.get("Key", {}).get("user_id", "")
            if user_id in ["user1@example.com"]:
                return {"Item": {"user_id": user_id}}
            return {}

        mock_table.get_item.side_effect = get_item_side_effect
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        mock_get_systems.return_value = None

        valid, invalid = are_valid_amplify_users(
            "test_token", ["user1@example.com", "invalid@example.com"]
        )

        assert valid == ["user1@example.com"]
        assert invalid == ["invalid@example.com"]

    @patch.dict(
        os.environ,
        {
            "COGNITO_USERS_DYNAMODB_TABLE": "test-cognito-table",
            "API_KEYS_DYNAMODB_TABLE": "test-api-keys-table",
        },
    )
    @patch("pycommon.api.amplify_users.boto3.resource")
    @patch("pycommon.api.amplify_users.get_system_ids")
    @patch("pycommon.api.amplify_users.get_email_suggestions")
    def test_are_valid_amplify_users_both_fail(
        self, mock_get_emails, mock_get_systems, mock_boto3_resource
    ):
        """Test validation when both API calls fail."""
        # Mock DynamoDB table - return empty for user
        mock_table = MagicMock()
        mock_table.get_item.return_value = {}
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        mock_get_emails.return_value = None
        mock_get_systems.return_value = None

        valid, invalid = are_valid_amplify_users(
            "test_token", ["user@example.com", "another@example.com"]
        )

        assert valid == []
        assert invalid == ["user@example.com", "another@example.com"]

    @patch.dict(
        os.environ,
        {
            "COGNITO_USERS_DYNAMODB_TABLE": "test-cognito-table",
            "API_KEYS_DYNAMODB_TABLE": "test-api-keys-table",
        },
    )
    @patch("pycommon.api.amplify_users.boto3.resource")
    @patch("pycommon.api.amplify_users.get_system_ids")
    def test_are_valid_amplify_users_system_data_without_owner(
        self, mock_get_systems, mock_boto3_resource
    ):
        """Test validation with system data that has missing or empty owner fields."""
        # Mock DynamoDB table
        mock_table = MagicMock()

        def get_item_side_effect(**kwargs):
            user_id = kwargs.get("Key", {}).get("user_id", "")
            if user_id in ["user1@example.com"]:
                return {"Item": {"user_id": user_id}}
            return {}

        mock_table.get_item.side_effect = get_item_side_effect
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        mock_get_systems.return_value = [
            {"owner": "system1@example.com", "systemId": "sys1"},
            {"systemId": "sys2"},  # Missing owner
            {"owner": "", "systemId": "sys3"},  # Empty owner
            {"owner": "system2@example.com", "systemId": "sys4"},
        ]

        valid, invalid = are_valid_amplify_users(
            "test_token",
            [
                "user1@example.com",
                "system1@example.com",
                "system2@example.com",
                "invalid@example.com",
            ],
        )

        assert valid == [
            "user1@example.com",
            "system1@example.com",
            "system2@example.com",
        ]
        assert invalid == ["invalid@example.com"]

    @patch.dict(
        os.environ,
        {
            "COGNITO_USERS_DYNAMODB_TABLE": "test-cognito-table",
            "API_KEYS_DYNAMODB_TABLE": "test-api-keys-table",
        },
    )
    @patch("pycommon.api.amplify_users.boto3.resource")
    @patch("pycommon.api.amplify_users.get_system_ids")
    @patch("pycommon.api.amplify_users.get_email_suggestions")
    def test_are_valid_amplify_users_duplicate_emails_in_input(
        self, mock_get_emails, mock_get_systems, mock_boto3_resource
    ):
        """Test validation with duplicate emails in input."""
        # Mock DynamoDB table
        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": {"user_id": "user1@example.com"}}
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        mock_get_emails.return_value = {}
        mock_get_systems.return_value = [
            {"owner": "system1@example.com", "systemId": "sys1"},
        ]

        valid, invalid = are_valid_amplify_users(
            "test_token",
            [
                "user1@example.com",
                "user1@example.com",
                "system1@example.com",
                "system1@example.com",
            ],
        )

        # Should handle duplicates by including them in results
        assert valid == [
            "user1@example.com",
            "user1@example.com",
            "system1@example.com",
            "system1@example.com",
        ]
        assert invalid == []

    @patch.dict(
        os.environ,
        {
            "COGNITO_USERS_DYNAMODB_TABLE": "test-cognito-table",
            "API_KEYS_DYNAMODB_TABLE": "test-api-keys-table",
        },
    )
    @patch("pycommon.api.amplify_users.boto3.resource")
    @patch("pycommon.api.amplify_users.get_system_ids")
    def test_are_valid_amplify_users_duplicate_emails_across_sources(
        self, mock_get_systems, mock_boto3_resource
    ):
        """Test validation with duplicate emails across
        email suggestions and system users."""
        # Mock DynamoDB table
        mock_table = MagicMock()

        def get_item_side_effect(**kwargs):
            user_id = kwargs.get("Key", {}).get("user_id", "")
            if user_id in ["user1@example.com"]:
                return {"Item": {"user_id": user_id}}
            return {}

        mock_table.get_item.side_effect = get_item_side_effect
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        mock_get_systems.return_value = [
            {"owner": "duplicate@example.com", "systemId": "sys1"},
            {"owner": "system1@example.com", "systemId": "sys2"},
        ]

        valid, invalid = are_valid_amplify_users(
            "test_token",
            [
                "duplicate@example.com",
                "user1@example.com",
                "system1@example.com",
                "invalid@example.com",
            ],
        )

        assert valid == [
            "duplicate@example.com",
            "user1@example.com",
            "system1@example.com",
        ]
        assert invalid == ["invalid@example.com"]

    @patch.dict(
        os.environ,
        {
            "COGNITO_USERS_DYNAMODB_TABLE": "test-cognito-table",
            "API_KEYS_DYNAMODB_TABLE": "test-api-keys-table",
        },
    )
    @patch("pycommon.api.amplify_users.boto3.resource")
    @patch("pycommon.api.amplify_users.get_system_ids")
    def test_are_valid_amplify_users_dynamodb_error(
        self, mock_get_systems, mock_boto3_resource
    ):
        """Test validation when DynamoDB throws a ClientError."""
        # Mock DynamoDB table to raise ClientError
        mock_table = MagicMock()
        mock_table.get_item.side_effect = ClientError(
            {"Error": {"Message": "Access denied"}}, "GetItem"
        )
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3_resource.return_value = mock_dynamodb

        mock_get_systems.return_value = []

        valid, invalid = are_valid_amplify_users("test_token", ["test@example.com"])

        assert valid == []
        assert invalid == ["test@example.com"]

    @patch.dict(
        os.environ,
        {
            "COGNITO_USERS_DYNAMODB_TABLE": "test-cognito-table",
            "API_KEYS_DYNAMODB_TABLE": "test-api-keys-table",
        },
    )
    @patch("pycommon.api.amplify_users.boto3.resource")
    @patch("pycommon.api.amplify_users.get_system_ids")
    def test_are_valid_amplify_users_group_system_id_valid(
        self, mock_get_systems, mock_boto3_resource
    ):
        """Test validation of valid group system ID."""
        # Mock DynamoDB tables
        mock_cognito_table = MagicMock()
        mock_cognito_table.get_item.return_value = {}

        mock_api_keys_table = MagicMock()
        mock_api_keys_table.get_item.return_value = {
            "Item": {
                "api_owner_id": "NewTestGroup/systemKey/"
                "9b97a48b-e2f3-4095-9ae9-62a0ec7a6304"
            }
        }

        def table_side_effect(table_name):
            if table_name == "test-cognito-table":
                return mock_cognito_table
            elif table_name == "test-api-keys-table":
                return mock_api_keys_table
            return MagicMock()

        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.side_effect = table_side_effect
        mock_boto3_resource.return_value = mock_dynamodb

        mock_get_systems.return_value = []

        valid, invalid = are_valid_amplify_users(
            "test_token", ["NewTestGroup_9b97a48b-e2f3-4095-9ae9-62a0ec7a6304"]
        )

        assert valid == [
            "NewTestGroup_9b97a48b-e2f3-4095-9ae9-62a0ec7a6304"
        ]  # Case preserved
        assert invalid == []

        # Verify the API keys table was called with correct api_owner_id
        mock_api_keys_table.get_item.assert_called_once_with(
            Key={
                "api_owner_id": "NewTestGroup/systemKey/"
                "9b97a48b-e2f3-4095-9ae9-62a0ec7a6304"
            },
            ProjectionExpression="api_owner_id",
        )

    @patch.dict(
        os.environ,
        {
            "COGNITO_USERS_DYNAMODB_TABLE": "test-cognito-table",
            "API_KEYS_DYNAMODB_TABLE": "test-api-keys-table",
        },
    )
    @patch("pycommon.api.amplify_users.boto3.resource")
    @patch("pycommon.api.amplify_users.get_system_ids")
    def test_are_valid_amplify_users_group_system_id_invalid(
        self, mock_get_systems, mock_boto3_resource
    ):
        """Test validation of invalid group system ID."""
        # Mock DynamoDB tables
        mock_cognito_table = MagicMock()
        mock_cognito_table.get_item.return_value = {}

        mock_api_keys_table = MagicMock()
        mock_api_keys_table.get_item.return_value = {}  # No item found

        def table_side_effect(table_name):
            if table_name == "test-cognito-table":
                return mock_cognito_table
            elif table_name == "test-api-keys-table":
                return mock_api_keys_table
            return MagicMock()

        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.side_effect = table_side_effect
        mock_boto3_resource.return_value = mock_dynamodb

        mock_get_systems.return_value = []

        valid, invalid = are_valid_amplify_users(
            "test_token", ["InvalidGroup_9b97a48b-e2f3-4095-9ae9-62a0ec7a6304"]
        )

        assert valid == []
        assert invalid == [
            "InvalidGroup_9b97a48b-e2f3-4095-9ae9-62a0ec7a6304"
        ]  # Case preserved

    @patch.dict(
        os.environ,
        {
            "COGNITO_USERS_DYNAMODB_TABLE": "test-cognito-table",
            "API_KEYS_DYNAMODB_TABLE": "test-api-keys-table",
        },
    )
    @patch("pycommon.api.amplify_users.boto3.resource")
    @patch("pycommon.api.amplify_users.get_system_ids")
    def test_are_valid_amplify_users_mixed_emails_and_group_system_ids(
        self, mock_get_systems, mock_boto3_resource
    ):
        """Test validation of mixed emails and group system IDs."""
        # Mock DynamoDB tables
        mock_cognito_table = MagicMock()

        def cognito_get_item_side_effect(**kwargs):
            user_id = kwargs.get("Key", {}).get("user_id", "")
            if user_id == "user@example.com":
                return {"Item": {"user_id": user_id}}
            return {}

        mock_cognito_table.get_item.side_effect = cognito_get_item_side_effect

        mock_api_keys_table = MagicMock()
        mock_api_keys_table.get_item.return_value = {
            "Item": {
                "api_owner_id": "TestGroup/systemKey/"
                "9b97a48b-e2f3-4095-9ae9-62a0ec7a6304"
            }
        }

        def table_side_effect(table_name):
            if table_name == "test-cognito-table":
                return mock_cognito_table
            elif table_name == "test-api-keys-table":
                return mock_api_keys_table
            return MagicMock()

        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.side_effect = table_side_effect
        mock_boto3_resource.return_value = mock_dynamodb

        mock_get_systems.return_value = []

        valid, invalid = are_valid_amplify_users(
            "test_token",
            [
                "user@example.com",  # Valid email (should be lowercase)
                "TestGroup_9b97a48b-e2f3-4095-9ae9-62a0ec7a6304",  # Valid group ID
                "invalid@example.com",  # Invalid email
            ],
        )

        assert valid == [
            "user@example.com",
            "TestGroup_9b97a48b-e2f3-4095-9ae9-62a0ec7a6304",
        ]
        assert invalid == ["invalid@example.com"]

    @patch.dict(
        os.environ,
        {
            "COGNITO_USERS_DYNAMODB_TABLE": "test-cognito-table",
            "API_KEYS_DYNAMODB_TABLE": "test-api-keys-table",
        },
    )
    @patch("pycommon.api.amplify_users.boto3.resource")
    @patch("pycommon.api.amplify_users.get_system_ids")
    def test_are_valid_amplify_users_group_system_id_client_error(
        self, mock_get_systems, mock_boto3_resource
    ):
        """Test validation when DynamoDB raises ClientError for group system ID."""
        # Mock DynamoDB tables
        mock_cognito_table = MagicMock()
        mock_cognito_table.get_item.return_value = {}

        mock_api_keys_table = MagicMock()
        mock_api_keys_table.get_item.side_effect = ClientError(
            {"Error": {"Message": "Access denied"}}, "GetItem"
        )

        def table_side_effect(table_name):
            if table_name == "test-cognito-table":
                return mock_cognito_table
            elif table_name == "test-api-keys-table":
                return mock_api_keys_table
            return MagicMock()

        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.side_effect = table_side_effect
        mock_boto3_resource.return_value = mock_dynamodb

        mock_get_systems.return_value = []

        valid, invalid = are_valid_amplify_users(
            "test_token", ["TestGroup_9b97a48b-e2f3-4095-9ae9-62a0ec7a6304"]
        )

        assert valid == []
        assert invalid == ["TestGroup_9b97a48b-e2f3-4095-9ae9-62a0ec7a6304"]

    @patch.dict(
        os.environ,
        {
            "COGNITO_USERS_DYNAMODB_TABLE": "test-cognito-table",
            "API_KEYS_DYNAMODB_TABLE": "test-api-keys-table",
        },
    )
    @patch("pycommon.api.amplify_users.boto3.resource")
    @patch("pycommon.api.amplify_users.get_system_ids")
    def test_are_valid_amplify_users_group_system_id_general_exception(
        self, mock_get_systems, mock_boto3_resource
    ):
        """Test validation when general exception occurs during group ID validation."""
        # Mock DynamoDB tables
        mock_cognito_table = MagicMock()
        mock_cognito_table.get_item.return_value = {}

        mock_api_keys_table = MagicMock()
        mock_api_keys_table.get_item.side_effect = Exception("Unexpected error")

        def table_side_effect(table_name):
            if table_name == "test-cognito-table":
                return mock_cognito_table
            elif table_name == "test-api-keys-table":
                return mock_api_keys_table
            return MagicMock()

        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.side_effect = table_side_effect
        mock_boto3_resource.return_value = mock_dynamodb

        mock_get_systems.return_value = []

        valid, invalid = are_valid_amplify_users(
            "test_token", ["TestGroup_9b97a48b-e2f3-4095-9ae9-62a0ec7a6304"]
        )

        assert valid == []
        assert invalid == ["TestGroup_9b97a48b-e2f3-4095-9ae9-62a0ec7a6304"]
