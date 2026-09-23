"""
Tests for parameter_store_sync module

Comprehensive test coverage for Parameter Store synchronization utilities.
"""

import json
from unittest.mock import MagicMock, Mock, patch

from pycommon.deployment.parameter_store_sync import (
    cfn_handler,
    create_or_update_parameter,
    extract_locally_defined_vars,
    handle_cloudformation_request,
    populate_parameters,
    send_cfn_response,
)


class TestExtractLocallyDefinedVars:
    """Test extract_locally_defined_vars function"""

    def test_extract_with_matching_prefix(self):
        """Test extraction of variables with matching service-stage prefix"""
        env_vars = {
            "MY_TABLE": "my-service-dev-users-table",
            "MY_BUCKET": "my-service-dev-files-bucket",
            "IMPORTED_VAR": "/amplify/dev/some-service/VAR",
            "AWS_REGION": "us-east-1",
        }

        result = extract_locally_defined_vars(env_vars, "my-service", "dev")

        assert len(result) == 2
        assert "MY_TABLE" in result
        assert "MY_BUCKET" in result
        assert result["MY_TABLE"] == "my-service-dev-users-table"
        assert result["MY_BUCKET"] == "my-service-dev-files-bucket"

    def test_skip_aws_managed_vars(self):
        """Test that AWS-managed variables are skipped"""
        env_vars = {
            "AWS_LAMBDA_FUNCTION_NAME": "my-service-dev-function",
            "AWS_REGION": "us-east-1",
            "AWS_ACCESS_KEY_ID": "AKIAIOSFODNN7EXAMPLE",
            "MY_TABLE": "my-service-dev-table",
        }

        result = extract_locally_defined_vars(env_vars, "my-service", "dev")

        assert len(result) == 1
        assert "MY_TABLE" in result
        assert "AWS_LAMBDA_FUNCTION_NAME" not in result
        assert "AWS_REGION" not in result
        assert "AWS_ACCESS_KEY_ID" not in result

    def test_skip_imported_ssm_vars(self):
        """Test that imported SSM parameters are skipped"""
        env_vars = {
            "LOCAL_VAR": "my-service-dev-resource",
            "IMPORTED_VAR": "/amplify/dev/other-service/SOME_VAR",
            "ANOTHER_IMPORT": "${ssm:/path/to/param}",
        }

        result = extract_locally_defined_vars(env_vars, "my-service", "dev")

        assert len(result) == 1
        assert "LOCAL_VAR" in result
        assert "IMPORTED_VAR" not in result
        assert "ANOTHER_IMPORT" not in result

    def test_skip_empty_values(self):
        """Test that empty values are skipped"""
        env_vars = {
            "EMPTY_VAR": "",
            "MY_TABLE": "my-service-dev-table",
        }

        result = extract_locally_defined_vars(env_vars, "my-service", "dev")

        assert len(result) == 1
        assert "MY_TABLE" in result
        assert "EMPTY_VAR" not in result

    def test_no_matching_vars(self):
        """Test when no variables match the pattern"""
        env_vars = {
            "IMPORTED_VAR": "/amplify/dev/service/VAR",
            "AWS_REGION": "us-east-1",
        }

        result = extract_locally_defined_vars(env_vars, "my-service", "dev")

        assert len(result) == 0
        assert result == {}

    def test_empty_env_vars(self):
        """Test with empty environment variables dict"""
        result = extract_locally_defined_vars({}, "my-service", "dev")

        assert len(result) == 0
        assert result == {}

    def test_different_stages(self):
        """Test that stage matters in prefix matching"""
        env_vars = {
            "DEV_TABLE": "my-service-dev-table",
            "PROD_TABLE": "my-service-prod-table",
        }

        # Extract for dev stage
        dev_result = extract_locally_defined_vars(env_vars, "my-service", "dev")
        assert "DEV_TABLE" in dev_result
        assert "PROD_TABLE" not in dev_result

        # Extract for prod stage
        prod_result = extract_locally_defined_vars(env_vars, "my-service", "prod")
        assert "PROD_TABLE" in prod_result
        assert "DEV_TABLE" not in prod_result

    def test_variables_starting_with_aws_underscore(self):
        """Test that variables starting with AWS_ are skipped"""
        env_vars = {
            "AWS_CUSTOM_VAR": "my-service-dev-resource",
            "MY_TABLE": "my-service-dev-table",
        }

        result = extract_locally_defined_vars(env_vars, "my-service", "dev")

        assert len(result) == 1
        assert "MY_TABLE" in result
        assert "AWS_CUSTOM_VAR" not in result


class TestCreateOrUpdateParameter:
    """Test create_or_update_parameter function"""

    def test_create_new_parameter(self):
        """Test creating a new parameter"""
        mock_ssm = Mock()
        mock_ssm.exceptions.ParameterNotFound = type(
            "ParameterNotFound", (Exception,), {}
        )
        mock_ssm.get_parameter.side_effect = mock_ssm.exceptions.ParameterNotFound()

        result = create_or_update_parameter(
            parameter_name="/test/param",
            value="test-value",
            description="Test parameter",
            ssm_client=mock_ssm,
        )

        assert result["status"] == "created"
        assert "Created with value test-value" in result["message"]
        mock_ssm.put_parameter.assert_called_once_with(
            Name="/test/param",
            Value="test-value",
            Type="String",
            Description="Test parameter",
        )

    def test_update_existing_parameter_with_different_value(self):
        """Test updating a parameter with different value"""
        mock_ssm = Mock()
        mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "old-value"}}

        result = create_or_update_parameter(
            parameter_name="/test/param",
            value="new-value",
            description="Test parameter",
            ssm_client=mock_ssm,
        )

        assert result["status"] == "updated"
        assert "Updated from old-value to new-value" in result["message"]
        mock_ssm.put_parameter.assert_called_once_with(
            Name="/test/param",
            Value="new-value",
            Type="String",
            Overwrite=True,
            Description="Test parameter",
        )

    def test_parameter_unchanged(self):
        """Test when parameter value hasn't changed"""
        mock_ssm = Mock()
        mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "same-value"}}

        result = create_or_update_parameter(
            parameter_name="/test/param",
            value="same-value",
            description="Test parameter",
            ssm_client=mock_ssm,
        )

        assert result["status"] == "unchanged"
        assert "Value already correct" in result["message"]
        mock_ssm.put_parameter.assert_not_called()

    def test_error_on_get_parameter(self):
        """Test error handling when get_parameter fails
        with non-ParameterNotFound exception"""
        mock_ssm = Mock()
        # Create a proper exception class hierarchy
        mock_ssm.exceptions.ParameterNotFound = type(
            "ParameterNotFound", (Exception,), {}
        )
        # Raise a different exception (not ParameterNotFound)
        mock_ssm.get_parameter.side_effect = Exception("Network error")

        result = create_or_update_parameter(
            parameter_name="/test/param",
            value="test-value",
            description="Test parameter",
            ssm_client=mock_ssm,
        )

        assert result["status"] == "error"
        assert "Network error" in result["message"]

    def test_error_on_put_parameter(self):
        """Test error handling when put_parameter fails"""
        mock_ssm = Mock()
        mock_ssm.exceptions.ParameterNotFound = type(
            "ParameterNotFound", (Exception,), {}
        )
        mock_ssm.get_parameter.side_effect = mock_ssm.exceptions.ParameterNotFound()
        mock_ssm.put_parameter.side_effect = Exception("Permission denied")

        result = create_or_update_parameter(
            parameter_name="/test/param",
            value="test-value",
            description="Test parameter",
            ssm_client=mock_ssm,
        )

        assert result["status"] == "error"
        assert "Permission denied" in result["message"]

    def test_uses_default_boto3_client_when_none_provided(self):
        """Test that default boto3 client is created when not
        provided"""
        with patch("pycommon.deployment.parameter_store_sync.boto3") as mock_boto3:
            mock_ssm = Mock()
            mock_ssm.exceptions.ParameterNotFound = type(
                "ParameterNotFound", (Exception,), {}
            )
            mock_ssm.get_parameter.side_effect = mock_ssm.exceptions.ParameterNotFound()
            mock_boto3.client.return_value = mock_ssm

            create_or_update_parameter(
                parameter_name="/test/param",
                value="test-value",
                description="Test parameter",
            )

            mock_boto3.client.assert_called_once_with("ssm")


class TestPopulateParameters:
    """Test populate_parameters function"""

    def test_populate_with_multiple_variables(self):
        """Test populating multiple variables"""
        env_vars = {
            "TABLE_1": "service-dev-table1",
            "TABLE_2": "service-dev-table2",
            "BUCKET": "service-dev-bucket",
        }

        mock_ssm = Mock()
        mock_ssm.exceptions.ParameterNotFound = type(
            "ParameterNotFound", (Exception,), {}
        )
        mock_ssm.get_parameter.side_effect = mock_ssm.exceptions.ParameterNotFound()

        result = populate_parameters(
            service_name="service", stage="dev", env_vars=env_vars, ssm_client=mock_ssm
        )

        assert result["totalVariables"] == 3
        assert result["created"] == 3
        assert result["updated"] == 0
        assert result["unchanged"] == 0
        assert result["errors"] == 0
        assert len(result["variables"]) == 3
        assert "TABLE_1" in result["variables"]
        assert "TABLE_2" in result["variables"]
        assert "BUCKET" in result["variables"]

    def test_populate_with_no_local_variables(self):
        """Test when there are no local variables to populate"""
        env_vars = {
            "AWS_REGION": "us-east-1",
            "IMPORTED_VAR": "/amplify/dev/service/VAR",
        }

        mock_ssm = Mock()

        result = populate_parameters(
            service_name="service", stage="dev", env_vars=env_vars, ssm_client=mock_ssm
        )

        assert result["totalVariables"] == 0
        assert result["created"] == 0
        assert result["updated"] == 0
        assert result["unchanged"] == 0
        assert result["errors"] == 0
        assert result["variables"] == {}
        mock_ssm.get_parameter.assert_not_called()
        mock_ssm.put_parameter.assert_not_called()

    def test_populate_with_mixed_results(self):
        """Test populating with mixed create/update/unchanged/error
        results"""
        # Use OrderedDict to ensure ERROR_VAR is NOT last,
        # so we test loop continuation after error
        from collections import OrderedDict

        env_vars = OrderedDict(
            [
                ("NEW_VAR", "service-dev-new"),
                # Error in middle to test loop continuation
                ("ERROR_VAR", "service-dev-error"),
                ("UPDATE_VAR", "service-dev-update"),
                ("SAME_VAR", "service-dev-same"),
            ]
        )

        mock_ssm = Mock()
        mock_ssm.exceptions.ParameterNotFound = type(
            "ParameterNotFound", (Exception,), {}
        )

        def get_parameter_side_effect(Name):
            if "NEW_VAR" in Name:
                raise mock_ssm.exceptions.ParameterNotFound()
            elif "UPDATE_VAR" in Name:
                return {"Parameter": {"Value": "old-value"}}
            elif "SAME_VAR" in Name:
                return {"Parameter": {"Value": "service-dev-same"}}
            elif "ERROR_VAR" in Name:
                raise Exception("Test error")

        mock_ssm.get_parameter.side_effect = get_parameter_side_effect

        result = populate_parameters(
            service_name="service", stage="dev", env_vars=env_vars, ssm_client=mock_ssm
        )

        assert result["totalVariables"] == 4
        assert result["created"] == 1  # NEW_VAR
        assert result["updated"] == 1  # UPDATE_VAR
        assert result["unchanged"] == 1  # SAME_VAR
        assert result["errors"] == 1  # ERROR_VAR

    def test_parameter_path_construction(self):
        """Test that parameter paths are constructed correctly"""
        env_vars = {
            "MY_VAR": "my-service-prod-resource",
        }

        mock_ssm = Mock()
        mock_ssm.exceptions.ParameterNotFound = type(
            "ParameterNotFound", (Exception,), {}
        )
        mock_ssm.get_parameter.side_effect = mock_ssm.exceptions.ParameterNotFound()

        populate_parameters(
            service_name="my-service",
            stage="prod",
            env_vars=env_vars,
            ssm_client=mock_ssm,
        )

        # Check that the parameter was created with correct path
        mock_ssm.put_parameter.assert_called_once()
        call_args = mock_ssm.put_parameter.call_args
        assert call_args[1]["Name"] == "/amplify/prod/my-service/MY_VAR"
        assert call_args[1]["Value"] == "my-service-prod-resource"
        assert (
            "Locally defined variable from my-service service"
            in call_args[1]["Description"]
        )

    def test_uses_default_boto3_client_when_none_provided(self):
        """Test that default boto3 client is created when not
        provided"""
        env_vars = {
            "MY_VAR": "service-dev-resource",
        }

        with patch("pycommon.deployment.parameter_store_sync.boto3") as mock_boto3:
            mock_ssm = Mock()
            mock_ssm.exceptions.ParameterNotFound = type(
                "ParameterNotFound", (Exception,), {}
            )
            mock_ssm.get_parameter.side_effect = mock_ssm.exceptions.ParameterNotFound()
            mock_boto3.client.return_value = mock_ssm

            populate_parameters(service_name="service", stage="dev", env_vars=env_vars)

            # boto3.client should be called in both extract
            # (for logging setup potentially)
            # and in create_or_update_parameter
            assert mock_boto3.client.call_count >= 1

    def test_empty_env_vars(self):
        """Test with empty environment variables"""
        mock_ssm = Mock()

        result = populate_parameters(
            service_name="service", stage="dev", env_vars={}, ssm_client=mock_ssm
        )

        assert result["totalVariables"] == 0
        assert result["variables"] == {}

    def test_multiple_errors_ensures_loop_continuation(self):
        """Test that multiple errors in a row still continues the loop"""
        from collections import OrderedDict

        env_vars = OrderedDict(
            [
                ("ERROR_VAR_1", "service-dev-error1"),
                # Second error ensures loop continues after first error
                ("ERROR_VAR_2", "service-dev-error2"),
                ("GOOD_VAR", "service-dev-good"),
            ]
        )

        mock_ssm = Mock()
        mock_ssm.exceptions.ParameterNotFound = type(
            "ParameterNotFound", (Exception,), {}
        )

        def get_parameter_side_effect(Name):
            if "ERROR_VAR" in Name:
                raise Exception("Test error")
            else:
                raise mock_ssm.exceptions.ParameterNotFound()

        mock_ssm.get_parameter.side_effect = get_parameter_side_effect

        result = populate_parameters(
            service_name="service", stage="dev", env_vars=env_vars, ssm_client=mock_ssm
        )

        assert result["totalVariables"] == 3
        assert result["errors"] == 2
        assert result["created"] == 1

    def test_unexpected_status_handled_gracefully(self):
        """Test that unexpected status values are handled gracefully"""
        env_vars = {
            "MY_VAR": "service-dev-resource",
        }

        mock_ssm = Mock()

        # Mock create_or_update_parameter to return unexpected status
        with patch(
            "pycommon.deployment.parameter_store_sync." "create_or_update_parameter"
        ) as mock_create:
            mock_create.return_value = {
                "status": "unknown_status",
                "message": "Something weird happened",
            }

            result = populate_parameters(
                service_name="service",
                stage="dev",
                env_vars=env_vars,
                ssm_client=mock_ssm,
            )

            assert result["totalVariables"] == 1
            assert result["errors"] == 1  # Unexpected status counted as error


class TestLoggingBehavior:
    """Test logging behavior of parameter store sync functions"""

    def test_extract_logs_found_variables(self, caplog):
        """Test that extract function logs found variables"""
        env_vars = {
            "MY_TABLE": "my-service-dev-table",
        }

        with caplog.at_level("DEBUG"):
            extract_locally_defined_vars(env_vars, "my-service", "dev")

        assert "Found locally defined variable: MY_TABLE" in caplog.text

    def test_create_logs_creation(self, caplog):
        """Test that create function logs parameter creation"""
        mock_ssm = Mock()
        mock_ssm.exceptions.ParameterNotFound = type(
            "ParameterNotFound", (Exception,), {}
        )
        mock_ssm.get_parameter.side_effect = mock_ssm.exceptions.ParameterNotFound()

        with caplog.at_level("INFO"):
            create_or_update_parameter(
                parameter_name="/test/param",
                value="test-value",
                description="Test",
                ssm_client=mock_ssm,
            )

        assert "Created: /test/param" in caplog.text

    def test_create_logs_update(self, caplog):
        """Test that create function logs parameter updates"""
        mock_ssm = Mock()
        mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "old-value"}}

        with caplog.at_level("INFO"):
            create_or_update_parameter(
                parameter_name="/test/param",
                value="new-value",
                description="Test",
                ssm_client=mock_ssm,
            )

        assert "Updated: /test/param" in caplog.text

    def test_populate_logs_summary(self, caplog):
        """Test that populate function logs completion summary"""
        env_vars = {
            "MY_VAR": "service-dev-resource",
        }

        mock_ssm = Mock()
        mock_ssm.exceptions.ParameterNotFound = type(
            "ParameterNotFound", (Exception,), {}
        )
        mock_ssm.get_parameter.side_effect = mock_ssm.exceptions.ParameterNotFound()

        with caplog.at_level("INFO"):
            populate_parameters(
                service_name="service",
                stage="dev",
                env_vars=env_vars,
                ssm_client=mock_ssm,
            )

        assert "Parameter Store population complete" in caplog.text
        assert "1 created" in caplog.text


def _make_cfn_event(request_type="Create"):
    """Return a minimal CloudFormation custom resource event."""
    return {
        "RequestType": request_type,
        "ResponseURL": "https://cfn-response.example.com/respond",
        "StackId": "arn:aws:cloudformation:us-east-1:123456789012:stack/test/abc",
        "RequestId": "req-1234",
        "LogicalResourceId": "ParamStoreAutoPopulate",
        "ResourceProperties": {},
    }


def _make_context(log_stream_name="test-log-stream"):
    ctx = MagicMock()
    ctx.log_stream_name = log_stream_name
    return ctx


class TestSendCfnResponse:
    """Test send_cfn_response function."""

    def test_sends_put_request_to_response_url(self):
        """Test that a PUT is issued to the ResponseURL."""
        event = _make_cfn_event()
        ctx = _make_context()

        with patch(
            "pycommon.deployment.parameter_store_sync.urllib3.PoolManager"
        ) as mock_pm:
            mock_http = Mock()
            mock_http.request.return_value = Mock(status=200)
            mock_pm.return_value = mock_http

            result = send_cfn_response(event, ctx, "SUCCESS", {"key": "val"})

        mock_http.request.assert_called_once()
        call_args = mock_http.request.call_args
        assert call_args[0][0] == "PUT"
        assert call_args[0][1] == event["ResponseURL"]
        body = json.loads(call_args[1]["body"])
        assert body["Status"] == "SUCCESS"
        assert body["StackId"] == event["StackId"]
        assert body["RequestId"] == event["RequestId"]
        assert body["LogicalResourceId"] == event["LogicalResourceId"]
        assert body["PhysicalResourceId"] == ctx.log_stream_name
        assert body["Data"] == {"key": "val"}
        assert result == {"statusCode": 200}

    def test_sends_failed_status(self):
        """Test that FAILED status is forwarded correctly."""
        event = _make_cfn_event()
        ctx = _make_context()

        with patch(
            "pycommon.deployment.parameter_store_sync.urllib3.PoolManager"
        ) as mock_pm:
            mock_http = Mock()
            mock_http.request.return_value = Mock(status=200)
            mock_pm.return_value = mock_http

            send_cfn_response(event, ctx, "FAILED", {"Error": "oops"})

        body = json.loads(mock_http.request.call_args[1]["body"])
        assert body["Status"] == "FAILED"
        assert body["Data"] == {"Error": "oops"}

    def test_swallows_http_exception_and_returns_200(self):
        """Test that HTTP errors are logged but do not raise."""
        event = _make_cfn_event()
        ctx = _make_context()

        with patch(
            "pycommon.deployment.parameter_store_sync.urllib3.PoolManager"
        ) as mock_pm:
            mock_http = Mock()
            mock_http.request.side_effect = Exception("connection refused")
            mock_pm.return_value = mock_http

            result = send_cfn_response(event, ctx, "SUCCESS", {})

        assert result == {"statusCode": 200}


class TestHandleCloudformationRequest:
    """Test handle_cloudformation_request function."""

    def test_delete_returns_success_immediately(self):
        """Test that Delete skips parameter population."""
        event = _make_cfn_event("Delete")
        ctx = _make_context()

        with (
            patch(
                "pycommon.deployment.parameter_store_sync.send_cfn_response"
            ) as mock_send,
            patch(
                "pycommon.deployment.parameter_store_sync.populate_parameters"
            ) as mock_pop,
        ):
            mock_send.return_value = {"statusCode": 200}
            handle_cloudformation_request(event, ctx)

        mock_pop.assert_not_called()
        mock_send.assert_called_once_with(
            event, ctx, "SUCCESS", {"Message": "Delete operation - no action taken"}
        )

    def test_missing_service_name_returns_failed(self):
        """Test FAILED response when SERVICE_NAME env var is absent."""
        event = _make_cfn_event("Create")
        ctx = _make_context()

        with (
            patch.dict("os.environ", {}, clear=True),
            patch(
                "pycommon.deployment.parameter_store_sync.send_cfn_response"
            ) as mock_send,
        ):
            mock_send.return_value = {"statusCode": 200}
            handle_cloudformation_request(event, ctx)

        mock_send.assert_called_once()
        args = mock_send.call_args[0]
        assert args[2] == "FAILED"
        assert "SERVICE_NAME" in args[3]["Error"]

    def test_missing_stage_returns_failed(self):
        """Test FAILED response when STAGE env var is absent."""
        event = _make_cfn_event("Create")
        ctx = _make_context()

        with (
            patch.dict("os.environ", {"SERVICE_NAME": "my-service"}, clear=True),
            patch(
                "pycommon.deployment.parameter_store_sync.send_cfn_response"
            ) as mock_send,
        ):
            mock_send.return_value = {"statusCode": 200}
            handle_cloudformation_request(event, ctx)

        mock_send.assert_called_once()
        args = mock_send.call_args[0]
        assert args[2] == "FAILED"
        assert "STAGE" in args[3]["Error"]

    def test_successful_population(self):
        """Test SUCCESS response on clean population."""
        event = _make_cfn_event("Create")
        ctx = _make_context()

        env = {"SERVICE_NAME": "my-service", "STAGE": "dev"}
        good_results = {
            "totalVariables": 2,
            "created": 2,
            "updated": 0,
            "unchanged": 0,
            "errors": 0,
            "variables": {},
        }

        with (
            patch.dict("os.environ", env, clear=True),
            patch(
                "pycommon.deployment.parameter_store_sync.populate_parameters"
            ) as mock_pop,
            patch(
                "pycommon.deployment.parameter_store_sync.send_cfn_response"
            ) as mock_send,
        ):
            mock_pop.return_value = good_results
            mock_send.return_value = {"statusCode": 200}
            handle_cloudformation_request(event, ctx)

        mock_send.assert_called_once()
        args = mock_send.call_args[0]
        assert args[2] == "SUCCESS"
        assert "2 variables" in args[3]["Message"]

    def test_partial_errors_still_sends_success(self):
        """Test that partial errors return SUCCESS (non-blocking)."""
        event = _make_cfn_event("Update")
        ctx = _make_context()

        env = {"SERVICE_NAME": "my-service", "STAGE": "dev"}
        partial_results = {
            "totalVariables": 3,
            "created": 2,
            "updated": 0,
            "unchanged": 0,
            "errors": 1,
            "variables": {},
        }

        with (
            patch.dict("os.environ", env, clear=True),
            patch(
                "pycommon.deployment.parameter_store_sync.populate_parameters"
            ) as mock_pop,
            patch(
                "pycommon.deployment.parameter_store_sync.send_cfn_response"
            ) as mock_send,
        ):
            mock_pop.return_value = partial_results
            mock_send.return_value = {"statusCode": 200}
            handle_cloudformation_request(event, ctx)

        args = mock_send.call_args[0]
        assert args[2] == "SUCCESS"
        assert "errors" in args[3]["Message"]

    def test_populate_exception_sends_failed(self):
        """Test FAILED response when populate_parameters raises."""
        event = _make_cfn_event("Create")
        ctx = _make_context()

        env = {"SERVICE_NAME": "my-service", "STAGE": "dev"}

        with (
            patch.dict("os.environ", env, clear=True),
            patch(
                "pycommon.deployment.parameter_store_sync.populate_parameters"
            ) as mock_pop,
            patch(
                "pycommon.deployment.parameter_store_sync.send_cfn_response"
            ) as mock_send,
        ):
            mock_pop.side_effect = Exception("boto3 exploded")
            mock_send.return_value = {"statusCode": 200}
            handle_cloudformation_request(event, ctx)

        args = mock_send.call_args[0]
        assert args[2] == "FAILED"
        assert "boto3 exploded" in args[3]["Error"]


class TestCfnHandler:
    """Test cfn_handler (Lambda entry-point)."""

    def test_routes_cfn_event_to_handler(self):
        """Test that CFN events are delegated to handle_cloudformation_request."""
        event = _make_cfn_event("Create")
        ctx = _make_context()

        with patch(
            "pycommon.deployment.parameter_store_sync." "handle_cloudformation_request"
        ) as mock_handle:
            mock_handle.return_value = {"statusCode": 200}
            result = cfn_handler(event, ctx)

        mock_handle.assert_called_once_with(event, ctx)
        assert result == {"statusCode": 200}

    def test_direct_invocation_returns_400(self):
        """Test that non-CFN (direct) invocations return 400."""
        ctx = _make_context()
        result = cfn_handler({}, ctx)

        assert result["statusCode"] == 400
        body = json.loads(result["body"])
        assert "Direct invocation not supported" in body["error"]

    def test_unexpected_exception_sends_cfn_failed(self):
        """Test that an unexpected top-level exception sends FAILED to CFN."""
        event = _make_cfn_event("Create")
        ctx = _make_context()

        with (
            patch(
                "pycommon.deployment.parameter_store_sync."
                "handle_cloudformation_request"
            ) as mock_handle,
            patch(
                "pycommon.deployment.parameter_store_sync.send_cfn_response"
            ) as mock_send,
        ):
            mock_handle.side_effect = RuntimeError("totally unexpected")
            mock_send.return_value = {"statusCode": 200}
            cfn_handler(event, ctx)

        mock_send.assert_called_once()
        args = mock_send.call_args[0]
        assert args[2] == "FAILED"
        assert "totally unexpected" in args[3]["Error"]

    def test_unexpected_exception_without_cfn_event_returns_500(self):
        """Test that an unexpected top-level exception on direct call returns 500."""
        ctx = _make_context()

        # Patch json.dumps so the *second* call (inside the 400-body) raises,
        # triggering the except branch without a RequestType in the event.
        original_dumps = json.dumps
        call_count = {"n": 0}

        def selective_raises(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 2:  # the json.dumps inside the 400-body
                raise TypeError("not serialisable")
            return original_dumps(*args, **kwargs)

        with patch(
            "pycommon.deployment.parameter_store_sync.json.dumps",
            side_effect=selective_raises,
        ):
            result = cfn_handler({}, ctx)

        assert result["statusCode"] == 500
