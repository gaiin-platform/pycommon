import pytest
from jsonschema.exceptions import ValidationError

from authz import _validate_data


def test_validate_data_success():
    """
    Test that _validate_data successfully validates data against a schema.
    """
    name = "test_operation"
    op = "create"
    data = {"data": {"key": "value"}}
    api_accessed = False
    validator_rules = {
        "validators": {
            "test_operation": {
                "create": {
                    "type": "object",
                    "properties": {"key": {"type": "string"}},
                },
                "required": ["key"],
            }
        }
    }

    _validate_data(name, op, data, api_accessed, validator_rules)


def test_validate_data_no_validator_found():
    """
    Test that _validate_data raises ValidationError when no validator is found.
    """
    name = "test_operation"
    op = "create"
    data = {"data": {"key": "value"}}
    api_accessed = False
    validator_rules = {}  # No validators provided

    with pytest.raises(ValidationError, match="No validator found for the operation"):
        _validate_data(name, op, data, api_accessed, validator_rules)


def test_validate_data_invalid_data():
    """
    Test that _validate_data raises ValidationError for invalid data.
    """
    name = "test_operation"
    op = "create"
    data = {"data": {"key": 123}}  # Invalid data (key should be a string)
    api_accessed = False
    validator_rules = {
        "validators": {
            "test_operation": {
                "create": {
                    "type": "object",
                    "properties": {"key": {"type": "string"}},
                    "required": ["key"],
                }
            }
        }
    }

    with pytest.raises(ValidationError, match="Invalid data: .*"):
        _validate_data(name, op, data, api_accessed, validator_rules)


def test_validate_data_invalid_schema():
    """
    Test that _validate_data raises ValidationError for an invalid schema.
    """
    name = "test_operation"
    op = "create"
    data = {"data": {"key": "value"}}
    api_accessed = False
    validator_rules = {
        "validators": {
            "test_operation": {
                "create": {
                    "type": "invalid_type",  # Invalid schema type
                    "properties": {"key": {"type": "string"}},
                }
            }
        }
    }

    with pytest.raises(ValidationError, match="Invalid schema: .*"):
        _validate_data(name, op, data, api_accessed, validator_rules)


def test_validate_data_invalid_path():
    """
    Test that _validate_data raises ValidationError for an invalid operation path.
    """
    name = "invalid_operation"
    op = "create"
    data = {"data": {"key": "value"}}
    api_accessed = False
    validator_rules = {
        "validators": {
            "test_operation": {
                "create": {
                    "type": "object",
                    "properties": {"key": {"type": "string"}},
                    "required": ["key"],
                }
            }
        }
    }

    with pytest.raises(ValidationError, match="Invalid data or path"):
        _validate_data(name, op, data, api_accessed, validator_rules)
