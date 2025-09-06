from unittest.mock import MagicMock

import pytest

from pycommon.dal.providers.aws import AwsAdminConfig


def test_get_config_returns_value(monkeypatch):
    dummy_provider = MagicMock()
    dummy_table = MagicMock()
    dummy_provider.get_table.return_value = dummy_table
    dummy_table.get_item.return_value = {"Item": {"data": {"bar": 1}}}
    monkeypatch.setattr(AwsAdminConfig, "provider", dummy_provider)
    result = AwsAdminConfig.get_config("foo")
    assert result == {"bar": 1}
    dummy_table.get_item.assert_called_once()


def test_get_config_returns_none(monkeypatch):
    dummy_provider = MagicMock()
    dummy_table = MagicMock()
    dummy_provider.get_table.return_value = dummy_table
    dummy_table.get_item.return_value = {"Item": None}
    monkeypatch.setattr(AwsAdminConfig, "provider", dummy_provider)
    result = AwsAdminConfig.get_config("foo")
    assert result is None


def test_get_config_data_returns_none(monkeypatch):
    dummy_provider = MagicMock()
    dummy_table = MagicMock()
    dummy_provider.get_table.return_value = dummy_table
    dummy_table.get_item.return_value = {"Item": {"data": {}}}
    monkeypatch.setattr(AwsAdminConfig, "provider", dummy_provider)
    result = AwsAdminConfig.get_config("foo")
    assert result is None


def test_get_config_raises_exception(monkeypatch):
    dummy_provider = MagicMock()
    dummy_table = MagicMock()
    dummy_provider.get_table.return_value = dummy_table
    dummy_table.get_item.return_value = {"Item": {"data": {}}}
    monkeypatch.setattr(AwsAdminConfig, "provider", dummy_provider)
    dummy_table.get_item.side_effect = Exception("Dynamo error")
    with pytest.raises(Exception, match="Dynamo error"):
        AwsAdminConfig.get_config("foo")


def test_list_fail_with_key_error(monkeypatch):
    dummy_provider = MagicMock()
    dummy_table = MagicMock()
    dummy_provider.get_table.return_value = dummy_table
    monkeypatch.setattr(AwsAdminConfig, "provider", dummy_provider)
    dummy_table.scan.return_value = {
        "Items": [{"key": "foo"}, {"key": "bar"}],
        "LastEvaluatedKey": None,
    }
    with pytest.raises(KeyError):
        AwsAdminConfig.list()


def test_list_success(monkeypatch):
    dummy_provider = MagicMock()
    dummy_table = MagicMock()
    dummy_provider.get_table.return_value = dummy_table
    monkeypatch.setattr(AwsAdminConfig, "provider", dummy_provider)
    dummy_table.scan.return_value = {
        "Items": [{"config_id": "foo"}, {"config_id": "bar"}],
        "LastEvaluatedKey": None,
    }
    keys, cursor = AwsAdminConfig.list()
    assert keys == ["foo", "bar"]
    assert cursor is None


def test_list_with_cursor(monkeypatch):
    dummy_provider = MagicMock()
    dummy_table = MagicMock()
    dummy_provider.get_table.return_value = dummy_table
    monkeypatch.setattr(AwsAdminConfig, "provider", dummy_provider)
    dummy_table.scan.return_value = {
        "Items": [{"config_id": "foo"}, {"config_id": "bar"}],
        "LastEvaluatedKey": {"config_id": "bar"},
    }
    keys, cursor = AwsAdminConfig.list(cursor="foo")
    assert keys == ["foo", "bar"]
    assert cursor == {"config_id": "bar"}
