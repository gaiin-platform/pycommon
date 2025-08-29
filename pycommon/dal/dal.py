from enum import Enum, auto
from typing import Any, Dict, Type

from .contracts import AccountABC, BackendABC, UserABC
from .errors import DalError


class Backend(Enum):
    MEMORY = auto()
    AWS = auto()
    # GCP = auto()
    # AZURE = auto()


# simple in-process registry
_REGISTRY: Dict[Backend, Type[BackendABC]] = {}


def register_backend(kind: Backend, impl: Type[BackendABC]) -> None:
    _REGISTRY[kind] = impl


class DAL:
    """
    Facade. After construction:
      d.User -> the provider's User class (subclass of UserABC)
      d.Account -> the provider's Account class (subclass of AccountABC)
    """

    def __init__(self, kind: Backend, **config: Any) -> None:
        try:
            backend_cls = _REGISTRY[kind]
        except KeyError as e:
            raise DalError(f"No backend registered for {kind}") from e
        self._backend: BackendABC = backend_cls(**config)
        # expose the bound classes
        self.User: Type[UserABC] = self._backend.User
        self.Account: Type[AccountABC] = self._backend.Account
