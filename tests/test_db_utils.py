import decimal

from pycommon.db_utils import convert_floats_to_decimal


def test_convert_floats_to_decimal_with_float():
    obj = 123.456
    result = convert_floats_to_decimal(obj)
    assert isinstance(result, decimal.Decimal)
    assert result == decimal.Decimal("123.456")


def test_convert_floats_to_decimal_with_dict():
    obj = {"price": 99.99, "tax": 8.25, "name": "Product"}
    result = convert_floats_to_decimal(obj)
    assert isinstance(result["price"], decimal.Decimal)
    assert isinstance(result["tax"], decimal.Decimal)
    assert result["price"] == decimal.Decimal("99.99")
    assert result["tax"] == decimal.Decimal("8.25")
    assert result["name"] == "Product"  # Non-float values unchanged


def test_convert_floats_to_decimal_with_list():
    obj = [1.5, 2.7, "text", 42]
    result = convert_floats_to_decimal(obj)
    assert isinstance(result[0], decimal.Decimal)
    assert isinstance(result[1], decimal.Decimal)
    assert result[0] == decimal.Decimal("1.5")
    assert result[1] == decimal.Decimal("2.7")
    assert result[2] == "text"  # Non-float values unchanged
    assert result[3] == 42  # Non-float values unchanged


def test_convert_floats_to_decimal_with_nested_structure():
    obj = {
        "items": [{"price": 10.99, "quantity": 2}, {"price": 5.50, "quantity": 1}],
        "discount": 0.15,
        "metadata": {"created": "2023-01-01", "version": 1.0},
    }
    result = convert_floats_to_decimal(obj)

    # Check nested floats are converted
    assert isinstance(result["items"][0]["price"], decimal.Decimal)
    assert isinstance(result["items"][1]["price"], decimal.Decimal)
    assert isinstance(result["discount"], decimal.Decimal)
    assert isinstance(result["metadata"]["version"], decimal.Decimal)

    # Check values are correct
    assert result["items"][0]["price"] == decimal.Decimal("10.99")
    assert result["items"][1]["price"] == decimal.Decimal("5.50")
    assert result["discount"] == decimal.Decimal("0.15")
    assert result["metadata"]["version"] == decimal.Decimal("1.0")

    # Check non-float values unchanged
    assert result["items"][0]["quantity"] == 2
    assert result["items"][1]["quantity"] == 1
    assert result["metadata"]["created"] == "2023-01-01"


def test_convert_floats_to_decimal_with_non_float_types():
    obj = {
        "string": "text",
        "integer": 42,
        "boolean": True,
        "none": None,
        "decimal": decimal.Decimal("123.45"),
    }
    result = convert_floats_to_decimal(obj)

    # All non-float types should remain unchanged
    assert result["string"] == "text"
    assert result["integer"] == 42
    assert result["boolean"] is True
    assert result["none"] is None
    assert result["decimal"] == decimal.Decimal("123.45")


def test_convert_floats_to_decimal_with_empty_structures():
    # Test empty dict
    assert convert_floats_to_decimal({}) == {}

    # Test empty list
    assert convert_floats_to_decimal([]) == []


def test_convert_floats_to_decimal_dynamodb_use_case():
    """Test the primary DynamoDB use case that this function solves"""
    # Simulate a typical DynamoDB item with float values that would cause errors
    dynamodb_item = {
        "id": "product-123",
        "name": "Example Product",
        "price": 19.99,  # This would cause DynamoDB error
        "dimensions": {
            "weight": 2.5,  # This would cause DynamoDB error
            "length": 10.0,  # This would cause DynamoDB error
            "width": 5.75,  # This would cause DynamoDB error
        },
        "tags": ["electronics", "gadget"],
        "in_stock": True,
        "quantity": 100,
    }

    # Convert for DynamoDB compatibility
    converted_item = convert_floats_to_decimal(dynamodb_item)

    # Verify floats are converted to Decimal
    assert isinstance(converted_item["price"], decimal.Decimal)
    assert isinstance(converted_item["dimensions"]["weight"], decimal.Decimal)
    assert isinstance(converted_item["dimensions"]["length"], decimal.Decimal)
    assert isinstance(converted_item["dimensions"]["width"], decimal.Decimal)

    # Verify values are preserved
    assert converted_item["price"] == decimal.Decimal("19.99")
    assert converted_item["dimensions"]["weight"] == decimal.Decimal("2.5")
    assert converted_item["dimensions"]["length"] == decimal.Decimal("10.0")
    assert converted_item["dimensions"]["width"] == decimal.Decimal("5.75")

    # Verify non-float fields are unchanged
    assert converted_item["id"] == "product-123"
    assert converted_item["name"] == "Example Product"
    assert converted_item["tags"] == ["electronics", "gadget"]
    assert converted_item["in_stock"] is True
    assert converted_item["quantity"] == 100


def test_convert_floats_to_decimal_with_negative_floats():
    obj = {"negative": -123.456, "zero": 0.0, "positive": 456.789}
    result = convert_floats_to_decimal(obj)

    assert isinstance(result["negative"], decimal.Decimal)
    assert isinstance(result["zero"], decimal.Decimal)
    assert isinstance(result["positive"], decimal.Decimal)

    assert result["negative"] == decimal.Decimal("-123.456")
    assert result["zero"] == decimal.Decimal("0.0")
    assert result["positive"] == decimal.Decimal("456.789")


def test_convert_floats_to_decimal_with_scientific_notation():
    obj = {"small": 1.23e-10, "large": 9.87e15}
    result = convert_floats_to_decimal(obj)

    assert isinstance(result["small"], decimal.Decimal)
    assert isinstance(result["large"], decimal.Decimal)

    # Verify the conversion preserves the value
    assert float(result["small"]) == 1.23e-10
    assert float(result["large"]) == 9.87e15
