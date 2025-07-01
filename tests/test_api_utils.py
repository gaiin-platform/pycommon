import pytest

from pycommon.api_utils import Token, TokenV1


class DummyToken(Token):
    def validate(self, raw_key: str) -> bool:
        return raw_key == "valid"


def test_token_eq_and_validate():
    token = DummyToken("abc", "salt")
    assert token == "valid"
    assert not (token == "invalid")
    with pytest.raises(TypeError):
        token == 123  # noqa: B015


def test_token_properties():
    token = DummyToken("abc", "salt")
    assert token.key == "abc"
    assert token.salt == "salt"


def test_token_validate_not_implemented():
    t = Token("abc", "salt")
    with pytest.raises(NotImplementedError):
        t.validate("abc")


def test_tokenv1_generation_and_properties():
    t1 = TokenV1()
    t2 = TokenV1()
    # Should generate different keys and salts
    assert t1.raw_key != t2.raw_key
    assert isinstance(t1.key, str)
    assert isinstance(t1.raw_key, str)


def test_tokenv1_validate_and_eq():
    key = "amp-v1-mykey"
    t = TokenV1(key)
    # Should validate with the correct raw key
    assert t.validate(key)
    # Should not validate with a wrong key
    assert not t.validate("wrongkey")
    # __eq__ should work
    assert t == key
    assert not (t == "wrongkey")
    with pytest.raises(TypeError):
        t == 123  # noqa: B015


def test_tokenv1_key_generator_consistency():
    key = "amp-v1-anotherkey"
    t = TokenV1(key)
    assert t._key_generator(key) == t.key


def test_tokenv1_string_input():
    key = 123
    with pytest.raises(TypeError):
        TokenV1(key)  # Should raise TypeError since key is not a string


def test_tokenv1_invalid_key_identifier():
    key = "bad-identifier"
    with pytest.raises(ValueError):
        TokenV1(key)
