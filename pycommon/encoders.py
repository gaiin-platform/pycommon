# Copyright (c) 2025 Vanderbilt University
"""
encoders.py

This module provides custom JSON encoders for handling Python Decimal objects
and other serialization needs. It includes multiple encoder classes tailored
to different use cases, such as preserving precision, converting to numeric
types, or truncating precision.

These encoders are designed to be used with the `json` module and provide
flexibility for APIs, financial applications, and other scenarios requiring
custom serialization logic.

Copyright (c) 2025 Vanderbilt University
Authors: Jules White, Allen Karns, Karely Rodriguez, Max Moundas, Sam Hays
"""

import json
from decimal import Decimal
from typing import Any


class SafeDecimalEncoder(json.JSONEncoder):
    """
    JSON encoder that converts Decimal objects to strings.

    This preserves full precision and avoids float rounding issues.
    Useful for APIs and financial data.

    Args:
        obj (object): The object to encode.

    Returns:
        str: The string representation of the Decimal.

    Raises:
        TypeError: If the object is not serializable.
    """

    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return str(obj)
        return super().default(obj)


class SmartDecimalEncoder(json.JSONEncoder):
    """
    JSON encoder that converts Decimal to int if whole, otherwise float.

    This attempts to maintain numeric fidelity without converting to strings.

    Args:
        obj (object): The object to encode.

    Returns:
        int or float: A numeric representation of the Decimal.

    Raises:
        TypeError: If the object is not serializable.
    """

    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return float(obj) if obj % 1 != 0 else int(obj)
        return super().default(obj)


class LossyDecimalEncoder(json.JSONEncoder):
    """
    JSON encoder that converts all Decimal values to integers.

    This truncates decimal precision. Use with caution.

    Args:
        obj (object): The object to encode.

    Returns:
        int: The truncated integer value of the Decimal.

    Raises:
        TypeError: If the object is not serializable.
    """

    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return int(obj)
        return super().default(obj)


def dumps_safe(obj: Any, **kwargs) -> str:
    """
    Serialize an object to JSON using SafeDecimalEncoder.

    Args:
        obj (object): The object to serialize.
        **kwargs: Additional arguments passed to json.dumps.

    Returns:
        str: JSON-encoded string with Decimal values as strings.
    """
    return json.dumps(obj, cls=SafeDecimalEncoder, **kwargs)


def dumps_smart(obj: Any, **kwargs) -> str:
    """
    Serialize an object to JSON using SmartDecimalEncoder.

    Args:
        obj (object): The object to serialize.
        **kwargs: Additional arguments passed to json.dumps.

    Returns:
        str: JSON-encoded string with Decimal values as int or float.
    """
    return json.dumps(obj, cls=SmartDecimalEncoder, **kwargs)


def dumps_lossy(obj: Any, **kwargs) -> str:
    """
    Serialize an object to JSON using LossyDecimalEncoder.

    Args:
        obj (object): The object to serialize.
        **kwargs: Additional arguments passed to json.dumps.

    Returns:
        str: JSON-encoded string with Decimal values as int (with truncation).
    """
    return json.dumps(obj, cls=LossyDecimalEncoder, **kwargs)
