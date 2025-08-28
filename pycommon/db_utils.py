# Copyright (c) 2025 Vanderbilt University
"""
db_utils.py

This module provides utilities for database operations, specifically for
DynamoDB compatibility and data transformation. It includes functions
for converting Python data types to formats required by various database
systems.

These utilities are designed to handle common database compatibility
issues, such as DynamoDB's requirement for Decimal types instead of
float types.

Copyright (c) 2025 Vanderbilt University
Authors: Jules White, Allen Karns, Karely Rodriguez, Max Moundas, Sam Hays
"""

from decimal import Decimal
from typing import Any


def convert_floats_to_decimal(obj: Any) -> Any:
    """
    Recursively convert float values to Decimal for DynamoDB compatibility.

    This function traverses nested data structures (dictionaries, lists) and
    converts any float values to Decimal objects to ensure compatibility
    with DynamoDB, which requires precise decimal handling and throws
    "Float types are not supported. Use Decimal types instead" errors.

    Args:
        obj (Any): The object to process, which can be a float, dict, list,
                  or any other type.

    Returns:
        Any: The processed object with float values converted to Decimal.
             The structure is preserved, but float values are replaced
             with their Decimal equivalents.

    Example:
        >>> data = {"price": 19.99, "items": [1.5, 2.7], "name": "Product"}
        >>> converted = convert_floats_to_decimal(data)
        >>> # Result: {"price": Decimal("19.99"), "items": [Decimal("1.5"),
        >>> #          Decimal("2.7")], "name": "Product"}
    """
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {key: convert_floats_to_decimal(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_floats_to_decimal(item) for item in obj]
    else:
        return obj
