# Copyright (c) 2024 Vanderbilt University
# Authors: Jules White, Allen Karns, Karely Rodriguez, Max Moundas

import json
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from pycommon.api.credentials import get_credentials, get_endpoint, get_json_credentials


@patch("pycommon.api.credentials.boto3.session.Session")
def test_get_credentials_success(mock_session):
    mock_client = MagicMock()
    mock_client.get_secret_value.return_value = {"SecretString": "secret_value"}
    mock_session.return_value.client.return_value = mock_client

    result = get_credentials("test_secret")

    assert result == "secret_value"
    mock_client.get_secret_value.assert_called_once_with(SecretId="test_secret")


@patch("pycommon.api.credentials.boto3.session.Session")
def test_get_credentials_client_error(mock_session):
    mock_client = MagicMock()
    mock_client.get_secret_value.side_effect = ClientError(
        {"Error": {"Code": "ResourceNotFoundException"}}, "GetSecretValue"
    )
    mock_session.return_value.client.return_value = mock_client

    with pytest.raises(ClientError):
        get_credentials("test_secret")


@patch("pycommon.api.credentials.boto3.session.Session")
def test_get_json_credentials_success(mock_session):
    """Test successful retrieval and parsing of JSON credentials."""
    # Mock the Secrets Manager client
    mock_client = MagicMock()
    mock_session.return_value.client.return_value = mock_client

    # Mock successful response
    test_secret = {"key1": "value1", "key2": "value2"}
    mock_client.get_secret_value.return_value = {
        "SecretString": json.dumps(test_secret)
    }

    # Call the function
    result = get_json_credentials("test_secret_arn")

    # Assertions
    assert result == test_secret
    mock_client.get_secret_value.assert_called_once_with(SecretId="test_secret_arn")


@patch("pycommon.api.credentials.boto3.session.Session")
def test_get_json_credentials_client_error(mock_session):
    """Test error handling when Secrets Manager raises a ClientError."""
    # Test JSON decode error in get_json_credentials lines 52-53
    mock_client = MagicMock()
    mock_session.return_value.client.return_value = mock_client

    # Mock ClientError
    error = ClientError(
        error_response={"Error": {"Code": "ResourceNotFoundException"}},
        operation_name="GetSecretValue",
    )
    mock_client.get_secret_value.side_effect = error

    # Call the function and expect it to raise the ClientError
    with pytest.raises(ClientError):
        get_json_credentials("test-secret")


@patch("pycommon.api.credentials.boto3.session.Session")
def test_get_json_credentials_json_decode_error(mock_session):
    """Test error handling when JSON parsing fails."""
    mock_client = MagicMock()
    mock_session.return_value.client.return_value = mock_client

    # Mock response with invalid JSON
    mock_client.get_secret_value.return_value = {"SecretString": "invalid json"}

    # Call the function and expect it to raise a JSONDecodeError
    with pytest.raises(json.JSONDecodeError):
        get_json_credentials("test-secret")


@patch("pycommon.api.credentials.random.choice")
@patch("pycommon.api.credentials.boto3.session.Session")
def test_get_endpoint_success(mock_session, mock_choice):
    mock_client = MagicMock()
    secret_data = {
        "models": [
            {
                "test_model": {
                    "endpoints": [
                        {"url": "http://endpoint1.com", "key": "key1"},
                        {"url": "http://endpoint2.com", "key": "key2"},
                    ]
                }
            }
        ]
    }
    mock_client.get_secret_value.return_value = {
        "SecretString": json.dumps(secret_data)
    }
    mock_session.return_value.client.return_value = mock_client
    mock_choice.return_value = {"url": "http://endpoint1.com", "key": "key1"}

    endpoint, api_key = get_endpoint("test_model", "test_arn")

    assert endpoint == "http://endpoint1.com"
    assert api_key == "key1"


@patch("pycommon.api.credentials.boto3.session.Session")
def test_get_endpoint_model_not_found(mock_session):
    mock_client = MagicMock()
    secret_data = {"models": [{"other_model": {"endpoints": []}}]}
    mock_client.get_secret_value.return_value = {
        "SecretString": json.dumps(secret_data)
    }
    mock_session.return_value.client.return_value = mock_client

    with pytest.raises(ValueError, match="Model named 'test_model' not found"):
        get_endpoint("test_model", "test_arn")


@patch("pycommon.api.credentials.boto3.session.Session")
def test_get_endpoint_json_decode_error_lines_51_53(mock_session):
    mock_client = MagicMock()
    mock_client.get_secret_value.return_value = {"SecretString": "invalid json content"}
    mock_session.return_value.client.return_value = mock_client

    with pytest.raises(json.JSONDecodeError):
        get_endpoint("test_model", "test_arn")


@patch("pycommon.api.credentials.boto3.session.Session")
def test_get_endpoint_client_error_lines_52_53(mock_session):
    # Test ClientError exception handling in get_endpoint lines 52-53
    mock_client = MagicMock()
    mock_client.get_secret_value.side_effect = ClientError(
        {"Error": {"Code": "ResourceNotFoundException"}}, "GetSecretValue"
    )
    mock_session.return_value.client.return_value = mock_client

    with pytest.raises(ClientError):
        get_endpoint("test_model", "test_arn")
