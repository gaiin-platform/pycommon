from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar, Iterable, Optional, Type


class UserABC(ABC):
    """
    Abstract base class representing a user entity with required fields and operations.

    Attributes:
        provider (Any): Backend/client provider, set by the Backend on initialization.
        user_id (str): Unique identifier for the user.
        updated_at (str): Timestamp of the last update.
        cust_saml_groups (str | None): Custom SAML groups associated with the user.
        cust_vu_groups (str | None): Custom VU groups associated with the user.
        family_name (str | None): User's family (last) name.
        given_name (str | None): User's given (first) name.
        email (str | None): User's email address.

    Methods:
        __init__(id: str | None, email: str, created_at: datetime | None = None) -> None:
            Initialize a user instance.

        save() -> None:
            Persist the user instance to the backend.

        delete() -> None:
            Remove the user instance from the backend.

        get(user_id: str) -> "UserABC":
            Retrieve a user instance by user ID.

        find_by_user_id(user_id: str) -> "UserABC":
            Find a user instance by user ID.

        list(limit: int = 100, cursor: str | None = None) -> tuple[Iterable["UserABC"], str | None]:
            List user instances with optional pagination.
    """  # noqa: E501

    # Implementations can stash backend/client here (set by the Backend on init)
    provider: ClassVar[Any] = None

    # Fields in the cognito users table
    # @@TableDescription env_name=COGNITO_USERS_DYNAMODB_TABLE
    user_id: str
    updated_at: str
    cust_saml_groups: str | None
    cust_vu_groups: str | None
    family_name: str | None
    given_name: str | None
    email: str | None

    @abstractmethod
    def __init__(
        self,
        *,
        user_id: str,
        email: str | None = None,
        family_name: str | None = None,
        given_name: str | None = None,
        cust_saml_groups: str | None = None,
        cust_vu_groups: str | None = None,
        updated_at: str | None = None,
    ) -> None: ...

    # Instance methods (perform action on instance objects)
    @abstractmethod
    def save(self) -> None: ...

    @abstractmethod
    def delete(self) -> None: ...

    @abstractmethod
    def accounts(self) -> list[AccountABC]: ...

    # Class methods (return objects)
    @classmethod
    @abstractmethod
    def get_by_user_id(cls, user_id: str) -> UserABC: ...

    @classmethod
    @abstractmethod
    def list(
        cls, *, limit: int = 100, cursor: str | None = None
    ) -> tuple[Iterable[UserABC], str | None]: ...


class AccountABC(ABC):
    provider: ClassVar[Any] = None

    user: str
    accounts: list

    @abstractmethod
    def __init__(self, *, id: str | None, name: str, owner_user_id: str) -> None: ...

    @abstractmethod
    def save(self) -> None: ...

    @abstractmethod
    def delete(self) -> None: ...

    @classmethod
    @abstractmethod
    def get_all_for_user(cls, user_id: str) -> list[AccountABC]: ...

    @classmethod
    @abstractmethod
    def get_account_by_id_for_user(
        cls, user_id: str, account_id: str
    ) -> AccountABC | None: ...


class AdminConfigABC(ABC):
    provider: ClassVar[Any] = None

    @abstractmethod
    def __init__(self, **config: Any) -> None:
        """Provides access to admin configuration tables"""
        pass

    @abstractmethod
    def get_config(self, key: str) -> dict | None:
        """Retrieve a configuration value by key."""
        pass

    @abstractmethod
    def set_config(self, key: str, value: Any) -> bool:
        """Set (overwrite) a configuration value by key."""
        pass

    @abstractmethod
    def delete_config(self, key: str) -> bool:
        """Delete a configuration value by key."""
        pass

    @abstractmethod
    def list(self, limit: int = 100, cursor: Optional[str] = None) -> list[str]:
        """List all configuration keys."""
        pass

    @abstractmethod
    def update_config(self, key: str, value: str) -> None:
        """Update a configuration value by key."""
        pass


# all required classes to fully implement a backend for Amplify
required = {"User": UserABC, "Account": AccountABC, "AdminConfig": AdminConfigABC}


class BackendABC(ABC):
    """
    Concrete providers MUST define a classes described in `required`

    In __init__, should bind provider state into User.provider / Account.provider.
    """

    # abstract "class attributes" (enforced by __init_subclass__)
    User: Type[UserABC]
    Account: Type[AccountABC]
    AdminConfig: Type[AdminConfigABC]

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        # Ensure the subclass defines concrete classes for User/Account
        for name, base in required.items():
            obj = cls.__dict__.get(name)
            if not (isinstance(obj, type) and issubclass(obj, base)):
                raise TypeError(
                    f"{cls.__name__} must define a concrete class '{name}' subclassing {base.__name__}"  # noqa E501
                )

    @abstractmethod
    def __init__(self, **config: Any) -> None:
        """Bind provider-specific clients/state and set .User.provider / .Account.provider."""  # noqa: E501
        ...
