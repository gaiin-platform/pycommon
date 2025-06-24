# =============================================================================
# Tests for api/ops.py
# =============================================================================

from unittest.mock import MagicMock

from api.ops import (
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
    from api.ops import _route_data

    assert _route_data == test_data


def test_set_permissions_by_state():
    test_permissions = {"/test": {"read": lambda user, data: True}}
    set_permissions_by_state(test_permissions)
    from api.ops import _permissions_by_state

    assert _permissions_by_state == test_permissions


def test_set_op_type():
    set_op_type("custom")
    from api.ops import _op_type

    assert _op_type == "custom"


def test_api_tool_decorator():
    # Reset global state
    # Set _route_data to a non-empty dict since the decorator only populates it
    # if it's truthy
    set_route_data({"dummy": {}})
    set_op_type("test")
    # Reset permissions_by_state to None to avoid the AttributeError
    from api.ops import set_permissions_by_state

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

    from api.ops import _route_data

    assert "/test" in _route_data
    assert _route_data["/test"]["name"] == "Test Tool"
    assert _route_data["/test"]["method"] == "GET"


def test_api_tool_decorator_without_route_data():
    # Reset global state to empty dict to test the condition where _route_data is falsy
    set_route_data({})
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

    # Since _route_data was empty, it shouldn't be populated
    from api.ops import _route_data

    assert _route_data == {}


def test_api_tool_decorator_permissions_by_state_lines_71_72():
    from api.ops import api_tool, set_permissions_by_state, set_route_data

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
    from api.ops import api_tool, set_permissions_by_state, set_route_data

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
