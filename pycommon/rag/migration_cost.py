"""What a document's migration rebuild has cost so far, kept on its migration row.

The charges table has no index by document, so a document's cost cannot be looked
up afterwards. Each cost is therefore added to the document's migration row
(``doc#global/<hash>.content.json``) at the moment it is recorded:

    embeddingCost  Nova embeddings, billed per call
    ocrCost        Textract pages, billed per run
    qaCalls        question generation calls (a count, not dollars: the chat
                   service bills them and does not return what a call cost, so
                   the admin tab prices each call from the chat usage records)

Only documents already in the migration have a row; nothing is ever created here,
and bookkeeping never raises.
"""

import logging
import os
from decimal import Decimal

import boto3

logger = logging.getLogger("rag_migration_cost")

LEGACY_PREFIX = "global/"
NEW_PREFIX = "global2/"
FIELDS = ("embeddingCost", "qaCalls", "ocrCost")

_table = None


def migration_doc_id(content_key):
    """The migration row id of a ``global/`` or ``global2/`` content key, else None."""
    key = str(content_key or "")
    key = key.split("://", 1)[1] if "://" in key else key
    if key.startswith(NEW_PREFIX):
        key = LEGACY_PREFIX + key[len(NEW_PREFIX) :]
    return f"doc#{key}" if key.startswith(LEGACY_PREFIX) else None


def migration_table():
    """The RAG_MIGRATION_TABLE table, or None where migration is not deployed."""
    global _table
    name = os.environ.get("RAG_MIGRATION_TABLE", "")
    if not name or name == "unset":
        return None
    if _table is None or _table.name != name:
        _table = boto3.resource("dynamodb").Table(name)
    return _table


def add_doc_cost(content_key, field, amount, table=None):
    """Add ``amount`` (USD, or a count for qaCalls) to ``field`` on the document's row.

    True when it was added.
    """
    doc_id = migration_doc_id(content_key)
    if field not in FIELDS or not doc_id or not amount or amount <= 0:
        return False
    try:
        table = table or migration_table()
        if table is None:
            return False
        table.update_item(
            Key={"id": doc_id},
            UpdateExpression=f"ADD {field} :cost",
            ConditionExpression="attribute_exists(id)",
            ExpressionAttributeValues={":cost": Decimal(str(round(float(amount), 9)))},
        )
        return True
    except Exception as error:
        if "ConditionalCheckFailed" not in str(
            error
        ):  # no row = not a migration document: the normal case
            logger.warning("Could not add %s to %s: %s", field, doc_id, error)
        return False
