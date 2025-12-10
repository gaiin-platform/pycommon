# Copyright (c) 2024 Vanderbilt University
# Authors: Jules White, Allen Karns, Karely Rodriguez, Max Moundas

import os
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from pycommon.api.request_state import request_killed
from pycommon.exceptions import EnvVarError


@patch.dict(os.environ, {"REQUEST_STATE_DYNAMO_TABLE": "test-requests-table"})
@patch("pycommon.api.request_state.boto3.client")
def test_request_killed_true(mock_boto_client):
    """Test request_killed returns True when killswitch is set."""
    mock_dynamodb = MagicMock()
    mock_boto_client.return_value = mock_dynamodb

    # Mock DynamoDB response with exit=True
    mock_dynamodb.get_item.return_value = {
        "Item": {"exit": {"BOOL": True}, "user": {"S": "test_user"}}
    }

    result = request_killed("test_user", "request_123")

    assert result is True
    mock_dynamodb.get_item.assert_called_once_with(
        TableName="test-requests-table",
        Key={"user": {"S": "test_user"}, "requestId": {"S": "request_123"}},
    )


@patch.dict(os.environ, {"REQUEST_STATE_DYNAMO_TABLE": "test-requests-table"})
@patch("pycommon.api.request_state.boto3.client")
def test_request_killed_false(mock_boto_client):
    """Test request_killed returns False when killswitch is not set."""
    mock_dynamodb = MagicMock()
    mock_boto_client.return_value = mock_dynamodb

    # Mock DynamoDB response with exit=False
    mock_dynamodb.get_item.return_value = {
        "Item": {"exit": {"BOOL": False}, "user": {"S": "test_user"}}
    }

    result = request_killed("test_user", "request_123")

    assert result is False
    mock_dynamodb.get_item.assert_called_once_with(
        TableName="test-requests-table",
        Key={"user": {"S": "test_user"}, "requestId": {"S": "request_123"}},
    )


@patch.dict(os.environ, {"REQUEST_STATE_DYNAMO_TABLE": "test-requests-table"})
@patch("pycommon.api.request_state.boto3.client")
def test_request_killed_item_not_found(mock_boto_client):
    """Test request_killed returns True when item is not found in DynamoDB."""
    mock_dynamodb = MagicMock()
    mock_boto_client.return_value = mock_dynamodb

    # Mock DynamoDB response with no Item (request not found)
    mock_dynamodb.get_item.return_value = {}

    result = request_killed("test_user", "request_123")

    # Should return True when item not found (assuming killed/deleted)
    assert result is True
    mock_dynamodb.get_item.assert_called_once_with(
        TableName="test-requests-table",
        Key={"user": {"S": "test_user"}, "requestId": {"S": "request_123"}},
    )


@patch.dict(os.environ, {"REQUEST_STATE_DYNAMO_TABLE": "test-requests-table"})
@patch("pycommon.api.request_state.boto3.client")
def test_request_killed_client_error(mock_boto_client):
    """Test request_killed returns False when ClientError occurs."""
    mock_dynamodb = MagicMock()
    mock_boto_client.return_value = mock_dynamodb

    # Mock DynamoDB ClientError
    mock_dynamodb.get_item.side_effect = ClientError(
        {"Error": {"Code": "ResourceNotFoundException", "Message": "Table not found"}},
        "GetItem",
    )

    result = request_killed("test_user", "request_123")

    # Should return False on ClientError
    assert result is False
    mock_dynamodb.get_item.assert_called_once()


@patch.dict(os.environ, {}, clear=True)
def test_request_killed_no_table_env_var():
    """Test request_killed raises EnvVarError when env var not set."""
    with pytest.raises(
        EnvVarError,
        match="REQUEST_STATE_DYNAMO_TABLE",
    ):
        request_killed("test_user", "request_123")


@patch.dict(os.environ, {"REQUEST_STATE_DYNAMO_TABLE": ""}, clear=True)
def test_request_killed_empty_table_env_var():
    """Test request_killed raises EnvVarError when env var is empty."""
    with pytest.raises(
        EnvVarError,
        match="REQUEST_STATE_DYNAMO_TABLE",
    ):
        request_killed("test_user", "request_123")


@patch.dict(os.environ, {"REQUEST_STATE_DYNAMO_TABLE": "test-requests-table"})
@patch("pycommon.api.request_state.boto3.client")
def test_request_killed_with_special_characters(mock_boto_client):
    """Test request_killed with special characters in user and request_id."""
    mock_dynamodb = MagicMock()
    mock_boto_client.return_value = mock_dynamodb

    # Mock DynamoDB response with exit=True
    mock_dynamodb.get_item.return_value = {
        "Item": {"exit": {"BOOL": True}, "user": {"S": "user@example.com"}}
    }

    result = request_killed("user@example.com", "request-abc-123-xyz")

    assert result is True
    mock_dynamodb.get_item.assert_called_once_with(
        TableName="test-requests-table",
        Key={
            "user": {"S": "user@example.com"},
            "requestId": {"S": "request-abc-123-xyz"},
        },
    )


@patch.dict(os.environ, {"REQUEST_STATE_DYNAMO_TABLE": "test-requests-table"})
@patch("pycommon.api.request_state.boto3.client")
def test_request_killed_with_long_identifiers(mock_boto_client):
    """Test request_killed with very long user and request_id values."""
    mock_dynamodb = MagicMock()
    mock_boto_client.return_value = mock_dynamodb

    long_user = "a" * 256
    long_request_id = "b" * 256

    # Mock DynamoDB response with exit=False
    mock_dynamodb.get_item.return_value = {
        "Item": {"exit": {"BOOL": False}, "user": {"S": long_user}}
    }

    result = request_killed(long_user, long_request_id)

    assert result is False
    mock_dynamodb.get_item.assert_called_once_with(
        TableName="test-requests-table",
        Key={"user": {"S": long_user}, "requestId": {"S": long_request_id}},
    )


@patch.dict(os.environ, {"REQUEST_STATE_DYNAMO_TABLE": "test-requests-table"})
@patch("pycommon.api.request_state.boto3.client")
def test_request_killed_throttling_error(mock_boto_client):
    """Test request_killed returns False when throttling error occurs."""
    mock_dynamodb = MagicMock()
    mock_boto_client.return_value = mock_dynamodb

    # Mock DynamoDB throttling error
    mock_dynamodb.get_item.side_effect = ClientError(
        {
            "Error": {
                "Code": "ProvisionedThroughputExceededException",
                "Message": "Rate exceeded",
            }
        },
        "GetItem",
    )

    result = request_killed("test_user", "request_123")

    # Should return False on throttling error
    assert result is False


@patch.dict(os.environ, {"REQUEST_STATE_DYNAMO_TABLE": "test-requests-table"})
@patch("pycommon.api.request_state.boto3.client")
def test_request_killed_access_denied_error(mock_boto_client):
    """Test request_killed returns False when access is denied."""
    mock_dynamodb = MagicMock()
    mock_boto_client.return_value = mock_dynamodb

    # Mock DynamoDB access denied error
    mock_dynamodb.get_item.side_effect = ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "Access denied"}},
        "GetItem",
    )

    result = request_killed("test_user", "request_123")

    # Should return False on access denied
    assert result is False
