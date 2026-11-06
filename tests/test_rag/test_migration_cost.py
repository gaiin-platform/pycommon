from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from pycommon.rag import migration_cost as mc

H = "a" * 64


@pytest.mark.parametrize(
    "key,expected",
    [
        (f"global2/{H}.content.json", f"doc#global/{H}.content.json"),
        (f"s3://global/{H}.content.json", f"doc#global/{H}.content.json"),
        ("user/2026/file.json", None),
        ("", None),
        (None, None),
    ],
)
def test_migration_doc_id(key, expected):
    assert mc.migration_doc_id(key) == expected


def test_add_doc_cost_adds_to_the_documents_row():
    table = MagicMock()
    assert (
        mc.add_doc_cost(
            f"global2/{H}.content.json",
            "embeddingCost",
            0.0000123456789123,
            table=table,
        )
        is True
    )
    kwargs = table.update_item.call_args.kwargs
    assert kwargs["Key"] == {"id": f"doc#global/{H}.content.json"}
    assert kwargs["UpdateExpression"] == "ADD embeddingCost :cost"
    assert kwargs["ConditionExpression"] == "attribute_exists(id)"
    assert kwargs["ExpressionAttributeValues"] == {":cost": Decimal("0.000012346")}


@pytest.mark.parametrize(
    "field,key,amount",
    [
        ("bogus", f"global2/{H}.content.json", 1.0),
        ("ocrCost", "user/file.json", 1.0),
        ("ocrCost", f"global2/{H}.content.json", 0),
        ("ocrCost", f"global2/{H}.content.json", -1.0),
    ],
)
def test_add_doc_cost_ignores_what_it_cannot_record(field, key, amount):
    table = MagicMock()
    assert mc.add_doc_cost(key, field, amount, table=table) is False
    table.update_item.assert_not_called()


def test_a_document_not_in_the_migration_is_not_an_error(caplog):
    table = MagicMock()
    table.update_item.side_effect = Exception("ConditionalCheckFailedException")
    assert (
        mc.add_doc_cost(f"global2/{H}.content.json", "qaCost", 1.0, table=table)
        is False
    )
    assert not caplog.records


def test_other_failures_are_logged_and_never_raised(caplog):
    table = MagicMock()
    table.update_item.side_effect = Exception("throttled")
    assert (
        mc.add_doc_cost(f"global2/{H}.content.json", "qaCost", 1.0, table=table)
        is False
    )
    assert "Could not add qaCost" in caplog.text


def test_migration_table_reads_the_environment(monkeypatch):
    monkeypatch.setattr(mc, "_table", None)
    monkeypatch.delenv("RAG_MIGRATION_TABLE", raising=False)
    assert mc.migration_table() is None
    monkeypatch.setenv("RAG_MIGRATION_TABLE", "unset")
    assert mc.migration_table() is None
    monkeypatch.setenv("RAG_MIGRATION_TABLE", "t1")
    with patch.object(mc.boto3, "resource") as resource:
        resource.return_value.Table.return_value = MagicMock(name="x")
        resource.return_value.Table.return_value.name = "t1"
        first = mc.migration_table()
        assert mc.migration_table() is first  # cached while the name is unchanged
        resource.return_value.Table.assert_called_once_with("t1")
    monkeypatch.setattr(mc, "_table", None)


def test_add_doc_cost_uses_the_environment_table(monkeypatch):
    table = MagicMock()
    monkeypatch.setattr(mc, "migration_table", lambda: table)
    assert mc.add_doc_cost(f"global/{H}.content.json", "ocrCost", 0.009) is True
    monkeypatch.setattr(mc, "migration_table", lambda: None)
    assert mc.add_doc_cost(f"global/{H}.content.json", "ocrCost", 0.009) is False
