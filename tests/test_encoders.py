import json
import decimal
from pydantic import BaseModel
from encoders import DecimalEncoder, CombinedEncoder


class SampleModel(BaseModel):
    name: str
    value: int


def test_decimal_encoder_with_decimal():
    obj = decimal.Decimal("10.5")
    result = json.dumps(obj, cls=DecimalEncoder)
    assert result == "10"


def test_decimal_encoder_with_non_decimal():
    obj = "test"
    result = json.dumps(obj, cls=DecimalEncoder)
    assert result == '"test"'


def test_combined_encoder_with_basemodel():
    obj = SampleModel(name="test", value=123)
    result = json.dumps(obj, cls=CombinedEncoder)
    assert result == '{"name": "test", "value": 123}'


def test_combined_encoder_with_set():
    obj = {1, 2, 3}
    result = json.dumps(obj, cls=CombinedEncoder)
    assert (
        result == "[1, 2, 3]" or result == "[2, 3, 1]" or result == "[3, 1, 2]"
    )  # Order may vary


def test_combined_encoder_with_decimal():
    obj = decimal.Decimal("42.7")
    result = json.dumps(obj, cls=CombinedEncoder)
    assert result == "42"


def test_combined_encoder_with_non_special_type():
    obj = "example"
    result = json.dumps(obj, cls=CombinedEncoder)
    assert result == '"example"'
