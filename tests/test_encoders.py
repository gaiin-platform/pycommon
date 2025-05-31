import json
import decimal
from encoders import (
    SafeDecimalEncoder,
    SmartDecimalEncoder,
    LossyDecimalEncoder,
    dumps_safe,
    dumps_smart,
    dumps_lossy,
)


def test_safe_decimal_encoder_with_decimal():
    obj = decimal.Decimal("10.5")
    result = json.dumps(obj, cls=SafeDecimalEncoder)
    assert result == '"10.5"'  # Decimal is serialized as a string


def test_safe_decimal_encoder_with_non_decimal():
    obj = "test"
    result = json.dumps(obj, cls=SafeDecimalEncoder)
    assert result == '"test"'  # Non-decimal objects are serialized normally


def test_safe_decimal_encoder_with_unseralizable_object():
    # a set is non-serializable by default
    obj = {1, 2, 3}
    try:
        json.dumps(obj, cls=SafeDecimalEncoder)
    except TypeError as e:
        assert str(e) == "Object of type set is not JSON serializable"


def test_smart_decimal_encoder_with_whole_decimal():
    obj = decimal.Decimal("10.0")
    result = json.dumps(obj, cls=SmartDecimalEncoder)
    assert result == "10"  # Whole decimal is serialized as an integer


def test_smart_decimal_encoder_with_fractional_decimal():
    obj = decimal.Decimal("10.5")
    result = json.dumps(obj, cls=SmartDecimalEncoder)
    assert result == "10.5"  # Fractional decimal is serialized as a float


def test_smart_decimal_encoder_with_unseralizable_object():
    # a set is non-serializable by default
    obj = {1, 2, 3}
    try:
        json.dumps(obj, cls=SmartDecimalEncoder)
    except TypeError as e:
        assert str(e) == "Object of type set is not JSON serializable"


def test_lossy_decimal_encoder_with_decimal():
    obj = decimal.Decimal("10.5")
    result = json.dumps(obj, cls=LossyDecimalEncoder)
    assert result == "10"  # Decimal is truncated to an integer


def test_lossy_decimal_encoder_with_whole_decimal():
    obj = decimal.Decimal("42.0")
    result = json.dumps(obj, cls=LossyDecimalEncoder)
    assert result == "42"  # Whole decimal is serialized as an integer


def test_lossy_decimal_encoder_with_unseralizable_object():
    # a set is non-serializable by default
    obj = {1, 2, 3}
    try:
        json.dumps(obj, cls=LossyDecimalEncoder)
    except TypeError as e:
        assert str(e) == "Object of type set is not JSON serializable"


def test_dumps_safe():
    obj = {"value": decimal.Decimal("123.456")}
    result = dumps_safe(obj)
    assert result == '{"value": "123.456"}'  # Decimal is serialized as a string


def test_dumps_smart():
    obj = {"value": decimal.Decimal("123.456")}
    result = dumps_smart(obj)
    assert result == '{"value": 123.456}'  # Decimal is serialized as a float


def test_dumps_lossy():
    obj = {"value": decimal.Decimal("123.456")}
    result = dumps_lossy(obj)
    assert result == '{"value": 123}'  # Decimal is truncated to an integerimport json
