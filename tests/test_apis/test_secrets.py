# =============================================================================
# Tests for api/secrets.py
# =============================================================================

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from pycommon.api.secrets import (
    delete_secret_parameter,
    get_secret_parameter,
    get_secret_value,
    store_secret_parameter,
    store_secrets_in_dict,
    update_dict_with_secrets,
)


@patch("pycommon.api.secrets.boto3.client")
def test_get_secret_value_success(mock_boto3_client):
    mock_client = MagicMock()
    mock_client.get_secret_value.return_value = {"SecretString": "secret_value"}
    mock_boto3_client.return_value = mock_client

    result = get_secret_value("test_secret")

    assert result == "secret_value"


@patch("pycommon.api.secrets.boto3.client")
def test_get_secret_value_success_binary(mock_boto3_client):
    """Test successful retrieval of binary secret."""
    mock_client = MagicMock()
    # Simulate binary secret (encoded as bytes)
    mock_client.get_secret_value.return_value = {"SecretBinary": b"binary_secret_value"}
    mock_boto3_client.return_value = mock_client

    result = get_secret_value("test_binary_secret")

    assert result == "binary_secret_value"


@patch("pycommon.api.secrets.boto3.client")
def test_get_secret_value_unexpected_format(mock_boto3_client):
    """Test handling of unexpected secret format
    (neither SecretString nor SecretBinary).
    """
    mock_client = MagicMock()
    mock_client.get_secret_value.return_value = {"SomeOtherField": "value"}
    mock_boto3_client.return_value = mock_client

    with pytest.raises(ValueError, match="Unexpected secret format for 'test_secret'"):
        get_secret_value("test_secret")


@patch("pycommon.api.secrets.boto3.client")
def test_get_secret_value_failure(mock_boto3_client):
    mock_client = MagicMock()
    mock_client.get_secret_value.side_effect = Exception("Secret not found")
    mock_boto3_client.return_value = mock_client

    with pytest.raises(ValueError, match="Failed to retrieve secret"):
        get_secret_value("test_secret")


@patch("pycommon.api.secrets.boto3.client")
def test_store_secret_parameter_success(mock_boto3_client):
    mock_client = MagicMock()
    mock_client.put_parameter.return_value = {"Version": 1}
    mock_boto3_client.return_value = mock_client

    result = store_secret_parameter("test_param", "secret_value")

    assert result == {"Version": 1}
    mock_client.put_parameter.assert_called_once_with(
        Name="/pdb/test_param",
        Value="secret_value",
        Type="SecureString",
        Overwrite=True,
    )


@patch("pycommon.api.secrets.boto3.client")
def test_store_secret_parameter_failure(mock_boto3_client):
    mock_client = MagicMock()
    mock_client.put_parameter.side_effect = ClientError(
        {"Error": {"Code": "ParameterLimitExceeded"}}, "PutParameter"
    )
    mock_boto3_client.return_value = mock_client

    result = store_secret_parameter("test_param", "secret_value")

    assert result is None


@patch("pycommon.api.secrets.boto3.client")
def test_get_secret_parameter_success(mock_boto3_client):
    mock_client = MagicMock()
    mock_client.get_parameter.return_value = {"Parameter": {"Value": "secret_value"}}
    mock_boto3_client.return_value = mock_client

    result = get_secret_parameter("test_param")

    assert result == "secret_value"


@patch("pycommon.api.secrets.boto3.client")
def test_get_secret_parameter_failure(mock_boto3_client):
    mock_client = MagicMock()
    mock_client.get_parameter.side_effect = ClientError(
        {"Error": {"Code": "ParameterNotFound"}}, "GetParameter"
    )
    mock_boto3_client.return_value = mock_client

    result = get_secret_parameter("test_param")

    assert result is None


@patch("pycommon.api.secrets.get_secret_parameter")
def test_update_dict_with_secrets_success(mock_get_secret):
    mock_get_secret.return_value = "secret_value"

    input_dict = {"s_api_key": "param_name", "regular_key": "regular_value"}
    result = update_dict_with_secrets(input_dict)

    expected = {"api_key": "secret_value", "regular_key": "regular_value"}
    assert result == expected


@patch("pycommon.api.secrets.get_secret_parameter")
def test_update_dict_with_secrets_secret_not_found(mock_get_secret):
    mock_get_secret.return_value = None

    input_dict = {"s_api_key": "param_name", "regular_key": "regular_value"}
    result = update_dict_with_secrets(input_dict)

    # If secret not found, the s_ key should remain
    expected = {"s_api_key": "param_name", "regular_key": "regular_value"}
    assert result == expected


@patch("pycommon.api.secrets.store_secret_parameter")
@patch("pycommon.api.secrets.uuid.uuid4")
def test_store_secrets_in_dict_success(mock_uuid, mock_store_secret):
    mock_uuid.return_value = "unique-id"
    mock_store_secret.return_value = {"Version": 1}

    input_dict = {"s_api_key": "secret_value", "regular_key": "regular_value"}
    result = store_secrets_in_dict(input_dict)

    expected = {"s_api_key": "unique-id", "regular_key": "regular_value"}
    assert result == expected
    mock_store_secret.assert_called_once_with("unique-id", "secret_value")


# NEW TEST: Cover branch 140->134 (when updated_parameter_name is falsy)
@patch("pycommon.api.secrets.store_secret_parameter")
@patch("pycommon.api.secrets.uuid.uuid4")
def test_store_secrets_in_dict_parameter_name_empty(mock_uuid, mock_store_secret):
    mock_uuid.return_value = ""  # Empty string (falsy)
    mock_store_secret.return_value = {"Version": 1}

    input_dict = {"s_api_key": "secret_value", "regular_key": "regular_value"}
    result = store_secrets_in_dict(input_dict)

    # Since parameter_name is empty, the original value should remain
    expected = {"s_api_key": "secret_value", "regular_key": "regular_value"}
    assert result == expected
    mock_store_secret.assert_called_once_with("", "secret_value")


@patch("pycommon.api.secrets.boto3.client")
def test_delete_secret_parameter_success(mock_boto3_client):
    """Test successful deletion of a secret parameter."""
    mock_client = MagicMock()
    mock_client.delete_parameter.return_value = None
    mock_boto3_client.return_value = mock_client

    result = delete_secret_parameter("test_param")

    assert result is True
    mock_client.delete_parameter.assert_called_once_with(Name="/pdb/test_param")


@patch("pycommon.api.secrets.boto3.client")
def test_delete_secret_parameter_success_custom_prefix(mock_boto3_client):
    """Test successful deletion with custom prefix."""
    mock_client = MagicMock()
    mock_client.delete_parameter.return_value = None
    mock_boto3_client.return_value = mock_client

    result = delete_secret_parameter("test_param", prefix="/custom")

    assert result is True
    mock_client.delete_parameter.assert_called_once_with(Name="/custom/test_param")


@patch("pycommon.api.secrets.boto3.client")
def test_delete_secret_parameter_failure(mock_boto3_client):
    """Test deletion failure when parameter doesn't exist."""
    mock_client = MagicMock()
    mock_client.delete_parameter.side_effect = ClientError(
        {"Error": {"Code": "ParameterNotFound"}}, "DeleteParameter"
    )
    mock_boto3_client.return_value = mock_client

    result = delete_secret_parameter("nonexistent_param")

    assert result is False
    mock_client.delete_parameter.assert_called_once_with(Name="/pdb/nonexistent_param")


@patch("pycommon.api.secrets.boto3.client")
def test_delete_secret_parameter_access_denied(mock_boto3_client):
    """Test deletion failure due to access denied."""
    mock_client = MagicMock()
    mock_client.delete_parameter.side_effect = ClientError(
        {"Error": {"Code": "AccessDenied"}}, "DeleteParameter"
    )
    mock_boto3_client.return_value = mock_client

    result = delete_secret_parameter("test_param")

    assert result is False
    mock_client.delete_parameter.assert_called_once_with(Name="/pdb/test_param")
