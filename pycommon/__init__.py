# Main pycommon package exports
# Copyright (c) 2024 Vanderbilt University

# Import commonly used root-level modules
# Import key modules for easy access
from . import api, authz, const, decorators, encoders, exceptions, llm, tools

# Import most commonly used functions directly for convenience
from .authz import get_claims, validated, verify_user_as_admin
from .decorators import required_env_vars
from .encoders import dumps_lossy, dumps_safe, dumps_smart
from .exceptions import (
    ClaimException,
    EnvVarError,
    HTTPBadRequest,
    HTTPException,
    HTTPNotFound,
    HTTPUnauthorized,
)

__version__ = "0.0.1-alpha"

__all__ = [
    # Modules
    "api",
    "llm",
    "tools",
    "authz",
    "exceptions",
    "encoders",
    "decorators",
    "const",
    # Common functions
    "validated",
    "get_claims",
    "verify_user_as_admin",
    "dumps_safe",
    "dumps_smart",
    "dumps_lossy",
    "required_env_vars",
    # Common exceptions
    "HTTPException",
    "HTTPBadRequest",
    "HTTPUnauthorized",
    "HTTPNotFound",
    "ClaimException",
    "EnvVarError",
]
