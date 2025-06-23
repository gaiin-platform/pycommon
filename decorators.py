"""decorators.py provides common decorators for amplify services.

This module provides utility functions and decorators for validating data,
parsing tokens, and performing authorization checks. It centralizes logic
for request validation, permission checks, and rate limiting, ensuring
consistency and security across the codebase.

The module integrates with AWS DynamoDB for account and rate limit management,
and supports OAuth-based authentication using JSON Web Tokens (JWT).

Copyright (c) 2025 Vanderbilt University
Authors: Jules White, Allen Karns, Karely Rodriguez, Max Moundas, Sam Hays
"""

import os
from typing import Any, Callable

from exceptions import EnvVarError


def required_env_vars(*vars: str) -> Callable:
    """Decorator to ensure required environment variables are set.

    Args:
        *vars (str): The names of the required environment variables.

    Returns:
        Callable: The decorated function.
    """

    def decorator(f: Callable) -> Callable:
        def wrapper(*args, **kwargs) -> Any:
            for var in vars:
                if not os.getenv(var):
                    raise EnvVarError(f"Env Var: '{var}' is not set")
            return f(*args, **kwargs)

        return wrapper

    return decorator
