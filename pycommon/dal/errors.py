class DalError(Exception):
    """Base class for all errors raised by the DAL."""


class NotFound(DalError):
    """The requested item does not exist."""


class AlreadyExists(DalError):
    """The item being created already exists."""


class Conflict(DalError):
    """The operation conflicts with the current state of the item."""


class TransientError(DalError):
    """A temporary failure occurred; the operation may succeed if retried."""


class PermissionDenied(DalError):
    """The caller is not permitted to perform the operation."""
