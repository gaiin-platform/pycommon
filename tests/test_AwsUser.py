import json
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
    mock_table.get_item.return_value = {}
    mock_table.put_item.return_value = {}
    monkeypatch.setattr(AwsUser, "_user_table", classmethod(lambda cls: mock_table))
    monkeypatch.setattr("pycommon.dal.providers.aws.helpers.nowstr", lambda: "now")
    user.save()
    assert mock_table.put_item.called


def test_save_condition_expression(monkeypatch):
    user = make_user()
    mock_table = MagicMock()
    mock_table.get_item.return_value = {}
    mock_table.put_item.return_value = {}
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
        class DummyProvider:
            def get_table(self, table_name):
                return f"table:{table_name}"

        monkeypatch.setattr(AwsUser, "provider", DummyProvider())
        result = AwsUser._user_table()
        assert result == f"table:{AwsUser.user_table_name}"


def test_list_exception(monkeypatch):
    mock_table = MagicMock()
    mock_table.scan.side_effect = Exception("scan error")
    monkeypatch.setattr(AwsUser, "_user_table", classmethod(lambda cls: mock_table))
    with pytest.raises(Exception, match="scan error"):
        AwsUser.list()


def test_user_table_uses_classvar(monkeypatch):
    called = {}

    class DummyProvider:
        def get_table(self, table_name):
            called["table_name"] = table_name
            return "dummy_table"

    monkeypatch.setattr(AwsUser, "provider", DummyProvider())
    table = AwsUser._user_table()
    assert table == "dummy_table"
    assert called["table_name"] == AwsUser.user_table_name


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
    mock_table.get_item.return_value = {}
    mock_table.put_item.return_value = {}
    monkeypatch.setattr(AwsUser, "_user_table", classmethod(lambda cls: mock_table))
    with patch(
        "pycommon.dal.providers.aws.AwsUser.nowstr", return_value="2024-06-01T12:00:00Z"
    ):
        user.save()
        args, kwargs = mock_table.put_item.call_args
        assert kwargs["Item"]["updated_at"] == "2024-06-01T12:00:00Z"


def test_save_existing_sets_updated_at(monkeypatch):
    user = make_user()
    mock_table = MagicMock()
    mock_table.get_item.return_value = {
        "Item": {"user_id": "u1", "email": "test@example.com"}
    }
    mock_table.update_item.return_value = {
        "ExpressionAttributeValues": {"updated_at": "2024-06-01T12:00:00Z"}
    }
    monkeypatch.setattr(AwsUser, "_user_table", classmethod(lambda cls: mock_table))
    with patch(
        "pycommon.dal.providers.aws.AwsUser.nowstr", return_value="2024-06-01T12:00:00Z"
    ):
        user.save()
        args, kwargs = mock_table.update_item.call_args
        assert (
            kwargs["ExpressionAttributeValues"][":updated_at"] == "2024-06-01T12:00:00Z"
        )


def test_save_existing_empty_data(monkeypatch):
    user = make_user()
    mock_table = MagicMock()
    mock_table.get_item.return_value = {
        "Item": {"user_id": "u1", "email": "test@example.com"}
    }
    mock_table.update_item.return_value = {
        "ExpressionAttributeValues": {"updated_at": "2024-06-01T12:00:00Z"}
    }
    user._create_non_null_dynamodb_dict = MagicMock(return_value={})
    monkeypatch.setattr(AwsUser, "_user_table", classmethod(lambda cls: mock_table))
    with patch(
        "pycommon.dal.providers.aws.AwsUser.nowstr", return_value="2024-06-01T12:00:00Z"
    ):
        user.save()
        assert not mock_table.update_item.called
        assert not mock_table.put_item.called


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


def test_get_version_default():
    user = make_user()
    assert user.version == 1  # Assuming default version is 1


def test_set_version(monkeypatch):
    user = make_user()
    user.version = 2
    assert user.version == 2


def test_set_version_invalid(monkeypatch):
    user = make_user()
    with pytest.raises(TypeError, match="version must be int"):
        user.version = "invalid"
