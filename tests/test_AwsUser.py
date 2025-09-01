import json
import os
from unittest.mock import MagicMock, patch

import pytest

from pycommon.dal.errors import NotFound
from pycommon.dal.providers.aws.AwsUser import AwsUser


def make_user(**kwargs):
    return AwsUser(
        user_id="u1",
        email="test@example.com",
        family_name="Smith",
        given_name="John",
        **kwargs,
    )


def test_family_name_getter_and_setter():
    user = make_user()
    assert user.family_name == "Smith"
    user.family_name = "Doe"
    assert user.family_name == "Doe"
    with pytest.raises(TypeError):
        user.family_name = 123


def test_given_name_getter_and_setter():
    user = make_user()
    assert user.given_name == "John"
    user.given_name = "Jane"
    assert user.given_name == "Jane"
    with pytest.raises(TypeError):
        user.given_name = 123


def test_cust_vu_groups_getter_and_setter():
    user = make_user()
    assert user.cust_vu_groups is None
    user.cust_vu_groups = ["group1", "group2"]
    assert json.loads(user.cust_vu_groups) == ["group1", "group2"]
    user.cust_vu_groups = None
    assert user.cust_vu_groups is None
    with pytest.raises(TypeError):
        user.cust_vu_groups = [1, 2]


def test_cust_saml_groups_getter_and_setter():
    user = make_user()
    assert user.cust_saml_groups is None
    user.cust_saml_groups = ["saml1", "saml2"]
    assert json.loads(user.cust_saml_groups) == ["saml1", "saml2"]
    user.cust_saml_groups = None
    assert user.cust_saml_groups is None
    with pytest.raises(TypeError):
        user.cust_saml_groups = [1, 2]


def test_updated_at_getter():
    user = make_user(updated_at="2024-01-01T00:00:00Z")
    assert user.updated_at == "2024-01-01T00:00:00Z"


def test_repr_returns_json():
    user = make_user()
    result = user.__repr__()
    assert isinstance(result, str)
    assert json.loads(result)["user_id"] == "u1"


def test_get_values_as_dict():
    user = make_user()
    d = user._get_values_as_dict()
    assert d["user_id"] == "u1"
    assert d["email"] == "test@example.com"


def test_create_non_null_dynamodb_dict():
    user = make_user()
    d = user._create_non_null_dynamodb_dict()
    assert "user_id" in d
    assert "email" in d
    user = AwsUser(user_id="u2")
    d = user._create_non_null_dynamodb_dict()
    assert "email" not in d


def test_save_calls_put_item(monkeypatch):
    user = make_user()
    mock_table = MagicMock()
    monkeypatch.setattr(AwsUser, "_user_table", classmethod(lambda cls: mock_table))
    monkeypatch.setattr("pycommon.dal.providers.aws.helpers.nowstr", lambda: "now")
    user.save()
    assert mock_table.put_item.called


def test_save_condition_expression(monkeypatch):
    user = make_user()
    mock_table = MagicMock()
    monkeypatch.setattr(AwsUser, "_user_table", classmethod(lambda cls: mock_table))
    monkeypatch.setattr("pycommon.dal.providers.aws.helpers.nowstr", lambda: "now")
    user.save(allow_overwrite=False)
    args, kwargs = mock_table.put_item.call_args
    assert "ConditionExpression" in kwargs


def test_delete_calls_delete_item(monkeypatch):
    user = make_user()
    mock_table = MagicMock()
    monkeypatch.setattr(AwsUser, "_user_table", classmethod(lambda cls: mock_table))
    user.delete()
    assert mock_table.delete_item.called


def test_delete_exception(monkeypatch):
    user = make_user()
    mock_table = MagicMock()
    monkeypatch.setattr(AwsUser, "_user_table", classmethod(lambda cls: mock_table))
    mock_table.delete_item.side_effect = Exception("DynamoDB error")
    with pytest.raises(Exception, match="DynamoDB error"):
        user.delete()


def test_cascading_account_deletion(monkeypatch):
    user = make_user()
    mock_table = MagicMock()
    mock_account1 = MagicMock()
    mock_account2 = MagicMock()

    # Mock accounts associated with the user
    monkeypatch.setattr(
        "pycommon.dal.providers.aws.AwsAccount.get_all_for_user",
        lambda user_id: [mock_account1, mock_account2],
    )
    # Mock delete method for AwsAccount
    mock_account1.delete = MagicMock()
    mock_account2.delete = MagicMock()

    monkeypatch.setattr(AwsUser, "_user_table", classmethod(lambda cls: mock_table))
    user.delete()
    assert mock_table.delete_item.called
    mock_account1.delete.assert_called_once()
    mock_account2.delete.assert_called_once()


def test_accounts_returns_cached(monkeypatch):
    user = make_user()
    user._accounts = ["acct1"]
    assert user.accounts() == ["acct1"]


def test_accounts_calls_get_all_for_user(monkeypatch):
    user = make_user()
    monkeypatch.setattr(
        "pycommon.dal.providers.aws.AwsAccount.get_all_for_user",
        lambda user_id: ["acct2"],
    )
    assert user.accounts(use_cache=False) == ["acct2"]


def test_accounts_calls_use_cache(monkeypatch):
    user = make_user()
    monkeypatch.setattr(
        "pycommon.dal.providers.aws.AwsAccount.get_all_for_user",
        lambda user_id: ["acct2"],
    )
    assert user.accounts(use_cache=True) == ["acct2"]


def test_get_by_user_id_success(monkeypatch):
    mock_table = MagicMock()
    mock_table.get_item.return_value = {
        "Item": {
            "user_id": "u1",
            "email": "test@example.com",
            "family_name": "Smith",
            "given_name": "John",
            "updated_at": "2024-01-01T00:00:00Z",
            "custom:saml_groups": None,
            "custom:vu_groups": None,
        }
    }
    monkeypatch.setattr(AwsUser, "_user_table", classmethod(lambda cls: mock_table))
    user = AwsUser.get_by_user_id("u1")
    assert user.user_id == "u1"
    assert user.email == "test@example.com"


def test_email_setter_type_error():
    user = make_user()
    with pytest.raises(TypeError):
        user.email = 123
    with pytest.raises(TypeError):
        user.email = None


def test_email_setter_correct():
    user = make_user()
    user.email = "new_email@example.com"
    assert user.email == "new_email@example.com"


def test_family_name_setter_type_error():
    user = make_user()
    with pytest.raises(TypeError):
        user.family_name = None
    with pytest.raises(TypeError):
        user.family_name = 123.45


def test_given_name_setter_type_error():
    user = make_user()
    with pytest.raises(TypeError):
        user.given_name = None
    with pytest.raises(TypeError):
        user.given_name = ["not", "a", "string"]


def test_cust_vu_groups_setter_type_error():
    user = make_user()
    with pytest.raises(TypeError):
        user.cust_vu_groups = "not a list"
    with pytest.raises(TypeError):
        user.cust_vu_groups = [1, "valid", {}]
    with pytest.raises(TypeError):
        user.cust_vu_groups = [None, "valid"]


def test_cust_saml_groups_setter_type_error():
    user = make_user()
    with pytest.raises(TypeError):
        user.cust_saml_groups = "not a list"
    with pytest.raises(TypeError):
        user.cust_saml_groups = [1, "valid", {}]
    with pytest.raises(TypeError):
        user.cust_saml_groups = [None, "valid"]


def test_get_by_user_id_not_found(monkeypatch):
    mock_table = MagicMock()
    mock_table.get_item.return_value = {"Item": None}
    monkeypatch.setattr(AwsUser, "_user_table", classmethod(lambda cls: mock_table))
    with pytest.raises(NotFound):
        AwsUser.get_by_user_id("u1")


def test_list_returns_users_and_cursor(monkeypatch):
    mock_table = MagicMock()
    mock_table.scan.return_value = {
        "Items": [
            {
                "user_id": "u1",
                "email": "test@example.com",
                "family_name": "Smith",
                "given_name": "John",
            },
            {
                "user_id": "u2",
                "email": "other@example.com",
                "family_name": "Doe",
                "given_name": "Jane",
            },
        ],
        "LastEvaluatedKey": {"user_id": "u2"},
    }
    monkeypatch.setattr(AwsUser, "_user_table", classmethod(lambda cls: mock_table))
    users, cursor = AwsUser.list(limit=2)
    assert len(users) == 2
    assert cursor == "u2"
    assert users[0].user_id == "u1"
    assert users[1].user_id == "u2"


def test_list_with_cursor(monkeypatch):
    mock_table = MagicMock()
    mock_table.scan.return_value = {
        "Items": [
            {
                "user_id": "u1",
                "email": "test@example.com",
                "family_name": "Smith",
                "given_name": "John",
            },
        ],
        "LastEvaluatedKey": {"user_id": "u1"},
    }
    monkeypatch.setattr(AwsUser, "_user_table", classmethod(lambda cls: mock_table))
    users, cursor = AwsUser.list(limit=1, cursor="u1")
    assert len(users) == 1
    assert cursor == "u1"
    assert users[0].user_id == "u1"


def test_list_empty(monkeypatch):
    mock_table = MagicMock()
    mock_table.scan.return_value = {"Items": [], "LastEvaluatedKey": None}
    monkeypatch.setattr(AwsUser, "_user_table", classmethod(lambda cls: mock_table))
    users, cursor = AwsUser.list(limit=2)
    assert users == []
    assert cursor is None


def test_user_table_returns_provider_table(monkeypatch):
    os.environ["COGNITO_USERS_DYNAMODB_TABLE"] = "dummy_table"
    dummy_provider = MagicMock()
    dummy_provider.get_table.return_value = "dummy_table"
    monkeypatch.setattr(AwsUser, "provider", dummy_provider)
    result = AwsUser._user_table()
    assert result == AwsUser.user_table_name


def test_list_exception(monkeypatch):
    mock_table = MagicMock()
    mock_table.scan.side_effect = Exception("scan error")
    monkeypatch.setattr(AwsUser, "_user_table", classmethod(lambda cls: mock_table))
    with pytest.raises(Exception, match="scan error"):
        AwsUser.list()


def test_user_table_uses_classvar(monkeypatch):
    dummy_provider = MagicMock()
    dummy_provider.get_table.return_value = "dummy_table"
    monkeypatch.setattr(AwsUser, "provider", dummy_provider)
    table = AwsUser._user_table()
    assert table == "dummy_table"
    assert dummy_provider.get_table.called


def test_create_non_null_dynamodb_dict_excludes_none_fields():
    user = AwsUser(
        user_id="u1",
        email=None,
        family_name="Smith",
        given_name=None,
        cust_saml_groups=None,
        cust_vu_groups=None,
        updated_at=None,
    )
    d = user._create_non_null_dynamodb_dict()
    assert "email" not in d
    assert "given_name" not in d
    assert "cust_saml_groups" not in d or d["cust_saml_groups"] is None
    assert "cust_vu_groups" not in d or d["cust_vu_groups"] is None
    assert "updated_at" not in d or d["updated_at"] is None
    assert d["family_name"] == "Smith"
    assert d["user_id"] == "u1"


def test_save_sets_updated_at(monkeypatch):
    user = make_user()
    mock_table = MagicMock()
    monkeypatch.setattr(AwsUser, "_user_table", classmethod(lambda cls: mock_table))
    with patch(
        "pycommon.dal.providers.aws.AwsUser.nowstr", return_value="2024-06-01T12:00:00Z"
    ):
        user.save()
        args, kwargs = mock_table.put_item.call_args
        assert kwargs["Item"]["updated_at"] == "2024-06-01T12:00:00Z"


def test_save_raises_mapped_exception(monkeypatch):
    user = make_user()

    class DummyTable:
        def put_item(self, **kwargs):
            raise Exception("dynamodb error")

    monkeypatch.setattr(AwsUser, "_user_table", classmethod(lambda cls: DummyTable()))
    with patch(
        "pycommon.dal.providers.aws.AwsUser.map_aws_error",
        lambda e: RuntimeError("mapped error"),
    ):
        with pytest.raises(RuntimeError, match="mapped error"):
            user.save()


def test_get_user_settings(monkeypatch):
    monkeypatch.setenv("DYNAMODB_TABLE", "dummy_table")
    dummy_provider = MagicMock()
    dummy_table = MagicMock()
    dummy_provider.get_table.return_value = dummy_table
    dummy_table.query.return_value = {
        "Items": [
            {
                "id": "u1",
            }
        ]
    }
    monkeypatch.setattr(AwsUser, "provider", dummy_provider)
    user = AwsUser(user_id="u1")
    settings = user.settings
    assert settings._id == "u1"


def test_no_user_settings(monkeypatch):
    # Set up environment variable for settings table
    monkeypatch.setenv("DYNAMODB_TABLE", "settings-table")

    # Create two mock tables
    mock_user_table = MagicMock()
    mock_user_table.get_item.return_value = {"Item": {"user_id": "u1"}}
    mock_settings_table = MagicMock()
    mock_settings_table.query.return_value = {"Items": []}

    # Create a provider that returns the correct table based on name
    def get_table(name):
        if name == "settings-table":
            return mock_settings_table
        else:
            return mock_user_table

    mock_provider = MagicMock()
    mock_provider.get_table.side_effect = get_table

    # Patch AwsUser.provider
    monkeypatch.setattr(AwsUser, "provider", mock_provider)

    # Test user table call
    user = AwsUser.get_by_user_id(user_id="u1")
    assert user.user_id == "u1"
    assert mock_user_table.get_item.called

    # # Test settings table call via user.settings
    with pytest.raises(NotFound):
        user.settings

    assert mock_settings_table.query.called


def test_update_settings_username(monkeypatch):
    monkeypatch.setenv("DYNAMODB_TABLE", "settings-table")
    mock_user_table = MagicMock()
    mock_user_table.get_item.return_value = {"Item": {"user_id": "u1"}}
    mock_settings_table = MagicMock()
    mock_settings_table.query.return_value = {"Items": [{"id": "u1"}]}
    mock_settings_table.get_item.return_value = {"Item": []}

    # Create a provider that returns the correct table based on name
    def get_table(name):
        if name == "settings-table":
            return mock_settings_table
        else:
            return mock_user_table

    mock_provider = MagicMock()
    mock_provider.get_table.side_effect = get_table

    monkeypatch.setattr(AwsUser, "provider", mock_provider)

    user = AwsUser.get_by_user_id(user_id="u1")
    settings = user.settings
    settings.update_username("new_username")
    assert settings._id == "u1"


def test_update_settings_username_already_taken(monkeypatch):
    monkeypatch.setenv("DYNAMODB_TABLE", "settings-table")
    mock_user_table = MagicMock()
    mock_user_table.get_item.return_value = {"Item": {"user_id": "u1"}}
    mock_settings_table = MagicMock()
    mock_settings_table.query.return_value = {"Items": [{"id": "u1"}]}
    mock_settings_table.get_item.return_value = {"Item": [{"id": "new_username"}]}

    # Create a provider that returns the correct table based on name
    def get_table(name):
        if name == "settings-table":
            return mock_settings_table
        else:
            return mock_user_table

    mock_provider = MagicMock()
    mock_provider.get_table.side_effect = get_table

    monkeypatch.setattr(AwsUser, "provider", mock_provider)

    user = AwsUser.get_by_user_id(user_id="u1")
    settings = user.settings
    with pytest.raises(ValueError, match="Username 'new_username' is already taken."):
        settings.update_username("new_username")
    assert settings._id == "u1"

    # snag the settings again to make sure the object has a cache
    settings = user.settings
    assert settings._id == "u1"
