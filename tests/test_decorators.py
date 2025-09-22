import os
from unittest.mock import Mock, patch

import pytest

from pycommon.dal.providers.aws.resource_perms import (
    DynamoDBOperation,
    S3Operation,
    SecretsManagerOperation,
)
from pycommon.decorators import EnvVarTracker, required_env_vars
from pycommon.exceptions import EnvVarError


class TestEnvVarTracker:
    """Test cases for the EnvVarTracker class"""

    def test_init_with_tracking_table(self):
        """Test EnvVarTracker initialization with tracking table"""
        with patch.dict(
            os.environ,
            {
                "STAGE": "test",
                "SERVICE_NAME": "test-service",
                "ENV_VARS_TRACKING_TABLE": "test-table",
                "AWS_REGION": "us-west-2",
            },
        ):
            with patch("boto3.resource"):
                tracker = EnvVarTracker()
                assert tracker.stage == "test"
                assert tracker.service_name == "test-service"
                assert tracker.tracking_table == "test-table"
                assert tracker.region == "us-west-2"
                assert tracker.tracking_enabled is True

    def test_init_without_tracking_table(self):
        """Test EnvVarTracker initialization without tracking table"""
        with patch.dict(os.environ, {}, clear=True):
            tracker = EnvVarTracker()
            assert tracker.stage == "dev"
            assert tracker.service_name == "unknown"
            assert tracker.tracking_table is None
            assert tracker.tracking_enabled is False

    def test_resolve_env_var_from_lambda_env(self):
        """Test resolving env var from Lambda environment"""
        with patch.dict(os.environ, {"TEST_VAR": "test_value"}):
            tracker = EnvVarTracker()
            result = tracker.resolve_env_var("TEST_VAR")
            assert result == "test_value"

    def test_resolve_env_var_from_parameter_store(self):
        """Test resolving env var from Parameter Store when not in Lambda env"""
        with patch.dict(
            os.environ, {"STAGE": "test", "SERVICE_NAME": "test-service"}, clear=True
        ):
            mock_ssm = Mock()
            mock_ssm.get_parameter.return_value = {
                "Parameter": {"Value": "parameter_store_value"}
            }

            tracker = EnvVarTracker()
            tracker.ssm = mock_ssm
            tracker.ssm_enabled = True

            result = tracker.resolve_env_var("TEST_VAR")
            assert result == "parameter_store_value"
            assert os.environ["TEST_VAR"] == "parameter_store_value"

            mock_ssm.get_parameter.assert_called_once_with(
                Name="/amplify/test/test-service/TEST_VAR"
            )

    def test_resolve_env_var_not_found(self):
        """Test resolving env var that doesn't exist anywhere"""
        with patch.dict(os.environ, {}, clear=True):
            tracker = EnvVarTracker()
            tracker.ssm_enabled = False

            with pytest.raises(
                EnvVarError, match="Environment variable 'MISSING_VAR' not found"
            ):
                tracker.resolve_env_var("MISSING_VAR")

    def test_track_env_var_disabled(self):
        """Test tracking when tracking is disabled"""
        tracker = EnvVarTracker()
        tracker.tracking_enabled = False

        # Should not raise any errors
        tracker.track_env_var("TEST_VAR", [DynamoDBOperation.GET_ITEM])

    def test_track_env_var_enabled(self):
        """Test tracking when tracking is enabled"""
        mock_table = Mock()
        mock_table.get_item.return_value = {}  # No existing item

        tracker = EnvVarTracker()
        tracker.tracking_enabled = True
        tracker.table = mock_table
        tracker.service_name = "test-service"

        with patch.dict(os.environ, {"TEST_VAR": "test_value"}):
            tracker.track_env_var(
                "TEST_VAR", [DynamoDBOperation.GET_ITEM], "test_value"
            )

        mock_table.put_item.assert_called_once()
        call_args = mock_table.put_item.call_args[1]["Item"]
        assert call_args["service_var_key"] == "test-service#TEST_VAR"
        assert call_args["var_name"] == "TEST_VAR"
        assert call_args["resolved_value"] == "test_value"
        assert call_args["operations"] == ["dynamodb:GetItem"]
        # Should have first_accessed but not last_accessed
        assert "first_accessed" in call_args
        assert "last_accessed" not in call_args

    def test_resolve_env_var_parameter_not_found(self):
        """Test resolving env var when parameter not found in Parameter Store"""
        with patch.dict(
            os.environ, {"STAGE": "test", "SERVICE_NAME": "test-service"}, clear=True
        ):
            mock_ssm = Mock()
            mock_ssm.exceptions.ParameterNotFound = Exception
            mock_ssm.get_parameter.side_effect = mock_ssm.exceptions.ParameterNotFound(
                "Not found"
            )

            tracker = EnvVarTracker()
            tracker.ssm = mock_ssm
            tracker.ssm_enabled = True

            with pytest.raises(EnvVarError):
                tracker.resolve_env_var("MISSING_VAR")

    def test_track_env_var_update_existing(self):
        """Test tracking when record already exists (update path)"""
        mock_table = Mock()
        mock_table.get_item.return_value = {
            "Item": {
                "operations": [],  # No existing operations
                "service_var_key": "test-service#TEST_VAR",
            }
        }
        # Mock update_item to return successful response
        mock_table.update_item.return_value = {
            "Attributes": {"operations": ["dynamodb:GetItem"]}
        }

        tracker = EnvVarTracker()
        tracker.tracking_enabled = True
        tracker.table = mock_table
        tracker.service_name = "test-service"

        with patch.dict(os.environ, {"TEST_VAR": "test_value"}):
            tracker.track_env_var("TEST_VAR", [DynamoDBOperation.GET_ITEM])

        # Should update with new operations
        mock_table.update_item.assert_called_once()
        mock_table.put_item.assert_not_called()

        # Check that operations were updated correctly
        call_args = mock_table.update_item.call_args[1]
        assert call_args["UpdateExpression"] == "SET operations = :operations"
        merged_ops = call_args["ExpressionAttributeValues"][":operations"]
        assert merged_ops == ["dynamodb:GetItem"]

    def test_track_env_var_with_none_values(self):
        """Test tracking with None resolved_value and operations"""
        mock_table = Mock()
        mock_table.get_item.return_value = {}

        tracker = EnvVarTracker()
        tracker.tracking_enabled = True
        tracker.table = mock_table
        tracker.service_name = "test-service"

        # Test with None values - should use defaults
        tracker.track_env_var("TEST_VAR", None, None)

        mock_table.put_item.assert_called_once()
        call_args = mock_table.put_item.call_args[1]["Item"]
        assert call_args["operations"] == []
        assert (
            call_args["resolved_value"] == ""
        )  # Should get empty string from os.getenv default

    def test_track_env_var_exception_handling(self):
        """Test tracking exception handling doesn't fail the function"""
        mock_table = Mock()
        mock_table.get_item.side_effect = Exception("DynamoDB error")
        mock_table.put_item.side_effect = Exception("Another error")

        tracker = EnvVarTracker()
        tracker.tracking_enabled = True
        tracker.table = mock_table
        tracker.service_name = "test-service"

        # Should not raise exception, just log warning
        tracker.track_env_var("TEST_VAR", [DynamoDBOperation.GET_ITEM])
        # If we get here, the exception was handled properly

    def test_init_with_dynamodb_exception(self):
        """Test EnvVarTracker initialization when DynamoDB resource fails"""
        with patch.dict(os.environ, {"ENV_VARS_TRACKING_TABLE": "test-table"}):
            with patch("boto3.resource") as mock_boto3_resource:
                mock_boto3_resource.side_effect = Exception(
                    "DynamoDB connection failed"
                )

                tracker = EnvVarTracker()
                assert tracker.tracking_enabled is False

    def test_init_with_ssm_exception(self):
        """Test EnvVarTracker initialization when SSM client fails"""
        with patch.dict(os.environ, {}):
            with patch("boto3.client") as mock_boto3_client:
                mock_boto3_client.side_effect = Exception("SSM connection failed")

                tracker = EnvVarTracker()
                assert tracker.ssm_enabled is False

    def test_resolve_env_var_parameter_store_exception(self):
        """Test resolving env var when Parameter Store has other exceptions"""
        with patch.dict(
            os.environ, {"STAGE": "test", "SERVICE_NAME": "test-service"}, clear=True
        ):
            mock_ssm = Mock()
            # Create a different exception class for ParameterNotFound

            class MockParameterNotFound(Exception):
                pass

            mock_ssm.exceptions.ParameterNotFound = MockParameterNotFound
            # Use a different exception to hit the general exception handler
            mock_ssm.get_parameter.side_effect = RuntimeError("SSM service error")

            tracker = EnvVarTracker()
            tracker.ssm = mock_ssm
            tracker.ssm_enabled = True

            with pytest.raises(EnvVarError):
                tracker.resolve_env_var("MISSING_VAR")

    def test_resolve_env_var_strips_whitespace(self):
        """Test that resolved env var values are stripped of whitespace"""
        with patch.dict(os.environ, {"TEST_VAR": "  test_value  "}):
            tracker = EnvVarTracker()
            result = tracker.resolve_env_var("TEST_VAR")
            assert result == "test_value"

    def test_resolve_env_var_parameter_store_strips_whitespace(self):
        """Test that Parameter Store values are stripped of whitespace"""
        with patch.dict(
            os.environ, {"STAGE": "test", "SERVICE_NAME": "test-service"}, clear=True
        ):
            mock_ssm = Mock()
            mock_ssm.get_parameter.return_value = {
                "Parameter": {"Value": "  parameter_value  "}
            }

            tracker = EnvVarTracker()
            tracker.ssm = mock_ssm
            tracker.ssm_enabled = True

            result = tracker.resolve_env_var("TEST_VAR")
            assert result == "parameter_value"
            assert os.environ["TEST_VAR"] == "parameter_value"

    def test_track_env_var_strips_resolved_value(self):
        """Test that tracking strips whitespace from resolved values"""
        mock_table = Mock()
        mock_table.get_item.return_value = {}

        tracker = EnvVarTracker()
        tracker.tracking_enabled = True
        tracker.table = mock_table
        tracker.service_name = "test-service"

        with patch.dict(os.environ, {"TEST_VAR": "  test_value  "}):
            tracker.track_env_var("TEST_VAR", [DynamoDBOperation.GET_ITEM])

        mock_table.put_item.assert_called_once()
        call_args = mock_table.put_item.call_args[1]["Item"]
        assert call_args["resolved_value"] == "test_value"

    def test_track_env_var_no_new_operations(self):
        """Test tracking when no new operations need to be added"""
        mock_table = Mock()
        mock_table.get_item.return_value = {
            "Item": {
                "operations": ["dynamodb:GetItem"],  # Already has this operation
                "service_var_key": "test-service#TEST_VAR",
            }
        }

        tracker = EnvVarTracker()
        tracker.tracking_enabled = True
        tracker.table = mock_table
        tracker.service_name = "test-service"

        # Try to track the same operation that already exists
        tracker.track_env_var("TEST_VAR", [DynamoDBOperation.GET_ITEM])

        # Should call get_item but not update_item or put_item
        mock_table.get_item.assert_called_once()
        mock_table.update_item.assert_not_called()
        mock_table.put_item.assert_not_called()

    def test_track_env_var_merges_operations(self):
        """Test that tracking merges new operations with existing ones"""
        mock_table = Mock()
        mock_table.get_item.return_value = {
            "Item": {
                "operations": ["dynamodb:GetItem"],
                "service_var_key": "test-service#TEST_VAR",
            }
        }
        # Mock update_item to return successful response
        mock_table.update_item.return_value = {
            "Attributes": {"operations": ["dynamodb:GetItem", "dynamodb:PutItem"]}
        }

        tracker = EnvVarTracker()
        tracker.tracking_enabled = True
        tracker.table = mock_table
        tracker.service_name = "test-service"

        # Add a new operation
        tracker.track_env_var("TEST_VAR", [DynamoDBOperation.PUT_ITEM])

        # Should merge operations
        mock_table.update_item.assert_called_once()
        mock_table.put_item.assert_not_called()
        call_args = mock_table.update_item.call_args[1]
        merged_ops = call_args["ExpressionAttributeValues"][":operations"]
        assert set(merged_ops) == {"dynamodb:GetItem", "dynamodb:PutItem"}

    def test_track_env_var_creates_record_without_last_accessed(self):
        """Test that new tracking records don't include last_accessed field"""
        mock_table = Mock()
        mock_table.get_item.return_value = {}

        tracker = EnvVarTracker()
        tracker.tracking_enabled = True
        tracker.table = mock_table
        tracker.service_name = "test-service"

        tracker.track_env_var("TEST_VAR", [DynamoDBOperation.GET_ITEM])

        mock_table.put_item.assert_called_once()
        call_args = mock_table.put_item.call_args[1]["Item"]

        # Should have first_accessed but not last_accessed
        assert "first_accessed" in call_args
        assert "last_accessed" not in call_args

    def test_track_env_var_update_fallback_to_put(self):
        """Test that when update_item fails, it falls back to put_item"""
        mock_table = Mock()
        mock_table.get_item.return_value = {
            "Item": {
                "operations": [],  # No existing operations
                "service_var_key": "test-service#TEST_VAR",
            }
        }
        # Mock update_item to raise an exception
        mock_table.update_item.side_effect = Exception("Update failed")

        tracker = EnvVarTracker()
        tracker.tracking_enabled = True
        tracker.table = mock_table
        tracker.service_name = "test-service"

        with patch.dict(os.environ, {"TEST_VAR": "test_value"}):
            tracker.track_env_var("TEST_VAR", [DynamoDBOperation.GET_ITEM])

        # Should call update_item first, then fall back to put_item
        mock_table.update_item.assert_called_once()
        mock_table.put_item.assert_called_once()

        # Check put_item was called with correct arguments
        call_args = mock_table.put_item.call_args[1]["Item"]
        assert call_args["service_var_key"] == "test-service#TEST_VAR"
        assert call_args["operations"] == ["dynamodb:GetItem"]


class TestRequiredEnvVarsDecorator:
    """Test cases for the required_env_vars decorator"""

    def test_decorator_with_valid_env_vars(self):
        """Test decorator with valid environment variables"""
        env_vars_dict = {
            "TEST_TABLE": [DynamoDBOperation.GET_ITEM, DynamoDBOperation.PUT_ITEM],
            "TEST_BUCKET": [S3Operation.GET_OBJECT, S3Operation.PUT_OBJECT],
        }

        @required_env_vars(env_vars_dict)
        def test_function():
            return "success"

        with patch.dict(
            os.environ, {"TEST_TABLE": "table-name", "TEST_BUCKET": "bucket-name"}
        ):
            with patch("pycommon.decorators.EnvVarTracker") as mock_tracker_class:
                mock_tracker = Mock()
                mock_tracker.resolve_env_var.side_effect = lambda x: os.environ[x]
                mock_tracker_class.return_value = mock_tracker

                result = test_function()
                assert result == "success"

                # Verify resolve_env_var was called for each env var
                assert mock_tracker.resolve_env_var.call_count == 2
                mock_tracker.track_env_var.assert_called()

    def test_decorator_with_missing_env_var(self):
        """Test decorator when required env var is missing"""
        env_vars_dict = {"MISSING_VAR": [DynamoDBOperation.GET_ITEM]}

        @required_env_vars(env_vars_dict)
        def test_function():
            return "success"

        with patch.dict(os.environ, {}, clear=True):
            with patch("pycommon.decorators.EnvVarTracker") as mock_tracker_class:
                mock_tracker = Mock()
                mock_tracker.resolve_env_var.side_effect = EnvVarError(
                    "Variable not found"
                )
                mock_tracker_class.return_value = mock_tracker

                with pytest.raises(EnvVarError):
                    test_function()

    def test_decorator_with_invalid_operations(self):
        """Test decorator with invalid operations"""
        env_vars_dict = {"TEST_VAR": ["invalid_operation"]}  # Not an enum

        with pytest.raises(
            ValueError, match="Invalid operation invalid_operation for TEST_VAR"
        ):

            @required_env_vars(env_vars_dict)
            def test_function():
                return "success"

    def test_decorator_with_invalid_env_vars_dict(self):
        """Test decorator with invalid env_vars_dict parameter"""
        with pytest.raises(ValueError, match="required_env_vars expects a dictionary"):

            @required_env_vars("not_a_dict")
            def test_function():
                return "success"

    def test_decorator_metadata(self):
        """Test that decorator adds metadata to the function"""
        env_vars_dict = {
            "TEST_TABLE": [DynamoDBOperation.GET_ITEM],
            "TEST_SECRET": [SecretsManagerOperation.GET_SECRET_VALUE],
        }

        @required_env_vars(env_vars_dict)
        def test_function():
            return "success"

        assert hasattr(test_function, "_required_env_vars")
        assert hasattr(test_function, "_env_var_operations")
        assert test_function._required_env_vars == env_vars_dict
        assert test_function._env_var_operations == {
            "TEST_TABLE": ["dynamodb:GetItem"],
            "TEST_SECRET": ["secretsmanager:GetSecretValue"],
        }

    def test_decorator_with_invalid_var_name_type(self):
        """Test decorator with invalid env var name (not string)"""
        env_vars_dict = {123: [DynamoDBOperation.GET_ITEM]}  # Invalid - not a string

        with pytest.raises(
            ValueError, match="Environment variable name must be a string: 123"
        ):

            @required_env_vars(env_vars_dict)
            def test_function():
                return "success"

    def test_decorator_with_invalid_operations_type(self):
        """Test decorator with invalid operations (not list)"""
        env_vars_dict = {"TEST_VAR": DynamoDBOperation.GET_ITEM}  # Invalid - not a list

        with pytest.raises(ValueError, match="Operations must be a list for TEST_VAR"):

            @required_env_vars(env_vars_dict)
            def test_function():
                return "success"

    def test_decorator_with_non_critical_error(self):
        """Test decorator handles non-critical errors gracefully"""
        env_vars_dict = {"TEST_VAR": [DynamoDBOperation.GET_ITEM]}

        @required_env_vars(env_vars_dict)
        def test_function():
            return "success"

        with patch.dict(os.environ, {"TEST_VAR": "test_value"}):
            with patch("pycommon.decorators.EnvVarTracker") as mock_tracker_class:
                mock_tracker = Mock()
                mock_tracker.resolve_env_var.return_value = "test_value"
                mock_tracker.track_env_var.side_effect = Exception(
                    "Non-critical tracking error"
                )
                mock_tracker_class.return_value = mock_tracker

                # Should still execute successfully despite tracking error
                result = test_function()
                assert result == "success"
