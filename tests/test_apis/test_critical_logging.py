# =============================================================================
# Tests for api/critical_logging.py
# =============================================================================

import json
import os
from unittest.mock import patch

from botocore.exceptions import ClientError

from pycommon.api.critical_logging import (
    SEVERITY_CRITICAL,
    SEVERITY_HIGH,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    log_critical_error,
)
from pycommon.exceptions import EnvVarError


class TestLogCriticalError:
    """Test cases for log_critical_error function."""

    @patch.dict(
        os.environ,
        {
            "CRITICAL_ERRORS_SQS_QUEUE_NAME": (
                "https://sqs.us-east-1.amazonaws.com/123456789012/critical-errors"
            )
        },
    )
    @patch("pycommon.api.critical_logging.sqs_client")
    @patch("pycommon.api.critical_logging.logger")
    def test_log_critical_error_success_minimal_params(
        self, mock_logger, mock_sqs_client
    ):
        """Test successful logging with minimal required parameters."""
        result = log_critical_error(
            function_name="test_function",
            error_type="TestError",
            error_message="Test error message",
        )

        # Verify result is always success
        assert result == {
            "success": True,
            "message": "Critical error queued for processing",
        }

        # Verify SQS call
        expected_message_body = {
            "service_name": "unknown",  # Default value
            "function_name": "test_function",
            "error_type": "TestError",
            "error_message": "Test error message",
            "current_user": None,
            "severity": SEVERITY_CRITICAL,
            "stack_trace": None,
            "context": None,
        }

        mock_sqs_client.send_message.assert_called_once_with(
            QueueUrl=(
                "https://sqs.us-east-1.amazonaws.com/123456789012/critical-errors"
            ),
            MessageBody=json.dumps(expected_message_body),
            MessageAttributes={
                "severity": {"StringValue": SEVERITY_CRITICAL, "DataType": "String"},
                "service_name": {"StringValue": "unknown", "DataType": "String"},
            },
        )

        # Verify logging
        mock_logger.info.assert_called_once_with(
            "Critical error queued: %s.%s | Type: %s",
            "unknown",
            "test_function",
            "TestError",
        )

    @patch.dict(
        os.environ,
        {
            "CRITICAL_ERRORS_SQS_QUEUE_NAME": (
                "https://sqs.us-east-1.amazonaws.com/123456789012/critical-errors"
            ),
            "SERVICE_NAME": "payment-service",
        },
    )
    @patch("pycommon.api.critical_logging.sqs_client")
    @patch("pycommon.api.critical_logging.logger")
    def test_log_critical_error_success_all_params(self, mock_logger, mock_sqs_client):
        """Test successful logging with all parameters provided."""
        context = {"order_id": 123, "amount": 99.99}
        stack_trace = "Traceback (most recent call last):\n  File..."

        result = log_critical_error(
            service_name="custom-service",
            function_name="process_payment",
            error_type="PaymentError",
            error_message="Payment failed",
            current_user="user@example.com",
            severity=SEVERITY_HIGH,
            stack_trace=stack_trace,
            context=context,
        )

        # Verify result
        assert result == {
            "success": True,
            "message": "Critical error queued for processing",
        }

        # Verify SQS call with all parameters
        expected_message_body = {
            "service_name": "custom-service",  # Explicit override
            "function_name": "process_payment",
            "error_type": "PaymentError",
            "error_message": "Payment failed",
            "current_user": "user@example.com",
            "severity": SEVERITY_HIGH,
            "stack_trace": stack_trace,
            "context": context,
        }

        mock_sqs_client.send_message.assert_called_once_with(
            QueueUrl=(
                "https://sqs.us-east-1.amazonaws.com/123456789012/critical-errors"
            ),
            MessageBody=json.dumps(expected_message_body),
            MessageAttributes={
                "severity": {"StringValue": SEVERITY_HIGH, "DataType": "String"},
                "service_name": {"StringValue": "custom-service", "DataType": "String"},
            },
        )

    @patch("pycommon.api.critical_logging.sqs_client")
    @patch("pycommon.api.critical_logging.logger")
    def test_log_critical_error_missing_queue_url(self, mock_logger, mock_sqs_client):
        """Test behavior when CRITICAL_ERRORS_SQS_QUEUE_NAME is not set."""
        # Ensure queue URL is not in environment
        if "CRITICAL_ERRORS_SQS_QUEUE_NAME" in os.environ:
            del os.environ["CRITICAL_ERRORS_SQS_QUEUE_NAME"]

        result = log_critical_error(
            function_name="test_function",
            error_type="TestError",
            error_message="Test message",
        )

        # Should still return success (fail-safe)
        assert result == {
            "success": True,
            "message": "Queue URL not configured, error not logged",
        }

        # Should not call SQS
        mock_sqs_client.send_message.assert_not_called()

        # Should log warning
        mock_logger.warning.assert_called_once_with(
            "CRITICAL_ERRORS_SQS_QUEUE_NAME not available, cannot log: %s.%s - %s",
            "unknown",
            "test_function",
            "TestError",
        )

    @patch.dict(
        os.environ,
        {
            "CRITICAL_ERRORS_SQS_QUEUE_NAME": (
                "https://sqs.us-east-1.amazonaws.com/123456789012/critical-errors"
            ),
            "SERVICE_NAME": "auto-detected-service",
        },
    )
    @patch("pycommon.api.critical_logging.sqs_client")
    def test_log_critical_error_auto_detect_service_name_from_env(
        self, mock_sqs_client
    ):
        """Test service_name auto-detected from SERVICE_NAME env var when None."""
        result = log_critical_error(
            function_name="test_function",
            error_type="TestError",
            error_message="Test message",
            # service_name=None (not provided, will auto-detect)
        )

        assert result["success"] is True

        # Verify service_name was auto-detected from SERVICE_NAME env var
        call_args = mock_sqs_client.send_message.call_args
        message_body = json.loads(call_args[1]["MessageBody"])
        assert message_body["service_name"] == "auto-detected-service"

        # Verify message attributes
        message_attrs = call_args[1]["MessageAttributes"]
        assert message_attrs["service_name"]["StringValue"] == "auto-detected-service"

    @patch.dict(
        os.environ,
        {
            "CRITICAL_ERRORS_SQS_QUEUE_NAME": (
                "https://sqs.us-east-1.amazonaws.com/123456789012/critical-errors"
            )
        },
    )
    @patch("pycommon.api.critical_logging.sqs_client")
    def test_log_critical_error_auto_detect_service_name_default_unknown(
        self, mock_sqs_client
    ):
        """Test service_name defaults to 'unknown' when SERVICE_NAME not set."""
        # Ensure SERVICE_NAME is not in environment
        if "SERVICE_NAME" in os.environ:
            del os.environ["SERVICE_NAME"]

        result = log_critical_error(
            function_name="test_function",
            error_type="TestError",
            error_message="Test message",
            # service_name=None (not provided, will default to "unknown")
        )

        assert result["success"] is True

        # Verify service_name defaulted to "unknown"
        call_args = mock_sqs_client.send_message.call_args
        message_body = json.loads(call_args[1]["MessageBody"])
        assert message_body["service_name"] == "unknown"

    @patch.dict(
        os.environ,
        {
            "CRITICAL_ERRORS_SQS_QUEUE_NAME": (
                "https://sqs.us-east-1.amazonaws.com/123456789012/critical-errors"
            )
        },
    )
    @patch("pycommon.api.critical_logging.sqs_client")
    def test_log_critical_error_different_severity_levels(self, mock_sqs_client):
        """Test logging with different severity levels."""
        severity_levels = [
            SEVERITY_CRITICAL,
            SEVERITY_HIGH,
            SEVERITY_MEDIUM,
            SEVERITY_LOW,
        ]

        for severity in severity_levels:
            mock_sqs_client.reset_mock()

            result = log_critical_error(
                function_name="test_function",
                error_type="TestError",
                error_message="Test message",
                severity=severity,
            )

            assert result["success"] is True

            # Verify severity in message body and attributes
            call_args = mock_sqs_client.send_message.call_args
            message_body = json.loads(call_args[1]["MessageBody"])
            assert message_body["severity"] == severity

            message_attrs = call_args[1]["MessageAttributes"]
            assert message_attrs["severity"]["StringValue"] == severity

    @patch.dict(
        os.environ,
        {
            "CRITICAL_ERRORS_SQS_QUEUE_NAME": (
                "https://sqs.us-east-1.amazonaws.com/123456789012/critical-errors"
            )
        },
    )
    @patch("pycommon.api.critical_logging.sqs_client")
    @patch("pycommon.api.critical_logging.logger")
    def test_log_critical_error_sqs_client_error(self, mock_logger, mock_sqs_client):
        """Test handling of SQS ClientError (fail-safe behavior)."""
        # Mock SQS to raise ClientError
        client_error = ClientError(
            {
                "Error": {
                    "Code": "QueueDoesNotExist",
                    "Message": "Queue not found",
                }
            },
            "SendMessage",
        )
        mock_sqs_client.send_message.side_effect = client_error

        result = log_critical_error(
            function_name="test_function",
            error_type="TestError",
            error_message="Test message",
        )

        # Should still return success (fail-safe)
        assert result == {"success": True, "message": "SQS error, logged locally only"}

        # Verify error was logged
        mock_logger.error.assert_called_once()
        error_call = mock_logger.error.call_args[0][0]
        assert "SQS error logging critical error (fail-safe mode)" in error_call

    @patch.dict(
        os.environ,
        {
            "CRITICAL_ERRORS_SQS_QUEUE_NAME": (
                "https://sqs.us-east-1.amazonaws.com/123456789012/critical-errors"
            )
        },
    )
    @patch("pycommon.api.critical_logging.sqs_client")
    @patch("pycommon.api.critical_logging.logger")
    def test_log_critical_error_general_exception(self, mock_logger, mock_sqs_client):
        """Test handling of general exceptions (fail-safe behavior)."""
        # Mock SQS to raise general exception
        mock_sqs_client.send_message.side_effect = Exception("Unexpected error")

        result = log_critical_error(
            function_name="test_function",
            error_type="TestError",
            error_message="Test message",
        )

        # Should still return success (fail-safe)
        assert result == {
            "success": True,
            "message": "Unexpected error, logged locally only",
        }

        # Verify error was logged
        mock_logger.error.assert_called_once()
        error_call = mock_logger.error.call_args[0][0]
        assert "Unexpected error logging critical error (fail-safe mode)" in error_call

    @patch.dict(
        os.environ,
        {
            "CRITICAL_ERRORS_SQS_QUEUE_NAME": (
                "https://sqs.us-east-1.amazonaws.com/123456789012/critical-errors"
            )
        },
    )
    @patch("pycommon.api.critical_logging.sqs_client")
    def test_log_critical_error_message_body_structure(self, mock_sqs_client):
        """Test that message body has correct structure."""
        context = {"key": "value", "number": 42}
        stack_trace = "Traceback..."

        result = log_critical_error(
            service_name="test-service",
            function_name="test_function",
            error_type="TestError",
            error_message="Test message",
            current_user="testuser@example.com",
            severity=SEVERITY_MEDIUM,
            stack_trace=stack_trace,
            context=context,
        )

        assert result["success"] is True

        # Verify message body structure
        call_args = mock_sqs_client.send_message.call_args
        message_body = json.loads(call_args[1]["MessageBody"])

        expected_body = {
            "service_name": "test-service",
            "function_name": "test_function",
            "error_type": "TestError",
            "error_message": "Test message",
            "current_user": "testuser@example.com",
            "severity": SEVERITY_MEDIUM,
            "stack_trace": stack_trace,
            "context": context,
        }

        assert message_body == expected_body

    @patch.dict(
        os.environ,
        {
            "CRITICAL_ERRORS_SQS_QUEUE_NAME": (
                "https://sqs.us-east-1.amazonaws.com/123456789012/critical-errors"
            )
        },
    )
    @patch("pycommon.api.critical_logging.sqs_client")
    def test_log_critical_error_message_attributes(self, mock_sqs_client):
        """Test that SQS message attributes are set correctly."""
        result = log_critical_error(
            service_name="attr-service",
            function_name="test_function",
            error_type="TestError",
            error_message="Test message",
            severity=SEVERITY_LOW,
        )

        assert result["success"] is True

        # Verify message attributes
        call_args = mock_sqs_client.send_message.call_args
        message_attrs = call_args[1]["MessageAttributes"]

        expected_attrs = {
            "severity": {"StringValue": SEVERITY_LOW, "DataType": "String"},
            "service_name": {"StringValue": "attr-service", "DataType": "String"},
        }

        assert message_attrs == expected_attrs

    @patch("pycommon.api.critical_logging.sqs_client")
    @patch("pycommon.api.critical_logging.logger")
    def test_log_critical_error_missing_queue_url_with_service_name(
        self, mock_logger, mock_sqs_client
    ):
        """Test warning message includes service_name when queue URL missing."""
        # Ensure queue URL is not in environment
        if "CRITICAL_ERRORS_SQS_QUEUE_NAME" in os.environ:
            del os.environ["CRITICAL_ERRORS_SQS_QUEUE_NAME"]

        result = log_critical_error(
            service_name="warning-service",
            function_name="test_function",
            error_type="TestError",
            error_message="Test message",
        )

        assert result["success"] is True

        # Should log warning with service name
        mock_logger.warning.assert_called_once_with(
            "CRITICAL_ERRORS_SQS_QUEUE_NAME not available, cannot log: %s.%s - %s",
            "warning-service",
            "test_function",
            "TestError",
        )

    @patch("pycommon.api.critical_logging._log_critical_error_internal")
    @patch("pycommon.api.critical_logging.logger")
    def test_log_critical_error_env_var_error_fail_safe(
        self, mock_logger, mock_internal_function
    ):
        """Test fail-safe behavior when @required_env_vars raises EnvVarError."""
        # Mock the internal function to raise EnvVarError
        mock_internal_function.side_effect = EnvVarError(
            "Environment variable 'CRITICAL_ERRORS_SQS_QUEUE_NAME' not found"
        )

        result = log_critical_error(
            function_name="test_function",
            error_type="TestError",
            error_message="Test message",
            service_name="test-service",
        )

        # Should still return success (fail-safe behavior)
        assert result == {
            "success": True,
            "message": "Queue URL not configured, error not logged",
        }

        # Verify internal function was called with correct parameters
        mock_internal_function.assert_called_once_with(
            function_name="test_function",
            error_type="TestError",
            error_message="Test message",
            current_user=None,
            severity=SEVERITY_CRITICAL,
            stack_trace=None,
            context=None,
            service_name="test-service",
        )

        # Should log warning about environment variable not being available
        mock_logger.warning.assert_called_once_with(
            "CRITICAL_ERRORS_SQS_QUEUE_NAME not available, cannot log: %s.%s - %s",
            "test-service",
            "test_function",
            "TestError",
        )

    @patch("pycommon.api.critical_logging._log_critical_error_internal")
    @patch("pycommon.api.critical_logging.logger")
    def test_log_critical_error_decorator_benefits_when_available(
        self, mock_logger, mock_internal_function
    ):
        """Test decorator benefits used when environment variable is available."""
        # Mock successful internal function call
        expected_result = {
            "success": True,
            "message": "Critical error queued for processing",
        }
        mock_internal_function.return_value = expected_result

        result = log_critical_error(
            function_name="test_function",
            error_type="TestError",
            error_message="Test message",
        )

        # Should return result from internal function
        assert result == expected_result

        # Verify internal decorated function was called
        mock_internal_function.assert_called_once_with(
            function_name="test_function",
            error_type="TestError",
            error_message="Test message",
            current_user=None,
            severity=SEVERITY_CRITICAL,
            stack_trace=None,
            context=None,
            service_name=None,
        )

        # Should not call logger.warning (no fallback needed)
        mock_logger.warning.assert_not_called()
