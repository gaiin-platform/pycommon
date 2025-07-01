# =============================================================================
# Tests for api/get_endpoint.py
# =============================================================================

import json
import os
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from pycommon.api.get_endpoint import EndpointType, get_endpoint


@patch.dict(os.environ, {"APP_ARN_NAME": "test_arn", "AWS_REGION": "us-east-1"})
@patch("pycommon.api.get_endpoint.boto3.session.Session")
def test_get_endpoint_success(mock_session):
    mock_client = MagicMock()
    secret_data = {"CHAT_ENDPOINT": "http://chat.example.com"}
    mock_client.get_secret_value.return_value = {
        "SecretString": json.dumps(secret_data)
    }
    mock_session.return_value.client.return_value = mock_client

    result = get_endpoint(EndpointType.CHAT_ENDPOINT)

    assert result == "http://chat.example.com"


@patch.dict(os.environ, {"APP_ARN_NAME": "test_arn", "AWS_REGION": "us-east-1"})
@patch("pycommon.api.get_endpoint.boto3.session.Session")
def test_get_endpoint_not_found(mock_session):
    mock_client = MagicMock()
    secret_data = {"OTHER_ENDPOINT": "http://other.example.com"}
    mock_client.get_secret_value.return_value = {
        "SecretString": json.dumps(secret_data)
    }
    mock_session.return_value.client.return_value = mock_client

    with pytest.raises(ValueError, match="Couldnt retrieve 'CHAT_ENDPOINT'"):
        get_endpoint(EndpointType.CHAT_ENDPOINT)


@patch.dict(os.environ, {"APP_ARN_NAME": "test_arn", "AWS_REGION": "us-east-1"})
@patch("pycommon.api.get_endpoint.boto3.session.Session")
def test_get_endpoint_client_error(mock_session):
    mock_client = MagicMock()
    mock_client.get_secret_value.side_effect = ClientError(
        {"Error": {"Code": "ResourceNotFoundException"}}, "GetSecretValue"
    )
    mock_session.return_value.client.return_value = mock_client

    with pytest.raises(ValueError, match="Couldnt retrieve 'CHAT_ENDPOINT'"):
        get_endpoint(EndpointType.CHAT_ENDPOINT)
