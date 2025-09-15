from __future__ import annotations

import os
from typing import Any, ClassVar, Dict, Optional

from pycommon.dal.contracts import AdminConfigABC
from pycommon.dal.providers.aws import AwsProvider
from pycommon.dal.providers.aws.helpers import map_aws_error, nowstr


class AwsAdminConfig(AdminConfigABC):
    """AWS-specific admin configuration implementation."""

    provider: ClassVar[AwsProvider]
    config_table: ClassVar[str] = os.getenv("AMPLIFY_ADMIN_DYNAMODB_TABLE")

    def __init__(self, **config: dict) -> None:
        """Provides access to admin configuration tables"""
        # Currently, there are no specific configurations needed.
        pass

    @classmethod
    def _table(cls):
        return cls.provider.get_table(cls.config_table)

    @classmethod
    def get_config(cls, key: str) -> dict | None:
        """Retrieve a configuration value by key.

        Because the config entries are not consistent, this function
        relies on the record including a 'data' field that is a dict.
        It is this dict that will be returned because the underlying
        structure is not guaranteed.

        """
        try:
            table = cls._table()
            resp = table.get_item(Key={"config_id": key})
            item = resp.get("Item")
            if not item:
                return None
            data = item.get("data")
            if not data:
                return None
            return data
        except Exception as e:
            raise map_aws_error(e)

    @classmethod
    def set_config(cls, key: str, value: Any) -> None:
        """Set (overwrite) a configuration value by key.

        The key is the config_id in the DynamoDB table. The value is stored
        in the 'data' field of the record. The 'last_updated' field is set to
        the current time in ISO format.
        """
        try:
            table = cls._table()
            table.put_item(
                Item={"config_id": key, "data": value, "last_updated": nowstr()}
            )
        except Exception as e:
            raise map_aws_error(e)

    def delete_config(self, key: str) -> bool:
        """Delete a configuration value by key."""
        raise NotImplementedError("delete_config is not implemented yet")

    @classmethod
    def list(
        cls, limit: int = 100, cursor: Optional[str] = None
    ) -> tuple[list[str], Optional[str]]:
        """List all configuration keys."""
        ret: list[str] = []
        try:
            table = cls._table()
            kwargs: Dict[str, Any] = {"Limit": limit}
            if cursor:
                kwargs["ExclusiveStartKey"] = {"config_id": cursor}

            resp = table.scan(ProjectionExpression="config_id")
            for item in resp.get("Items", []):
                ret.append(item["config_id"])
            return ret, resp.get("LastEvaluatedKey")
        except Exception as e:
            raise map_aws_error(e)

    def update_config(self, key: str, value: str) -> None:
        """Update a configuration value by key."""
        raise NotImplementedError("update_config is not implemented yet")
