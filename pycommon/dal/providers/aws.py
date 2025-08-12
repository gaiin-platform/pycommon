# dal/providers/aws.py
from boto3.dynamodb.conditions import Key
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from typing import Any, Callable, ClassVar, Dict, Iterable, Optional, Tuple, Type

import boto3
import botocore.exceptions

from ..contracts import BackendABC, UserABC, AccountABC
from ..dal import Backend, register_backend
from ..errors import Conflict, NotFound, PermissionDenied, TransientError

# get a timestamp string for right now w/ `nowstr()`
nowstr: Callable = lambda: datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

# ---------- Provider context ----------


@dataclass
class _AwsProvider:
    dynamodb: Any
    tables: dict = field(default_factory=dict)

    def get_table(self, name: str):
        if name not in self.tables:
            self.tables[name] = self.dynamodb.Table(name)
        return self.tables[name]


def _map_aws_error(e: Exception) -> Exception:
    if isinstance(e, botocore.exceptions.ClientError):
        code = e.response.get("Error", {}).get("Code", "")
        if code in {"ProvisionedThroughputExceededException", "ThrottlingException"}:
            return TransientError(str(e))
        if code in {"AccessDeniedException"}:
            return PermissionDenied(str(e))
        if code in {"ConditionalCheckFailedException"}:
            return Conflict(str(e))
    return e


# ---------- Concrete User implementation ----------


class _AwsUser(UserABC):
    provider: ClassVar[_AwsProvider]
    user_table_name: ClassVar[str] = "amplify-v6-object-access-dev-cognito-users"

    def __init__(
        self,
        *,
        user_id: str,
        email: str | None = None,
        family_name: str | None = None,
        given_name: str | None = None,
        cust_saml_groups: str | None = None,
        cust_vu_groups: str | None = None,
    ) -> None:

        self._user_id = user_id
        self._email = email
        self._family_name = family_name
        self._given_name = given_name
        self._cust_saml_groups = cust_saml_groups
        self._cust_vu_groups = cust_vu_groups
        self._updated_at = None

    @classmethod
    def _user_table(cls):
        return cls.provider.get_table(cls.user_table_name)

    def __repr__(self):
        return json.dumps(self._get_values_as_dict(), indent=2)

    @property
    def user_id(self) -> str:
        """
        Gets the user ID associated with this instance.

        Returns:
            str: The user ID.
        """
        return self._user_id

    @property
    def email(self) -> str | None:
        """
        Gets the email address associated with the instance.

        Returns:
            str | None: The email address if set, otherwise None.
        """
        return self._email

    @email.setter
    def email(self, value: str) -> None:
        """
        Sets the email address for the provider.

        Args:
            value (str): The email address to set.

        Raises:
            TypeError: If the provided value is not a string.
        """
        if not isinstance(value, str):
            raise TypeError("email must be str")
        self._email = value

    @property
    def family_name(self) -> str | None:
        return self._family_name

    @family_name.setter
    def family_name(self, value: str) -> None:
        if not isinstance(value, str):
            raise TypeError("family_name must be str")
        self._family_name = value

    @property
    def given_name(self) -> str | None:
        return self._given_name

    @given_name.setter
    def given_name(self, value: str) -> None:
        if not isinstance(value, str):
            raise TypeError("given_name must be str")
        self._given_name = value

    @property
    def cust_saml_groups(self) -> str | None:
        return self._cust_saml_groups

    @cust_saml_groups.setter
    def cust_saml_groups(self, value: list[str] | None) -> None:
        if value is None:
            self._cust_saml_groups = None
            return
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise TypeError("cust_saml_groups must be a list of strings")
        self._cust_saml_groups = json.dumps(value)

    @property
    def updated_at(self) -> str:
        return self._updated_at

    def _get_values_as_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "email": self.email,
            "family_name": self.family_name,
            "given_name": self.given_name,
            "custom:saml_groups": self.cust_saml_groups,
            # "custom:vu_groups": self.cust_vu_groups,
            "updated_at": self.updated_at,  # TODO(sam) make setter/getter
        }

    def _create_non_null_dynamodb_dict(self) -> dict:
        return {k: v for k, v in self._get_values_as_dict().items() if v is not None}

    # Active-Record persistence
    def save(self, allow_overwrite: bool = True) -> None:
        """
        Saves the current object to the DynamoDB table using upsert semantics.

        If allow_overwrite is False, the operation will fail if an item with
        the same user_id already exists.

        Raises:
            Exception: If the DynamoDB operation fails, an appropriate mapped
                       AWS error is raised.
        """
        try:
            data: dict = self._create_non_null_dynamodb_dict()
            data["updated_at"] = nowstr()
            kwargs: dict = {"Item": data}
            if not allow_overwrite:
                kwargs["ConditionExpression"] = "attribute_not_exists(user_id)"
            table = self._user_table()
            table.put_item(**kwargs)
        except Exception as e:
            raise _map_aws_error(e)

    def delete(self) -> None:
        """
        Deletes the user from the DynamoDB table.

        Raises:
            Exception: If the DynamoDB operation fails, an appropriate mapped
                       AWS error is raised.
        """
        try:
            table = self._user_table()
            table.delete_item(
                Key={"user_id": self.user_id},
                ConditionExpression="attribute_exists(user_id)",
            )
        except Exception as e:
            raise _map_aws_error(e)

    # Lookups
    @classmethod
    def get(cls, user_id: str) -> "_AwsUser":
        """
        Retrieves a user by user_id from the DynamoDB table.

        Args:
            user_id (str): The unique identifier of the user.

        Returns:
            _AwsUser: An instance of _AwsUser populated with all available attributes.

        Raises:
            NotFound: If the user with the given user_id does not exist.
            Exception: If the DynamoDB operation fails, an appropriate mapped AWS error is raised.
        """
        try:
            table = cls._user_table()
            resp = table.get_item(Key={"user_id": user_id}, ConsistentRead=True)
            item = resp.get("Item")
            if not item:
                raise NotFound(user_id)
            user: _AwsUser = _AwsUser(
                user_id=item.get("user_id"),
                email=item.get("email"),
                family_name=item.get("family_name"),
                given_name=item.get("given_name"),
            )
            user.cust_saml_groups = item.get("custom:saml_groups", None)
            user.cust_vu_groups = item.get("custom:vu_groups", None)

            return user

        except Exception as e:
            raise _map_aws_error(e)

    @classmethod
    def find_by_user_id(cls, user_id: str) -> "_AwsUser":
        try:
            table = cls._user_table()
            resp = table.query(
                KeyConditionExpression=Key("user_id").eq(user_id),
                Limit=1,
            )
            items = resp.get("Items") or []
            if not items:
                raise NotFound(user_id)
            it = items[0]
            return _AwsUser(
                user_id=it.get("user_id"),
                email=it.get("email"),
                family_name=it.get("family_name"),
                given_name=it.get("given_name"),
            )
        except Exception as e:
            raise _map_aws_error(e)

    @classmethod
    def list(
        cls, *, limit: int = 100, cursor: Optional[str] = None
    ) -> Tuple[Iterable["_AwsUser"], Optional[str]]:
        try:
            table = cls._user_table()
            kwargs: Dict[str, Any] = {"Limit": limit}
            if cursor:
                kwargs["ExclusiveStartKey"] = {"user_id": cursor}

            resp = table.scan(**kwargs)
            users = [
                _AwsUser(
                    user_id=item.get("user_id"),
                    email=item.get("email"),
                    family_name=item.get("family_name"),
                    given_name=item.get("given_name"),
                )
                for item in resp.get("Items", [])
                if item.get("user_id")
            ]
            next_cursor = (resp.get("LastEvaluatedKey") or {}).get("user_id")
            return users, next_cursor
        except Exception as e:
            raise _map_aws_error(e)


# ---------- Concrete Account implementation ----------


class _AwsAccount(AccountABC):
    provider: ClassVar[_AwsProvider]

    def __init__(self, *, id: str | None, name: str, owner_user_id: str) -> None:
        if not name or not owner_user_id:
            raise ValueError("name and owner_user_id are required")
        self.id = id or f"{owner_user_id}:{name}"
        self.name = name
        self.owner_user_id = owner_user_id

    def save(self) -> None:
        pass

    def delete(self) -> None:
        pass

    @classmethod
    def get(cls, account_id: str) -> "_AwsAccount":
        pass

    @classmethod
    def find_by_owner(
        cls, user_id: str, *, limit: int = 100, cursor: Optional[str] = None
    ) -> Tuple[Iterable["_AwsAccount"], Optional[str]]:
        pass


# ---------- Backend binding ----------


class AwsBackend(BackendABC):

    User = _AwsUser
    Account = _AwsAccount

    def __init__(self, **config: Any) -> None:
        boto3_kwargs: Dict[str, Any] = config.get("boto3_kwargs", {}) or {}

        dynamodb = boto3.resource("dynamodb", **boto3_kwargs)

        provider = _AwsProvider(dynamodb=dynamodb)

        # Bind provider context to the AR classes
        self.User.provider = provider
        self.Account.provider = provider


# Register at import time
register_backend(Backend.AWS, AwsBackend)
