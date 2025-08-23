from unittest.mock import MagicMock, patch

import pytest

from pycommon.dal.contracts import BackendABC, UserABC
from pycommon.dal.dal import _REGISTRY, Backend
from pycommon.dal.providers.aws import AwsAccount, AwsBackend, AwsProvider, AwsUser


def test_awsbackend_initializes_and_sets_provider():
    mock_dynamodb = MagicMock()
    mock_provider = MagicMock(spec=AwsProvider)
    with patch("boto3.resource", return_value=mock_dynamodb):
        with patch(
            "pycommon.dal.providers.aws.AwsProvider", return_value=mock_provider
        ):
            backend = AwsBackend()
            # Check that User and Account classes are set
            assert backend.User is AwsUser
            assert backend.Account is AwsAccount
            # Check that provider is set on both AR classes
            assert isinstance(backend.User.provider, AwsProvider)
            assert isinstance(backend.Account.provider, AwsProvider)


def test_register_backend_sets_registry():
    # The registry should contain Backend.AWS mapped to AwsBackend
    assert _REGISTRY[Backend.AWS] is AwsBackend


def test_backendabc_init_subclass_raises_typeerror():
    # Missing Account class
    with pytest.raises(TypeError, match="must define a concrete class 'Account'"):

        class BadBackend(BackendABC):
            User = UserABC

        BadBackend()
    with pytest.raises(TypeError, match="must define a concrete class 'Account'"):
        # Account is not a subclass of AccountABC
        class NotAccount:
            pass

        class BadBackend2(BackendABC):
            User = UserABC
            Account = NotAccount

        BadBackend2()
