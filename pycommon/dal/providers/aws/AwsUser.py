from __future__ import annotations

import json
import os
from typing import Any, ClassVar, Dict, Iterable, Optional, Tuple

from pycommon.dal.contracts import UserABC
from pycommon.dal.errors import NotFound
from pycommon.dal.providers.aws import AwsAccount, AwsProvider
from pycommon.dal.providers.aws.helpers import map_aws_error, nowstr


class AwsUser(UserABC):
    provider: ClassVar[AwsProvider]
    user_table_name: ClassVar[str] = os.getenv("COGNITO_USERS_DYNAMODB_TABLE")

    def __init__(
        self,
        *,
        user_id: str,
        email: str | None = None,
        family_name: str | None = None,
        given_name: str | None = None,
        cust_saml_groups: str | None = None,
        updated_at: str | None = None,
    ) -> None:

        self._user_id = user_id
        self.email = email
        self.family_name = family_name
        self.given_name = given_name
        self.cust_saml_groups = cust_saml_groups
        self._updated_at = updated_at
        self.version = 1

    @classmethod
    def _user_table(cls):
        return cls.provider.get_table(cls.user_table_name)

    def __repr__(self):
        return json.dumps(self._get_values_as_dict(), indent=2)

    @property
    def version(self) -> int:
        """
        Gets the version of the user object.

        Returns:
            int: The version number.
        """
        return self._version

    @version.setter
    def version(self, value: int) -> None:
        """
        Sets the version of the user object.

        Args:
            value (int): The version number to set.

        Raises:
            TypeError: If the provided value is not an integer.
        """
        if not isinstance(value, int):
            raise TypeError("version must be int")
        self._version = value

    @property
    def user_id(self) -> str:
        """
        Gets the user ID associated with this instance.

        Returns:
            str: The user ID.
        """
        return self._user_id

    @user_id.setter
    def user_id(self, value: str) -> None:
        """
        Sets the user ID for the provider.

        Args:
            value (str): The user ID to set.
        Raises:
            TypeError: If the provided value is not a string.
        """
        if not isinstance(value, str):
            raise TypeError("user_id must be str")
        self._user_id = value

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
        if not isinstance(value, str) and value is not None:
            raise TypeError("email must be str")
        self._email = value

    @property
    def family_name(self) -> str | None:
        """
        Returns the family name (surname) of the user.

        Returns:
            str | None: The family name if available, otherwise None.
        """
        return self._family_name

    @family_name.setter
    def family_name(self, value: str) -> None:
        """
        Setter for the family_name property.

        Args:
            value (str): The family name to set.

        Raises:
            TypeError: If the provided value is not a string.
        """
        if not isinstance(value, str) and value is not None:
            raise TypeError("family_name must be str")
        self._family_name = value

    @property
    def given_name(self) -> str | None:
        """
        Returns the given name of the user.

        Returns:
            str | None: The given name if available, otherwise None.
        """
        return self._given_name

    @given_name.setter
    def given_name(self, value: str) -> None:
        """
        Sets the given name of the user.

        Args:
            value (str): The given name to assign.

        Raises:
            TypeError: If the provided value is not a string.
        """
        if not isinstance(value, str) and value is not None:
            raise TypeError("given_name must be str")
        self._given_name = value

    @property
    def updated_at(self) -> str | None:
        """
        Gets the timestamp indicating when the user was last updated.

        Returns:
            str | None: The ISO 8601 formatted timestamp of the last update, or None if not set.
        """  # noqa: E501
        return self._updated_at

    @property
    def cust_saml_groups(self) -> str | None:
        """
        Returns the custom SAML groups associated with the user.

        Returns:
            str | None: A string containing the custom SAML groups if
                        available, otherwise None.
        """
        return self._cust_saml_groups

    @cust_saml_groups.setter
    def cust_saml_groups(self, value: list[str] | str | None) -> None:
        """
        Sets the custom SAML groups for the user.

        Args:
            value (list[str] | str | None): A list of group names as strings, or None
                                      to clear the groups. Some legacy Dynamodb records
                                      included a string that was not deserializable JSON.

        Raises:
            TypeError: If value is not a list of strings.

        Side Effects:
            Updates the internal _cust_saml_groups attribute with a JSON-encoded
            list (stringified) of group names or None.
        """  # noqa: E501
        if value is None:
            self._cust_saml_groups = None
            return
        if isinstance(value, str):
            value = [
                str(item).strip("'\" ")  # treat as string, remove quotes and spaces
                for item in value.strip("[]").split(",")
                if item.strip() and item is not None
            ]
        elif isinstance(value, list):
            value = [str(x) for x in value if x is not None]
        else:
            raise TypeError("cust_saml_groups must be a list of strings or a string")
        self._cust_saml_groups = json.dumps(value)

    def _get_values_as_dict(self) -> dict:
        """
        Returns a dictionary representation of the user's attributes.

        Returns:
            dict: A dictionary containing user information including user_id, email,
                  family_name, given_name, custom SAML groups
                  and updated_at.
        """
        return {
            "user_id": self.user_id,
            "email": self.email,
            "family_name": self.family_name,
            "given_name": self.given_name,
            "custom:saml_groups": self.cust_saml_groups,
            "updated_at": self.updated_at,  # TODO(sam) make setter/getter
            "version": self.version,
        }

    def _create_non_null_dynamodb_dict(self) -> dict:
        """
        Creates a dictionary of the user's attributes for DynamoDB,
        excluding any attributes that have a value of None.

        Returns:
            dict: A dictionary containing only non-null user attributes.
        """
        return {k: v for k, v in self._get_values_as_dict().items() if v is not None}

    def save(self, allow_overwrite: bool = True) -> None:
        """
        Saves the current object to the DynamoDB table using upsert semantics.

        If allow_overwrite is False, the operation will fail if an item with
        the same user_id already exists.

        Raises:
            Exception: If the DynamoDB operation fails, an appropriate mapped
                       AWS error is raised.
        """
        # because the dynamodb table has keys like "custom:saml_groups",
        # we need to alias them for the update expression because boto3
        # doesn't like special characters in the expression attribute names.
        key_alias = lambda k: f"{k.replace(':','_')}"  # noqa: E731

        try:
            table = self._user_table()
            data = self._get_values_as_dict()
            kwargs = {"Item": data}
            if not allow_overwrite:
                kwargs["ConditionExpression"] = "attribute_not_exists(user_id)"

            resp = table.get_item(Key={"user_id": self.user_id})
            if not resp.get("Item"):
                data["updated_at"] = nowstr()
                table.put_item(**kwargs)
            else:
                # remove any keys that don't need updated
                keys_to_delete = []
                attrs_to_delete = []
                data["updated_at"] = nowstr()

                # remove any keys which match both sides
                for k, v in data.items():
                    if data.get(k) is None and resp["Item"].get(k) is not None:
                        attrs_to_delete.append(k)
                    elif resp["Item"].get(k) == v:
                        keys_to_delete.append(k)

                for k in keys_to_delete:
                    del data[k]

                if not data or data.keys() == {"updated_at"}:
                    return

                update_expr = "SET " + ", ".join(
                    f"#{key_alias(k)}=:{key_alias(k)}"
                    for k in data.keys()
                    if k != "user_id" and k not in attrs_to_delete
                )
                if attrs_to_delete:
                    update_expr += " REMOVE " + ", ".join(
                        [f"#{key_alias(k)}" for k in attrs_to_delete]
                    )

                expr_attr_names = {
                    f"#{key_alias(k)}": k for k in data.keys() if k != "user_id"
                }
                expr_attr_values = {
                    f":{key_alias(k)}": v
                    for k, v in data.items()
                    if k != "user_id" and k not in attrs_to_delete
                }

                table.update_item(
                    Key={"user_id": self.user_id},
                    UpdateExpression=update_expr,
                    ExpressionAttributeNames=expr_attr_names,
                    ExpressionAttributeValues=expr_attr_values,
                )
        except Exception as e:
            raise map_aws_error(e)

    def delete(self) -> None:
        """
        Deletes:
            The entry from the User DDB Table.
            Any Accounts from the Account DDB Table for this user.

        WARNING: This operation deletes the record without respect to other records
                 which may still reference it other than those mentioned here.

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

            # now delete the Accounts
            for account in self.accounts(use_cache=False):
                account.delete()
        except Exception as e:
            raise map_aws_error(e)

    def accounts(self, use_cache=True) -> list:
        """
        Retrieves the list of AWS accounts associated with the user.

        Args:
            use_cache (bool, optional): If True, returns cached accounts
                if available, otherwise retrieve the accounts and populate
                the cache. Defaults to True.

        Returns:
            list: A list of AWS accounts for the user.
        """
        if use_cache:
            if hasattr(self, "_accounts"):
                return self._accounts
        self._accounts = AwsAccount.get_all_for_user(self.user_id)
        return self._accounts

    # ClassMethods (other than dunders) go below here.

    @classmethod
    def get_by_user_id(cls, user_id: str) -> AwsUser:
        """
        Retrieves a user by user_id from the DynamoDB table.

        Args:
            user_id (str): The unique identifier of the user.

        Returns:
            AwsUser: An instance of AwsUser populated with all available attributes.

        Raises:
            NotFound: If the user with the given user_id does not exist.
            Exception: If the DynamoDB operation fails, an appropriate mapped
                       AWS error is raised.
        """
        try:
            table = cls._user_table()
            resp = table.get_item(Key={"user_id": user_id}, ConsistentRead=True)
            item = resp.get("Item")
            if not item:
                raise NotFound(user_id)
            user: AwsUser = AwsUser(
                user_id=item.get("user_id"),
                email=item.get("email"),
                family_name=item.get("family_name"),
                given_name=item.get("given_name"),
                updated_at=item.get("updated_at", None),
            )
            user.cust_saml_groups = item.get("custom:saml_groups", None)

            return user

        except Exception as e:
            raise map_aws_error(e)

    @classmethod
    def list(
        cls, *, limit: int = 100, cursor: Optional[str] = None
    ) -> Tuple[Iterable["AwsUser"], Optional[str]]:
        """
        Retrieves a list of AwsUser objects from the user table with optional pagination.

        Args:
            limit (int, optional): Maximum number of users to retrieve. Defaults to 100.
            cursor (Optional[str], optional): The user_id to start scanning from for pagination. Defaults to None.

        Returns:
            Tuple[Iterable["AwsUser"], Optional[str]]:
                A tuple containing:
                    - An iterable of AwsUser instances.
                    - The next cursor (user_id) for pagination, or None if there are no more results.

        Raises:
            Exception: Raises a mapped AWS error if the scan operation fails.
        """  # noqa: E501
        try:
            table = cls._user_table()
            kwargs: Dict[str, Any] = {"Limit": limit}
            if cursor:
                kwargs["ExclusiveStartKey"] = {"user_id": cursor}

            resp = table.scan(**kwargs)
            users = [
                AwsUser(
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
            raise map_aws_error(e)
