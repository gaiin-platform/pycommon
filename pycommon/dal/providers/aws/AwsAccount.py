from __future__ import annotations

import json
from typing import ClassVar, List, TypedDict

from pycommon.dal.contracts import AccountABC
from pycommon.dal.providers.aws import AwsProvider


# These classes represent internal data structures in the Amplify Implementation
# in AWS as designed by the Amplify team.
class RateLimitDict(TypedDict, total=False):
    """
    Typed dictionary representing rate limit information.

    This class is used in the AccountDict class.

    Attributes:
        limit (int): The maximum number of allowed requests within the specified period.
        period (str): The time period for which the rate limit applies (e.g., 'minute', 'hour').
    """  # noqa: E501

    rate: int
    period: str


class AccountDict(TypedDict):
    """
    AccountDict is a TypedDict data structure used to represent account information stored in DynamoDB.

    Attributes:
        id (str): The unique identifier for the account.
        isDefault (bool): Indicates whether this account is the default account.
        name (str): The display name of the account.
        rateLimit (RateLimitDict): A dictionary containing rate limit configuration for the account.
    """  # noqa: E501

    id: str
    isDefault: bool
    name: str
    rateLimit: RateLimitDict


class AwsAccount(AccountABC):
    provider: ClassVar[AwsProvider]
    user_table_name: ClassVar[str] = "amplify-v6-lambda-dev-accounts"

    def __init__(
        self,
        *,
        id: str | None,
        name: str,
        owner_user_id: str,
        is_default: bool = False,
        rate_limit_period: str = "Unlimited",
        rate_limit_rate: int | None = None,
    ) -> None:
        """
        Initialize an AwsAccount instance.

        Args:
            id (str | None): Optional unique identifier for the account. If not
                             provided, it is generated from owner_user_id and name.
            name (str): The display name of the account. Must not be empty.
            owner_user_id (str): The user ID of the account owner. Must not be empty.
            is_default (bool, optional): Indicates if this account is the default. Defaults to False.
            rate_limit_period (str, optional): The period for rate limiting. Defaults to "Unlimited".
            rate_limit_rate (int | None, optional): The maximum number of allowed requests. Defaults to None.

        Raises:
            ValueError: If name or owner_user_id is not provided.
        """  # noqa: E501
        if not name or not owner_user_id:
            raise ValueError("name and owner_user_id are required")
        self._account: AccountDict = {
            "id": id or f"{owner_user_id}:{name}",
            "isDefault": is_default,
            "name": name,
            "rateLimit": RateLimitDict(
                period=rate_limit_period,
                rate=rate_limit_rate,
            ),
        }
        self._owner: str = owner_user_id

    def __repr__(self):
        return json.dumps(
            {
                "accountOwner": self._owner,
                "id": self._account["id"],
                "isDefault": self._account["isDefault"],
                "name": self._account["name"],
                "rateLimit": {
                    "period": self._account["rateLimit"]["period"],
                    "rate": self._account["rateLimit"]["rate"],
                },
            },
            indent=2,
        )

    @classmethod
    def _user_table(cls):
        return cls.provider.get_table(cls.user_table_name)

    def save(self) -> None:
        """
        Saves the current AwsAccount instance to the user table in DynamoDB.
        If the account already exists for the user, it updates the entry;
        otherwise, it adds a new one.
        """
        table = self.__class__._user_table()
        user = self._owner
        response = table.get_item(Key={"user": user})
        item = response.get("Item", {"user": user, "accounts": []})
        accounts = item.get("accounts", [])

        # Remove any existing account with the same id
        accounts = [acct for acct in accounts if acct.get("id") != self._account["id"]]
        # Add the current account (the one we've presumably modified)
        accounts.append(self._account)

        # Save back to DynamoDB
        table.put_item(Item={"user": user, "accounts": accounts})

    def delete(self) -> None:
        """
        Deletes this AwsAccount instance from the user table in DynamoDB.
        If the account does not exist, the operation is a no-op.
        """
        table = self.__class__._user_table()
        user = self._owner
        response = table.get_item(Key={"user": user})
        item = response.get("Item")
        if not item:
            return
        accounts = item.get("accounts", [])
        accounts = [acct for acct in accounts if acct.get("id") != self._account["id"]]

        # unlike save(), we simply don't re-add this one back to the list
        table.put_item(Item={"user": user, "accounts": accounts})

    @classmethod
    def get_all_for_user(cls, user: str) -> List[AwsAccount]:
        """
        Retrieves all AWS accounts associated with a given user.

        Args:
            user (str): The user identifier for which to fetch AWS accounts.

        Returns:
            List[AwsAccount]: A list of AwsAccount instances associated with the user.
                              Returns an empty list if no accounts are found.

        """
        return cls.get_account_by_id_for_user(user, None)

    @classmethod
    def get_account_by_id_for_user(
        cls, user: str, account_id: str | None
    ) -> List[AwsAccount]:
        """
        Retrieves a list of AwsAccount objects for a given user and account ID.

        Args:
            user (str): The user identifier.
            account_id (str): The AWS account ID to filter by.

        Returns:
            List[AwsAccount]: A list of AwsAccount objects matching the specified account ID for the user.
        """  # noqa: E501
        table = cls._user_table()
        response = table.get_item(Key={"user": user})
        item = response.get("Item")
        if not item:
            return []

        accounts = item.get("accounts", [])
        if not accounts:
            return []

        resp: list = []
        for i in accounts:
            if account_id and i.get("id") != account_id:
                continue

            # rate will be a Decimal
            rate = i.get("rateLimit", {}).get("rate", None)
            # Convert Decimal to int if necessary
            if rate is not None:
                try:
                    rate = int(rate)
                except (ValueError, TypeError):
                    rate = None

            acct = AwsAccount(
                id=i.get("id"),
                name=i.get("name"),
                owner_user_id=user,
                is_default=i.get("isDefault", False),
                rate_limit_period=i.get("rateLimit", {}).get("period", "Unlimited"),
                rate_limit_rate=rate,
            )
            resp.append(acct)
        return resp
