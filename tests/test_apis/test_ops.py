# =============================================================================
# Tests for api/ops.py
# =============================================================================

from unittest.mock import MagicMock

import pytest

from pycommon.api import ops
from pycommon.api.ops import (
    PermissionChecker,
    api_tool,
    set_op_type,
    set_permissions_by_state,
    set_route_data,
)


def test_permission_checker_protocol():
    """Test that PermissionChecker protocol can be used for type hints and
    callable objects."""

    # Create a class that implements the PermissionChecker protocol
    class TestPermissionChecker:
        def __call__(self, user: str, data) -> bool:
            return user == "admin"

    # Create an instance and use it
    checker: PermissionChecker = TestPermissionChecker()
    assert checker("admin", {}) is True
    assert checker("user", {}) is False

    # Also test with a simple function
    def test_checker_func(user: str, data) -> bool:
        return user == "admin"

    func_checker: PermissionChecker = test_checker_func
    assert func_checker("admin", {}) is True
    assert func_checker("user", {}) is False


def test_set_route_data():
    test_data = {"/test": {"method": "POST"}}
    set_route_data(test_data)

    assert ops._route_data == test_data


def test_set_permissions_by_state():
    test_permissions = {"/test": {"read": lambda user, data: True}}
    set_permissions_by_state(test_permissions)

    assert ops._permissions_by_state == test_permissions


def test_set_op_type():
    set_op_type("custom")

    assert ops._op_type == "custom"


def test_api_tool_decorator():
    # Reset global state
    # Set _route_data to a non-empty dict since the decorator only populates it
    # if it's truthy
    set_route_data({"dummy": {}})
    set_op_type("test")
    # Reset permissions_by_state to None to avoid the AttributeError
    set_permissions_by_state(None)

    @api_tool(
        path="/test",
        name="Test Tool",
        description="A test tool",
        parameters={"type": "object"},
        method="GET",
    )
    def test_function():
        return {"result": "success"}

    result = test_function()
    assert result == {"result": "success"}

    assert "/test" in ops._route_data
    assert ops._route_data["/test"]["name"] == "Test Tool"
    assert ops._route_data["/test"]["method"] == "GET"


def test_api_tool_decorator_without_route_data():
    # Reset global state to None to test the condition where _route_data is None
    set_route_data(None)
    set_op_type("test")

    @api_tool(
        path="/test",
        name="Test Tool",
        description="A test tool",
        parameters={"type": "object"},
        method="GET",
    )
    def test_function():
        return {"result": "success"}

    result = test_function()
    assert result == {"result": "success"}

    # Since _route_data was None, it shouldn't be populated
    assert ops._route_data is None


def test_api_tool_decorator_permissions_by_state_lines_71_72():
    # Create a mock permissions object with permissions_by_state_type attribute
    mock_permissions = MagicMock()
    mock_permissions.permissions_by_state_type = {}

    set_permissions_by_state(mock_permissions)
    set_route_data({"dummy": {}})  # Ensure route_data is truthy

    @api_tool(
        path="/test_path",
        name="Test Tool",
        description="A test tool",
        parameters={"type": "object"},
        method="GET",
    )
    def test_function():
        return {"result": "success"}

    result = test_function()
    assert result == {"result": "success"}

    # Check that the permission was added
    assert "/test_path" in mock_permissions.permissions_by_state_type


# NEW TEST: Cover branch 10->exit (early return when permissions already exist)
def test_api_tool_decorator_permissions_already_exist():
    # Create a mock permissions object with pre-existing path
    mock_permissions = MagicMock()
    mock_permissions.permissions_by_state_type = {
        "/existing_path": {"read": lambda user, data: True}
    }

    set_permissions_by_state(mock_permissions)
    set_route_data({"dummy": {}})  # Ensure route_data is truthy

    @api_tool(
        path="/existing_path",
        name="Existing Tool",
        description="A tool with existing permissions",
        parameters={"type": "object"},
        method="GET",
    )
    def test_function():
        return {"result": "success"}

    result = test_function()
    assert result == {"result": "success"}

    # The existing permission should remain unchanged
    assert "/existing_path" in mock_permissions.permissions_by_state_type
    assert "read" in mock_permissions.permissions_by_state_type["/existing_path"]


def test_api_tool_decorator_method_validation():
    """Test that api_tool validates method parameter correctly."""
    # Reset global state
    set_route_data({"dummy": {}})
    set_op_type("test")
    set_permissions_by_state(None)

    # Test valid methods: GET
    @api_tool(
        path="/test_get",
        name="Test GET Tool",
        description="A test GET tool",
        parameters={"type": "object"},
        method="GET",
    )
    def test_function_get():
        return {"result": "success"}

    result = test_function_get()
    assert result == {"result": "success"}

    assert "/test_get" in ops._route_data
    assert ops._route_data["/test_get"]["method"] == "GET"

    # Test valid methods: POST
    @api_tool(
        path="/test_post",
        name="Test POST Tool",
        description="A test POST tool",
        parameters={"type": "object"},
        method="POST",
    )
    def test_function_post():
        return {"result": "success"}

    result_post = test_function_post()
    assert result_post == {"result": "success"}
    assert "/test_post" in ops._route_data
    assert ops._route_data["/test_post"]["method"] == "POST"

    # Test valid methods: DELETE
    @api_tool(
        path="/test_delete",
        name="Test DELETE Tool",
        description="A test DELETE tool",
        parameters={"type": "object"},
        method="DELETE",
    )
    def test_function_delete():
        return {"result": "success"}

    result_delete = test_function_delete()
    assert result_delete == {"result": "success"}
    assert "/test_delete" in ops._route_data
    assert ops._route_data["/test_delete"]["method"] == "DELETE"

    # Test valid methods: PUT
    @api_tool(
        path="/test_put",
        name="Test PUT Tool",
        description="A test PUT tool",
        parameters={"type": "object"},
        method="PUT",
    )
    def test_function_put():
        return {"result": "success"}

    result_put = test_function_put()
    assert result_put == {"result": "success"}
    assert "/test_put" in ops._route_data
    assert ops._route_data["/test_put"]["method"] == "PUT"


def test_api_tool_decorator_invalid_method():
    """Test that api_tool raises ValueError for invalid methods."""
    # Reset global state
    set_route_data({"dummy": {}})
    set_op_type("test")
    set_permissions_by_state(None)

    # Test invalid method - should raise ValueError during decoration
    with pytest.raises(
        ValueError, match="Method must be GET, POST, DELETE, or PUT, got 'PATCH'"
    ):

        @api_tool(
            path="/test_invalid",
            name="Test Invalid Tool",
            description="A test tool with invalid method",
            parameters={"type": "object"},
            method="PATCH",
        )
        def test_function_invalid():
            return {"result": "success"}

    # Test another invalid method
    with pytest.raises(
        ValueError, match="Method must be GET, POST, DELETE, or PUT, got 'OPTIONS'"
    ):

        @api_tool(
            path="/test_invalid2",
            name="Test Invalid Tool 2",
            description="A test tool with invalid method",
            parameters={"type": "object"},
            method="OPTIONS",
        )
        def test_function_invalid2():
            return {"result": "success"}

    # Test non-string method (should be invalid)
    with pytest.raises(
        ValueError, match="Method must be GET, POST, DELETE, or PUT, got '123'"
    ):

        @api_tool(
            path="/test_invalid4",
            name="Test Invalid Tool 4",
            description="A test tool with non-string method",
            parameters={"type": "object"},
            method=123,
        )
        def test_function_invalid4():
            return {"result": "success"}


def test_api_tool_decorator_lowercase_method():
    """Test that api_tool properly handles lowercase method names."""
    # Reset global state
    set_route_data({"dummy": {}})
    set_op_type("test")
    set_permissions_by_state(None)

    # Test lowercase method - should be converted to uppercase and work
    @api_tool(
        path="/test_lowercase",
        name="Test Lowercase Tool",
        description="A test tool with lowercase method",
        parameters={"type": "object"},
        method="get",
    )
    def test_function_lowercase():
        return {"result": "success"}

    result = test_function_lowercase()
    assert result == {"result": "success"}
    assert "/test_lowercase" in ops._route_data
    assert ops._route_data["/test_lowercase"]["method"] == "GET"
