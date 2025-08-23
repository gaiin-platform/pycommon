from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from pycommon.dal.providers.aws.AwsAccount import AwsAccount, RateLimitDict


class DummyProvider:
    def __init__(self):
        self.tables = {}
        self.called = []

    def get_table(self, name):
        self.called.append(name)
        return self.tables.setdefault(name, MagicMock())


def setup_provider(monkeypatch):
    provider = DummyProvider()
    monkeypatch.setattr(AwsAccount, "provider", provider)
    return provider


def make_account(**kwargs):
    return AwsAccount(
        id=kwargs.get("id", "u1:acct1"),
        name=kwargs.get("name", "acct1"),
        owner_user_id=kwargs.get("owner_user_id", "u1"),
        is_default=kwargs.get("is_default", False),
        rate_limit_period=kwargs.get("rate_limit_period", "Unlimited"),
        rate_limit_rate=kwargs.get("rate_limit_rate", None),
    )


def test_init_valid():
    acct = make_account()
    assert acct._account["id"] == "u1:acct1"
    assert acct._account["name"] == "acct1"
    assert acct._account["rateLimit"]["period"] == "Unlimited"


def test_init_missing_name_or_owner_raises():
    with pytest.raises(ValueError):
        AwsAccount(id="id", name="", owner_user_id="u1")
    with pytest.raises(ValueError):
        AwsAccount(id="id", name="acct", owner_user_id="")


def test_repr():
    acct = make_account()
    result = acct.__repr__()
    assert '"id": "u1:acct1"' in result
    assert '"name": "acct1"' in result


def test_user_table(monkeypatch):
    provider = setup_provider(monkeypatch)
    table = AwsAccount._user_table()
    assert provider.called == [AwsAccount.user_table_name]
    assert table is provider.tables[AwsAccount.user_table_name]


def test_save_adds_account(monkeypatch):
    provider = setup_provider(monkeypatch)
    table = provider.get_table(AwsAccount.user_table_name)
    # Simulate no accounts yet
    table.get_item.return_value = {"Item": {"user": "u1", "accounts": []}}
    acct = make_account()
    acct.save()
    table.put_item.assert_called_once()
    args, kwargs = table.put_item.call_args
    assert kwargs["Item"]["user"] == "u1"
    assert kwargs["Item"]["accounts"][0]["id"] == "u1:acct1"


def test_save_updates_account(monkeypatch):
    provider = setup_provider(monkeypatch)
    table = provider.get_table(AwsAccount.user_table_name)
    # Simulate existing account with same id
    table.get_item.return_value = {
        "Item": {
            "user": "u1",
            "accounts": [
                {
                    "id": "u1:acct1",
                    "isDefault": False,
                    "name": "acct1",
                    "rateLimit": RateLimitDict(period="Unlimited", rate=None),
                }
            ],
        }
    }
    acct = make_account()
    acct.save()
    table.put_item.assert_called_once()
    accounts = table.put_item.call_args[1]["Item"]["accounts"]
    assert len(accounts) == 1
    assert accounts[0]["id"] == "u1:acct1"


def test_save_creates_new_item(monkeypatch):
    provider = setup_provider(monkeypatch)
    table = provider.get_table(AwsAccount.user_table_name)
    # Simulate no Item returned
    table.get_item.return_value = {}
    acct = make_account()
    acct.save()
    table.put_item.assert_called_once()
    assert table.put_item.call_args[1]["Item"]["user"] == "u1"


def test_delete_removes_account(monkeypatch):
    provider = setup_provider(monkeypatch)
    table = provider.get_table(AwsAccount.user_table_name)
    # Simulate existing accounts
    table.get_item.return_value = {
        "Item": {
            "user": "u1",
            "accounts": [
                {
                    "id": "u1:acct1",
                    "isDefault": True,
                    "name": "acct1",
                    "rateLimit": {"period": "minute", "rate": 10},
                },
                {
                    "id": "u1:acct2",
                    "isDefault": False,
                    "name": "acct2",
                    "rateLimit": {"period": "hour", "rate": 100},
                },
            ],
        }
    }
    acct = make_account(id="u1:acct1")
    acct.delete()
    table.put_item.assert_called_once()
    accounts = table.put_item.call_args[1]["Item"]["accounts"]
    # Only acct2 should remain
    assert len(accounts) == 1
    assert accounts[0]["id"] == "u1:acct2"


def test_delete_no_item(monkeypatch):
    provider = setup_provider(monkeypatch)
    table = provider.get_table(AwsAccount.user_table_name)
    # Simulate no existing accounts
    table.get_item.return_value = {}
    acct = make_account(id="u1:acct1")
    acct.delete()
    table.put_item.assert_not_called()


def test_get_all_for_user_calls_get_account_by_id_for_user(monkeypatch):
    monkeypatch.setattr(
        AwsAccount,
        "get_account_by_id_for_user",
        classmethod(lambda cls, user, account_id: ["acct"]),
    )
    result = AwsAccount.get_all_for_user("u1")
    assert result == ["acct"]


def test_get_account_by_id_for_user_no_item(monkeypatch):
    provider = setup_provider(monkeypatch)
    table = provider.get_table(AwsAccount.user_table_name)
    table.get_item.return_value = {"Item": None}
    result = AwsAccount.get_account_by_id_for_user("u1", None)
    assert result == []


def test_get_account_by_id_for_user_no_accounts(monkeypatch):
    provider = setup_provider(monkeypatch)
    table = provider.get_table(AwsAccount.user_table_name)
    table.get_item.return_value = {"Item": {"user": "u1", "accounts": []}}
    result = AwsAccount.get_account_by_id_for_user("u1", None)
    assert result == []


def test_get_account_by_id_for_user_found(monkeypatch):
    provider = setup_provider(monkeypatch)
    table = provider.get_table(AwsAccount.user_table_name)
    table.get_item.return_value = {
        "Item": {
            "user": "u1",
            "accounts": [
                {
                    "id": "u1:acct1",
                    "isDefault": True,
                    "name": "acct1",
                    "rateLimit": {"period": "minute", "rate": 10},
                },
                {
                    "id": "u1:acct2",
                    "isDefault": False,
                    "name": "acct2",
                    "rateLimit": {"period": "hour", "rate": 100},
                },
            ],
        }
    }
    result = AwsAccount.get_account_by_id_for_user("u1", "u1:acct2")
    assert len(result) == 1
    acct = result[0]
    assert isinstance(acct, AwsAccount)
    assert acct._account["id"] == "u1:acct2"
    assert acct._account["rateLimit"]["period"] == "hour"


def test_get_account_by_id_for_user_all(monkeypatch):
    provider = setup_provider(monkeypatch)
    table = provider.get_table(AwsAccount.user_table_name)
    table.get_item.return_value = {
        "Item": {
            "user": "u1",
            "accounts": [
                {
                    "id": "u1:acct1",
                    "isDefault": True,
                    "name": "acct1",
                    "rateLimit": {"period": "minute", "rate": 10},
                },
                {
                    "id": "u1:acct2",
                    "isDefault": False,
                    "name": "acct2",
                    "rateLimit": {"period": "hour", "rate": 100},
                },
            ],
        }
    }
    result = AwsAccount.get_account_by_id_for_user("u1", None)
    assert len(result) == 2
    assert all(isinstance(a, AwsAccount) for a in result)


def test_get_account_has_decimal_rate(monkeypatch):
    provider = setup_provider(monkeypatch)
    table = provider.get_table(AwsAccount.user_table_name)
    table.get_item.return_value = {
        "Item": {
            "user": "u1",
            "accounts": [
                {
                    "id": "u1:acct1",
                    "isDefault": True,
                    "name": "acct1",
                    "rateLimit": {"period": "minute", "rate": 105.5},
                },
                {
                    "id": "u1:acct2",
                    "isDefault": False,
                    "name": "acct2",
                    "rateLimit": {"period": "hour", "rate": Decimal("175")},
                },
                {
                    "id": "u1:acct3",
                    "isDefault": False,
                    "name": "acct3",
                    "rateLimit": {"period": "day", "rate": "BAD"},
                },
                {
                    "id": "u1:acct4",
                    "isDefault": False,
                    "name": "acct4",
                    "rateLimit": {"period": "week", "rate": None},
                },
            ],
        }
    }
    result = AwsAccount.get_account_by_id_for_user("u1", None)
    assert len(result) == 4
    assert all(isinstance(a, AwsAccount) for a in result)
    assert isinstance(result[0]._account["rateLimit"]["rate"], int)
    assert result[0]._account["rateLimit"]["rate"] == 105
    assert isinstance(result[1]._account["rateLimit"]["rate"], int)
    assert result[1]._account["rateLimit"]["rate"] == 175
    assert result[2]._account["rateLimit"]["rate"] is None
