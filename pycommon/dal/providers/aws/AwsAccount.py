from __future__ import annotations

from collections.abc import Iterable
from typing import ClassVar, List, Optional, Tuple, TypedDict

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
                limit=rate_limit_rate,
            ),
        }

    @classmethod
    def _user_table(cls):
        return cls.provider.get_table(cls.user_table_name)

    def save(self) -> None:
        pass

    def delete(self) -> None:
        pass

    @classmethod
    def get_all_for_user(cls, user: str) -> List[AwsAccount]:
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
            acct = AwsAccount(
                id=i.get("id"),
                name=i.get("name"),
                owner_user_id=item.get("user"),
                is_default=i.get("isDefault", False),
                rate_limit_period=i.get("rateLimit", {}).get("period", "Unlimited"),
                rate_limit_rate=i.get("rateLimit", {}).get("rate", None),
            )
            resp.append(acct)
        return resp

    @classmethod
    def get_account_by_id_for_user(cls, user: str, account_id: str) -> List[AwsAccount]:
        table = cls._user_table()
        response = table.get_item(Key={"user": user})
        item = response.get("Item")
        if item:
            resp: list = []
            for i in item:
                if i.get("id") != account_id:
                    continue
                acct = AwsAccount(
                    id=i.get("id"),
                    name=i.get("name"),
                    owner_user_id=i.get("owner_user_id"),
                    is_default=i.get("isDefault", False),
                    rate_limit_period=i.get("rateLimit", {}).get("period", "Unlimited"),
                    rate_limit_rate=i.get("rateLimit", {}).get("rate", None),
                )
                resp.append(acct)
            return resp

    @classmethod
    def find_by_owner(
        cls, user_id: str, *, limit: int = 100, cursor: Optional[str] = None
    ) -> Tuple[Iterable["AwsAccount"], Optional[str]]:
        pass
