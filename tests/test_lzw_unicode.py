# =============================================================================
# Tests for the unicode handling of lzw.py
#
# The wire format is shared with the frontend (utils/app/lzwCompression.ts in amplify-genai-frontend);
# tests/fixtures/lzw_vectors.json holds vectors that BOTH implementations must reproduce exactly.
# =============================================================================

import json
from pathlib import Path

import pytest

from pycommon.lzw import (
    _preprocess,
    lzw_compress,
    lzw_uncompress,
    lzw_uncompress_text,
)

SAMPLES = {
    "ascii": "Hello, world! The quick brown fox jumps over the lazy dog.",
    "latin1": "café niño éñ",
    "polish": "zażółć gęślą jaźń Łódź",
    "turkish": "İstanbul şğı",
    "cyrillic": "Привет, мир! абв",
    "greek": "Γεια σου κόσμε αβγ",
    "hebrew": "שלום עולם",
    "arabic": "مرحبا بالعالم",
    "devanagari": "नमस्ते दुनिया",
    "thai": "สวัสดีชาวโลก",
    "cjk": "你好，世界 こんにちは 한국어",
    "emoji": "hi \U0001F600 there",
    "emoji_modifier": "ok \U0001F44D\U0001F3FD done",
    "literal_tag": "U+0041",
    "literal_tag_in_text": "type U+0041 or U+ here",
    "literal_u_plus_end": "ends with U+",
    "double_u_plus": "U+U+U",
    "tag_lookalike_prefix": "U+00",
    "lowercase_tag_lookalike": "u+0041 and u+00e9",
    "three_digit_char_before_hex": "ā" + "abc" + "ł" + "deadbeef",
    "mixed_json": json.dumps({"name": "łódź \U0001F600", "t": "U+0041"}, ensure_ascii=False),
    "repetitive": "abababababababababab" * 20,
}


class TestUnicodeRoundTrip:
    @pytest.mark.parametrize("label", sorted(SAMPLES))
    def test_round_trip_text(self, label):
        text = SAMPLES[label]
        assert lzw_uncompress_text(lzw_compress(text)) == text

    @pytest.mark.parametrize("label", sorted(SAMPLES))
    def test_round_trip_json(self, label):
        obj = {"id": "c1", "messages": [{"content": SAMPLES[label]}]}
        assert lzw_uncompress(lzw_compress(json.dumps(obj))) == obj
        assert lzw_uncompress(lzw_compress(json.dumps(obj, ensure_ascii=False))) == obj

    def test_empty_input(self):
        assert lzw_compress("") == []
        assert lzw_uncompress([]) == ""
        assert lzw_uncompress_text([]) == ""

    def test_large_non_latin_document(self):
        text = "Привет мир U+0041 — zażółć \U0001F600 " * 5000
        assert lzw_uncompress_text(lzw_compress(text)) == text


class TestWireFormat:
    def test_tags_are_four_digit_lowercase_utf16_units(self):
        assert _preprocess("а") == "U+0430"
        assert _preprocess("ł") == "U+0142"
        assert _preprocess("你") == "U+4f60"
        assert _preprocess("\U0001F600") == "U+d83dU+de00"
        assert _preprocess("\U0001F44D\U0001F3FD") == "U+d83dU+dc4dU+d83cU+dffd"
        assert _preprocess("éñ") == "éñ"  # <= 255 stays literal

    def test_literal_u_plus_is_escaped(self):
        assert _preprocess("U+0041") == "U+0055+0041"
        assert _preprocess("U+") == "U+0055+"
        assert _preprocess("U+U+") == "U+0055+U+0055+"
        assert _preprocess("Up") == "Up"  # only 'U' directly followed by '+'
        assert _preprocess("U") == "U"

    def test_no_five_digit_emoji_tags(self):
        # the old encoder wrote "U+1f600", which the decoder read as "U+1f60" + "0"
        codes = lzw_compress("\U0001F600")
        assert "U+1f600" not in "".join(chr(c) for c in codes if c < 256)
        assert lzw_uncompress_text(codes) == "\U0001F600"

    def test_lowercase_prefix_is_plain_text(self):
        assert lzw_uncompress_text(lzw_compress("u+0041")) == "u+0041"

    def test_hex_digits_may_be_either_case(self):
        assert lzw_uncompress_text([ord(c) for c in "U+4F60"]) == "你"

    def test_surrogate_pairs_recombine(self):
        assert lzw_uncompress_text([ord(c) for c in "U+d83dU+de00"]) == "\U0001F600"
        # a lone surrogate must not raise
        assert lzw_uncompress_text([ord(c) for c in "U+d83d"]) == "�"

    def test_lone_surrogate_input_does_not_raise(self):
        assert lzw_uncompress_text(lzw_compress("a\ud83db")) == "a�b"


class TestLegacyThreeDigitTags:
    """Older frontends wrote U+430 (unpadded). Those chats are still stored and must stay readable."""

    def test_three_digit_tag_followed_by_non_hex(self):
        assert lzw_uncompress_text([ord(c) for c in "U+430 "]) == "а "
        assert lzw_uncompress_text([ord(c) for c in "U+142"]) == "ł"

    def test_four_digits_win_when_a_fourth_hex_digit_follows(self):
        assert lzw_uncompress_text([ord(c) for c in "U+0430"]) == "а"
        assert lzw_uncompress_text([ord(c) for c in "U+430a"]) == "䌊"

    def test_fewer_than_three_digits_is_not_a_tag(self):
        assert lzw_uncompress_text([ord(c) for c in "U+43 "]) == "U+43 "


class TestInvalidData:
    def test_bad_codes_raise_value_error(self):
        with pytest.raises(ValueError):
            lzw_uncompress([300])
        with pytest.raises(ValueError):
            lzw_uncompress([65, 999])

    def test_non_list_raises_value_error(self):
        with pytest.raises(ValueError):
            lzw_uncompress_text(12345)

    def test_non_json_raises_value_error(self):
        with pytest.raises(ValueError):
            lzw_uncompress(lzw_compress("not json"))


class TestCrossLanguageVectors:
    """tests/fixtures/lzw_vectors.json is also checked by the frontend tests."""

    VECTORS = json.loads((Path(__file__).parent / "fixtures" / "lzw_vectors.json").read_text(encoding="utf-8"))

    @pytest.mark.parametrize("vector", VECTORS, ids=lambda v: repr(v["text"])[:40])
    def test_compress_matches(self, vector):
        assert lzw_compress(vector["text"]) == vector["codes"]

    @pytest.mark.parametrize("vector", VECTORS, ids=lambda v: repr(v["text"])[:40])
    def test_uncompress_matches(self, vector):
        assert lzw_uncompress_text(vector["codes"]) == vector["text"]
