# Copyright (c) 2025 Vanderbilt University
# Authors: Jules White, Allen Karns, Karely Rodriguez, Max Moundas, Sam Hays

import json
import decimal
from pydantic import BaseModel


class DecimalEncoder(json.JSONEncoder):
    """
    A custom JSON encoder that converts decimal.Decimal objects to integers.
    """

    def default(self, obj: object) -> object:
        """
        Override the default method to handle decimal.Decimal objects.

        Args:
            obj (object): The object to encode.

        Returns:
            object: The encoded object, converting decimal.Decimal to int if applicable.
        """
        if isinstance(obj, decimal.Decimal):
            return int(obj)
        return super(DecimalEncoder, self).default(obj)


def pydantic_encoder(obj: object) -> dict:
    """
    Encode Pydantic BaseModel objects into dictionaries.

    Args:
        obj (object): The object to encode.

    Returns:
        dict: The dictionary representation of the BaseModel object.

    Raises:
        TypeError: If the object is not a Pydantic BaseModel.
    """
    if isinstance(obj, BaseModel):
        return obj.dict()
    raise TypeError(f"Object of type '{obj.__class__.__name__}' is not serializable")


class CombinedEncoder(json.JSONEncoder):
    """
    A custom JSON encoder that combines encoding for Pydantic BaseModel objects
    and decimal.Decimal objects.
    """

    def default(self, obj: object) -> object:
        """
        Override the default method to handle BaseModel, set, and decimal.Decimal objects.

        Args:
            obj (object): The object to encode.

        Returns:
            object: The encoded object, converting BaseModel to a dictionary,
                    set to a list, and decimal.Decimal to an integer if applicable.
        """
        if isinstance(obj, BaseModel):
            return obj.model_dump()
        elif isinstance(obj, set):
            return list(obj)
        # Use the default DecimalEncoder for any other type it covers
        return DecimalEncoder.default(self, obj)
