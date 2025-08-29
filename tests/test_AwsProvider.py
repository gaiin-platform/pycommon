from pycommon.dal.providers.aws.AwsProvider import AwsProvider


class DummyDynamoDB:
    def __init__(self):
        self.called = []

    def Table(self, name):
        self.called.append(name)
        return f"Table:{name}"


def test_awsprovider_instantiation():
    dummy_db = DummyDynamoDB()
    provider = AwsProvider(dynamodb=dummy_db)
    assert provider.dynamodb is dummy_db
    assert isinstance(provider.tables, dict)
    assert provider.tables == {}


def test_get_table_creates_and_caches():
    dummy_db = DummyDynamoDB()
    provider = AwsProvider(dynamodb=dummy_db)
    table1 = provider.get_table("users")
    assert table1 == "Table:users"
    assert provider.tables["users"] == "Table:users"
    # Should not call Table again for the same name
    table2 = provider.get_table("users")
    assert table2 == "Table:users"
    assert dummy_db.called == ["users"]


def test_get_table_multiple_tables():
    dummy_db = DummyDynamoDB()
    provider = AwsProvider(dynamodb=dummy_db)
    t1 = provider.get_table("users")
    t2 = provider.get_table("accounts")
    assert t1 == "Table:users"
    assert t2 == "Table:accounts"
    assert set(provider.tables.keys()) == {"users", "accounts"}
    assert dummy_db.called == ["users", "accounts"]
