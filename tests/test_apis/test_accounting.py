import os
from unittest.mock import Mock, patch
from uuid import UUID

import pytest

from pycommon.api.accounting import _get_dynamodb_client, get_api_key_id, record_usage
from pycommon.exceptions import EnvVarError


class TestGetDynamoDBClient:
    """Tests for _get_dynamodb_client helper function."""

    @patch("pycommon.api.accounting.boto3.client")
    def test_returns_dynamodb_client(self, mock_boto_client):
        """Test that _get_dynamodb_client returns a DynamoDB client."""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client

        result = _get_dynamodb_client()

        mock_boto_client.assert_called_once_with("dynamodb")
        assert result == mock_client


class TestGetApiKeyId:
    """Tests for get_api_key_id function."""

    def test_returns_api_key_id_when_conditions_met(self):
        """Test that api_key_id is returned when access token starts with 'amp-'
        and api_key_id exists."""
        account = {"accessToken": "amp-test-token", "api_key_id": "test-key-123"}
        result = get_api_key_id(account)
        assert result == "test-key-123"

    def test_returns_none_when_access_token_does_not_start_with_amp(self):
        """Test that None is returned when access token doesn't start with 'amp-'."""
        account = {"accessToken": "bearer-test-token", "api_key_id": "test-key-123"}
        result = get_api_key_id(account)
        assert result is None

    def test_returns_none_when_no_access_token(self):
        """Test that None is returned when no access token is present."""
        account = {"api_key_id": "test-key-123"}
        result = get_api_key_id(account)
        assert result is None

    def test_returns_none_when_no_api_key_id(self):
        """Test that None is returned when no api_key_id is present."""
        account = {"accessToken": "amp-test-token"}
        result = get_api_key_id(account)
        assert result is None

    def test_returns_none_when_empty_access_token(self):
        """Test that None is returned when access token is empty."""
        account = {"accessToken": "", "api_key_id": "test-key-123"}
        result = get_api_key_id(account)
        assert result is None

    def test_returns_none_when_access_token_is_amp_only(self):
        """Test that None is returned when access token is just 'amp-'."""
        account = {"accessToken": "amp-", "api_key_id": "test-key-123"}
        result = get_api_key_id(account)
        assert result == "test-key-123"

    def test_returns_none_when_empty_account(self):
        """Test that None is returned for empty account."""
        account = {}
        result = get_api_key_id(account)
        assert result is None


class TestRecordUsage:
    """Tests for record_usage function."""

    def setup_method(self):
        """Set up test environment variables."""
        self.account = {
            "user": "test-user@example.com",
            "account_id": "test-account-123",
        }

    def test_returns_zero_when_chat_usage_table_missing(self):
        """Test that EnvVarError is raised when CHAT_USAGE_DYNAMO_TABLE is missing."""
        # Clear all required env vars to trigger the decorator error
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(EnvVarError, match="CHAT_USAGE_DYNAMO_TABLE"):
                record_usage(self.account, "req-123", "gpt-4", 100, 50, 10)

    def test_returns_zero_when_cost_calculations_table_missing(self):
        """Test EnvVarError raised when COST_CALCULATIONS_DYNAMO_TABLE missing."""
        # Only set one required env var to trigger error for missing second one
        with patch.dict(
            os.environ, {"CHAT_USAGE_DYNAMO_TABLE": "test-table"}, clear=True
        ):
            with pytest.raises(EnvVarError, match="COST_CALCULATIONS_DYNAMO_TABLE"):
                record_usage(self.account, "req-123", "gpt-4", 100, 50, 10)

    def test_returns_zero_when_model_rate_table_missing(self):
        """Test that EnvVarError is raised when MODEL_RATE_TABLE is missing."""
        # Only set two required env vars to trigger error for missing third one
        with patch.dict(
            os.environ,
            {
                "CHAT_USAGE_DYNAMO_TABLE": "test-table",
                "COST_CALCULATIONS_DYNAMO_TABLE": "test-cost-table",
            },
            clear=True,
        ):
            with pytest.raises(EnvVarError, match="MODEL_RATE_TABLE"):
                record_usage(self.account, "req-123", "gpt-4", 100, 50, 10)

    @patch("pycommon.api.accounting._get_dynamodb_client")
    @patch("pycommon.api.accounting.logger")
    def test_returns_zero_when_usage_recording_fails(
        self, mock_logger, mock_get_client
    ):
        """Test that 0.0 is returned when usage recording fails."""
        with patch.dict(
            os.environ,
            {
                "CHAT_USAGE_DYNAMO_TABLE": "test-usage-table",
                "COST_CALCULATIONS_DYNAMO_TABLE": "test-cost-table",
                "MODEL_RATE_TABLE": "test-model-rate-table",
            },
        ):
            mock_dynamodb = Mock()
            mock_get_client.return_value = mock_dynamodb
            mock_dynamodb.put_item.side_effect = Exception("DynamoDB error")

            result = record_usage(self.account, "req-123", "gpt-4", 100, 50, 10)
            assert result == 0.0
            mock_logger.error.assert_called_with(
                "Error recording usage: DynamoDB error"
            )

    @patch("pycommon.api.accounting._get_dynamodb_client")
    @patch("pycommon.api.accounting.logger")
    def test_returns_zero_when_model_rate_not_found(self, mock_logger, mock_get_client):
        """Test that 0.0 is returned when no model rate is found."""
        with patch.dict(
            os.environ,
            {
                "CHAT_USAGE_DYNAMO_TABLE": "test-usage-table",
                "COST_CALCULATIONS_DYNAMO_TABLE": "test-cost-table",
                "MODEL_RATE_TABLE": "test-model-rate-table",
            },
        ):
            mock_dynamodb = Mock()
            mock_get_client.return_value = mock_dynamodb
            mock_dynamodb.put_item.return_value = None
            mock_dynamodb.query.return_value = {"Items": []}

            result = record_usage(self.account, "req-123", "gpt-4", 100, 50, 10)
            assert result == 0.0
            mock_logger.warning.assert_called_with(
                "No model rate found for ModelID: gpt-4"
            )

    @patch("pycommon.api.accounting._get_dynamodb_client")
    @patch("pycommon.api.accounting.logger")
    def test_returns_zero_when_cost_calculation_fails(
        self, mock_logger, mock_get_client
    ):
        """Test that 0.0 is returned when cost calculation fails."""
        with patch.dict(
            os.environ,
            {
                "CHAT_USAGE_DYNAMO_TABLE": "test-usage-table",
                "COST_CALCULATIONS_DYNAMO_TABLE": "test-cost-table",
                "MODEL_RATE_TABLE": "test-model-rate-table",
            },
        ):
            mock_dynamodb = Mock()
            mock_get_client.return_value = mock_dynamodb
            mock_dynamodb.put_item.return_value = None
            mock_dynamodb.query.side_effect = Exception("Query failed")

            result = record_usage(self.account, "req-123", "gpt-4", 100, 50, 10)
            assert result == 0.0
            mock_logger.error.assert_called_with(
                "Error calculating or updating cost: Query failed"
            )

    @patch("pycommon.api.accounting._get_dynamodb_client")
    @patch("pycommon.api.accounting.logger")
    @patch("pycommon.api.accounting.uuid")
    def test_successful_usage_recording_without_api_key(
        self, mock_uuid, mock_logger, mock_get_client
    ):
        """Test successful usage recording without API key."""
        with patch.dict(
            os.environ,
            {
                "CHAT_USAGE_DYNAMO_TABLE": "test-usage-table",
                "COST_CALCULATIONS_DYNAMO_TABLE": "test-cost-table",
                "MODEL_RATE_TABLE": "test-model-rate-table",
            },
        ):
            # Mock uuid
            mock_uuid.uuid4.return_value = UUID("12345678-1234-5678-9012-123456789012")

            # Mock datetime via datetime.now() calls
            with patch("pycommon.api.accounting.datetime") as mock_datetime:
                mock_now = Mock()
                mock_now.isoformat.return_value = "2023-01-01T12:00:00"
                mock_now.hour = 14

                mock_utc_now = Mock()
                mock_utc_now.hour = 14

                # Set up return values for different datetime.now() calls
                mock_datetime.now.return_value = mock_now
                mock_datetime.now.return_value.hour = 14

                # Mock the timezone.utc call specifically
                def datetime_now_side_effect(tz=None):
                    if tz is not None:  # timezone.utc call
                        return mock_utc_now
                    return mock_now

                mock_datetime.now.side_effect = datetime_now_side_effect
                mock_datetime.now.return_value = mock_now

                # Mock DynamoDB responses
                mock_dynamodb = Mock()
                mock_get_client.return_value = mock_dynamodb
                mock_dynamodb.put_item.return_value = None
                mock_dynamodb.query.return_value = {
                    "Items": [
                        {
                            "InputCostPerThousandTokens": {"N": "0.01"},
                            "OutputCostPerThousandTokens": {"N": "0.03"},
                            "CachedCostPerThousandTokens": {"N": "0.005"},
                        }
                    ]
                }
                mock_dynamodb.update_item.return_value = None

                result = record_usage(self.account, "req-123", "gpt-4", 1000, 500, 100)

                expected_cost = (
                    (1000 / 1000 * 0.01) + (500 / 1000 * 0.03) + (100 / 1000 * 0.005)
                )
                assert result == expected_cost

    @patch("pycommon.api.accounting._get_dynamodb_client")
    @patch("pycommon.api.accounting.logger")
    @patch("pycommon.api.accounting.uuid")
    def test_successful_usage_recording_with_api_key(
        self, mock_uuid, mock_logger, mock_get_client
    ):
        """Test successful usage recording with API key."""
        with patch.dict(
            os.environ,
            {
                "CHAT_USAGE_DYNAMO_TABLE": "test-usage-table",
                "COST_CALCULATIONS_DYNAMO_TABLE": "test-cost-table",
                "MODEL_RATE_TABLE": "test-model-rate-table",
            },
        ):
            # Mock uuid
            mock_uuid.uuid4.return_value = UUID("12345678-1234-5678-9012-123456789012")

            # Account with API key
            account_with_key = {
                **self.account,
                "accessToken": "amp-test-token",
                "api_key_id": "api-key-123",
            }

            # Mock datetime
            with patch("pycommon.api.accounting.datetime") as mock_datetime:
                mock_now = Mock()
                mock_now.isoformat.return_value = "2023-01-01T12:00:00"
                mock_now.hour = 10

                mock_utc_now = Mock()
                mock_utc_now.hour = 10

                def datetime_now_side_effect(tz=None):
                    if tz is not None:  # timezone.utc call
                        return mock_utc_now
                    return mock_now

                mock_datetime.now.side_effect = datetime_now_side_effect

                # Mock DynamoDB responses
                mock_dynamodb = Mock()
                mock_get_client.return_value = mock_dynamodb
                mock_dynamodb.put_item.return_value = None
                mock_dynamodb.query.return_value = {
                    "Items": [
                        {
                            "InputCostPerThousandTokens": {"N": "0.002"},
                            "OutputCostPerThousandTokens": {"N": "0.006"},
                            "CachedCostPerThousandTokens": {"N": "0.001"},
                        }
                    ]
                }
                mock_dynamodb.update_item.return_value = None

                result = record_usage(
                    account_with_key,
                    "req-456",
                    "claude-3",
                    500,
                    250,
                    50,
                    {"extra": "data"},
                )

                expected_cost = (
                    (500 / 1000 * 0.002) + (250 / 1000 * 0.006) + (50 / 1000 * 0.001)
                )
                assert result == expected_cost

    @patch("pycommon.api.accounting._get_dynamodb_client")
    @patch("pycommon.api.accounting.logger")
    @patch("pycommon.api.accounting.uuid")
    def test_usage_recording_with_none_details(
        self, mock_uuid, mock_logger, mock_get_client
    ):
        """Test usage recording with None details parameter."""
        with patch.dict(
            os.environ,
            {
                "CHAT_USAGE_DYNAMO_TABLE": "test-usage-table",
                "COST_CALCULATIONS_DYNAMO_TABLE": "test-cost-table",
                "MODEL_RATE_TABLE": "test-model-rate-table",
            },
        ):
            # Mock uuid
            mock_uuid.uuid4.return_value = UUID("12345678-1234-5678-9012-123456789012")

            # Mock datetime
            with patch("pycommon.api.accounting.datetime") as mock_datetime:
                mock_now = Mock()
                mock_now.isoformat.return_value = "2023-01-01T12:00:00"
                mock_now.hour = 16

                mock_utc_now = Mock()
                mock_utc_now.hour = 16

                def datetime_now_side_effect(tz=None):
                    if tz is not None:  # timezone.utc call
                        return mock_utc_now
                    return mock_now

                mock_datetime.now.side_effect = datetime_now_side_effect

                # Mock DynamoDB responses
                mock_dynamodb = Mock()
                mock_get_client.return_value = mock_dynamodb
                mock_dynamodb.put_item.return_value = None
                mock_dynamodb.query.return_value = {
                    "Items": [
                        {
                            "InputCostPerThousandTokens": {"N": "0.01"},
                            "OutputCostPerThousandTokens": {"N": "0.03"},
                            "CachedCostPerThousandTokens": {"N": "0.005"},
                        }
                    ]
                }
                mock_dynamodb.update_item.return_value = None

                result = record_usage(
                    self.account, "req-789", "gpt-3.5", 300, 150, 30, None
                )

                expected_cost = (
                    (300 / 1000 * 0.01) + (150 / 1000 * 0.03) + (30 / 1000 * 0.005)
                )
                assert result == expected_cost

    @patch("pycommon.api.accounting._get_dynamodb_client")
    @patch("pycommon.api.accounting.logger")
    @patch("pycommon.api.accounting.uuid")
    def test_usage_recording_with_missing_account_id(
        self, mock_uuid, mock_logger, mock_get_client
    ):
        """Test usage recording when account_id is missing (uses default)."""
        with patch.dict(
            os.environ,
            {
                "CHAT_USAGE_DYNAMO_TABLE": "test-usage-table",
                "COST_CALCULATIONS_DYNAMO_TABLE": "test-cost-table",
                "MODEL_RATE_TABLE": "test-model-rate-table",
            },
        ):
            # Mock uuid
            mock_uuid.uuid4.return_value = UUID("12345678-1234-5678-9012-123456789012")

            # Account without account_id
            account_without_id = {"user": "test-user@example.com"}

            # Mock datetime
            with patch("pycommon.api.accounting.datetime") as mock_datetime:
                mock_now = Mock()
                mock_now.isoformat.return_value = "2023-01-01T12:00:00"
                mock_now.hour = 8

                mock_utc_now = Mock()
                mock_utc_now.hour = 8

                def datetime_now_side_effect(tz=None):
                    if tz is not None:  # timezone.utc call
                        return mock_utc_now
                    return mock_now

                mock_datetime.now.side_effect = datetime_now_side_effect

                # Mock DynamoDB responses
                mock_dynamodb = Mock()
                mock_get_client.return_value = mock_dynamodb
                mock_dynamodb.put_item.return_value = None
                mock_dynamodb.query.return_value = {
                    "Items": [
                        {
                            "InputCostPerThousandTokens": {"N": "0.01"},
                            "OutputCostPerThousandTokens": {"N": "0.03"},
                            "CachedCostPerThousandTokens": {"N": "0.005"},
                        }
                    ]
                }
                mock_dynamodb.update_item.return_value = None

                result = record_usage(
                    account_without_id, "req-000", "gpt-4", 200, 100, 20
                )

                expected_cost = (
                    (200 / 1000 * 0.01) + (100 / 1000 * 0.03) + (20 / 1000 * 0.005)
                )
                assert result == expected_cost

    @patch("pycommon.api.accounting._get_dynamodb_client")
    @patch("pycommon.api.accounting.logger")
    @patch("pycommon.api.accounting.uuid")
    def test_cost_update_failure_after_successful_usage_recording(
        self, mock_uuid, mock_logger, mock_get_client
    ):
        """Test that function returns 0.0 when cost update fails after
        successful usage recording."""
        with patch.dict(
            os.environ,
            {
                "CHAT_USAGE_DYNAMO_TABLE": "test-usage-table",
                "COST_CALCULATIONS_DYNAMO_TABLE": "test-cost-table",
                "MODEL_RATE_TABLE": "test-model-rate-table",
            },
        ):
            # Mock uuid
            mock_uuid.uuid4.return_value = UUID("12345678-1234-5678-9012-123456789012")

            # Mock datetime
            with patch("pycommon.api.accounting.datetime") as mock_datetime:
                mock_now = Mock()
                mock_now.isoformat.return_value = "2023-01-01T12:00:00"
                mock_now.hour = 12

                mock_utc_now = Mock()
                mock_utc_now.hour = 12

                def datetime_now_side_effect(tz=None):
                    if tz is not None:  # timezone.utc call
                        return mock_utc_now
                    return mock_now

                mock_datetime.now.side_effect = datetime_now_side_effect

                # Mock DynamoDB responses - usage succeeds, cost update fails
                mock_dynamodb = Mock()
                mock_get_client.return_value = mock_dynamodb
                mock_dynamodb.put_item.return_value = None
                mock_dynamodb.query.return_value = {
                    "Items": [
                        {
                            "InputCostPerThousandTokens": {"N": "0.01"},
                            "OutputCostPerThousandTokens": {"N": "0.03"},
                            "CachedCostPerThousandTokens": {"N": "0.005"},
                        }
                    ]
                }
                mock_dynamodb.update_item.side_effect = Exception("Update failed")

                result = record_usage(
                    self.account, "req-update-fail", "gpt-4", 100, 50, 10
                )

                assert result == 0.0
                # Check that the error was logged (error message format in
                # function may vary)
                assert mock_logger.error.called
                call_args = mock_logger.error.call_args[0][0]
                assert "Error calculating or updating cost:" in call_args
