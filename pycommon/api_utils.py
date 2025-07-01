"""api_utils.py

This module provides utilities for API usage, such as key management and
verification helpers.

Copyright (c) 2025 Vanderbilt University
Authors: Jules White, Allen Karns, Karely Rodriguez, Max Moundas, Sam Hays
"""

import secrets
from abc import ABC
from hashlib import shake_256


class Token(ABC):
    """
    Represents a token with a key and salt.
    """

    _key: str
    _salt: str

    def __init__(self, key: str, salt: str):
        self._key = key
        self._salt = salt

    def __eq__(self, value):
        """
        Compares the provided value with the token's key.

        Args:
            value (str): The value to compare with the token's key.

        Returns:
            bool: True if the value matches the token's key, False otherwise.

        Example:
            token = TokenV1()
            user_key = token.raw_key # This is the key to be provided to the user
            private_key = token.key # This is the hashed key to be stored in the database
            token == user_key # This will return True if the user_key matches the token's key
        """  # noqa: E501
        if not isinstance(value, str):
            raise TypeError("TokenV1 can only be compared with a string value.")
        return self.validate(value)

    @property
    def salt(self) -> str:
        """
        Returns the salt of the token.

        Returns:
            str: The salt of the token.
        """
        return self._salt

    @property
    def key(self) -> str:
        """
        Returns the (storable) key of the token.

        Returns:
            str: The key of the token.
        """
        return self._key

    def validate(self, raw_key: str) -> bool:
        """
        Validates the provided key against the token's key.

        Args:
            raw_key (str): The key to validate.

        Returns:
            bool: True if the key is valid, False otherwise.
        """
        raise NotImplementedError("Subclasses must implement this method.")


class TokenV1(Token):
    """Represents a version 1 token with a key and salt.

    Inherits from the Token class.
    """

    # we do not salt this token due to the high entropy of the key and
    # the fact that it is already a secure random value and, finally, because
    # the hash is used as an index in the database.
    # Remember salting is used to prevent rainbow table attacks, but in this case,
    # the key is already a secure random value with high entropy.
    _salt: str = ""
    _raw_key: str
    _key: str
    _identifier: str = "amp-"

    def __init__(self, key: str = ""):

        if not isinstance(key, str):
            raise TypeError("Key must be a string.")

        if key != "":
            if not key.startswith(self._identifier):
                raise ValueError(f"TokenV1 key must start with '{self._identifier}'.")
            self._raw_key = key
            self._key = self._key_generator(self._raw_key, self._salt)
        else:
            self._raw_key = f"{self._identifier}v1-{secrets.token_urlsafe(32)}"
            self._key = self._key_generator(self._raw_key, self._salt)

        super().__init__(self._key, self._salt)

    def _key_generator(self, raw_key: str, salt: str = "") -> str:
        """Generates a hashed key using the raw key and salt.

        Note that in the V1 token, the salt is not used in the hashing process
        because the key is already a secure random value with high entropy.

        Args:
            raw_key (str): The raw key to be hashed.
            salt (str): The salt to be used in the hashing process.
        Returns:
            str: The hashed key as a base64 encoded string.
        """
        return shake_256(raw_key.encode() + salt.encode()).hexdigest(64)

    def validate(self, raw_key: str) -> bool:
        return secrets.compare_digest(
            self.key, self._key_generator(raw_key, self._salt)
        )

    def __eq__(self, value):
        """
        Compares the provided value with the token's key.

        Args:
            value (str): The value to compare with the token's key.

        Returns:
            bool: True if the value matches the token's key, False otherwise.

        Example:
            token = TokenV1()
            user_key = token.raw_key # This is the key to be provided to the user
            private_key = token.key # This is the hashed key to be stored in the database
            token == user_key # This will return True if the user_key matches the token's key
        """  # noqa: E501
        if not isinstance(value, str):
            raise TypeError("TokenV1 can only be compared with a string value.")
        return self.validate(value)

    @property
    def raw_key(self) -> str:
        """
        This property retrieves the raw key of the token.
        The raw key is the original key generated during instantiation.
        This is the key that should be provided to the user for API access.
        It is not hashed and should be kept secret and will not
        be stored in the database.

        Returns:
            str: The raw key of the token.
        """
        return self._raw_key
