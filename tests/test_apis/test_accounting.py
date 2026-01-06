import os
from unittest.mock import Mock, patch
from uuid import UUID

import pytest

from pycommon.api.accounting import (
    _get_dynamodb_client,
    get_api_key_id,
    record_additional_charge,
    record_usage,
)
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
                record_usage(self.account, "req-123", "gpt-4", 100, 50, 10, 0)

    def test_returns_zero_when_cost_calculations_table_missing(self):
        """Test EnvVarError raised when COST_CALCULATIONS_DYNAMO_TABLE missing."""
        # Only set one required env var to trigger error for missing second one
        with patch.dict(
            os.environ, {"CHAT_USAGE_DYNAMO_TABLE": "test-table"}, clear=True
        ):
            with pytest.raises(EnvVarError, match="COST_CALCULATIONS_DYNAMO_TABLE"):
                record_usage(self.account, "req-123", "gpt-4", 100, 50, 10, 0)

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
                record_usage(self.account, "req-123", "gpt-4", 100, 50, 10, 0)

    @patch("pycommon.api.accounting._get_dynamodb_client")
    @patch("pycommon.api.accounting.logger")
    @patch("pycommon.api.accounting.log_critical_error")
    def test_returns_zero_when_usage_recording_fails(
        self, mock_log_critical, mock_logger, mock_get_client
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

            result = record_usage(self.account, "req-123", "gpt-4", 100, 50, 10, 0)
            assert result == 0.0
            mock_logger.error.assert_called_with(
                "Error recording usage: DynamoDB error"
            )

            # Verify critical error was logged
            mock_log_critical.assert_called_once()
            call_kwargs = mock_log_critical.call_args[1]
            assert call_kwargs["function_name"] == "record_usage"
            assert call_kwargs["error_type"] == "UsageRecordingFailure"

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

            result = record_usage(self.account, "req-123", "gpt-4", 100, 50, 10, 0)
            assert result == 0.0
            mock_logger.warning.assert_called_with(
                "No model rate found for ModelID: gpt-4"
            )

    @patch("pycommon.api.accounting._get_dynamodb_client")
    @patch("pycommon.api.accounting.logger")
    @patch("pycommon.api.accounting.log_critical_error")
    def test_returns_zero_when_cost_calculation_fails(
        self, mock_log_critical, mock_logger, mock_get_client
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

            result = record_usage(self.account, "req-123", "gpt-4", 100, 50, 10, 0)
            assert result == 0.0
            mock_logger.error.assert_called_with(
                "Error calculating or updating cost: Query failed"
            )

            # Verify critical error was logged
            mock_log_critical.assert_called_once()
            call_kwargs = mock_log_critical.call_args[1]
            assert call_kwargs["function_name"] == "record_usage_costCalculation"
            assert call_kwargs["error_type"] == "CostCalculationFailure"

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
                            "InputCachedCostPerThousandTokens": {"N": "0.005"},
                            "InputWriteCachedCostPerThousandTokens": {"N": "0.0025"},
                        }
                    ]
                }
                mock_dynamodb.update_item.return_value = None

                result = record_usage(
                    self.account, "req-123", "gpt-4", 1000, 500, 100, 50
                )

                expected_cost = (
                    (1000 / 1000 * 0.01)
                    + (500 / 1000 * 0.03)
                    + (100 / 1000 * 0.005)
                    + (50 / 1000 * 0.0025)
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
                            "InputCachedCostPerThousandTokens": {"N": "0.001"},
                            "InputWriteCachedCostPerThousandTokens": {"N": "0.0005"},
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
                    25,
                    {"extra": "data"},
                )

                expected_cost = (
                    (500 / 1000 * 0.002)
                    + (250 / 1000 * 0.006)
                    + (50 / 1000 * 0.001)
                    + (25 / 1000 * 0.0005)
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
                            "InputCachedCostPerThousandTokens": {"N": "0.005"},
                        }
                    ]
                }
                mock_dynamodb.update_item.return_value = None

                result = record_usage(
                    self.account, "req-789", "gpt-3.5", 300, 150, 30, 0, None
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
                            "InputCachedCostPerThousandTokens": {"N": "0.005"},
                        }
                    ]
                }
                mock_dynamodb.update_item.return_value = None

                result = record_usage(
                    account_without_id, "req-000", "gpt-4", 200, 100, 20, 0
                )

                expected_cost = (
                    (200 / 1000 * 0.01) + (100 / 1000 * 0.03) + (20 / 1000 * 0.005)
                )
                assert result == expected_cost

    @patch("pycommon.api.accounting._get_dynamodb_client")
    @patch("pycommon.api.accounting.logger")
    @patch("pycommon.api.accounting.uuid")
    @patch("pycommon.api.accounting.log_critical_error")
    def test_cost_update_failure_after_successful_usage_recording(
        self, mock_log_critical, mock_uuid, mock_logger, mock_get_client
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
                            "InputCachedCostPerThousandTokens": {"N": "0.005"},
                        }
                    ]
                }
                mock_dynamodb.update_item.side_effect = Exception("Update failed")

                result = record_usage(
                    self.account, "req-update-fail", "gpt-4", 100, 50, 10, 0
                )

                assert result == 0.0
                # Check that the error was logged (error message format in
                # function may vary)
                assert mock_logger.error.called
                call_args = mock_logger.error.call_args[0][0]
                assert "Error calculating or updating cost:" in call_args

                # Verify critical error was logged
                mock_log_critical.assert_called_once()

    @patch("pycommon.api.accounting._get_dynamodb_client")
    @patch("pycommon.api.accounting.logger")
    @patch("pycommon.api.accounting.log_critical_error")
    def test_logs_error_when_usage_critical_logging_fails(
        self, mock_log_critical, mock_logger, mock_get_client
    ):
        """Test error is logged if critical logging fails in usage recording."""
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

            # Make critical logging fail too
            mock_log_critical.side_effect = Exception("Logging error")

            result = record_usage(self.account, "req-123", "gpt-4", 100, 50, 10, 0)

            assert result == 0.0
            # Verify that the failure to log critical error was also logged
            assert mock_logger.error.call_count >= 2
            calls = [str(call) for call in mock_logger.error.call_args_list]
            assert any("Failed to log critical error" in call for call in calls)

    @patch("pycommon.api.accounting._get_dynamodb_client")
    @patch("pycommon.api.accounting.logger")
    @patch("pycommon.api.accounting.uuid")
    def test_successful_usage_recording_with_legacy_cached_field(
        self, mock_uuid, mock_logger, mock_get_client
    ):
        """Test backward compatibility with legacy CachedCostPerThousandTokens."""
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
                mock_now.hour = 10

                mock_utc_now = Mock()
                mock_utc_now.hour = 10

                def datetime_now_side_effect(tz=None):
                    if tz is not None:  # timezone.utc call
                        return mock_utc_now
                    return mock_now

                mock_datetime.now.side_effect = datetime_now_side_effect

                # Mock DynamoDB with legacy field only
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
                    self.account, "req-999", "gpt-4", 1000, 500, 100, 0
                )

                # Should use legacy field for input_cached_tokens
                expected_cost = (
                    (1000 / 1000 * 0.01) + (500 / 1000 * 0.03) + (100 / 1000 * 0.005)
                )
                assert result == expected_cost

    @patch("pycommon.api.accounting._get_dynamodb_client")
    @patch("pycommon.api.accounting.logger")
    @patch("pycommon.api.accounting.uuid")
    def test_successful_usage_recording_legacy_ignored_when_new_field_exists(
        self, mock_uuid, mock_logger, mock_get_client
    ):
        """Test legacy field ignored when new field exists."""
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
                mock_now.hour = 10

                mock_utc_now = Mock()
                mock_utc_now.hour = 10

                def datetime_now_side_effect(tz=None):
                    if tz is not None:  # timezone.utc call
                        return mock_utc_now
                    return mock_now

                mock_datetime.now.side_effect = datetime_now_side_effect

                # Mock DynamoDB with BOTH legacy and new fields
                mock_dynamodb = Mock()
                mock_get_client.return_value = mock_dynamodb
                mock_dynamodb.put_item.return_value = None
                mock_dynamodb.query.return_value = {
                    "Items": [
                        {
                            "InputCostPerThousandTokens": {"N": "0.01"},
                            "OutputCostPerThousandTokens": {"N": "0.03"},
                            "InputCachedCostPerThousandTokens": {"N": "0.002"},  # New
                            "CachedCostPerThousandTokens": {"N": "0.005"},  # Legacy
                        }
                    ]
                }
                mock_dynamodb.update_item.return_value = None

                result = record_usage(
                    self.account, "req-legacy-ignored", "gpt-4", 1000, 500, 100, 0
                )

                # Should use new field value (0.002) not legacy (0.005)
                expected_cost = (
                    (1000 / 1000 * 0.01) + (500 / 1000 * 0.03) + (100 / 1000 * 0.002)
                )
                assert result == expected_cost

    @patch("pycommon.api.accounting._get_dynamodb_client")
    @patch("pycommon.api.accounting.logger")
    @patch("pycommon.api.accounting.log_critical_error")
    def test_logs_error_when_cost_calculation_critical_logging_fails(
        self, mock_log_critical, mock_logger, mock_get_client
    ):
        """Test error is logged if critical logging fails in cost calc."""
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

            # Make critical logging fail too
            mock_log_critical.side_effect = Exception("Logging error")

            result = record_usage(self.account, "req-123", "gpt-4", 100, 50, 10, 0)

            assert result == 0.0
            # Verify that the failure to log critical error was also logged
            assert mock_logger.error.call_count >= 2
            calls = [str(call) for call in mock_logger.error.call_args_list]
            assert any("Failed to log critical error" in call for call in calls)


class TestRecordAdditionalCharge:
    """Tests for record_additional_charge function."""

    def setup_method(self):
        """Set up test environment variables and account data."""
        self.account = {
            "user": "test-user@example.com",
            "account_id": "test-account-123",
        }

    def test_raises_error_when_additional_charges_table_missing(self):
        """Test that EnvVarError is raised when ADDITIONAL_CHARGES_TABLE is missing."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(EnvVarError, match="ADDITIONAL_CHARGES_TABLE"):
                record_additional_charge(
                    self.account, "text-embedding-3-small", 1000, "embedding"
                )

    def test_raises_error_when_model_rate_table_missing(self):
        """Test that EnvVarError is raised when MODEL_RATE_TABLE is missing."""
        with patch.dict(
            os.environ, {"ADDITIONAL_CHARGES_TABLE": "test-charges-table"}, clear=True
        ):
            with pytest.raises(EnvVarError, match="MODEL_RATE_TABLE"):
                record_additional_charge(
                    self.account, "text-embedding-3-small", 1000, "embedding"
                )

    @patch("pycommon.api.accounting._get_dynamodb_client")
    @patch("pycommon.api.accounting.logger")
    def test_returns_zero_when_account_user_missing(self, mock_logger, mock_get_client):
        """Test that 0.0 is returned when account.user is missing."""
        with patch.dict(
            os.environ,
            {
                "ADDITIONAL_CHARGES_TABLE": "test-charges-table",
                "MODEL_RATE_TABLE": "test-model-rate-table",
            },
        ):
            account_no_user = {"account_id": "test-account-123"}
            result = record_additional_charge(
                account_no_user, "text-embedding-3-small", 1000, "embedding"
            )

            assert result == 0.0
            mock_logger.warning.assert_called_once()
            assert "Missing account.user" in str(mock_logger.warning.call_args)

    @patch("pycommon.api.accounting._get_dynamodb_client")
    @patch("pycommon.api.accounting.logger")
    def test_returns_zero_when_model_rate_not_found(self, mock_logger, mock_get_client):
        """Test that 0.0 is returned when no model rate is found."""
        with patch.dict(
            os.environ,
            {
                "ADDITIONAL_CHARGES_TABLE": "test-charges-table",
                "MODEL_RATE_TABLE": "test-model-rate-table",
            },
        ):
            mock_dynamodb = Mock()
            mock_get_client.return_value = mock_dynamodb
            mock_dynamodb.query.return_value = {"Items": []}

            result = record_additional_charge(
                self.account, "unknown-model", 1000, "embedding"
            )

            assert result == 0.0
            mock_logger.warning.assert_called_once()
            assert "No pricing found for model" in str(mock_logger.warning.call_args)

    @patch("pycommon.api.accounting._get_dynamodb_client")
    @patch("pycommon.api.accounting.logger")
    @patch("pycommon.api.accounting.uuid")
    @patch("pycommon.api.accounting.log_critical_error")
    def test_returns_zero_and_logs_critical_error_on_failure(
        self, mock_log_critical, mock_uuid, mock_logger, mock_get_client
    ):
        """Test 0.0 returned and critical error logged when recording fails."""
        with patch.dict(
            os.environ,
            {
                "ADDITIONAL_CHARGES_TABLE": "test-charges-table",
                "MODEL_RATE_TABLE": "test-model-rate-table",
            },
        ):
            mock_dynamodb = Mock()
            mock_get_client.return_value = mock_dynamodb
            mock_dynamodb.query.side_effect = Exception("DynamoDB error")

            result = record_additional_charge(
                self.account, "text-embedding-3-small", 1000, "embedding"
            )

            assert result == 0.0
            mock_logger.error.assert_called_once()
            assert "Failed to record additional charge" in str(
                mock_logger.error.call_args
            )

            # Verify critical error was logged
            mock_log_critical.assert_called_once()
            call_kwargs = mock_log_critical.call_args[1]
            assert call_kwargs["function_name"] == "record_additional_charge"
            assert call_kwargs["error_type"] == "AdditionalChargeRecordingFailure"
            assert call_kwargs["severity"] == "HIGH"
            assert call_kwargs["current_user"] == "test-user@example.com"

    @patch("pycommon.api.accounting._get_dynamodb_client")
    @patch("pycommon.api.accounting.logger")
    @patch("pycommon.api.accounting.uuid")
    def test_successful_charge_recording_with_basic_params(
        self, mock_uuid, mock_logger, mock_get_client
    ):
        """Test successful charge recording with basic parameters."""
        with patch.dict(
            os.environ,
            {
                "ADDITIONAL_CHARGES_TABLE": "test-charges-table",
                "MODEL_RATE_TABLE": "test-model-rate-table",
            },
        ):
            # Mock uuid
            mock_uuid.uuid4.return_value = UUID("12345678-1234-5678-9012-123456789012")

            # Mock datetime
            with patch("pycommon.api.accounting.datetime") as mock_datetime:
                mock_now = Mock()
                mock_now.isoformat.return_value = "2023-01-01T12:00:00Z"

                mock_datetime.now.return_value = mock_now

                # Mock DynamoDB responses
                mock_dynamodb = Mock()
                mock_get_client.return_value = mock_dynamodb
                mock_dynamodb.query.return_value = {
                    "Items": [{"InputCostPerThousandTokens": {"N": "0.0001"}}]
                }
                mock_dynamodb.put_item.return_value = None

                result = record_additional_charge(
                    self.account, "text-embedding-3-small", 1000, "embedding"
                )

                expected_cost = 1000 / 1000 * 0.0001  # 0.0001
                assert result == expected_cost

                # Verify put_item was called with correct structure
                put_item_call = mock_dynamodb.put_item.call_args
                assert put_item_call is not None
                item = put_item_call[1]["Item"]
                assert item["user"]["S"] == "test-user@example.com"
                assert item["accountId"]["S"] == "test-account-123"
                assert item["modelId"]["S"] == "text-embedding-3-small"
                # Verify itemType is at top level AND in details
                assert item["itemType"]["S"] == "embedding"
                assert item["details"]["M"]["itemType"]["S"] == "embedding"

    @patch("pycommon.api.accounting._get_dynamodb_client")
    @patch("pycommon.api.accounting.logger")
    @patch("pycommon.api.accounting.uuid")
    def test_successful_charge_recording_with_details(
        self, mock_uuid, mock_logger, mock_get_client
    ):
        """Test successful charge recording with additional details."""
        with patch.dict(
            os.environ,
            {
                "ADDITIONAL_CHARGES_TABLE": "test-charges-table",
                "MODEL_RATE_TABLE": "test-model-rate-table",
            },
        ):
            # Mock uuid
            mock_uuid.uuid4.return_value = UUID("12345678-1234-5678-9012-123456789012")

            # Mock datetime
            with patch("pycommon.api.accounting.datetime") as mock_datetime:
                mock_now = Mock()
                mock_now.isoformat.return_value = "2023-01-01T12:00:00Z"
                mock_datetime.now.return_value = mock_now

                # Mock DynamoDB responses
                mock_dynamodb = Mock()
                mock_get_client.return_value = mock_dynamodb
                mock_dynamodb.query.return_value = {
                    "Items": [{"InputCostPerThousandTokens": {"N": "0.0002"}}]
                }
                mock_dynamodb.put_item.return_value = None

                details = {
                    "document_key": "doc-456.pdf",
                    "chunk_id": 123,
                    "is_test": True,
                    "nested": {"key": "value"},
                }

                result = record_additional_charge(
                    self.account,
                    "text-embedding-3-large",
                    2000,
                    "embedding",
                    details=details,
                )

                expected_cost = 2000 / 1000 * 0.0002  # 0.0004
                assert result == expected_cost

                # Verify details were properly serialized
                put_item_call = mock_dynamodb.put_item.call_args
                item = put_item_call[1]["Item"]
                item_details = item["details"]["M"]
                assert item_details["document_key"]["S"] == "doc-456.pdf"
                assert item_details["chunk_id"]["N"] == "123"
                # Boolean values are stored as BOOL in DynamoDB with nested structure
                assert "is_test" in item_details
                assert "nested" in item_details

    @patch("pycommon.api.accounting._get_dynamodb_client")
    @patch("pycommon.api.accounting.logger")
    @patch("pycommon.api.accounting.uuid")
    @patch("pycommon.api.accounting.time")
    def test_successful_charge_recording_with_ttl(
        self, mock_time, mock_uuid, mock_logger, mock_get_client
    ):
        """Test successful charge recording with TTL."""
        with patch.dict(
            os.environ,
            {
                "ADDITIONAL_CHARGES_TABLE": "test-charges-table",
                "MODEL_RATE_TABLE": "test-model-rate-table",
            },
        ):
            # Mock time and uuid
            mock_time.time.return_value = 1609459200  # 2021-01-01 00:00:00
            mock_uuid.uuid4.return_value = UUID("12345678-1234-5678-9012-123456789012")

            # Mock datetime
            with patch("pycommon.api.accounting.datetime") as mock_datetime:
                mock_now = Mock()
                mock_now.isoformat.return_value = "2023-01-01T12:00:00Z"
                mock_datetime.now.return_value = mock_now

                # Mock DynamoDB responses
                mock_dynamodb = Mock()
                mock_get_client.return_value = mock_dynamodb
                mock_dynamodb.query.return_value = {
                    "Items": [{"InputCostPerThousandTokens": {"N": "0.0001"}}]
                }
                mock_dynamodb.put_item.return_value = None

                result = record_additional_charge(
                    self.account,
                    "text-embedding-3-small",
                    1000,
                    "embedding",
                    ttl_days=90,
                )

                assert result > 0.0

                # Verify TTL was set correctly
                put_item_call = mock_dynamodb.put_item.call_args
                item = put_item_call[1]["Item"]
                assert "ttl" in item
                expected_ttl = 1609459200 + (90 * 24 * 60 * 60)
                assert item["ttl"]["N"] == str(expected_ttl)

    @patch("pycommon.api.accounting._get_dynamodb_client")
    @patch("pycommon.api.accounting.logger")
    @patch("pycommon.api.accounting.uuid")
    def test_successful_charge_recording_with_custom_request_id(
        self, mock_uuid, mock_logger, mock_get_client
    ):
        """Test successful charge recording with custom request_id."""
        with patch.dict(
            os.environ,
            {
                "ADDITIONAL_CHARGES_TABLE": "test-charges-table",
                "MODEL_RATE_TABLE": "test-model-rate-table",
            },
        ):
            # Mock datetime
            with patch("pycommon.api.accounting.datetime") as mock_datetime:
                mock_now = Mock()
                mock_now.isoformat.return_value = "2023-01-01T12:00:00Z"
                mock_datetime.now.return_value = mock_now

                # Mock DynamoDB responses
                mock_dynamodb = Mock()
                mock_get_client.return_value = mock_dynamodb
                mock_dynamodb.query.return_value = {
                    "Items": [{"InputCostPerThousandTokens": {"N": "0.0001"}}]
                }
                mock_dynamodb.put_item.return_value = None

                custom_request_id = "custom-req-789"
                result = record_additional_charge(
                    self.account,
                    "text-embedding-3-small",
                    1000,
                    "embedding",
                    request_id=custom_request_id,
                )

                assert result > 0.0

                # Verify request_id was used
                put_item_call = mock_dynamodb.put_item.call_args
                item = put_item_call[1]["Item"]
                assert item["requestId"]["S"] == custom_request_id
                assert custom_request_id in item["id"]["S"]

    @patch("pycommon.api.accounting._get_dynamodb_client")
    @patch("pycommon.api.accounting.logger")
    @patch("pycommon.api.accounting.uuid")
    def test_charge_recording_with_account_fallback(
        self, mock_uuid, mock_logger, mock_get_client
    ):
        """Test charge recording when account uses 'account' instead of 'account_id'."""
        with patch.dict(
            os.environ,
            {
                "ADDITIONAL_CHARGES_TABLE": "test-charges-table",
                "MODEL_RATE_TABLE": "test-model-rate-table",
            },
        ):
            # Mock datetime
            with patch("pycommon.api.accounting.datetime") as mock_datetime:
                mock_now = Mock()
                mock_now.isoformat.return_value = "2023-01-01T12:00:00Z"
                mock_datetime.now.return_value = mock_now

                # Mock DynamoDB responses
                mock_dynamodb = Mock()
                mock_get_client.return_value = mock_dynamodb
                mock_dynamodb.query.return_value = {
                    "Items": [{"InputCostPerThousandTokens": {"N": "0.0001"}}]
                }
                mock_dynamodb.put_item.return_value = None

                # Account with 'account' instead of 'account_id'
                account_alt = {
                    "user": "test-user@example.com",
                    "account": "alt-acc-456",
                }

                result = record_additional_charge(
                    account_alt, "text-embedding-3-small", 1000, "embedding"
                )

                assert result > 0.0

                # Verify accountId was set correctly
                put_item_call = mock_dynamodb.put_item.call_args
                item = put_item_call[1]["Item"]
                assert item["accountId"]["S"] == "alt-acc-456"

    @patch("pycommon.api.accounting._get_dynamodb_client")
    @patch("pycommon.api.accounting.logger")
    @patch("pycommon.api.accounting.uuid")
    def test_charge_recording_with_no_account_id_uses_default(
        self, mock_uuid, mock_logger, mock_get_client
    ):
        """Test charge recording uses 'general_account' when no account_id."""
        with patch.dict(
            os.environ,
            {
                "ADDITIONAL_CHARGES_TABLE": "test-charges-table",
                "MODEL_RATE_TABLE": "test-model-rate-table",
            },
        ):
            # Mock datetime
            with patch("pycommon.api.accounting.datetime") as mock_datetime:
                mock_now = Mock()
                mock_now.isoformat.return_value = "2023-01-01T12:00:00Z"
                mock_datetime.now.return_value = mock_now

                # Mock DynamoDB responses
                mock_dynamodb = Mock()
                mock_get_client.return_value = mock_dynamodb
                mock_dynamodb.query.return_value = {
                    "Items": [{"InputCostPerThousandTokens": {"N": "0.0001"}}]
                }
                mock_dynamodb.put_item.return_value = None

                # Account without account_id or account
                account_no_id = {"user": "test-user@example.com"}

                result = record_additional_charge(
                    account_no_id, "text-embedding-3-small", 1000, "embedding"
                )

                assert result > 0.0

                # Verify default accountId was used
                put_item_call = mock_dynamodb.put_item.call_args
                item = put_item_call[1]["Item"]
                assert item["accountId"]["S"] == "general_account"

    @patch("pycommon.api.accounting._get_dynamodb_client")
    @patch("pycommon.api.accounting.logger")
    @patch("pycommon.api.accounting.uuid")
    def test_charge_recording_for_different_item_types(
        self, mock_uuid, mock_logger, mock_get_client
    ):
        """Test charge recording works for various item types."""
        with patch.dict(
            os.environ,
            {
                "ADDITIONAL_CHARGES_TABLE": "test-charges-table",
                "MODEL_RATE_TABLE": "test-model-rate-table",
            },
        ):
            # Mock datetime
            with patch("pycommon.api.accounting.datetime") as mock_datetime:
                mock_now = Mock()
                mock_now.isoformat.return_value = "2023-01-01T12:00:00Z"
                mock_datetime.now.return_value = mock_now

                # Mock DynamoDB responses
                mock_dynamodb = Mock()
                mock_get_client.return_value = mock_dynamodb
                mock_dynamodb.query.return_value = {
                    "Items": [{"InputCostPerThousandTokens": {"N": "0.01"}}]
                }
                mock_dynamodb.put_item.return_value = None

                item_types = [
                    "embedding",
                    "image_generation",
                    "fine_tuning",
                    "audio_transcription",
                ]

                for item_type in item_types:
                    result = record_additional_charge(
                        self.account, "test-model", 100, item_type
                    )

                    assert result > 0.0

                    # Verify item type at top level and in details
                    put_item_call = mock_dynamodb.put_item.call_args
                    item = put_item_call[1]["Item"]
                    assert item["itemType"]["S"] == item_type
                    assert item["details"]["M"]["itemType"]["S"] == item_type

    @patch("pycommon.api.accounting._get_dynamodb_client")
    @patch("pycommon.api.accounting.logger")
    @patch("pycommon.api.accounting.uuid")
    def test_item_type_stored_as_top_level_column(
        self, mock_uuid, mock_logger, mock_get_client
    ):
        """Test that itemType is stored as a top-level column for easy querying."""
        with patch.dict(
            os.environ,
            {
                "ADDITIONAL_CHARGES_TABLE": "test-charges-table",
                "MODEL_RATE_TABLE": "test-model-rate-table",
            },
        ):
            # Mock datetime
            with patch("pycommon.api.accounting.datetime") as mock_datetime:
                mock_now = Mock()
                mock_now.isoformat.return_value = "2023-01-01T12:00:00Z"
                mock_datetime.now.return_value = mock_now

                # Mock DynamoDB responses
                mock_dynamodb = Mock()
                mock_get_client.return_value = mock_dynamodb
                mock_dynamodb.query.return_value = {
                    "Items": [{"InputCostPerThousandTokens": {"N": "0.0001"}}]
                }
                mock_dynamodb.put_item.return_value = None

                result = record_additional_charge(
                    self.account,
                    "text-embedding-3-small",
                    1000,
                    "embedding",
                    details={"document_key": "test.pdf"},
                )

                assert result > 0.0

                # Verify itemType is at top level (for DynamoDB GSI queries)
                put_item_call = mock_dynamodb.put_item.call_args
                item = put_item_call[1]["Item"]

                # Top-level itemType column exists
                assert "itemType" in item
                assert item["itemType"]["S"] == "embedding"

                # Also preserved in details for backward compatibility
                assert "itemType" in item["details"]["M"]
                assert item["details"]["M"]["itemType"]["S"] == "embedding"

    @patch("pycommon.api.accounting._get_dynamodb_client")
    @patch("pycommon.api.accounting.logger")
    @patch("pycommon.api.accounting.uuid")
    @patch("pycommon.api.accounting.log_critical_error")
    def test_logs_error_when_critical_logging_fails(
        self, mock_log_critical, mock_uuid, mock_logger, mock_get_client
    ):
        """Test that error is logged if critical error logging itself fails."""
        with patch.dict(
            os.environ,
            {
                "ADDITIONAL_CHARGES_TABLE": "test-charges-table",
                "MODEL_RATE_TABLE": "test-model-rate-table",
            },
        ):
            mock_dynamodb = Mock()
            mock_get_client.return_value = mock_dynamodb
            mock_dynamodb.query.side_effect = Exception("DynamoDB error")

            # Make critical logging fail too
            mock_log_critical.side_effect = Exception("Logging error")

            result = record_additional_charge(
                self.account, "text-embedding-3-small", 1000, "embedding"
            )

            assert result == 0.0
            # Verify that the failure to log critical error was also logged
            assert mock_logger.error.call_count >= 2
            calls = [str(call) for call in mock_logger.error.call_args_list]
            assert any("Failed to log critical error" in call for call in calls)

    @patch("pycommon.api.accounting._get_dynamodb_client")
    @patch("pycommon.api.accounting.logger")
    @patch("pycommon.api.accounting.uuid")
    def test_successful_charge_recording_with_boolean_details(
        self, mock_uuid, mock_logger, mock_get_client
    ):
        """Test successful charge recording with boolean value in details."""
        with patch.dict(
            os.environ,
            {
                "ADDITIONAL_CHARGES_TABLE": "test-charges-table",
                "MODEL_RATE_TABLE": "test-model-rate-table",
            },
        ):
            # Mock datetime
            with patch("pycommon.api.accounting.datetime") as mock_datetime:
                mock_now = Mock()
                mock_now.isoformat.return_value = "2023-01-01T12:00:00Z"
                mock_datetime.now.return_value = mock_now

                # Mock DynamoDB responses
                mock_dynamodb = Mock()
                mock_get_client.return_value = mock_dynamodb
                mock_dynamodb.query.return_value = {
                    "Items": [{"InputCostPerThousandTokens": {"N": "0.0001"}}]
                }
                mock_dynamodb.put_item.return_value = None

                details = {"is_production": False}

                result = record_additional_charge(
                    self.account,
                    "text-embedding-3-small",
                    1000,
                    "embedding",
                    details=details,
                )

                assert result > 0.0

                # Verify boolean was properly serialized
                put_item_call = mock_dynamodb.put_item.call_args
                item = put_item_call[1]["Item"]
                item_details = item["details"]["M"]
                assert "is_production" in item_details
                # Boolean values are stored with BOOL type in DynamoDB
                assert "BOOL" in item_details["is_production"]

    @patch("pycommon.api.accounting._get_dynamodb_client")
    @patch("pycommon.api.accounting.logger")
    @patch("pycommon.api.accounting.uuid")
    def test_successful_charge_recording_with_mixed_type_details(
        self, mock_uuid, mock_logger, mock_get_client
    ):
        """Test successful charge recording with all detail value types."""
        with patch.dict(
            os.environ,
            {
                "ADDITIONAL_CHARGES_TABLE": "test-charges-table",
                "MODEL_RATE_TABLE": "test-model-rate-table",
            },
        ):
            # Mock datetime
            with patch("pycommon.api.accounting.datetime") as mock_datetime:
                mock_now = Mock()
                mock_now.isoformat.return_value = "2023-01-01T12:00:00Z"
                mock_datetime.now.return_value = mock_now

                # Mock DynamoDB responses
                mock_dynamodb = Mock()
                mock_get_client.return_value = mock_dynamodb
                mock_dynamodb.query.return_value = {
                    "Items": [{"InputCostPerThousandTokens": {"N": "0.0001"}}]
                }
                mock_dynamodb.put_item.return_value = None

                details = {
                    "string_field": "test_value",
                    "int_field": 42,
                    "float_field": 3.14,
                    "bool_field": True,
                    "dict_field": {"nested_key": "nested_value"},
                }

                result = record_additional_charge(
                    self.account,
                    "text-embedding-3-small",
                    1000,
                    "embedding",
                    details=details,
                )

                assert result > 0.0

                # Verify all types were properly serialized
                put_item_call = mock_dynamodb.put_item.call_args
                item = put_item_call[1]["Item"]
                item_details = item["details"]["M"]
                assert "string_field" in item_details
                assert item_details["string_field"]["S"] == "test_value"
                assert "int_field" in item_details
                assert item_details["int_field"]["N"] == "42"
                assert "float_field" in item_details
                assert item_details["float_field"]["N"] == "3.14"
                assert "bool_field" in item_details
                assert "BOOL" in item_details["bool_field"]
                assert "dict_field" in item_details
                assert "M" in item_details["dict_field"]

    @patch("pycommon.api.accounting._get_dynamodb_client")
    @patch("pycommon.api.accounting.logger")
    @patch("pycommon.api.accounting.uuid")
    def test_successful_charge_recording_with_flat_cost(
        self, mock_uuid, mock_logger, mock_get_client
    ):
        """Test successful charge recording with flat cost (no model rate lookup)."""
        with patch.dict(
            os.environ,
            {
                "ADDITIONAL_CHARGES_TABLE": "test-charges-table",
                "MODEL_RATE_TABLE": "test-model-rate-table",
            },
        ):
            # Mock datetime
            with patch("pycommon.api.accounting.datetime") as mock_datetime:
                mock_now = Mock()
                mock_now.isoformat.return_value = "2023-01-01T12:00:00Z"
                mock_datetime.now.return_value = mock_now

                # Mock DynamoDB responses
                mock_dynamodb = Mock()
                mock_get_client.return_value = mock_dynamodb
                # No query should be made when flat_cost is provided
                mock_dynamodb.put_item.return_value = None

                # Code interpreter session: flat $0.03 fee
                result = record_additional_charge(
                    self.account,
                    "gpt-4o",
                    token_count=0,  # Not used with flat_cost
                    item_type="codeInterpreterSession",
                    request_id="session-123",
                    details={"session_duration": "1h"},
                    flat_cost=0.03,  # Flat fee
                )

                # Should return exactly the flat cost
                assert result == 0.03

                # Verify NO model rate query was made
                mock_dynamodb.query.assert_not_called()

                # Verify put_item was called with correct cost
                put_item_call = mock_dynamodb.put_item.call_args
                item = put_item_call[1]["Item"]
                assert item["cost"]["N"] == "0.03"
                assert item["itemType"]["S"] == "codeInterpreterSession"

    @patch("pycommon.api.accounting._get_dynamodb_client")
    @patch("pycommon.api.accounting.logger")
    @patch("pycommon.api.accounting.uuid")
    def test_successful_charge_recording_with_other_types_in_details(
        self, mock_uuid, mock_logger, mock_get_client
    ):
        """Test successful charge recording with other types (list, None) in details."""
        with patch.dict(
            os.environ,
            {
                "ADDITIONAL_CHARGES_TABLE": "test-charges-table",
                "MODEL_RATE_TABLE": "test-model-rate-table",
            },
        ):
            # Mock datetime
            with patch("pycommon.api.accounting.datetime") as mock_datetime:
                mock_now = Mock()
                mock_now.isoformat.return_value = "2023-01-01T12:00:00Z"
                mock_datetime.now.return_value = mock_now

                # Mock DynamoDB responses
                mock_dynamodb = Mock()
                mock_get_client.return_value = mock_dynamodb
                mock_dynamodb.query.return_value = {
                    "Items": [{"InputCostPerThousandTokens": {"N": "0.0001"}}]
                }
                mock_dynamodb.put_item.return_value = None

                details = {
                    "list_field": ["item1", "item2"],
                    "none_field": None,
                }

                result = record_additional_charge(
                    self.account,
                    "text-embedding-3-small",
                    1000,
                    "embedding",
                    details=details,
                )

                assert result > 0.0

                # Verify other types were converted to strings
                put_item_call = mock_dynamodb.put_item.call_args
                item = put_item_call[1]["Item"]
                item_details = item["details"]["M"]
                assert "list_field" in item_details
                assert item_details["list_field"]["S"] == str(["item1", "item2"])
                assert "none_field" in item_details
                assert item_details["none_field"]["S"] == "None"
