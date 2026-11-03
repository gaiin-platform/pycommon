import json
import re
import struct
from typing import Any


def is_lzw_compressed_format(data: Any) -> bool:
    """
    Check if the input data could possibly be in LZW compressed format.

    Args:
        data: The data to check

    Returns:
        bool: True if data could be LZW compressed, False otherwise
    """
    # Check if data is a list or tuple
    if not isinstance(data, (list, tuple)):
        return False

    # Empty data is not valid LZW compressed format
    if not data:
        return False

    # All elements should be integers
    if not all(isinstance(item, int) for item in data):
        return False

    # All codes should be non-negative
    if not all(code >= 0 for code in data):
        return False

    # First code should be in initial dictionary range (0-255)
    if data[0] > 255:
        return False

    # Check for reasonable progression - codes should generally increase
    # but we allow some flexibility since codes can be reused
    # Allow for more flexible bounds as LZW can have wider code ranges
    max_expected_code = 256 + len(data) * 50  # More generous estimate
    if any(code > max_expected_code for code in data):
        return False

    return True


# ---------------------------------------------------------------------------
# Wire format (shared with the frontend, utils/app/lzwCompression.ts)
#
# LZW works on bytes of a string whose characters are all <= 255. Anything above
# U+00FF is written as a text tag before compression and turned back after
# decompression:
#
#   * the input is read as UTF-16 code units; a unit > 255 is written as "U+" +
#     exactly four lowercase hex digits. Characters above U+FFFF (emoji)
#     therefore become two surrogate tags, e.g. "U+d83dU+de00".
#   * a literal "U" directly followed by "+" is written as the tag for 'U'
#     ("U+0055"), so user text such as "U+0041" can never be mistaken for a tag.
#   * decoding replaces tags by their code unit, then pairs surrogates back into
#     real characters. The legacy unpadded three digit form ("U+430") that older
#     frontends wrote is accepted when no further hex digit follows (otherwise it
#     is ambiguous and the four digit reading wins).
#   * the "U+" prefix is case sensitive (text such as "u+0041" is plain text);
#     hex digits may be either case.
# ---------------------------------------------------------------------------
_TAG_PATTERN = re.compile(r"U\+([0-9a-fA-F]{4})|U\+([0-9a-fA-F]{3})(?![0-9a-fA-F])")


def _utf16_code_units(text: str):
    raw = text.encode("utf-16-le", "surrogatepass")
    return struct.unpack(f"<{len(raw) // 2}H", raw)


def _preprocess(text: str) -> str:
    units = _utf16_code_units(text)
    out = []
    for i, unit in enumerate(units):
        if unit > 255:
            out.append(f"U+{unit:04x}")
        elif unit == 0x55 and i + 1 < len(units) and units[i + 1] == 0x2B:
            out.append("U+0055")
        else:
            out.append(chr(unit))
    return "".join(out)


def _postprocess(text: str) -> str:
    # Substituted code units may be lone surrogates; pair them back up into real
    # characters.
    with_units = _TAG_PATTERN.sub(
        lambda m: chr(int(m.group(1) or m.group(2), 16)), text
    )
    return with_units.encode("utf-16-le", "surrogatepass").decode(
        "utf-16-le", "replace"
    )


def lzw_uncompress_text(compressed_data) -> str:
    """Decode to the original text without parsing it.

    Returns "" for empty input and raises ValueError for data that is not valid
    LZW output.
    """
    if not compressed_data:
        return ""

    dictionary = {i: chr(i) for i in range(256)}  # Build initial dictionary

    try:
        previous_entry = dictionary.get(compressed_data[0])
    except TypeError:
        raise ValueError("Invalid compressed data: not a list of codes")
    if not previous_entry:
        raise ValueError("Invalid compressed data: First entry not found in dictionary")

    parts = [previous_entry]
    next_code = 256

    for code in compressed_data[1:]:
        if code in dictionary:
            current_entry = dictionary[code]
        elif code == next_code:
            current_entry = previous_entry + previous_entry[0]
        else:
            raise ValueError("Invalid compressed data: Entry for code not found")

        parts.append(current_entry)
        dictionary[next_code] = previous_entry + current_entry[0]
        next_code += 1
        previous_entry = current_entry

    return _postprocess("".join(parts))


def lzw_uncompress(compressed_data):
    if not compressed_data:
        return ""

    output = lzw_uncompress_text(compressed_data)
    try:
        # Ensure the decompressed string is parsed into a dictionary
        return json.loads(output)
    except json.JSONDecodeError:
        raise ValueError("Failed to parse JSON from decompressed string")


def lzw_compress(str_input):
    if not str_input:
        return []

    # Initialize the dictionary with single-character mappings
    dictionary = {chr(i): i for i in range(256)}
    next_code = 256
    compressed_output = []

    current_pattern = ""
    for character in _preprocess(str_input):
        new_pattern = current_pattern + character
        if new_pattern in dictionary:
            current_pattern = new_pattern
        else:
            compressed_output.append(dictionary[current_pattern])
            dictionary[new_pattern] = next_code
            next_code += 1
            current_pattern = character

    if current_pattern != "":
        compressed_output.append(dictionary[current_pattern])

    return compressed_output


def safe_compress(data):
    """
    Safely attempt to compress data. If compression fails, return the original data.

    Args:
        data: The data to attempt compression on

    Returns:
        The compressed data if successful, otherwise the original data
    """
    try:
        # If data is already a string, try to compress it
        if isinstance(data, str):
            compressed = lzw_compress(data)
            # Only return compressed if it actually reduces size meaningfully
            if len(compressed) < len(data) * 0.8:  # 20% size reduction threshold
                return compressed
            return data

        # If data is not a string, try to convert to JSON and compress
        elif isinstance(data, (dict, list, int, float, bool)) or data is None:
            json_str = json.dumps(data)
            compressed = lzw_compress(json_str)
            # Only return compressed if it reduces size meaningfully
            if len(compressed) < len(json_str) * 0.8:
                return compressed
            return data

    except Exception:
        # If anything goes wrong, just return the original data
        pass

    return data
