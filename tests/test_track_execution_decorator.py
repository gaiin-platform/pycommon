"""Tests for track_execution decorator

Copyright (c) 2025 Vanderbilt University
"""

import json
import os
from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from pycommon.decorators import track_execution


class TestTrackExecutionDecorator:
    """Tests for @track_execution decorator"""

    @patch.dict(os.environ, {"ADDITIONAL_CHARGES_TABLE": "test-table"})
    @patch("pycommon.metrics.get_usage_tracker")
    def test_basic_sqs_event(self, mock_get_tracker):
        """Test track_execution with basic SQS event"""
        mock_tracker = Mock()
        mock_tracker.start_tracking.return_value = {
            "start_time": datetime.utcnow(),
            "user": "test_user",
        }
        mock_tracker.end_tracking.return_value = Mock(user="test_user")
        mock_tracker.record_metrics.return_value = None
        mock_get_tracker.return_value = mock_tracker

        @track_execution("process_sqs_message", "system", "system")
        def handler(event, context):
            return {"success": True}

        event = {
            "Records": [
                {
                    "eventSource": "aws:sqs",
                    "body": json.dumps(
                        {"user": "test_user", "account": "test_account"}
                    ),
                }
            ]
        }
        context = Mock(aws_request_id="req-123", memory_limit_in_mb=512)

        result = handler(event, context)

        assert result == {"success": True}
        assert mock_tracker.start_tracking.called
        assert mock_tracker.end_tracking.called
        assert mock_tracker.record_metrics.called

    @patch.dict(os.environ, {"ADDITIONAL_CHARGES_TABLE": "test-table"})
    @patch("pycommon.metrics.get_usage_tracker")
    def test_s3_event_user_extraction(self, mock_get_tracker):
        """Test user extraction from S3 key"""
        mock_tracker = Mock()
        mock_tracker.start_tracking.return_value = {"start_time": datetime.utcnow()}
        mock_tracker.end_tracking.return_value = Mock()
        mock_tracker.record_metrics.return_value = None
        mock_get_tracker.return_value = mock_tracker

        @track_execution(
            "process_s3_event", "system", "system", extract_from_event=True
        )
        def handler(event, context):
            return {"statusCode": 200}

        event = {
            "Records": [
                {
                    "eventSource": "aws:s3",
                    "s3": {"object": {"key": "user%40example.com/2024/document.pdf"}},
                }
            ]
        }
        context = Mock(aws_request_id="req-456")

        handler(event, context)

        # Verify start_tracking was called with extracted user
        call_args = mock_tracker.start_tracking.call_args
        assert call_args[1]["user"] == "user@example.com"

    @patch.dict(os.environ, {"ADDITIONAL_CHARGES_TABLE": "test-table"})
    @patch("pycommon.metrics.get_usage_tracker")
    def test_sqs_with_nested_s3_event(self, mock_get_tracker):
        """Test SQS body containing S3 event (embedding pattern)"""
        mock_tracker = Mock()
        mock_tracker.start_tracking.return_value = {"start_time": datetime.utcnow()}
        mock_tracker.end_tracking.return_value = Mock()
        mock_tracker.record_metrics.return_value = None
        mock_get_tracker.return_value = mock_tracker

        @track_execution("process_embedding", "system", "system")
        def handler(event, context):
            return {"success": True}

        event = {
            "Records": [
                {
                    "eventSource": "aws:sqs",
                    "body": json.dumps(
                        {
                            "Records": [
                                {
                                    "s3": {
                                        "object": {
                                            "key": "embedded-user@test.com/doc.txt"
                                        }
                                    }
                                }
                            ]
                        }
                    ),
                }
            ]
        }
        context = Mock()

        handler(event, context)

        # Verify user was extracted from nested S3 key
        call_args = mock_tracker.start_tracking.call_args
        assert call_args[1]["user"] == "embedded-user@test.com"

    @patch.dict(os.environ, {"ADDITIONAL_CHARGES_TABLE": "test-table"})
    @patch("pycommon.metrics.get_usage_tracker")
    def test_dynamodb_stream_event(self, mock_get_tracker):
        """Test DynamoDB Stream event"""
        mock_tracker = Mock()
        mock_tracker.start_tracking.return_value = {"start_time": datetime.utcnow()}
        mock_tracker.end_tracking.return_value = Mock()
        mock_tracker.record_metrics.return_value = None
        mock_get_tracker.return_value = mock_tracker

        @track_execution("process_dynamodb_stream", "system", "system")
        def handler(event, context):
            return {"success": True}

        event = {
            "Records": [
                {
                    "eventSource": "aws:dynamodb",
                    "dynamodb": {
                        "NewImage": {
                            "user": {"S": "dynamodb_user"},
                            "accountId": {"S": "dynamodb_account"},
                        }
                    },
                }
            ]
        }
        context = Mock()

        handler(event, context)

        call_args = mock_tracker.start_tracking.call_args
        assert call_args[1]["user"] == "dynamodb_user"

    @patch.dict(os.environ, {"ADDITIONAL_CHARGES_TABLE": "test-table"})
    @patch("pycommon.decorators.boto3")  # Mock boto3 for @required_env_vars
    @patch("pycommon.metrics.get_usage_tracker")
    def test_eventbridge_scheduled_event(self, mock_get_tracker, mock_boto3):
        """Test EventBridge scheduled event"""
        mock_tracker = Mock()
        mock_tracker.start_tracking.return_value = {"start_time": datetime.utcnow()}
        mock_tracker.end_tracking.return_value = Mock()
        mock_tracker.record_metrics.return_value = None
        mock_get_tracker.return_value = mock_tracker

        @track_execution("daily_cleanup", "system", "system")
        def handler(event, context):
            return {"success": True}

        event = {"source": "aws.events", "detail-type": "Scheduled Event"}
        context = Mock()

        result = handler(event, context)

        assert result == {"success": True}
        call_args = mock_tracker.start_tracking.call_args
        assert call_args[1]["endpoint"] == "event://aws.events/daily_cleanup"

    @patch.dict(os.environ, {"ADDITIONAL_CHARGES_TABLE": "test-table"})
    @patch("pycommon.metrics.get_usage_tracker")
    def test_exception_handling(self, mock_get_tracker):
        """Test that exceptions are tracked and re-raised"""
        mock_tracker = Mock()
        mock_tracker.start_tracking.return_value = {"start_time": datetime.utcnow()}
        mock_tracker.end_tracking.return_value = Mock()
        mock_tracker.record_metrics.return_value = None
        mock_get_tracker.return_value = mock_tracker

        @track_execution("failing_operation", "system", "system")
        def handler(event, context):
            raise ValueError("Test error")

        event = {}
        context = Mock()

        with pytest.raises(ValueError, match="Test error"):
            handler(event, context)

        # Verify tracking still happened
        assert mock_tracker.end_tracking.called
        call_args = mock_tracker.end_tracking.call_args
        assert call_args[1]["error_type"] == "ValueError"

    @patch.dict(os.environ, {"ADDITIONAL_CHARGES_TABLE": "test-table"})
    @patch("pycommon.metrics.get_usage_tracker")
    def test_extract_from_event_disabled(self, mock_get_tracker):
        """Test with extract_from_event=False"""
        mock_tracker = Mock()
        mock_tracker.start_tracking.return_value = {"start_time": datetime.utcnow()}
        mock_tracker.end_tracking.return_value = Mock()
        mock_tracker.record_metrics.return_value = None
        mock_get_tracker.return_value = mock_tracker

        @track_execution(
            "static_operation",
            "static_account",
            "static_user",
            extract_from_event=False,
        )
        def handler(event, context):
            return {"success": True}

        event = {"user": "should_not_extract", "account": "should_not_extract"}
        context = Mock()

        handler(event, context)

        # Verify defaults were used, not extracted values
        call_args = mock_tracker.start_tracking.call_args
        assert call_args[1]["user"] == "static_user"

    @patch.dict(os.environ, {}, clear=True)
    @patch("pycommon.decorators.boto3")  # Mock boto3 for @required_env_vars
    def test_missing_env_var_warning(self, mock_boto3, caplog):
        """Test warning when ADDITIONAL_CHARGES_TABLE is missing"""
        import logging

        caplog.set_level(logging.WARNING)

        @track_execution("test_operation")
        def handler(event, context):
            return {"success": True}

        # Just defining the decorator should log a warning about the missing env var
        assert "ADDITIONAL_CHARGES_TABLE" in caplog.text

    @patch.dict(os.environ, {"ADDITIONAL_CHARGES_TABLE": "test-table"})
    @patch("pycommon.metrics.get_usage_tracker")
    def test_top_level_event_extraction(self, mock_get_tracker):
        """Test extraction from top-level event fields"""
        mock_tracker = Mock()
        mock_tracker.start_tracking.return_value = {"start_time": datetime.utcnow()}
        mock_tracker.end_tracking.return_value = Mock()
        mock_tracker.record_metrics.return_value = None
        mock_get_tracker.return_value = mock_tracker

        @track_execution("test_op", "system", "system")
        def handler(event, context):
            return {"success": True}

        event = {"user": "top_level_user", "accountId": "top_level_account"}
        context = Mock()

        handler(event, context)

        call_args = mock_tracker.start_tracking.call_args
        assert call_args[1]["user"] == "top_level_user"

    @patch.dict(os.environ, {"ADDITIONAL_CHARGES_TABLE": "test-table"})
    @patch("pycommon.metrics.get_usage_tracker")
    def test_result_success_detection(self, mock_get_tracker):
        """Test detection of success field in result"""
        mock_tracker = Mock()
        mock_tracker.start_tracking.return_value = {"start_time": datetime.utcnow()}
        mock_tracker.end_tracking.return_value = Mock()
        mock_tracker.record_metrics.return_value = None
        mock_get_tracker.return_value = mock_tracker

        @track_execution("test_op", "system", "system")
        def handler(event, context):
            return {"success": False, "error": "OperationFailed"}

        event = {}
        context = Mock()

        handler(event, context)

        # Verify error_type was passed to end_tracking
        call_args = mock_tracker.end_tracking.call_args
        assert call_args[1]["error_type"] == "OperationFailed"

    @patch.dict(os.environ, {"ADDITIONAL_CHARGES_TABLE": "test-table"})
    @patch("pycommon.metrics.get_usage_tracker")
    def test_api_gateway_event(self, mock_get_tracker):
        """Test API Gateway event detection"""
        mock_tracker = Mock()
        mock_tracker.start_tracking.return_value = {"start_time": datetime.utcnow()}
        mock_tracker.end_tracking.return_value = Mock()
        mock_tracker.record_metrics.return_value = None
        mock_get_tracker.return_value = mock_tracker

        @track_execution("api_operation", "system", "system")
        def handler(event, context):
            return {"statusCode": 200}

        event = {
            "requestContext": {"requestId": "api-request-123"},
            "httpMethod": "POST",
        }
        context = Mock()

        handler(event, context)

        # Verify endpoint format includes API Gateway detection
        call_args = mock_tracker.start_tracking.call_args
        assert "api_operation" in call_args[1]["endpoint"]

    @patch.dict(os.environ, {"ADDITIONAL_CHARGES_TABLE": "test-table"})
    @patch("pycommon.metrics.get_usage_tracker")
    def test_sqs_with_invalid_json(self, mock_get_tracker):
        """Test SQS with invalid JSON in body - covers exception handling"""
        mock_tracker = Mock()
        mock_tracker.start_tracking.return_value = {"start_time": datetime.utcnow()}
        mock_tracker.end_tracking.return_value = Mock()
        mock_tracker.record_metrics.return_value = None
        mock_get_tracker.return_value = mock_tracker

        @track_execution("process_invalid", "default_account", "default_user")
        def handler(event, context):
            return {"success": True}

        event = {"Records": [{"eventSource": "aws:sqs", "body": "INVALID JSON {{{{"}]}
        context = Mock()

        handler(event, context)

        # Should use default values when JSON parsing fails
        call_args = mock_tracker.start_tracking.call_args
        assert call_args[1]["user"] == "default_user"

    @patch.dict(os.environ, {"ADDITIONAL_CHARGES_TABLE": "test-table"})
    @patch("pycommon.metrics.get_usage_tracker")
    def test_dynamodb_with_user_id_field(self, mock_get_tracker):
        """Test DynamoDB Stream with user_id field instead of user"""
        mock_tracker = Mock()
        mock_tracker.start_tracking.return_value = {"start_time": datetime.utcnow()}
        mock_tracker.end_tracking.return_value = Mock()
        mock_tracker.record_metrics.return_value = None
        mock_get_tracker.return_value = mock_tracker

        @track_execution("process_dynamodb", "system", "system")
        def handler(event, context):
            return {"success": True}

        event = {
            "Records": [
                {
                    "eventSource": "aws:dynamodb",
                    "dynamodb": {
                        "NewImage": {
                            "user_id": {"S": "user_from_user_id"},
                            "account": {"S": "account_from_dynamodb"},
                        }
                    },
                }
            ]
        }
        context = Mock()

        handler(event, context)

        # Check start_tracking for user
        start_call_args = mock_tracker.start_tracking.call_args
        assert start_call_args[1]["user"] == "user_from_user_id"

        # Check end_tracking for account
        end_call_args = mock_tracker.end_tracking.call_args
        assert end_call_args[1]["claims"]["account"] == "account_from_dynamodb"

    @patch.dict(os.environ, {"ADDITIONAL_CHARGES_TABLE": "test-table"})
    @patch("pycommon.metrics.get_usage_tracker")
    def test_dynamodb_with_username_field(self, mock_get_tracker):
        """Test DynamoDB Stream with username field"""
        mock_tracker = Mock()
        mock_tracker.start_tracking.return_value = {"start_time": datetime.utcnow()}
        mock_tracker.end_tracking.return_value = Mock()
        mock_tracker.record_metrics.return_value = None
        mock_get_tracker.return_value = mock_tracker

        @track_execution("process_dynamodb", "system", "system")
        def handler(event, context):
            return {"success": True}

        event = {
            "Records": [
                {
                    "eventSource": "aws:dynamodb",
                    "dynamodb": {
                        "NewImage": {
                            "username": {"S": "user_from_username"},
                            "accountId": {"S": "account_from_accountId"},
                        }
                    },
                }
            ]
        }
        context = Mock()

        handler(event, context)

        # Check start_tracking for user
        start_call_args = mock_tracker.start_tracking.call_args
        assert start_call_args[1]["user"] == "user_from_username"

        # Check end_tracking for account
        end_call_args = mock_tracker.end_tracking.call_args
        assert end_call_args[1]["claims"]["account"] == "account_from_accountId"

    @patch.dict(os.environ, {"ADDITIONAL_CHARGES_TABLE": "test-table"})
    @patch("pycommon.metrics.get_usage_tracker")
    def test_s3_event_with_invalid_key(self, mock_get_tracker):
        """Test S3 event with invalid key format - covers exception handling"""
        mock_tracker = Mock()
        mock_tracker.start_tracking.return_value = {"start_time": datetime.utcnow()}
        mock_tracker.end_tracking.return_value = Mock()
        mock_tracker.record_metrics.return_value = None
        mock_get_tracker.return_value = mock_tracker

        @track_execution("process_s3", "default_account", "default_user")
        def handler(event, context):
            return {"success": True}

        # Create a mock S3 structure where accessing the key raises AttributeError
        # This simulates a malformed S3 event structure
        class BrokenS3Object:
            def __getitem__(self, key):
                if key == "key":
                    raise AttributeError("Cannot access key")
                raise KeyError(key)

        class BrokenObject:
            def __getitem__(self, key):
                if key == "object":
                    return BrokenS3Object()
                raise KeyError(key)

        event = {"Records": [{"eventSource": "aws:s3", "s3": BrokenObject()}]}
        context = Mock()

        handler(event, context)

        # Should use default values when S3 key parsing fails
        call_args = mock_tracker.start_tracking.call_args
        assert call_args[1]["user"] == "default_user"

    @patch.dict(os.environ, {"ADDITIONAL_CHARGES_TABLE": "test-table"})
    @patch("pycommon.metrics.get_usage_tracker")
    def test_result_not_dict(self, mock_get_tracker):
        """Test when Lambda returns non-dict result - covers branch 573->579"""
        mock_tracker = Mock()
        mock_tracker.start_tracking.return_value = {"start_time": datetime.utcnow()}
        mock_tracker.end_tracking.return_value = Mock()
        mock_tracker.record_metrics.return_value = None
        mock_get_tracker.return_value = mock_tracker

        @track_execution("test_op", "account", "user")
        def handler(event, context):
            return "simple string result"  # Not a dict

        event = {}
        context = Mock()
        result = handler(event, context)

        assert result == "simple string result"
        # Verify end_tracking was called with default success values
        call_args = mock_tracker.end_tracking.call_args
        assert call_args[1]["result"]["statusCode"] == 200

    @patch.dict(os.environ, {"ADDITIONAL_CHARGES_TABLE": "test-table"})
    @patch("pycommon.metrics.get_usage_tracker")
    def test_event_not_dict(self, mock_get_tracker):
        """Test when event is not a dict - covers branch 539->555"""
        mock_tracker = Mock()
        mock_tracker.start_tracking.return_value = {"start_time": datetime.utcnow()}
        mock_tracker.end_tracking.return_value = Mock()
        mock_tracker.record_metrics.return_value = None
        mock_get_tracker.return_value = mock_tracker

        @track_execution("test_op", "account", "user")
        def handler(event, context):
            return {"success": True}

        event = "not a dictionary"  # Non-dict event
        context = Mock()
        handler(event, context)

        # Should use default values
        call_args = mock_tracker.start_tracking.call_args
        assert call_args[1]["user"] == "user"
        assert call_args[1]["endpoint"] == "event://unknown/test_op"

    @patch.dict(os.environ, {"ADDITIONAL_CHARGES_TABLE": "test-table"})
    @patch("pycommon.metrics.get_usage_tracker")
    def test_s3_key_invalid_format(self, mock_get_tracker):
        """Test S3 key that doesn't look like user - covers branch 528->536"""
        mock_tracker = Mock()
        mock_tracker.start_tracking.return_value = {"start_time": datetime.utcnow()}
        mock_tracker.end_tracking.return_value = Mock()
        mock_tracker.record_metrics.return_value = None
        mock_get_tracker.return_value = mock_tracker

        @track_execution("process_s3", "default_account", "default_user")
        def handler(event, context):
            return {"success": True}

        event = {
            "Records": [
                {
                    "eventSource": "aws:s3",
                    "s3": {
                        "object": {
                            "key": "shortkey"  # Too short, no @, no long UUID format
                        }
                    },
                }
            ]
        }
        context = Mock()
        handler(event, context)

        # Should use default values
        call_args = mock_tracker.start_tracking.call_args
        assert call_args[1]["user"] == "default_user"

    @patch.dict(os.environ, {"ADDITIONAL_CHARGES_TABLE": "test-table"})
    @patch("pycommon.metrics.get_usage_tracker")
    def test_dynamodb_without_newimage(self, mock_get_tracker):
        """Test DynamoDB Stream without NewImage - covers branch 497->536"""
        mock_tracker = Mock()
        mock_tracker.start_tracking.return_value = {"start_time": datetime.utcnow()}
        mock_tracker.end_tracking.return_value = Mock()
        mock_tracker.record_metrics.return_value = None
        mock_get_tracker.return_value = mock_tracker

        @track_execution("process_dynamodb", "default_account", "default_user")
        def handler(event, context):
            return {"success": True}

        event = {
            "Records": [
                {
                    "eventSource": "aws:dynamodb",
                    "dynamodb": {"Keys": {"id": {"S": "123"}}},  # No NewImage
                }
            ]
        }
        context = Mock()
        handler(event, context)

        # Should use default values
        call_args = mock_tracker.start_tracking.call_args
        assert call_args[1]["user"] == "default_user"

    @patch.dict(os.environ, {"ADDITIONAL_CHARGES_TABLE": "test-table"})
    @patch("pycommon.metrics.get_usage_tracker")
    def test_dynamodb_username_without_account(self, mock_get_tracker):
        """Test DynamoDB username without account (branch 504->509, 513->536)"""
        mock_tracker = Mock()
        mock_tracker.start_tracking.return_value = {"start_time": datetime.utcnow()}
        mock_tracker.end_tracking.return_value = Mock()
        mock_tracker.record_metrics.return_value = None
        mock_get_tracker.return_value = mock_tracker

        @track_execution("process_dynamodb", "default_account", "default_user")
        def handler(event, context):
            return {"success": True}

        event = {
            "Records": [
                {
                    "eventSource": "aws:dynamodb",
                    "dynamodb": {
                        "NewImage": {
                            "username": {"S": "test_username"}
                            # No account or accountId fields
                        }
                    },
                }
            ]
        }
        context = Mock()
        handler(event, context)

        # Check that username was extracted
        start_call_args = mock_tracker.start_tracking.call_args
        assert start_call_args[1]["user"] == "test_username"

        # Check that default account was used (no account fields present)
        end_call_args = mock_tracker.end_tracking.call_args
        assert end_call_args[1]["claims"]["account"] == "default_account"

    @patch.dict(os.environ, {"ADDITIONAL_CHARGES_TABLE": "test-table"})
    @patch("pycommon.metrics.get_usage_tracker")
    def test_sqs_nested_s3_without_s3_key(self, mock_get_tracker):
        """Test SQS with nested S3 record but no s3 key - covers branch 473->536"""
        mock_tracker = Mock()
        mock_tracker.start_tracking.return_value = {"start_time": datetime.utcnow()}
        mock_tracker.end_tracking.return_value = Mock()
        mock_tracker.record_metrics.return_value = None
        mock_get_tracker.return_value = mock_tracker

        @track_execution("process_sqs", "default_account", "default_user")
        def handler(event, context):
            return {"success": True}

        event = {
            "Records": [
                {
                    "eventSource": "aws:sqs",
                    "body": json.dumps(
                        {
                            "Records": [
                                {
                                    "eventSource": "aws:s3"
                                    # Missing "s3" key
                                }
                            ]
                        }
                    ),
                }
            ]
        }
        context = Mock()
        handler(event, context)

        # Should use default values
        call_args = mock_tracker.start_tracking.call_args
        assert call_args[1]["user"] == "default_user"

    @patch.dict(os.environ, {"ADDITIONAL_CHARGES_TABLE": "test-table"})
    @patch("pycommon.metrics.get_usage_tracker")
    def test_sqs_nested_s3_user_already_found(self, mock_get_tracker):
        """Test SQS with nested S3 but user already found - covers branch 479->536"""
        mock_tracker = Mock()
        mock_tracker.start_tracking.return_value = {"start_time": datetime.utcnow()}
        mock_tracker.end_tracking.return_value = Mock()
        mock_tracker.record_metrics.return_value = None
        mock_get_tracker.return_value = mock_tracker

        @track_execution("process_sqs", "default_account", "default_user")
        def handler(event, context):
            return {"success": True}

        event = {
            "Records": [
                {
                    "eventSource": "aws:sqs",
                    "body": json.dumps(
                        {
                            "user": "found_user",  # User already found here
                            "Records": [
                                {
                                    "s3": {
                                        "object": {
                                            # Should be ignored
                                            "key": "other_user@example.com/file.txt"
                                        }
                                    }
                                }
                            ],
                        }
                    ),
                }
            ]
        }
        context = Mock()
        handler(event, context)

        # Should use the user from body, not S3 key
        call_args = mock_tracker.start_tracking.call_args
        assert call_args[1]["user"] == "found_user"

    @patch.dict(os.environ, {"ADDITIONAL_CHARGES_TABLE": "test-table"})
    @patch("pycommon.metrics.get_usage_tracker")
    def test_sqs_nested_s3_invalid_user_format(self, mock_get_tracker):
        """Test SQS nested S3 with invalid user format (branch 485->536)"""
        mock_tracker = Mock()
        mock_tracker.start_tracking.return_value = {"start_time": datetime.utcnow()}
        mock_tracker.end_tracking.return_value = Mock()
        mock_tracker.record_metrics.return_value = None
        mock_get_tracker.return_value = mock_tracker

        @track_execution("process_sqs", "default_account", "default_user")
        def handler(event, context):
            return {"success": True}

        event = {
            "Records": [
                {
                    "eventSource": "aws:sqs",
                    "body": json.dumps(
                        {
                            "Records": [
                                {
                                    "s3": {
                                        "object": {
                                            # "short" doesn't look like user
                                            "key": "short/file.txt"
                                        }
                                    }
                                }
                            ]
                        }
                    ),
                }
            ]
        }
        context = Mock()
        handler(event, context)

        # Should use default user since key doesn't look like valid user
        call_args = mock_tracker.start_tracking.call_args
        assert call_args[1]["user"] == "default_user"

    @patch.dict(os.environ, {"ADDITIONAL_CHARGES_TABLE": "test-table"})
    @patch("pycommon.metrics.get_usage_tracker")
    def test_dynamodb_with_user_field(self, mock_get_tracker):
        """Test DynamoDB with user field (not username) - covers branch 504->509"""
        mock_tracker = Mock()
        mock_tracker.start_tracking.return_value = {"start_time": datetime.utcnow()}
        mock_tracker.end_tracking.return_value = Mock()
        mock_tracker.record_metrics.return_value = None
        mock_get_tracker.return_value = mock_tracker

        @track_execution("process_dynamodb", "default_account", "default_user")
        def handler(event, context):
            return {"success": True}

        event = {
            "Records": [
                {
                    "eventSource": "aws:dynamodb",
                    "dynamodb": {
                        "NewImage": {
                            "user": {"S": "user_from_user_field"},
                            "account": {"S": "account_from_dynamodb"},
                        }
                    },
                }
            ]
        }
        context = Mock()
        handler(event, context)

        # Check that user field was extracted (skipping username elif)
        start_call_args = mock_tracker.start_tracking.call_args
        assert start_call_args[1]["user"] == "user_from_user_field"

    @patch.dict(os.environ, {"ADDITIONAL_CHARGES_TABLE": "test-table"})
    @patch("pycommon.metrics.get_usage_tracker")
    def test_kinesis_event(self, mock_get_tracker):
        """Test Kinesis event (not S3, not DynamoDB) - covers branch 519->536"""
        mock_tracker = Mock()
        mock_tracker.start_tracking.return_value = {"start_time": datetime.utcnow()}
        mock_tracker.end_tracking.return_value = Mock()
        mock_tracker.record_metrics.return_value = None
        mock_get_tracker.return_value = mock_tracker

        @track_execution("process_kinesis", "default_account", "default_user")
        def handler(event, context):
            return {"success": True}

        event = {
            "Records": [
                {"eventSource": "aws:kinesis", "kinesis": {"data": "base64encodeddata"}}
            ]
        }
        context = Mock()
        handler(event, context)

        # Should use default values for non-S3/non-DynamoDB event
        call_args = mock_tracker.start_tracking.call_args
        assert call_args[1]["user"] == "default_user"

    @patch.dict(os.environ, {"ADDITIONAL_CHARGES_TABLE": "test-table"})
    @patch("pycommon.metrics.get_usage_tracker")
    def test_s3_event_empty_key(self, mock_get_tracker):
        """Test S3 event with empty key"""
        mock_tracker = Mock()
        mock_tracker.start_tracking.return_value = {"start_time": datetime.utcnow()}
        mock_tracker.end_tracking.return_value = Mock()
        mock_tracker.record_metrics.return_value = None
        mock_get_tracker.return_value = mock_tracker

        @track_execution("process_s3", "default_account", "default_user")
        def handler(event, context):
            return {"success": True}

        event = {
            "Records": [
                {"eventSource": "aws:s3", "s3": {"object": {"key": ""}}}  # Empty key
            ]
        }
        context = Mock()
        handler(event, context)

        # Should use default values when key is empty
        call_args = mock_tracker.start_tracking.call_args
        assert call_args[1]["user"] == "default_user"

    @patch.dict(os.environ, {"ADDITIONAL_CHARGES_TABLE": "test-table"})
    @patch("pycommon.metrics.get_usage_tracker")
    def test_dynamodb_no_user_fields(self, mock_get_tracker):
        """Test DynamoDB with no user-identifying fields - covers branch 504->509"""
        mock_tracker = Mock()
        mock_tracker.start_tracking.return_value = {"start_time": datetime.utcnow()}
        mock_tracker.end_tracking.return_value = Mock()
        mock_tracker.record_metrics.return_value = None
        mock_get_tracker.return_value = mock_tracker

        @track_execution("process_dynamodb", "default_account", "default_user")
        def handler(event, context):
            return {"success": True}

        event = {
            "Records": [
                {
                    "eventSource": "aws:dynamodb",
                    "dynamodb": {
                        "NewImage": {
                            "someField": {"S": "someValue"},
                            # No user, user_id, or username fields
                            "account": {"S": "account_value"},
                        }
                    },
                }
            ]
        }
        context = Mock()
        handler(event, context)

        # Should use default user when no user fields present
        start_call_args = mock_tracker.start_tracking.call_args
        assert start_call_args[1]["user"] == "default_user"
        # Should extract account
        end_call_args = mock_tracker.end_tracking.call_args
        assert end_call_args[1]["claims"]["account"] == "account_value"

    @patch.dict(os.environ, {"ADDITIONAL_CHARGES_TABLE": "test-table"})
    @patch("pycommon.metrics.get_usage_tracker")
    def test_s3_key_split_empty(self, mock_get_tracker):
        """Test S3 event where split returns empty (branch 525->536)"""
        mock_tracker = Mock()
        mock_tracker.start_tracking.return_value = {"start_time": datetime.utcnow()}
        mock_tracker.end_tracking.return_value = Mock()
        mock_tracker.record_metrics.return_value = None
        mock_get_tracker.return_value = mock_tracker

        @track_execution("process_s3", "default_account", "default_user")
        def handler(event, context):
            return {"success": True}

        # Create a mock key that when split returns empty list
        class MockKey:
            def split(self, sep):
                return []  # Return empty list to cover the False branch

        with patch("urllib.parse.unquote") as mock_unquote:
            mock_unquote.return_value = MockKey()

            event = {
                "Records": [
                    {"eventSource": "aws:s3", "s3": {"object": {"key": "test"}}}
                ]
            }
            context = Mock()
            handler(event, context)

            # Should use default values when split returns empty
            call_args = mock_tracker.start_tracking.call_args
            assert call_args[1]["user"] == "default_user"
