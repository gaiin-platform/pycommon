"""Tests for usage_tracker module

Copyright (c) 2025 Vanderbilt University
"""

import os
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

from pycommon.metrics.usage_tracker import (
    LambdaExecutionMetrics,
    UsageTracker,
    get_usage_tracker,
)


class TestLambdaExecutionMetrics:
    """Tests for LambdaExecutionMetrics dataclass"""

    def test_estimated_cost_calculation(self):
        """Test AWS Lambda cost calculation"""
        start = datetime.now()
        end = start + timedelta(seconds=2)  # 2 second execution

        metrics = LambdaExecutionMetrics(
            start_timestamp=start,
            end_timestamp=end,
            duration_ms=2000.0,
            user="test_user",
            account="test_account",
            api_key_id=None,
            operation="test_op",
            endpoint="/test",
            api_accessed=False,
            status_code=200,
            success=True,
            error_type=None,
            request_id="test-request-123",
            memory_limit_mb=1024,  # 1 GB
        )

        cost = metrics.estimated_cost_usd()

        # 1 GB * 2 seconds = 2 GB-seconds
        # 2 * 0.0000166667 = 0.0000333334
        expected_cost = Decimal("0.0000333334")

        assert abs(cost - expected_cost) < Decimal("0.0000000001")

    def test_estimated_cost_with_512mb(self):
        """Test cost calculation with 512MB memory"""
        start = datetime.now()
        end = start + timedelta(milliseconds=500)  # 500ms execution

        metrics = LambdaExecutionMetrics(
            start_timestamp=start,
            end_timestamp=end,
            duration_ms=500.0,
            user="test_user",
            account="test_account",
            api_key_id=None,
            operation="test_op",
            endpoint="/test",
            api_accessed=False,
            status_code=200,
            success=True,
            error_type=None,
            request_id="test-request-123",
            memory_limit_mb=512,  # 0.5 GB
        )

        cost = metrics.estimated_cost_usd()

        # 0.5 GB * 0.5 seconds = 0.25 GB-seconds
        # 0.25 * 0.0000166667 = 0.0000041667
        expected_cost = Decimal("0.0000041667")

        assert abs(cost - expected_cost) < Decimal("0.0000000001")

    def test_estimated_cost_with_no_memory(self):
        """Test cost calculation returns zero when memory limit is None"""
        start = datetime.now()
        end = start + timedelta(seconds=1)

        metrics = LambdaExecutionMetrics(
            start_timestamp=start,
            end_timestamp=end,
            duration_ms=1000.0,
            user="test_user",
            account="test_account",
            api_key_id=None,
            operation="test_op",
            endpoint="/test",
            api_accessed=False,
            status_code=200,
            success=True,
            error_type=None,
            request_id="test-request-123",
            memory_limit_mb=None,
        )

        cost = metrics.estimated_cost_usd()
        assert cost == Decimal("0.0")

    def test_to_dynamodb_item_all_fields(self):
        """Test conversion to DynamoDB item with all fields"""
        start = datetime(2025, 1, 15, 10, 30, 0)
        end = datetime(2025, 1, 15, 10, 30, 2)

        metrics = LambdaExecutionMetrics(
            start_timestamp=start,
            end_timestamp=end,
            duration_ms=2000.0,
            user="test_user",
            account="test_account",
            api_key_id="api-key-123",
            operation="create",
            endpoint="/api/resource",
            api_accessed=True,
            status_code=201,
            success=True,
            error_type="ValueError",
            request_id="req-123",
            memory_limit_mb=1024,
            purpose="group_system",
            service_name="amplify-lambda",
            function_name="test_function",
        )

        item = metrics.to_dynamodb_item()

        assert item["account"] == "test_account"
        assert item["timestamp"] == "2025-01-15T10:30:00"
        assert item["user"] == "test_user"
        assert item["operation"] == "create"
        assert item["endpoint"] == "/api/resource"
        assert item["duration_ms"] == Decimal("2000.0")
        assert item["status_code"] == 201
        assert item["success"] is True
        assert item["api_accessed"] is True
        assert item["api_key_id"] == "api-key-123"
        assert item["error_type"] == "ValueError"  # Now included
        assert item["request_id"] == "req-123"
        assert item["memory_limit_mb"] == 1024
        assert item["purpose"] == "group_system"
        assert item["service_name"] == "amplify-lambda"
        assert item["function_name"] == "test_function"
        assert "estimated_cost_usd" in item

    def test_to_dynamodb_item_minimal_fields(self):
        """Test conversion to DynamoDB item with only required fields"""
        start = datetime.now()
        end = start + timedelta(seconds=1)

        metrics = LambdaExecutionMetrics(
            start_timestamp=start,
            end_timestamp=end,
            duration_ms=1000.0,
            user="test_user",
            account="test_account",
            api_key_id=None,
            operation="read",
            endpoint="/api/resource",
            api_accessed=False,
            status_code=200,
            success=True,
            error_type=None,
            request_id=None,
            memory_limit_mb=None,
        )

        item = metrics.to_dynamodb_item()

        # Required fields
        assert item["account"] == "test_account"
        assert item["user"] == "test_user"
        assert item["operation"] == "read"
        assert item["endpoint"] == "/api/resource"

        # Optional fields should not be present
        assert "api_key_id" not in item
        assert "error_type" not in item
        assert "request_id" not in item
        assert "memory_limit_mb" not in item
        assert "purpose" not in item

    def test_success_field_based_on_status_code(self):
        """Test that success field is correctly set based on status code"""
        start = datetime.now()
        end = start + timedelta(seconds=1)

        # Successful execution (200)
        metrics_success = LambdaExecutionMetrics(
            start_timestamp=start,
            end_timestamp=end,
            duration_ms=1000.0,
            user="test_user",
            account="test_account",
            api_key_id=None,
            operation="test_op",
            endpoint="/test",
            api_accessed=False,
            status_code=200,
            success=True,
            error_type=None,
            request_id=None,
            memory_limit_mb=None,
        )
        assert metrics_success.success is True

        # Failed execution (500)
        metrics_fail = LambdaExecutionMetrics(
            start_timestamp=start,
            end_timestamp=end,
            duration_ms=1000.0,
            user="test_user",
            account="test_account",
            api_key_id=None,
            operation="test_op",
            endpoint="/test",
            api_accessed=False,
            status_code=500,
            success=False,
            error_type="InternalServerError",
            request_id=None,
            memory_limit_mb=None,
        )
        assert metrics_fail.success is False
        assert metrics_fail.error_type == "InternalServerError"


class TestUsageTracker:
    """Tests for UsageTracker class"""

    @patch.dict(os.environ, {"ADDITIONAL_CHARGES_TABLE": "test-metrics-table"})
    @patch("pycommon.metrics.usage_tracker.boto3")
    def test_initialization_with_env_var(self, mock_boto3):
        """Test tracker initialization with environment variable"""
        mock_dynamodb = Mock()
        mock_boto3.resource.return_value = mock_dynamodb

        tracker = UsageTracker()

        assert tracker.enabled is True
        assert tracker.table_name == "test-metrics-table"
        mock_boto3.resource.assert_called_once_with("dynamodb")

    @patch.dict(os.environ, {}, clear=True)
    def test_initialization_without_table_name(self):
        """Test tracker disables when no table name provided"""
        tracker = UsageTracker()

        assert tracker.enabled is False

    @patch.dict(os.environ, {"ENABLE_USAGE_TRACKING": "false"})
    def test_initialization_disabled_via_env_var(self):
        """Test tracker can be disabled via environment variable"""
        tracker = UsageTracker(dynamodb_table="test-table")

        assert tracker.enabled is False

    @patch.dict(os.environ, {"ADDITIONAL_CHARGES_TABLE": "test-table"})
    @patch("pycommon.metrics.usage_tracker.boto3")
    def test_initialization_boto3_exception(self, mock_boto3):
        """Test tracker disables when boto3 fails"""
        mock_boto3.resource.side_effect = Exception("AWS credentials error")

        tracker = UsageTracker()

        assert tracker.enabled is False

    @patch.dict(os.environ, {"ADDITIONAL_CHARGES_TABLE": "test-table"})
    @patch("pycommon.metrics.usage_tracker.boto3")
    def test_start_tracking(self, mock_boto3):
        """Test start_tracking creates proper context"""
        mock_dynamodb = Mock()
        mock_boto3.resource.return_value = mock_dynamodb

        tracker = UsageTracker()

        mock_context = Mock()
        mock_context.aws_request_id = "req-123"
        mock_context.memory_limit_in_mb = 512

        before_start = datetime.utcnow()
        context = tracker.start_tracking(
            user="test_user",
            operation="create",
            endpoint="/api/resource",
            api_accessed=True,
            context=mock_context,
        )
        after_start = datetime.utcnow()

        assert context["user"] == "test_user"
        assert context["operation"] == "create"
        assert context["endpoint"] == "/api/resource"
        assert context["api_accessed"] is True
        assert context["request_id"] == "req-123"
        assert context["memory_limit"] == 512
        assert before_start <= context["start_time"] <= after_start

    def test_start_tracking_when_disabled(self):
        """Test start_tracking returns empty dict when disabled"""
        tracker = UsageTracker(enabled=False)

        context = tracker.start_tracking(
            user="test_user",
            operation="create",
            endpoint="/api/resource",
            api_accessed=True,
            context=Mock(),
        )

        assert context == {}

    @patch.dict(os.environ, {"ADDITIONAL_CHARGES_TABLE": "test-table"})
    @patch("pycommon.metrics.usage_tracker.boto3")
    def test_end_tracking(self, mock_boto3):
        """Test end_tracking creates metrics object"""
        mock_dynamodb = Mock()
        mock_boto3.resource.return_value = mock_dynamodb

        tracker = UsageTracker()

        start_time = datetime.utcnow()
        tracking_context = {
            "start_time": start_time,
            "user": "test_user",
            "operation": "create",
            "endpoint": "/api/resource",
            "api_accessed": True,
            "request_id": "req-123",
            "memory_limit": 1024,
        }

        claims = {
            "account": "test_account",
            "api_key_id": "api-key-123",
            "purpose": "testing",
        }

        result = {"statusCode": 201}

        metrics = tracker.end_tracking(tracking_context, result, claims)

        assert metrics is not None
        assert metrics.user == "test_user"
        assert metrics.account == "test_account"
        assert metrics.api_key_id == "api-key-123"
        assert metrics.operation == "create"
        assert metrics.endpoint == "/api/resource"
        assert metrics.api_accessed is True
        assert metrics.status_code == 201
        assert metrics.success is True
        assert metrics.error_type is None
        assert metrics.request_id == "req-123"
        assert metrics.memory_limit_mb == 1024
        assert metrics.purpose == "testing"
        assert metrics.duration_ms > 0

    @patch.dict(os.environ, {"ADDITIONAL_CHARGES_TABLE": "test-table"})
    @patch("pycommon.metrics.usage_tracker.boto3")
    def test_end_tracking_with_error(self, mock_boto3):
        """Test end_tracking with error information"""
        mock_dynamodb = Mock()
        mock_boto3.resource.return_value = mock_dynamodb

        tracker = UsageTracker()

        tracking_context = {
            "start_time": datetime.utcnow(),
            "user": "test_user",
            "operation": "delete",
            "endpoint": "/api/resource",
            "api_accessed": False,
            "request_id": "req-456",
            "memory_limit": 512,
        }

        claims = {"account": "test_account"}
        result = {"statusCode": 500}

        metrics = tracker.end_tracking(
            tracking_context, result, claims, error_type="InternalServerError"
        )

        assert metrics is not None
        assert metrics.status_code == 500
        assert metrics.success is False
        assert metrics.error_type == "InternalServerError"

    def test_end_tracking_when_disabled(self):
        """Test end_tracking returns None when disabled"""
        tracker = UsageTracker(enabled=False)

        metrics = tracker.end_tracking({}, {}, {})

        assert metrics is None

    @patch.dict(os.environ, {"ADDITIONAL_CHARGES_TABLE": "test-table"})
    @patch("pycommon.metrics.usage_tracker.boto3")
    def test_end_tracking_exception_handling(self, mock_boto3):
        """Test end_tracking handles exceptions gracefully"""
        mock_dynamodb = Mock()
        mock_boto3.resource.return_value = mock_dynamodb

        tracker = UsageTracker()

        # Pass invalid tracking context to trigger exception
        tracking_context = {"invalid": "data"}
        result = {"statusCode": 200}
        claims = {"account": "test"}

        metrics = tracker.end_tracking(tracking_context, result, claims)

        # Should return None on exception
        assert metrics is None

    @patch.dict(os.environ, {"ADDITIONAL_CHARGES_TABLE": "test-table"})
    @patch("pycommon.metrics.usage_tracker.boto3")
    def test_record_metrics(self, mock_boto3):
        """Test record_metrics stores in DynamoDB"""
        mock_dynamodb = Mock()
        mock_table = Mock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3.resource.return_value = mock_dynamodb

        tracker = UsageTracker()

        start = datetime.now()
        end = start + timedelta(seconds=1)

        metrics = LambdaExecutionMetrics(
            start_timestamp=start,
            end_timestamp=end,
            duration_ms=1000.0,
            user="test_user",
            account="test_account",
            api_key_id="api-key-123",
            operation="create",
            endpoint="/api/resource",
            api_accessed=True,
            status_code=200,
            success=True,
            error_type=None,
            request_id="req-123",
            memory_limit_mb=1024,
        )

        tracker.record_metrics(metrics)

        # Verify put_item was called
        mock_table.put_item.assert_called_once()
        call_args = mock_table.put_item.call_args
        item = call_args[1]["Item"]

        # Verify ADDITIONAL_CHARGES_TABLE format
        assert item["accountId"] == "test_account"
        assert item["user"] == "test_user"
        assert "id" in item  # user#lambda#uuid format
        assert item["id"].startswith("test_user#lambda#")
        assert "cost" in item  # Top-level cost field
        assert "ttl" in item  # 90-day TTL
        assert "details" in item  # All execution details nested
        assert item["details"]["itemType"] == "lambda_execution"
        assert item["details"]["execution"]["operation"] == "create"
        assert "modelId" in item  # service/function format
        assert "time" in item
        assert "requestId" in item

    @patch.dict(os.environ, {"ADDITIONAL_CHARGES_TABLE": "test-table"})
    @patch("pycommon.metrics.usage_tracker.boto3")
    def test_record_metrics_handles_errors(self, mock_boto3):
        """Test record_metrics handles errors gracefully"""
        mock_dynamodb = Mock()
        mock_table = Mock()
        mock_table.put_item.side_effect = Exception("DynamoDB error")
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3.resource.return_value = mock_dynamodb

        tracker = UsageTracker()

        start = datetime.now()
        end = start + timedelta(seconds=1)

        metrics = LambdaExecutionMetrics(
            start_timestamp=start,
            end_timestamp=end,
            duration_ms=1000.0,
            user="test_user",
            account="test_account",
            api_key_id=None,
            operation="test_op",
            endpoint="/test",
            api_accessed=False,
            status_code=200,
            success=True,
            error_type=None,
            request_id=None,
            memory_limit_mb=None,
        )

        # Should not raise exception
        tracker.record_metrics(metrics)

    def test_record_metrics_when_disabled(self):
        """Test record_metrics does nothing when disabled"""
        tracker = UsageTracker(enabled=False)

        metrics = Mock()
        tracker.record_metrics(metrics)

        # Should not call any methods on metrics
        metrics.to_dynamodb_item.assert_not_called()


class TestGetUsageTracker:
    """Tests for get_usage_tracker singleton function"""

    @patch("pycommon.metrics.usage_tracker._usage_tracker", None)
    @patch.dict(os.environ, {"ADDITIONAL_CHARGES_TABLE": "test-table"})
    @patch("pycommon.metrics.usage_tracker.boto3")
    def test_get_usage_tracker_creates_singleton(self, mock_boto3):
        """Test get_usage_tracker creates and returns singleton"""
        mock_dynamodb = Mock()
        mock_boto3.resource.return_value = mock_dynamodb

        tracker1 = get_usage_tracker()
        tracker2 = get_usage_tracker()

        assert tracker1 is tracker2
        assert isinstance(tracker1, UsageTracker)


class TestIntegration:
    """Integration tests for complete tracking flow"""

    @patch.dict(os.environ, {"ADDITIONAL_CHARGES_TABLE": "test-table"})
    @patch("pycommon.metrics.usage_tracker.boto3")
    def test_complete_tracking_flow(self, mock_boto3):
        """Test complete tracking from start to end to record"""
        mock_dynamodb = Mock()
        mock_table = Mock()
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3.resource.return_value = mock_dynamodb

        tracker = UsageTracker()

        # Mock Lambda context
        mock_context = Mock()
        mock_context.aws_request_id = "req-integration-test"
        mock_context.memory_limit_in_mb = 2048

        # Start tracking
        tracking_context = tracker.start_tracking(
            user="integration_user",
            operation="test_operation",
            endpoint="/api/test",
            api_accessed=False,
            context=mock_context,
        )

        # Simulate some work
        import time

        time.sleep(0.1)

        # End tracking
        claims = {
            "account": "integration_account",
            "purpose": "integration_test",
        }
        result = {"statusCode": 200}

        metrics = tracker.end_tracking(tracking_context, result, claims)

        # Record metrics
        tracker.record_metrics(metrics)

        # Verify the complete flow
        assert metrics.user == "integration_user"
        assert metrics.account == "integration_account"
        assert metrics.operation == "test_operation"
        assert metrics.duration_ms >= 100  # At least 100ms from sleep
        assert metrics.success is True

        # Verify DynamoDB was called
        mock_table.put_item.assert_called_once()
