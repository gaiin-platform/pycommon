from permissions import (
    can_chat,
    can_create_assistant,
    can_create_assistant_thread,
    can_delete_file,
    can_delete_item,
    can_read,
    can_save,
    can_share,
    can_upload,
    get_data_owner,
    get_permission_checker,
    get_user,
    permissions_by_state_type,
)


def test_can_share():
    assert can_share("mock_user", {}) is True


def test_can_save():
    assert can_save("mock_user", {}) is True


def test_can_delete_item():
    assert can_delete_item("mock_user", {}) is True


def test_can_upload():
    assert can_upload("mock_user", {}) is True


def test_can_create_assistant():
    assert can_create_assistant("mock_user", {}) is True


def test_can_create_assistant_thread():
    assert can_create_assistant_thread("mock_user", {}) is True


def test_can_read():
    assert can_read("mock_user", {}) is True


def test_can_chat():
    assert can_chat("mock_user", {}) is True


def test_can_delete_file():
    assert can_delete_file("mock_user", {}) is True


def test_get_user():
    event = {}
    data = {"user": "mock_user"}
    assert get_user(event, data) == "mock_user"


def test_get_data_owner():
    event = {}
    data = {"user": "mock_user"}
    assert get_data_owner(event, data) == "mock_user"


def test_get_permission_checker_valid():
    user = "mock_user"
    type = "/state/share"
    op = "append"
    data = {}
    checker = get_permission_checker(user, type, op, data)
    assert checker(user, data) is True


def test_get_permission_checker_invalid_type():
    user = "mock_user"
    type = "/invalid/type"
    op = "append"
    data = {}
    checker = get_permission_checker(user, type, op, data)
    assert checker(user, data) is False


def test_get_permission_checker_invalid_op():
    user = "mock_user"
    type = "/state/share"
    op = "invalid_op"
    data = {}
    checker = get_permission_checker(user, type, op, data)
    assert checker(user, data) is False


def test_permissions_by_state_type():
    # Ensure all keys in permissions_by_state_type are callable
    for _state_type, operations in permissions_by_state_type.items():
        for _op, func in operations.items():
            assert callable(func)
