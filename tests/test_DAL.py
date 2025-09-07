from enum import Enum

import pytest

from pycommon.dal.contracts import AccountABC, AdminConfigABC, BackendABC, UserABC
from pycommon.dal.dal import _REGISTRY, DAL, Backend, DalError, register_backend


class DummyUser(UserABC):
    pass


class DummyAccount(AccountABC):
    pass


class DummyAdminConfig(AdminConfigABC):
    pass


class DummyBackend(BackendABC):
    User = DummyUser
    Account = DummyAccount
    AdminConfig = DummyAdminConfig

    def __init__(self, **config):
        self.User = DummyUser
        self.Account = DummyAccount
        self.AdminConfig = DummyAdminConfig


def test_register_backend_and_dal_instantiation():
    # Register DummyBackend for MEMORY
    register_backend(Backend.MEMORY, DummyBackend)
    assert _REGISTRY[Backend.MEMORY] is DummyBackend

    # DAL should instantiate DummyBackend and expose User/Account
    dal = DAL(Backend.MEMORY)
    assert isinstance(dal._backend, DummyBackend)
    assert dal.User is DummyUser
    assert dal.Account is DummyAccount


def test_dal_raises_on_unregistered_backend():
    # Use a backend that is not registered
    class FakeBackend(Enum):
        FAKE = 999

    with pytest.raises(DalError, match="No backend registered for"):
        DAL(FakeBackend.FAKE)


def test_dal_passes_config_to_backend():
    class ConfigBackend(BackendABC):
        User = DummyUser
        Account = DummyAccount
        AdminConfig = DummyAdminConfig

        def __init__(self, **config):
            self.config = config
            self.User = DummyUser
            self.Account = DummyAccount
            self.AdminConfig = DummyAdminConfig

    register_backend(Backend.AWS, ConfigBackend)
    dal = DAL(Backend.AWS, foo="bar")
    assert isinstance(dal._backend, ConfigBackend)
    assert dal._backend.config["foo"] == "bar"
