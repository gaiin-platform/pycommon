"""
Deployment utilities for AWS services.

This package contains utilities used during service deployment,
such as Parameter Store synchronization.
"""

from .parameter_store_sync import (
    create_or_update_parameter,
    extract_locally_defined_vars,
    populate_parameters,
)

__all__ = [
    "extract_locally_defined_vars",
    "create_or_update_parameter",
    "populate_parameters",
]
