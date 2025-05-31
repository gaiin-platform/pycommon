# Copyright (c) 2025 Vanderbilt University
"""
exceptions.py

This module serves as a repository of custom exception classes for use across
various projects. It provides a centralized location for defining and managing
custom exceptions, ensuring consistency and reusability throughout the codebase.

Copyright (c) 2025 Vanderbilt University
Authors: Jules White, Allen Karns, Karely Rodriguez, Max Moundas, Sam Hays
"""
# Authors: Jules White, Allen Karns, Karely Rodriguez, Max Moundas, Sam Hays


class HTTPException(Exception):
    """
    Custom exception to represent HTTP errors.

    Attributes:
        status_code (int): The HTTP status code associated with the error.
        message (str): A description of the error.

    Args:
        status_code (int): The HTTP status code to associate with the exception.
        message (str): A description of the error.
    """

    def __init__(self, status_code, message):
        super().__init__(message)
        self.status_code = status_code


class HTTPBadRequest(HTTPException):
    """
    Exception raised for a bad HTTP request.

    Attributes:
        message (str): Explanation of the error. Defaults to "Bad Request".
    """

    def __init__(self, message="Bad Request"):
        super().__init__(400, message)


class HTTPUnauthorized(HTTPException):
    """
    Exception raised for unauthorized access.

    Attributes:
        message (str): The error message describing the unauthorized access.
                       Defaults to "Unauthorized".
    """

    def __init__(self, message="Unauthorized"):
        super().__init__(401, message)


class HTTPNotFound(HTTPException):
    """
    Exception raised for HTTP 404 Not Found errors.

    Attributes:
        message (str): Explanation of the error. Defaults to "Not Found".
    """

    def __init__(self, message="Not Found"):
        super().__init__(404, message)
