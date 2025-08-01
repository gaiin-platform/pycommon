from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Protocol

_route_data: Dict[str, Dict[str, Any]] = None
_permissions_by_state = None
_op_type: str = "built_in"


class PermissionChecker(Protocol):
    def __call__(self, user: str, data: Any) -> bool:
        """Check if user has permission to access data."""
        pass  # pragma: no cover


def set_route_data(route_data: Dict[str, Dict[str, Any]]):
    """
    Allow services to inject their own route_data.

    Args:
        route_data: Dictionary containing route configuration data
    """
    global _route_data
    _route_data = route_data


def set_permissions_by_state(
    permissions_by_state: Dict[str, Dict[str, PermissionChecker]],
):
    """
    Allow services to inject their own permissions_by_state.

    Args:
        permissions_by_state: Dictionary mapping states to permission checkers
    """
    global _permissions_by_state
    _permissions_by_state = permissions_by_state


def set_op_type(op_type: str):
    """
    Allow services to set a default op_type for all operations.

    Args:
        op_type: The operation type to set as default
    """
    global _op_type
    _op_type = op_type


def api_tool(
    path: str,
    name: str,
    description: str,
    parameters: Optional[
        Dict[str, Any]
    ] = None,  # Input schema (OpenAI spec compatible)
    output: Optional[Dict[str, Any]] = None,  # Output schema
    tags: Optional[List[str]] = None,
    method: str = "POST",
    permissions: Optional[Dict[str, Any]] = None,
) -> Callable:
    """
    Register an API tool/operation with standardized parameters.

    Args:
        path: The API endpoint path (e.g., "/state/share")
        name: Human-readable name for the operation
        description: Detailed description of what the operation does
        parameters: JSON schema for input validation (OpenAI spec compatible)
        output: JSON schema for output validation
        tags: List of tags for categorization
        method: HTTP method (GET, POST)
        permissions: Permission configuration for the operation

    Returns:
        Decorated function that registers the operation

    Raises:
        ValueError: If method is not "GET" or "POST"
    """

    # Validate that method is either GET or POST
    if method not in ["GET", "POST"]:
        raise ValueError(f"Method must be either 'GET' or 'POST', got '{method}'")

    # This is the actual decorator
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):

            if (
                _permissions_by_state is not None
                and not _permissions_by_state.permissions_by_state_type.get(path, None)
            ):
                operation = path.split("/")[-1]
                _permissions_by_state.permissions_by_state_type[path] = {
                    operation: lambda user, data: True
                }

            # Call the actual function
            result = func(*args, **kwargs)
            return result

        if _route_data is not None:
            _route_data[path] = {
                "method": method,
                "parameters": parameters,  # Input schema
                "output": output,  # Output schema
                "tags": tags,
                "name": name,
                "description": description,
                "handler": wrapper,
                "permissions": permissions or {},
                "op_type": _op_type,
            }

        return wrapper

    return decorator
